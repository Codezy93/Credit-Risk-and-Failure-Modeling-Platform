"""Annotate existing local MLflow runs; leave numerical evidence unchanged."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from mlflow import MlflowClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from util.risk_scope import SCOPE_TAGS, scope_description


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def main():
    database = ROOT / "models/mlflow.db"
    assert database.exists(), "The existing local MLflow database is required."
    client = MlflowClient(tracking_uri="sqlite:///" + str(database))
    names = ["lendingclub_resolved_36m", "lendingclub_auc_ablation",
        "lendingclub_validation_hardening", "lendingclub_basel_loss_proxies",
        "lendingclub_ann_challengers", "lendingclub_coefficient_validation",
        "lendingclub_interpretability_bias", "lendingclub_streaming_smoke",
        "lendingclub_streaming_load_tests", "lendingclub_streaming_recovery"]
    evidence = sorted((ROOT / "assets/results").rglob("*.csv"))
    evidence += sorted((ROOT / "assets/results").glob("*_latest.json"))
    evidence += sorted((ROOT / "models").rglob("*.joblib"))
    before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in evidence}
    updates = []
    for name in names:
        experiment = client.get_experiment_by_name(name)
        if experiment is None:
            continue
        for key, value in SCOPE_TAGS.items():
            client.set_experiment_tag(experiment.experiment_id, key, value)
        client.set_experiment_tag(experiment.experiment_id, "mlflow.note.content",
            scope_description(experiment.tags.get("mlflow.note.content", "")))
        runs = client.search_runs([experiment.experiment_id], max_results=1000)
        assert len(runs) < 1000, "Paginate before annotating an experiment with 1,000 or more runs."
        for run in runs:
            numerical_before = fingerprint({"metrics": run.data.metrics, "params": run.data.params,
                "status": run.info.status, "start_time": run.info.start_time, "end_time": run.info.end_time})
            for key, value in SCOPE_TAGS.items():
                client.set_tag(run.info.run_id, key, value)
            client.set_tag(run.info.run_id, "mlflow.note.content",
                scope_description(run.data.tags.get("mlflow.note.content", "")))
            refreshed = client.get_run(run.info.run_id)
            numerical_after = fingerprint({"metrics": refreshed.data.metrics, "params": refreshed.data.params,
                "status": refreshed.info.status, "start_time": refreshed.info.start_time, "end_time": refreshed.info.end_time})
            assert numerical_before == numerical_after, run.info.run_id
        updates.append({"experiment": name, "runs_annotated": len(runs)})
    assert updates, "No matching experiments were found."
    after = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in evidence}
    assert before == after, "Recorded results or model binaries changed."
    proof = {"status": "passed", "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Terminology annotations only; no fitting, scoring or metric regeneration",
        "experiments": updates, "runs_annotated": sum(row["runs_annotated"] for row in updates),
        "run_metrics_params_status_times_unchanged": True,
        "evidence_files_unchanged": len(before), "evidence_hashes_fingerprint": fingerprint(before),
        "scope_tags": SCOPE_TAGS,
        "historical_manifests_and_logged_artifacts_rewritten": False,
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__), ROOT / "util/risk_scope.py"]}}
    path = ROOT / "assets/results/risk_terminology_verification.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(f"Annotated {proof['runs_annotated']} existing runs; {len(before)} evidence files unchanged.")


if __name__ == "__main__":
    main()
