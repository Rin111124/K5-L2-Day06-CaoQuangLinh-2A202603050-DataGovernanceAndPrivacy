from src.pipeline import _components, _pair_labels
from src.main import main
import json
import pandas as pd


def test_pair_labels_separate_positive_from_borderline_candidate():
    params = {"corr_min": 0.92, "corr_hash_min": 0.78, "phash_max": 8,
             "dhash_max": 12, "candidate_corr_min": 0.70, "candidate_phash_max": 16}
    assert _pair_labels(True, 0.1, 63, 63, params) == (True, True)
    assert _pair_labels(False, 0.95, 40, 40, params) == (True, True)
    assert _pair_labels(False, 0.80, 8, 12, params) == (True, True)
    assert _pair_labels(False, 0.79, 10, 10, params) == (False, True)
    assert _pair_labels(False, 0.69, 2, 2, params) == (False, False)


def test_components_keep_linked_images_together_and_singletons_separate():
    groups = _components(["a", "b", "c", "d"], [("a", "b"), ("b", "c")])
    assert groups["a"] == groups["b"] == groups["c"]
    assert groups["d"] != groups["a"]


def _assert_run_artifacts(output):
    pred = pd.read_csv(output / "suspect_pairs.csv")
    split = pd.read_csv(output / "split_manifest.csv")
    decision = json.loads((output / "decision.json").read_text(encoding="utf-8"))
    assert {"img_a", "img_b", "score", "pred_dup"}.issubset(pred.columns)
    assert list(split.columns) == ["image_id", "split"]
    assert set(split.split) <= {"train", "test", "drop"}
    assert len(split) == 120 and split.image_id.is_unique
    assert decision["status"] == "HOLD"
    assert decision["reason_code"] and decision["owner"]
    assert decision["evidence"]
    assert all((output.parent.parent / path).exists() for path in decision["evidence"])


def test_t05_poc_runs_end_to_end_with_contract_and_split(tmp_path):
    output = tmp_path / "poc"
    rc = main(["--config", "configs/lab.yaml", "--track", "t05", "--output", str(output), "--offline", "--seed", "42"])
    assert rc == 0
    _assert_run_artifacts(output)
    pred = pd.read_csv(output / "suspect_pairs.csv")
    split = pd.read_csv(output / "split_manifest.csv").set_index("image_id").split.to_dict()
    positive = pred[pred.pred_dup == 1]
    assert all(split[r.img_a] == split[r.img_b] for r in positive.itertuples())


def test_t05_baseline_runs_end_to_end_with_evidence(tmp_path):
    output = tmp_path / "baseline"
    rc = main(["--config", "configs/lab.yaml", "--track", "t05", "--output", str(output),
               "--pipeline", "src.examples.t05_baseline", "--offline", "--seed", "42"])
    assert rc == 0
    _assert_run_artifacts(output)
