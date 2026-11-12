"""Rerun modelling stages from prepared data, keeping prior runs and evidence."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from time import perf_counter
import xml.etree.ElementTree as ET

from mlflow import MlflowClient

ROOT = Path(__file__).resolve().parents[1]
STAGES = [
    ("05_train_models.py", "model_experiments"),
    ("07_improve_auc.py", "auc_improvement"),
    ("08_validate_models.py", "validation_hardening"),
    ("09_basel_loss_experiment.py", "basel_loss"),
    ("11_ann_experiments.py", "ann_experiments"),
    ("13_review_validation.py", "validation_review"),
    ("14_interpret_bias.py", "interpret_bias"),
]


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run_snapshot(client):
    runs = {}
    for experiment in client.search_experiments():
        page_token = None
        while True:
            page = client.search_runs([experiment.experiment_id], max_results=1000, page_token=page_token)
            for run in page:
                runs[run.info.run_id] = {"metrics": run.data.metrics, "params": run.data.params,
                    "tags": run.data.tags, "status": run.info.status, "start_time": run.info.start_time,
                    "end_time": run.info.end_time, "artifact_uri": run.info.artifact_uri}
            page_token = page.token
            if not page_token:
                break
    return runs


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = ROOT / "assets/results/refresh" / stamp
    local = ROOT / "models/refresh" / stamp
    snapshots = output / "previous_manifests"
    snapshots.mkdir(parents=True)
    local.mkdir(parents=True)
    original_statistics = (ROOT / "assets/statistics.md").read_text()
    (local / "previous_statistics.md").write_text(original_statistics)
    for path in (ROOT / "assets/results").glob("*_latest.json"):
        shutil.copy2(path, snapshots / path.name)
    shutil.copy2(ROOT / "models/selected_model.joblib", local / "previous_selected_model.joblib")

    historical_files = {}
    for _, name in STAGES:
        previous = json.loads((snapshots / f"{name}_latest.json").read_text())
        for key in ["result_directory", "figure_directory", "model_directory"]:
            if previous.get(key):
                for path in (ROOT / previous[key]).rglob("*"):
                    if path.is_file():
                        historical_files[str(path.relative_to(ROOT))] = file_hash(path)
    (output / "historical_file_hashes.json").write_text(json.dumps(historical_files, indent=2) + "\n")
    client = MlflowClient(tracking_uri="sqlite:///" + str(ROOT / "models/mlflow.db"))
    historical_runs = run_snapshot(client)
    (local / "previous_mlflow_runs.json").write_text(json.dumps(historical_runs, indent=2) + "\n")
    source_paths = [*sorted((ROOT / "scripts").glob("*.py")), *sorted((ROOT / "util").glob("*.py")),
        *sorted((ROOT / "sql").glob("*.sql")), *sorted((ROOT / "notebooks").glob("*.py")),
        *sorted((ROOT / "tests").glob("*.py")), ROOT / "requirements.lock",
        ROOT / "requirements-streaming.lock", ROOT / "requirements.txt", ROOT / "Makefile",
        ROOT / "pytest.ini", ROOT / ".github/workflows/tests.yml"]
    sources = {str(p.relative_to(ROOT)): file_hash(p) for p in source_paths}
    data = json.loads((ROOT / "assets/results/model_data_manifest.json").read_text())
    inputs = {item["path"]: file_hash(ROOT / item["path"]) for item in data["artifacts"]}
    proof = {"status": "running", "refresh_id": stamp, "source_sha256": sources,
        "prepared_input_sha256": inputs, "historical_files_checked": len(historical_files),
        "historical_runs_checked": len(historical_runs), "stages": []}

    def save():
        (output / "verification.json").write_text(json.dumps(proof, indent=2) + "\n")

    def execute(label, command):
        log = local / f"{label}.log"
        started = perf_counter()
        print(f"Running {label}; log: {log.relative_to(ROOT)}", flush=True)
        with log.open("w") as stream:
            result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        record = {"stage": label, "returncode": result.returncode, "seconds": perf_counter() - started,
            "log_path_local": str(log.relative_to(ROOT)), "log_sha256": file_hash(log)}
        proof["stages"].append(record)
        if result.returncode:
            proof["status"] = "failed"
            save()
            raise RuntimeError(f"{label} failed; read {log}")
        save()
        return record

    save()
    execute("pytest", [sys.executable, "-m", "pytest", "-q", f"--junitxml={output / 'pytest.xml'}"])
    suites = ET.parse(output / "pytest.xml").getroot().iter("testsuite")
    totals = {key: 0 for key in ["tests", "failures", "errors", "skipped"]}
    for suite in suites:
        for key in totals:
            totals[key] += int(suite.get(key, 0))
    assert totals["tests"] > 0 and totals["failures"] == totals["errors"] == totals["skipped"] == 0, totals
    proof["pytest"] = totals
    for script, name in STAGES:
        record = execute(script.removesuffix(".py"), [sys.executable, "scripts/" + script])
        manifest = json.loads((ROOT / "assets/results" / f"{name}_latest.json").read_text())
        previous = json.loads((snapshots / f"{name}_latest.json").read_text())
        assert manifest["status"] == "complete"
        assert manifest["batch_run_id"] != previous["batch_run_id"]
        expected = sources["scripts/" + script]
        recorded = manifest.get("execution_script_sha256", manifest.get("training_script_sha256", manifest.get("script_sha256")))
        assert recorded == expected, (script, recorded, expected)
        for filename, digest in manifest["results_sha256"].items():
            assert file_hash(ROOT / manifest["result_directory"] / filename) == digest, filename
        record.update(batch_run_id=manifest["batch_run_id"], previous_batch_run_id=previous["batch_run_id"],
            execution_source_sha256=expected, result_directory=manifest["result_directory"],
            result_csv_hashes_verified=len(manifest["results_sha256"]))
        save()

    # Keep the teaching-data audit, which is outside this refresh, in the statistics reference.
    marker = "<!-- teaching-extract-audit-statistics -->"
    statistics = ROOT / "assets/statistics.md"
    if marker not in statistics.read_text() and marker in original_statistics:
        teaching = original_statistics.split(marker, 1)[1].split("<!-- coefficient-validation-statistics -->", 1)[0]
        statistics.write_text(statistics.read_text().replace("<!-- coefficient-validation-statistics -->",
            marker + teaching + "<!-- coefficient-validation-statistics -->", 1))
    repository = "https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/"
    raw = "https://raw.githubusercontent.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/main/"
    for path in (ROOT / "docs").glob("*.md"):
        def link(match):
            image, title, target = match.groups()
            if not target.startswith("../"):
                return match.group(0)
            return f"{image}[{title}]({raw if image else repository}{target[3:]})"
        text = re.sub(r"(!?)\[([^\]]*)\]\(([^)]+)\)", link, path.read_text())
        if path.stem in ["model_experiments", "auc_improvement", "validation_hardening", "basel_loss_experiment",
                          "ann_experiments", "coefficient_validation", "interpret_bias"] and "(risk_terminology.md)" not in text:
            head, body = text.split("\n", 1)
            text = head + "\n\nTerminology: [lifetime charge-off probability, snapshot losses and capital scenarios](risk_terminology.md).\n" + body
        path.write_text(text)
    execute("loss_limitations_report", [sys.executable, "scripts/26_report_loss_limitations.py"])
    execute("model_review_export", [sys.executable, "-m", "marimo", "export", "html",
        "notebooks/10_model_review.py", "-o", "docs/model_review.html", "--no-include-code"])

    for name, digest in historical_files.items():
        assert file_hash(ROOT / name) == digest, f"Historical file changed: {name}"
    current_runs = run_snapshot(client)
    assert all(current_runs[key] == value for key, value in historical_runs.items()), "Historical MLflow run changed."
    assert all(file_hash(ROOT / name) == digest for name, digest in inputs.items()), "Prepared data changed."
    assert all(file_hash(ROOT / name) == digest for name, digest in sources.items()), "Source changed during execution."
    proof.update(status="passed", completed_at_utc=datetime.now(timezone.utc).isoformat(),
        historical_files_unchanged=True, historical_runs_unchanged=True, prepared_inputs_unchanged=True,
        execution_sources_unchanged=True, new_mlflow_runs=len(current_runs) - len(historical_runs))
    save()
    (ROOT / "assets/results/experiment_refresh_latest.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(f"Refresh passed: {output.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
