"""T05 PoC: near-duplicate candidates and group-aware train/test split."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from .common.contact_sheet import render_contact_sheet
from .common.context import RunContext
from .common.decision import Decision, write_decision
from .common.image_ops import dhash, hamming, load_rgb, phash, to_gray
from .common.io import sha256_file
from .common.manifest import verify_manifest
from .common.review import load_review_decisions, make_review_queue, write_review_queue
from .metrics.tracks import get_track


def _load_images(root: Path, images: pd.DataFrame) -> dict[str, dict]:
    features = {}
    for row in images.itertuples(index=False):
        image_id, relpath = str(row.image_id), str(row.path)
        path = root / relpath
        if not path.is_file():
            raise FileNotFoundError(f"image listed in images.csv is missing: {relpath}")
        rgb = load_rgb(path)
        gray = np.asarray(Image.fromarray(to_gray(rgb).astype(np.uint8)).resize((128, 72)), dtype=np.float32)
        gray = (gray - gray.mean()) / max(float(gray.std()), 1e-6)
        features[image_id] = {
            "path": relpath,
            "camera": str(row.camera_id),
            "time": pd.to_datetime(row.captured_at, utc=True, errors="coerce"),
            "sha": sha256_file(path),
            "phash": phash(rgb),
            "dhash": dhash(rgb),
            "gray": gray,
        }
    return features


def _build_candidates(ctx: RunContext, images: pd.DataFrame, features: dict[str, dict]) -> pd.DataFrame:
    p = ctx.config.get("params", {})
    ids = images.image_id.astype(str).tolist()
    rows = []
    for i, a in enumerate(ids):
        fa = features[a]
        for b in ids[i + 1:]:
            fb = features[b]
            exact = fa["sha"] == fb["sha"]
            pdist = hamming(fa["phash"], fb["phash"])
            ddist = hamming(fa["dhash"], fb["dhash"])
            corr = float(np.mean(fa["gray"] * fb["gray"]))
            positive, candidate = _pair_labels(exact, corr, pdist, ddist, p)
            if not candidate:
                continue
            score = 0.55 * ((corr + 1) / 2) + 0.25 * (1 - pdist / 64) + 0.20 * (1 - ddist / 64)
            review_priority = 0.0 if exact else max(0.0, 1.0 - abs(corr - float(p.get("corr_min", 0.92))))
            if exact:
                score = 1.0
            rows.append({
                "pair_id": f"{a}::{b}", "img_a": a, "img_b": b, "score": score,
                "review_priority": review_priority,
                "pred_dup": int(positive),
                "reason": "exact_sha256" if exact else f"visual corr={corr:.3f}; phash={pdist}; dhash={ddist}",
                "path_a": fa["path"], "path_b": fb["path"],
            })
    return pd.DataFrame(rows, columns=["pair_id", "img_a", "img_b", "score", "review_priority", "pred_dup", "reason", "path_a", "path_b"])


def _pair_labels(exact: bool, corr: float, pdist: int, ddist: int, params: dict) -> tuple[bool, bool]:
    positive = exact or corr >= float(params.get("corr_min", 0.92)) or (
        corr >= float(params.get("corr_hash_min", 0.78))
        and pdist <= int(params.get("phash_max", 8))
        and ddist <= int(params.get("dhash_max", 12))
    )
    candidate = positive or (
        corr >= float(params.get("candidate_corr_min", 0.70))
        and pdist <= int(params.get("candidate_phash_max", 16))
    )
    return positive, candidate


def _components(ids: list[str], edges: list[tuple[str, str]]) -> dict[str, str]:
    parent = {x: x for x in ids}

    def find(x: str) -> str:
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    return {x: find(x) for x in ids}


def _make_split(ctx: RunContext, images: pd.DataFrame, features: dict[str, dict], pairs: pd.DataFrame) -> pd.DataFrame:
    ids = images.image_id.astype(str).tolist()
    positive = pairs[pairs.pred_dup.astype(int) == 1] if len(pairs) else pairs
    edges = list(zip(positive.img_a.astype(str), positive.img_b.astype(str)))
    burst_s = float(ctx.config.get("params", {}).get("burst_seconds", 60))
    cameras: dict[str, list[tuple[pd.Timestamp, str]]] = {}
    for image_id, f in features.items():
        if pd.notna(f["time"]):
            cameras.setdefault(f["camera"], []).append((f["time"], image_id))
    for captures in cameras.values():
        captures.sort()
        for (ta, a), (tb, b) in zip(captures, captures[1:]):
            if (tb - ta).total_seconds() <= burst_s:
                edges.append((a, b))
    group_of = _components(ids, edges)
    groups = sorted(set(group_of.values()))
    fraction = min(max(float(ctx.config.get("params", {}).get("test_fraction", .3)), 0), 1)
    n_test = int(round(len(groups) * fraction))
    if len(groups) > 1 and fraction > 0:
        n_test = min(max(n_test, 1), len(groups) - 1)
    test_groups = set(ctx.rng.permutation(groups)[:n_test])
    return pd.DataFrame({"image_id": ids,
                         "split": ["test" if group_of[x] in test_groups else "train" for x in ids]})


def load(ctx: RunContext) -> tuple[pd.DataFrame, dict[str, dict]]:
    manifest = ctx.input_dir / "manifest.csv"
    problems = verify_manifest(manifest) if manifest.exists() else [{"problem": "no_manifest"}]
    if problems and ctx.config.get("strict_provenance", True):
        raise ValueError(f"provenance check failed ({len(problems)} problems), first: {problems[:3]}")
    images = pd.read_csv(ctx.input_dir / "images.csv", dtype={"image_id": str, "path": str, "camera_id": str})
    required = {"image_id", "path", "camera_id", "captured_at"}
    missing = sorted(required - set(images.columns))
    if missing:
        raise ValueError(f"images.csv missing columns: {missing}")
    if images.image_id.duplicated().any():
        raise ValueError("images.csv contains duplicate image_id")
    return images, _load_images(ctx.input_dir, images)


def process(ctx: RunContext, data: tuple[pd.DataFrame, dict[str, dict]]) -> pd.DataFrame:
    if ctx.track != "t05":
        spec = get_track(ctx.track)
        raise NotImplementedError(f"Implement process() for {spec.track} ({spec.title}); this PoC implements T05 only")
    images, features = data
    pairs = _build_candidates(ctx, images, features)
    ctx.stats.update({"n_images": len(images), "n_candidate_pairs": len(pairs),
                      "n_predicted_duplicate_pairs": int(pairs.pred_dup.sum()) if len(pairs) else 0})
    return pairs


def rank(ctx: RunContext, scored: pd.DataFrame) -> pd.DataFrame:
    if scored.empty:
        scored = pd.DataFrame(columns=["pair_id", "review_priority", "reason", "path_a", "path_b"])
    q = make_review_queue(scored, "pair_id", "review_priority", int(ctx.param("budget", 20)),
                          reason_col="reason", evidence_col="path_a")
    paths = scored.set_index("pair_id")[["path_a", "path_b"]] if len(scored) else pd.DataFrame(columns=["path_a", "path_b"])
    q["path_a"] = q.item_id.map(paths.path_a) if len(paths) else ""
    q["path_b"] = q.item_id.map(paths.path_b) if len(paths) else ""
    write_review_queue(q, ctx.out("review_queue.csv"))
    render_contact_sheet(q, ctx.out("contact_sheet.html"), image_col="path_b", before_image_col="path_a",
                         image_root=ctx.input_dir, title="T05 suspected near-duplicate pairs")
    return q


def review(ctx: RunContext, scored: pd.DataFrame, queue: pd.DataFrame) -> pd.DataFrame:
    path = ctx.output_dir / "review_queue_reviewed.csv"
    if not path.exists():
        return scored
    decisions = load_review_decisions(path)
    out = scored.copy()
    known = set(out.pair_id)
    for row in decisions.itertuples(index=False):
        if row.item_id not in known:
            raise ValueError(f"reviewed pair not found in this run: {row.item_id}")
        mask = out.pair_id == row.item_id
        before = int(out.loc[mask, "pred_dup"].iloc[0])
        if row.reviewer_decision == "approve":
            after = 1
        elif row.reviewer_decision == "reject":
            after = 0
        elif row.reviewer_decision == "edit":
            if str(row.override_value).strip() not in {"0", "1"}:
                raise ValueError("edit decisions require override_value 0 or 1")
            after = int(row.override_value)
        else:
            after = before
        out.loc[mask, "pred_dup"] = after
        ctx.audit.log(actor=row.reviewer, action=f"review:{row.reviewer_decision}", item_id=row.item_id,
                      before=before, after=after, reason=row.review_note)
    ctx.stats["n_reviewed"] = len(decisions)
    return out


def run(ctx: RunContext) -> None:
    if ctx.track != "t05":
        spec = get_track(ctx.track)
        raise NotImplementedError(f"Implement process() for {spec.track} ({spec.title}); this PoC implements T05 only")
    spec = get_track(ctx.track)
    data = load(ctx)
    scored = process(ctx, data)
    queue = rank(ctx, scored)
    final = review(ctx, scored, queue)
    images, features = data
    _make_split(ctx, images, features, final).to_csv(ctx.out("split_manifest.csv"), index=False)
    final[spec.pred_columns + ["score", "pred_dup"]].to_csv(ctx.out(spec.pred_file), index=False)
    decision = Decision(status="HOLD", reason_code="T05_REVIEW_AND_GT_REQUIRED",
                        reason="Review candidate pairs and evaluate with instructor ground truth before release.",
                        owner=ctx.config.get("owner", "TODO-owner"), scope=ctx.track,
                        evidence=[str(ctx.out(spec.pred_file)), str(ctx.out("split_manifest.csv")),
                                  str(ctx.out("review_queue.csv"))])
    write_decision(decision, ctx.out("decision.json"), ctx.out("decision_log.csv"))
