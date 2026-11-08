import json
import shutil

import pandas as pd
import pytest

from test_workflow import ROOT, load_script
from util.feature_policy import POLICY


def preparation_project(tmp_path, database):
    script = load_script("04_prepare_model_data")
    results = tmp_path / "assets/results"
    results.mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "data/clean").mkdir(parents=True)
    (tmp_path / "assets/statistics.md").write_text("# Statistics\n")
    shutil.copytree(ROOT / "sql", tmp_path / "sql")
    database.execute("COPY loans TO ? (FORMAT PARQUET)", [str(tmp_path / "data/clean/loans.parquet")])
    candidates = POLICY["groups"]["baseline"]
    eda = {"status": "complete", "checks_passed": True, "benchmark_term_months": 36,
           "train_years": [2011, 2012, 2013], "validation_years": [2014],
           "exploratory_test_years": [2015], "candidate_features": candidates,
           "splits": [{"proposed_split": name, "eligible_resolved_loans": rows,
                       "charged_off": 1, "fully_paid": rows - 1}
                      for name, rows in [("train", 3), ("validation", 2), ("exploratory_test", 2)]]}
    (results / "eda_completion_manifest.json").write_text(json.dumps(eda))
    pd.DataFrame({"column": candidates, "initial_feature_decision": "candidate"}).to_csv(
        results / "eda_feature_decisions.csv", index=False)
    script.ROOT, script.RESULTS = tmp_path, results
    return script, eda


def test_prepared_files_preserve_row_alignment_and_training_only_selection(tmp_path, database):
    script, _ = preparation_project(tmp_path, database)
    script.main()
    manifest = json.loads((script.RESULTS / "model_data_manifest.json").read_text())
    assert "application_type" in manifest["training_only_dropped_features"]
    assert set(manifest["features"]).isdisjoint({"loan_id", "loan_status", "issue_date", "charged_off"})
    expected_ids = {"train": [1001, 1002, 1003], "validation": [1005, 1006], "exploratory_test": [1007, 1008]}
    for split, ids in expected_ids.items():
        frame = pd.read_parquet(tmp_path / f"data/clean/modeling/{split}.parquet")
        metadata = pd.read_parquet(tmp_path / f"data/clean/modeling/{split}_metadata.parquet")
        assert metadata.loan_id.tolist() == ids
        expected_labels = [0, 1, 0] if split == "train" else [0, 1]
        assert frame.charged_off.tolist() == expected_labels
        assert script.file_hash(tmp_path / f"data/clean/modeling/{split}.parquet") == next(
            item["sha256"] for item in manifest["artifacts"] if item["split"] == split and item["kind"] == "features_and_target")
    # Validation contains new home-ownership values, yet training-constant fields stay dropped.
    assert "home_ownership" in manifest["training_only_dropped_features"]


def test_preparation_rejects_post_origination_candidate_before_export(tmp_path, database):
    script, eda = preparation_project(tmp_path, database)
    eda["candidate_features"] = [*eda["candidate_features"], "total_pymnt"]
    (script.RESULTS / "eda_completion_manifest.json").write_text(json.dumps(eda))
    with pytest.raises(ValueError, match="[Dd]enied|[Ff]orbidden"):
        script.main()
    assert not (tmp_path / "data/clean/modeling").exists()
