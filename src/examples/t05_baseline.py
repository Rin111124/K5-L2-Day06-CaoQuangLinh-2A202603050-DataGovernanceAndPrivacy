"""T05 baseline: exact SHA-256 matching and image-independent random split."""
from __future__ import annotations

from itertools import combinations

import pandas as pd

from ..common.context import RunContext
from ..common.decision import Decision, write_decision
from ..common.io import sha256_file
from ..common.manifest import verify_manifest
from ..common.review import make_review_queue, write_review_queue


def run(ctx: RunContext) -> None:
    manifest = ctx.input_dir / "manifest.csv"
    problems = verify_manifest(manifest) if manifest.exists() else [{"problem": "no_manifest"}]
    if problems and ctx.config.get("strict_provenance", True):
        raise ValueError(f"provenance check failed ({len(problems)} problems), first: {problems[:3]}")
    images = pd.read_csv(ctx.input_dir / "images.csv", dtype={"image_id": str, "path": str})
    by_hash: dict[str, list[str]] = {}
    for row in images.itertuples(index=False):
        by_hash.setdefault(sha256_file(ctx.input_dir / row.path), []).append(row.image_id)
    pairs = [{"pair_id": f"{a}::{b}", "img_a": a, "img_b": b, "score": 1.0,
              "pred_dup": 1, "reason": "exact_sha256"}
             for sha, ids in by_hash.items() for a, b in combinations(sorted(ids), 2)]
    pred = pd.DataFrame(pairs, columns=["pair_id", "img_a", "img_b", "score", "pred_dup", "reason"])
    pred[["img_a", "img_b", "score", "pred_dup"]].to_csv(ctx.out("suspect_pairs.csv"), index=False)

    fraction = min(max(float(ctx.config.get("params", {}).get("test_fraction", .3)), 0), 1)
    n_test = int(round(len(images) * fraction))
    if len(images) > 1 and fraction > 0:
        n_test = min(max(n_test, 1), len(images) - 1)
    test_ids = set(ctx.rng.permutation(images.image_id.to_numpy())[:n_test])
    pd.DataFrame({"image_id": images.image_id,
                  "split": ["test" if item in test_ids else "train" for item in images.image_id]
                  }).to_csv(ctx.out("split_manifest.csv"), index=False)

    if len(pred):
        queue = make_review_queue(pred, "pair_id", "score", int(ctx.param("budget", 20)), reason_col="reason")
    else:
        empty = pd.DataFrame(columns=["pair_id", "score", "reason"])
        queue = make_review_queue(empty, "pair_id", "score", int(ctx.param("budget", 20)), reason_col="reason")
    write_review_queue(queue, ctx.out("review_queue.csv"))
    ctx.stats.update({"n_images": len(images), "n_candidate_pairs": len(pred), "baseline": "exact_sha256"})
    decision = Decision(status="HOLD", reason_code="BASELINE_ONLY",
                        reason="Exact-hash baseline with image-level random split; not a release decision.",
                        owner=ctx.config.get("owner", "baseline"), scope=ctx.track,
                        evidence=[str(ctx.out("suspect_pairs.csv")), str(ctx.out("split_manifest.csv")),
                                  str(ctx.out("review_queue.csv"))])
    write_decision(decision, ctx.out("decision.json"), ctx.out("decision_log.csv"))
