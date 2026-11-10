"""Verify the persisted recovery evidence and publish the local project report."""

import hashlib
import json
from pathlib import Path
import sqlite3
import sys

from confluent_kafka import Consumer, TopicPartition
import mlflow
from mlflow import MlflowClient
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from util.mlflow_evaluation import markdown_table


def main():
    manifest = json.loads((ROOT / "assets/results/recovery_latest.json").read_text())
    directory = ROOT / manifest["result_directory"]
    for path, digest in manifest["source_sha256"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    assert hashlib.sha256((ROOT / "models/selected_model.joblib").read_bytes()).hexdigest() == manifest["model_sha256"]
    assert hashlib.sha256((ROOT / "data/clean/modeling/validation.parquet").read_bytes()).hexdigest() == manifest["validation_parquet_sha256"]
    database = ROOT / manifest["database"]
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    outcomes = pd.read_sql_query("SELECT outcome,COUNT(*) AS rows FROM deliveries GROUP BY outcome", connection)
    counts = dict(zip(outcomes.outcome, outcomes.rows))
    assert counts["inserted"] == manifest["stored_total_unique_rows_including_warmup"]
    assert counts["duplicate"] == manifest["suppressed_duplicate_deliveries"]
    assert counts["conflict"] == 1
    assert connection.execute("SELECT COUNT(*) FROM scores").fetchone()[0] == manifest["rows"] + 100
    for (payload,) in connection.execute("SELECT payload_json FROM scores"):
        assert json.loads(payload)["model_sha256"] == manifest["model_sha256"]
    assert connection.execute("SELECT COUNT(*) FROM log_outbox WHERE exported=0").fetchone()[0] == 0
    connection.close()
    batch = manifest["batch_id"]
    consumer = Consumer({"bootstrap.servers": "localhost:9092", "group.id": batch + "-store", "enable.auto.commit": False})
    outputs = [TopicPartition(batch + "-" + topic, p) for topic in ["scores", "invalid"] for p in range(3)]
    committed = consumer.committed(outputs, timeout=15)
    output_lag = {}
    for partition in committed:
        end = consumer.get_watermark_offsets(partition, timeout=5)[1]
        output_lag[f"{partition.topic}:{partition.partition}"] = end - max(0, partition.offset)
    consumer.close()
    assert sum(output_lag.values()) == 0, output_lag
    checkpoint = database.parent / "checkpoint"
    latest = max(int(p.name) for p in (checkpoint / "commits").iterdir() if p.name.isdigit())
    offsets = json.loads((checkpoint / "offsets" / str(latest)).read_text().splitlines()[-1])
    assert sum(offsets[batch + "-input"].values()) == manifest["rows"] + 150
    if manifest["elk_verified"]:
        response = requests.post("http://127.0.0.1:19200/credit-risk-monitoring-*/_count", json={"query": {
            "bool": {"must": [{"term": {"event_type": "score_delivery"}},
                {"terms": {"run_id": [batch + "-main", batch + "-warmup"]}}]}}}, timeout=30)
        response.raise_for_status()
        assert response.json()["count"] == manifest["stored_delivery_rows"]
        response = requests.get("http://127.0.0.1:15601/api/saved_objects/dashboard/credit-risk-streaming", timeout=60)
        response.raise_for_status()
        assert len(response.json()["references"]) == 8
    mlflow.set_tracking_uri("sqlite:///" + str(ROOT / "models/mlflow.db"))
    run = MlflowClient().get_run(manifest["mlflow_run_id"])
    assert run.info.status == "FINISHED" and len(run.inputs.dataset_inputs) == 1
    proof = {"status": "passed", "batch_id": batch, "source_model_and_input_hashes_match": True,
        "sqlite_outcomes_reconciled": True, "original_model_results_preserved_after_conflict": True,
        "spark_checkpoint_input_offsets_reconciled": True, "sink_group_lag": output_lag,
        "transactional_outbox_pending": 0, "elasticsearch_delivery_count_matches_sqlite": manifest["elk_verified"],
        "kibana_dashboard_references": 8 if manifest["elk_verified"] else 0,
        "mlflow_run_finished_with_replay_dataset": True,
        "reporter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "result_sha256": {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(directory.rglob("*")) if p.is_file()}}
    (ROOT / "assets/results/recovery_verification.json").write_text(json.dumps(proof, indent=2) + "\n")
    table = markdown_table(pd.DataFrame([
        {"Measurement": "Main replay events", "Value": manifest["rows"]},
        {"Measurement": "Unique stored results including 100 warmup events", "Value": manifest["stored_total_unique_rows_including_warmup"]},
        {"Measurement": "Main event rate / second", "Value": manifest["rate"]},
        {"Measurement": "Missing main scores", "Value": manifest["missing_main_scores"]},
        {"Measurement": "Restart to first outage-event result (seconds)", "Value": manifest["restart_to_first_outage_event_result_seconds"]},
        {"Measurement": "Crash to first outage-event result (seconds)", "Value": manifest["crash_to_first_outage_event_result_seconds"]},
        {"Measurement": "Peak sampled checkpoint lag", "Value": manifest["peak_checkpoint_lag"]},
        {"Measurement": "Final checkpoint lag", "Value": manifest["end_checkpoint_lag"]},
        {"Measurement": "Suppressed duplicate deliveries", "Value": manifest["suppressed_duplicate_deliveries"]},
        {"Measurement": "Deliberately injected duplicate deliveries", "Value": 110},
        {"Measurement": "Conflicts flagged, first score preserved", "Value": 1},
        {"Measurement": "Maximum probability difference", "Value": manifest["maximum_probability_error"]},
        {"Measurement": "End-to-end p95, including outage (ms)", "Value": manifest["end_to_end_p95_ms"]},
        {"Measurement": "Sink restart to outbox drained (seconds)", "Value": manifest["sink_restart_to_outbox_drained_seconds"]},
        {"Measurement": "Sink restart to committed Kafka offsets caught up (seconds)", "Value": manifest["sink_restart_to_kafka_offsets_caught_up_seconds"]},
        {"Measurement": "Monitoring documents indexed", "Value": manifest.get("indexed_monitoring_logs", 0)},
    ]))
    transcript = directory / "test_results.txt"
    tests = transcript.read_text().strip().splitlines()[-1] if transcript.exists() else "No regression-test transcript attached."
    report = f'''# Recovery, deduplication and ELK monitoring

Batch `{batch}` completed {manifest['completed_at_utc']}. Status: **passed**.
Regression transcript: `{tests}`.

{table}

## Failure experiment

A warmed Spark query processes historical validation events while a producer
continues at {manifest['rate']} events/second. The test waits for a source offset
file without its matching batch commit, then sends SIGKILL to that test's own
Spark process group. After {manifest['configured_downtime_seconds']} seconds,
Spark restarts from the same checkpoint. The producer was still active throughout
the injected downtime. The checkpoint query ID is preserved; no new checkpoint
or offset reset is used. Every main event's final probability and risk flag is
compared with direct predictions from the unchanged model.

First-result recovery measures the earliest stored result for an event emitted
during the outage, so already-buffered pre-crash results do not count. The
restart measurement includes JVM/connector startup. End-to-end latency uses the
first durable score's reception time and includes the outage. Peak checkpoint
lag is sampled, includes in-flight records and is not a latency SLA.

The test then injects 50 repeated application events, 50 repeated Kafka scores,
and one deliberately conflicting model fingerprint for an existing event ID.
Finally, it stops the store, injects 10 more duplicate scores, and crashes a new
store process with exit 73 immediately after its SQLite commit but before Kafka
offset commit. Restarting the same group/database retries those offsets and
drains the durable log outbox without adding score or delivery-ledger rows twice.
The test then waits for the restarted consumer's committed offsets to reach all
output partition ends. Outbox drainage alone is not treated as consumer recovery.

These are 110 deliberately repeated deliveries, separate from any natural Spark
retry duplicates observed before injection. The intentional conflict is retained
as evidence and triggers monitoring; it does not replace the original score.
This single local experiment does not establish broker failover, disk-loss
recovery, multi-host clock accuracy or distributed database availability.

## Durable deduplication

`scripts/20_store_scores.py` stores scores in SQLite with `event_id` as primary
key and a separate delivery ledger keyed by Kafka topic/partition/offset.
Logical equality includes run ID, original emission time, model fingerprint,
status, probability, flag, validation reason and threshold. Source output offsets
and scoring timestamps may change on retry. An ID reused for a different logical
result is a conflict: the first result stays intact and the conflict is recorded.
Use a new event ID for a changed application/model-scoring request.

The database uses WAL and FULL synchronization. Scores, delivery records and the
monitoring outbox commit in one transaction before Kafka offsets advance. Logs
are flushed from the outbox before it is marked exported. A repeated log export
keeps the same document ID, so Elasticsearch replaces that monitoring document.
SQLite is the authoritative score store. Kafka transport remains at least once;
this is persistent local idempotent storage, not an end-to-end exactly-once claim.
The ledger grows with deliveries and has no automatic retention policy.

## ELK

JSON-lines logs under ignored `models/streaming/logs/` feed Logstash's persistent
file reader and persistent queue. Elasticsearch stores `credit-risk-monitoring-*` with explicit field
types and stable `log_id` document IDs. Kibana has eight panels: stored results,
suppressed duplicates, conflicts, p95 score latency, stored results/minute,
checkpoint lag, average risk score and errors/invalid outputs. Counts of inserted
results exclude suppressed duplicates. Logs omit application features and loan IDs.

Dashboard: **http://127.0.0.1:15601/app/dashboards#/view/credit-risk-streaming**.
The default view includes all retained test batches. To isolate this batch, use:

```text
pipeline_id:"{batch}" or run_id:"{batch}-main" or run_id:"{batch}-warmup" or group_id:"{batch}-store"
```

The stored-result count includes 100 warmup events in addition to the main replay.
Elasticsearch: **http://127.0.0.1:19200**. These local services bind to loopback;
Elasticsearch security is disabled for this local demo. The monitoring services
use pinned Elastic 8.17.3 images, persistent data volumes and reduced heaps for
this machine. Kafka uses persistent ignored `models/streaming/kafka-data/`.
Existing broker data was preserved when adding that mount.

`make monitor-check` runs on-demand checks for conflicts/monitor errors, invalid
outputs, p95 above 10 seconds and latest checkpoint lag above 10,000. Add
`--expect-running` to the script to check for progress older than 30 seconds.
It emits JSON locally; no scheduled alerting, external messages or notifications
are configured. The deliberately injected conflict can produce a warning.
Score distributions are visible; this is not a statistical drift detector.

## Run

```bash
make streaming-setup
make kafka-up
make elk-up

# Separate terminals for normal operation; replay creates the topics.
make replay ARGS="--rows 10000 --rate 200 --run-id demo-unique-id"
make stream
make store-scores

# Automated isolated failure/retry experiment, including ELK verification.
make recovery-test
make monitor-check

# Stop services when finished; data, topics and checkpoints are retained.
make elk-down
make kafka-down
```

Spark Makefile targets select Java 21 at `/usr/lib/jvm/java-21-openjdk-amd64`.
Override `STREAM_JAVA_HOME=/your/java-21` on other machines. The optional runtime
and matching Kafka connector now use Spark 4.1.4. Fault injection reproduced
[SPARK-55271](https://issues.apache.org/jira/browse/SPARK-55271) on 4.1.2;
the patched release was installed before this successful test. Historical smoke
and load measurements retain their 4.1.2 fingerprints and are not restated as
4.1.4 measurements. Core modelling dependencies and the model are unchanged.

![Recovery checkpoint lag](../{manifest['result_directory']}/recovery_lag.png)

MLflow experiment: `lendingclub_streaming_recovery`; run `{manifest['mlflow_run_id']}`.
The replay dataset, metrics, logs and source snapshots are attached.
[Manifest](../assets/results/recovery_latest.json),
[verification](../assets/results/recovery_verification.json), and
[delivery ledger](../{manifest['result_directory']}/deliveries.csv.gz).

<details><summary>All recovery statistics and source fingerprints</summary>

```json
{json.dumps(manifest, indent=2)}
```

</details>

Configuration follows the official [Logstash file input](https://www.elastic.co/guide/en/logstash/8.17/plugins-inputs-file.html)
and [Elasticsearch output](https://www.elastic.co/guide/en/logstash/8.17/plugins-outputs-elasticsearch.html) documentation.
'''
    (ROOT / "docs/recovery_monitoring.md").write_text(report)
    statistics = ROOT / "assets/statistics.md"
    text = statistics.read_text()
    start, end = "<!-- recovery-statistics -->", "<!-- end-recovery-statistics -->"
    section = start + "\n" + report.replace("# Recovery, deduplication and ELK monitoring", "## Latest recovery, deduplication and ELK statistics", 1).replace("../assets/", "") + "\n" + end + "\n\n"
    if start in text:
        before, remaining = text.split(start, 1);_, after = remaining.split(end, 1)
        text = before + section + after.lstrip("\n")
    else:
        position = text.index("<!-- load-test-statistics -->")
        text = text[:position] + section + text[position:]
    statistics.write_text(text)
    with mlflow.start_run(run_id=manifest["mlflow_run_id"]):
        for path in [ROOT / "docs/recovery_monitoring.md", statistics,
                     ROOT / "assets/results/recovery_verification.json", Path(__file__)]:
            mlflow.log_artifact(str(path), artifact_path="verified_report")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
