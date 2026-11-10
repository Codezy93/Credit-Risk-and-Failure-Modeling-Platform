"""Check saved load-test evidence and refresh the report and statistics reference."""

import hashlib
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("MPLCONFIGDIR", "/tmp/credit-risk-mpl")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
from mlflow import MlflowClient
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from util.mlflow_evaluation import markdown_table


def main():
    manifest = json.loads((ROOT / "assets/results/load_test_latest.json").read_text())
    directory = ROOT / manifest["result_directory"]
    metrics = pd.read_csv(directory / "stage_metrics.csv")
    for path, expected in manifest["source_sha256"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path
    assert hashlib.sha256((ROOT / "models/selected_model.joblib").read_bytes()).hexdigest() == manifest["model_sha256"]
    assert hashlib.sha256((ROOT / "data/clean/modeling/validation.parquet").read_bytes()).hexdigest() == manifest["validation_parquet_sha256"]
    fig, ax = plt.subplots(figsize=(8, 4))
    for _, row in metrics.iterrows():
        stage = directory / row.stage
        outputs = pd.read_csv(stage / "output_records.csv.gz")
        first = outputs.drop_duplicates("event_id")
        assert len(outputs) == row.received_records and len(first) == row.unique_outputs
        for p in [50, 95, 99]:
            latency = first[first.status == "scored"].received_at_ms - first[first.status == "scored"].emitted_at_ms
            np.testing.assert_allclose(np.percentile(latency, p), row[f"end_to_end_p{p}_ms"], atol=1e-8)
        assert (outputs.model_sha256 == manifest["model_sha256"]).all()
        backlog = pd.read_csv(stage / "backlog.csv")
        assert backlog.checkpoint_lag.max() == row.peak_sampled_checkpoint_lag
        assert backlog.checkpoint_lag.iloc[-1] == row.end_checkpoint_lag
        ax.plot((backlog.sampled_at_ms - backlog.sampled_at_ms.iloc[0]) / 1000,
                backlog.checkpoint_lag, label=f"{row.target_rows_per_second} messages/s")
    ax.set(xlabel="Seconds from first stage sample", ylabel="Kafka end minus Spark completed offsets",
           title="Sampled checkpoint lag, including in-flight batches")
    ax.legend();fig.tight_layout()
    for extension in ["png", "svg"]:
        fig.savefig(directory / f"checkpoint_lag.{extension}", dpi=160)
    plt.close(fig)
    mlflow.set_tracking_uri("sqlite:///" + str(ROOT / "models/mlflow.db"))
    client = MlflowClient()
    parent = client.get_run(manifest["mlflow_run_id"])
    children = client.search_runs([parent.info.experiment_id], filter_string=f"tags.mlflow.parentRunId = '{parent.info.run_id}'")
    assert parent.info.status == "FINISHED" and len(children) == len(metrics)
    assert all(child.info.status == "FINISHED" for child in children)
    proof = {"status": "passed", "batch_id": manifest["batch_id"], "source_and_input_hashes_match": True,
        "raw_output_counts_and_latency_percentiles_recomputed": True, "backlog_samples_reconciled": True,
        "mlflow_parent_and_children_finished": True,
        "model_unchanged": True, "measured_rows": int(metrics.expected_rows.sum()),
        "missing_rows": int(metrics.missing_rows.sum()), "duplicate_records": int(metrics.duplicate_records.sum()),
        "failure_injection_tested": False,
        "result_sha256": {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sorted(directory.rglob("*")) if path.is_file()},
        "reporter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (ROOT / "assets/results/load_test_verification.json").write_text(json.dumps(proof, indent=2) + "\n")
    columns = ["target_rows_per_second", "expected_rows", "actual_emission_rows_per_second",
        "completed_rows_per_second", "end_to_end_p50_ms", "end_to_end_p95_ms", "end_to_end_p99_ms",
        "peak_sampled_checkpoint_lag", "drain_after_last_ack_seconds", "missing_rows", "duplicate_records"]
    table = markdown_table(metrics[columns])
    test_note = (directory / "test_results.txt").read_text().strip().splitlines()[-1] if (directory / "test_results.txt").exists() else "No test transcript attached to this batch."
    text = f'''# Kafka–PySpark load-test results

Batch `{manifest['batch_id']}`, completed {manifest['completed_at_utc']}.
Status: **{manifest['status']}**. The frozen model and threshold were unchanged.
Regression test transcript: `{test_note}`.

{table}

<details><summary>Complete per-stage metrics</summary>

```json
{json.dumps(metrics.to_dict(orient='records'), indent=2)}
```

</details>

## What was measured

One continuous Spark query was warmed with 100 records, then given one
{manifest['duration_seconds_per_stage']}-second paced stage per target rate. Each
stage drained before the next began. Topics and checkpoint were unique to the
test. Each stage reuses the first N historical validation applications; they are
distinct events within a stage, not new borrowers across stages. No invalid
fixtures were injected during the load test. Raw output and producer logs are
retained separately for warmup and every stage.

Actual emission rate is (N−1)/(last emission−first emission). Completed rows/s is
unique valid scores/(last collector receipt−first emission), including drain.
Latency percentiles use the first output per event and measure producer emission
to collector receipt from the output Kafka topic. They include micro-batch
scheduling, scoring, Kafka transport and collector polling/buffering; they are
not pure model inference times. Emit-to-worker-score percentiles are also saved.
Clocks share this local host; negative latency counts are recorded explicitly.

Lag is sampled about once per second: Kafka input log-end offsets minus the end
offsets in completed Spark progress. It includes the in-flight micro-batch and is
not Kafka consumer-group committed lag. Peak values can miss subsecond peaks.
`pending_at_last_emission` in the full metrics counts expected events without a
collected output at the final producer timestamp. Drain time ends at the last
unique receipt and starts at the last producer acknowledgement.

Every received valid probability and risk flag was compared with direct model
scoring. Stage metrics also count missing outputs, unexpected invalid outputs,
duplicates and delivery errors. Raw output IDs, model SHA and source offsets are
retained. A two-second quiet collection period follows each drain; duplicates
arriving later would require longer observation. Kafka delivery remains at least
once; no failure-injection or exactly-once claim is made.

## Machine and configuration

CPU: {manifest['cpu_model']}; {manifest['logical_cpus']} logical host CPUs.
Host memory: {manifest['host_memory_kib']/1024/1024:.2f} GiB.
Docker VM: {manifest['docker_resources']['cpus']} CPUs,
{manifest['docker_resources']['memory_bytes']/1024**3:.2f} GiB RAM.
Spark: local[2], 2-second trigger, 10,000 maximum offsets/trigger, 1,000-row Arrow
batches, three partitions per topic and one model thread per worker. Python
{manifest['python']}; PySpark {manifest['versions']['pyspark']}. Exact Java,
dependency versions, source hashes and input fingerprint are in the manifest.
The collector, producer and Spark share the host; the Kafka broker runs in Docker.

<details><summary>Complete environment, source fingerprints and manifest</summary>

```json
{json.dumps(manifest, indent=2)}
```

</details>

These are short local runs with one measurement per rate. They do not establish
long-duration stability, a production capacity limit or a latency SLA. JVM startup
was warmed, but stage-specific batch/model-loading costs remain part of the run.
Broker failure, worker failure, restart under active load and downstream
deduplication remain untested in this benchmark. ELK monitoring is still pending.

![Emission, completion and latency](../{manifest['result_directory']}/load_results.png)

![Checkpoint lag](../{manifest['result_directory']}/checkpoint_lag.png)

## Reproduce

With Java 17/21 and the optional streaming environment installed:

```bash
make kafka-up
make load-test
# Change the stage rates/duration; each stage must fit within 162,570 rows.
make load-test ARGS="--rates 100 500 2000 --duration 30 --drain-timeout 120"
```

Results are saved by batch ID. MLflow experiment:
`lendingclub_streaming_load_tests`; parent `{manifest['mlflow_run_id']}`, with one
child per measured stage. The query is stopped after drain. Kafka stays available
until `make kafka-down`. No source messages, topics or checkpoints are deleted.

[Full metrics](../{manifest['result_directory']}/stage_metrics.csv),
[manifest](../{manifest['result_directory']}/manifest.json), and
[verification](../assets/results/load_test_verification.json).
See the [Spark Kafka guide](https://spark.apache.org/docs/4.1.2/streaming/structured-streaming-kafka-integration.html)
for source/sink and offset semantics.
'''
    (ROOT / "docs/load_testing.md").write_text(text)
    stats = ROOT / "assets/statistics.md"
    content = stats.read_text()
    start, end = "<!-- load-test-statistics -->", "<!-- end-load-test-statistics -->"
    section = start + "\n" + text.replace("# Kafka–PySpark load-test results", "## Latest Kafka–PySpark load-test statistics", 1).replace("../assets/", "") + "\n" + end + "\n\n"
    # Report paths are relative to docs/; statistics paths are relative to assets/.
    if start in content:
        before, rest = content.split(start, 1)
        _, after = rest.split(end, 1)
        content = before + section + after.lstrip("\n")
    else:
        position = content.index("\n## Latest streaming verification:")
        content = content[:position] + "\n" + section + content[position:]
    stats.write_text(content)
    with mlflow.start_run(run_id=manifest['mlflow_run_id']):
        replay = pd.read_parquet(ROOT / "data/clean/modeling/validation.parquet")
        feature_names = json.loads((ROOT / "assets/results/model_data_manifest.json").read_text())["features"]
        if not client.get_run(manifest['mlflow_run_id']).inputs.dataset_inputs:
            mlflow.log_input(mlflow.data.from_pandas(replay[feature_names].head(int(metrics.expected_rows.max())),
                source=str(ROOT / "data/clean/modeling/validation.parquet"), name="load_replay_features"), context="load_replay")
        for child in children:
            if not client.get_run(child.info.run_id).inputs.dataset_inputs:
                stage = metrics[metrics.stage == child.data.tags["mlflow.runName"]].iloc[0]
                with mlflow.start_run(run_id=child.info.run_id, nested=True):
                    sample = replay[feature_names].head(int(stage.expected_rows))
                    mlflow.log_input(mlflow.data.from_pandas(sample, source=str(ROOT / "data/clean/modeling/validation.parquet"),
                        name=stage.stage + "_features"), context="load_replay")
                    mlflow.log_table(sample.head(100), artifact_file="replay_preview.json")
        for path in [ROOT/'docs/load_testing.md', stats, ROOT/'assets/results/load_test_verification.json', Path(__file__)]:
            mlflow.log_artifact(str(path), artifact_path="verified_report")
        for path in directory.glob('checkpoint_lag.*'):
            mlflow.log_artifact(str(path), artifact_path="verified_report")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
