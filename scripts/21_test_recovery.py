"""Kill Spark under load, resume its checkpoint, and test durable deduplication."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
import uuid

os.environ.setdefault("MPLCONFIGDIR", "/tmp/credit-risk-mpl")
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
import requests
from confluent_kafka import Consumer, Producer, TopicPartition, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from util.logging import write_event
from util.load_test import committed_offsets
from util.score_store import open_store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=6000)
    parser.add_argument("--rate", type=int, default=200)
    parser.add_argument("--downtime", type=float, default=5)
    parser.add_argument("--bootstrap-servers", default="localhost:9092")
    parser.add_argument("--skip-elk", action="store_true")
    args = parser.parse_args()
    if args.rows < 1000 or args.rows > 162570 or args.rate < 1 or args.rows / args.rate < 25 or args.downtime < 1:
        parser.error("Use 1000–162570 rows, positive rate, at least 25 seconds of replay and downtime >=1.")
    if not args.skip_elk:
        requests.get("http://127.0.0.1:19200/_cluster/health", timeout=10).raise_for_status()
        requests.get("http://127.0.0.1:15601/api/status", timeout=60).raise_for_status()
    batch = datetime.now(timezone.utc).strftime("recovery-%Y%m%dT%H%M%S-") + uuid.uuid4().hex[:6]
    result = ROOT / "assets/results/recovery" / batch
    runtime = ROOT / "models/streaming/recovery" / batch
    result.mkdir(parents=True); runtime.mkdir(parents=True)
    logs = ROOT / "models/streaming/logs"
    spark_log, sink_log, test_log = [logs / f"{batch}-{name}.jsonl" for name in ["spark", "sink", "test"]]
    topics = [batch + "-" + name for name in ["input", "scores", "invalid"]]
    admin = AdminClient({"bootstrap.servers": args.bootstrap_servers})
    for future in admin.create_topics([NewTopic(t, num_partitions=3, replication_factor=1) for t in topics], request_timeout=20).values():
        future.result()
    database = runtime / "scores.sqlite"
    connection = open_store(database)
    monitor = Consumer({"bootstrap.servers": args.bootstrap_servers, "group.id": batch + "-monitor", "enable.auto.commit": False})
    store_offsets = Consumer({"bootstrap.servers": args.bootstrap_servers, "group.id": batch + "-store", "enable.auto.commit": False})
    # Topic creation can be acknowledged before partition leaders serve reads.
    ready_deadline = time.monotonic() + 30
    while True:
        try:
            for partition in range(3):
                monitor.get_watermark_offsets(TopicPartition(topics[0], partition), timeout=3)
            break
        except KafkaException:
            if time.monotonic() > ready_deadline:
                raise
            monitor.list_topics(topics[0], timeout=5)
            time.sleep(.2)
    processes, handles, samples = [], [], []
    last_sample = 0
    main_run = batch + "-main"

    def launch(command, name, session=False):
        handle = (result / f"{name}.log").open("w");handles.append(handle)
        process = subprocess.Popen([sys.executable, *command], cwd=ROOT, stdout=handle,
                                   stderr=subprocess.STDOUT, start_new_session=session)
        processes.append(process)
        return process

    def start_spark(name):
        return launch(["scripts/16_stream_score.py", "--bootstrap-servers", args.bootstrap_servers,
            "--input-topic", topics[0], "--output-topic", topics[1], "--invalid-topic", topics[2],
            "--checkpoint", str(runtime / "checkpoint"), "--ready-file", str(runtime / (name + ".ready")),
            "--stop-file", str(runtime / "spark.stop"), "--progress-dir", str(result / name),
            "--pipeline-id", batch, "--log-file", str(spark_log)], name, True)

    def start_sink(name, crash=False):
        return launch(["scripts/20_store_scores.py", "--bootstrap-servers", args.bootstrap_servers,
            "--topics", *topics[1:], "--group-id", batch + "-store", "--database", str(database),
            "--stop-file", str(runtime / "sink.stop"), "--log-file", str(sink_log),
            *( ["--crash-after-store"] if crash else [])], name)

    def count(table, run=None):
        if run:
            return connection.execute(f"SELECT COUNT(*) FROM {table} WHERE run_id=?", (run,)).fetchone()[0]
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def sample():
        nonlocal last_sample
        if time.monotonic() - last_sample < 1:
            return
        progress = [json.loads(p.read_text()) for name in ["spark-before", "spark-after"]
                    for p in sorted((result / name).glob("*.json"))]
        committed = committed_offsets(progress, topics[0])
        end = sum(monitor.get_watermark_offsets(TopicPartition(topics[0], p), timeout=5)[1] for p in range(3))
        row = {"sampled_at_ms": time.time_ns() // 1_000_000, "source_log_end": end,
            "spark_completed_end": sum(committed.values()), "checkpoint_lag": max(0, end - sum(committed.values())),
            "stored_unique_results": count("scores"), "stored_main_results": count("scores", main_run)}
        samples.append(row)
        write_event(test_log, "recovery_sample", component="recovery_test", pipeline_id=batch, **row)
        last_sample = time.monotonic()

    def wait(condition, active, label, timeout=180):
        deadline = time.monotonic() + timeout
        while not condition():
            for process in active:
                if process.poll() is not None:
                    raise RuntimeError(f"{label}: process exited {process.returncode}; inspect {result}")
            if time.monotonic() > deadline:
                raise TimeoutError(label)
            sample();time.sleep(.2)

    def replay(name, rows, rate):
        return launch(["scripts/15_replay_loans.py", "--bootstrap-servers", args.bootstrap_servers,
            "--topic", topics[0], "--output-topic", topics[1], "--invalid-topic", topics[2],
            "--rows", str(rows), "--rate", str(rate), "--run-id", name,
            "--summary", str(result / (name + ".json"))], name)

    def in_flight():
        checkpoint = runtime / "checkpoint"
        offsets = [int(p.name) for p in (checkpoint / "offsets").glob("*") if p.name.isdigit()]
        commits = [int(p.name) for p in (checkpoint / "commits").glob("*") if p.name.isdigit()]
        return max(offsets, default=-1) > max(commits, default=-1)

    def sink_caught_up():
        partitions = [TopicPartition(topic, p) for topic in topics[1:] for p in range(3)]
        positions = store_offsets.committed(partitions, timeout=5)
        return all(max(0, item.offset) == monitor.get_watermark_offsets(item, timeout=5)[1] for item in positions)

    metrics = {"batch_id": batch, "rows": args.rows, "rate": args.rate, "configured_downtime_seconds": args.downtime}
    try:
        sink = start_sink("sink-before")
        spark = start_spark("spark-before")
        wait(lambda: (runtime / "spark-before.ready").exists(), [sink, spark], "Spark ready")
        warmup = replay(batch + "-warmup", 100, 0)
        wait(lambda: warmup.poll() is not None and count("scores") == 100 and samples and samples[-1]["checkpoint_lag"] == 0,
             [sink, spark], "Warmup drain")
        assert warmup.returncode == 0
        producer = replay(main_run, args.rows, args.rate)
        wait(lambda: count("scores", main_run) >= 100 and in_flight(), [sink, spark], "Active batch before crash")
        assert producer.poll() is None, "Producer finished before fault injection"
        killed_at = time.time_ns() // 1_000_000
        metrics["spark_killed_at_ms"] = killed_at
        metrics["main_results_before_crash"] = count("scores", main_run)
        metrics["crashed_with_uncommitted_batch"] = True
        os.killpg(spark.pid, signal.SIGKILL)
        spark.wait(timeout=15)
        print(json.dumps({"phase": "spark_killed_during_uncommitted_batch", "stored_main_results": metrics["main_results_before_crash"]}), flush=True)
        metrics["spark_exit_code"] = spark.returncode
        write_event(test_log, "spark_crash_injected", component="recovery_test", pipeline_id=batch)
        until = time.monotonic() + args.downtime
        while time.monotonic() < until:
            sample();time.sleep(.2)
        metrics["producer_active_after_downtime"] = producer.poll() is None
        assert metrics["producer_active_after_downtime"]
        restarted_at = time.time_ns() // 1_000_000
        metrics["spark_restart_launched_at_ms"] = restarted_at
        spark = start_spark("spark-after")
        wait(lambda: (runtime / "spark-after.ready").exists(), [sink, spark], "Restart ready")
        wait(lambda: producer.poll() is not None and count("scores", main_run) == args.rows and samples[-1]["checkpoint_lag"] == 0,
             [sink, spark], "Recovery drain")
        assert producer.returncode == 0
        print(json.dumps({"phase": "spark_recovered", "stored_main_results": count("scores", main_run)}), flush=True)
        metrics["natural_duplicate_deliveries_before_injection"] = connection.execute("SELECT COUNT(*) FROM deliveries WHERE outcome='duplicate'").fetchone()[0]
        first_after = connection.execute("SELECT MIN(first_received_at_ms) FROM scores WHERE run_id=? AND json_extract(payload_json,'$.emitted_at_ms')>=? AND first_received_at_ms>=?",
                                         (main_run, killed_at, restarted_at)).fetchone()[0]
        metrics["restart_to_first_outage_event_result_seconds"] = (first_after - restarted_at) / 1000
        metrics["crash_to_first_outage_event_result_seconds"] = (first_after - killed_at) / 1000
        stored = pd.read_sql_query("SELECT * FROM scores", connection)
        main = stored[stored.run_id == main_run].copy()
        main["index"] = main.event_id.str.rsplit(":", n=1).str[-1].astype(int)
        main = main.sort_values("index")
        reference = json.loads((ROOT / "assets/results/model_experiments_latest.json").read_text())
        inputs = pd.read_parquet(ROOT / "data/clean/modeling/validation.parquet", columns=reference["features"]).head(args.rows)
        model = joblib.load(ROOT / "models/selected_model.joblib")
        with threadpool_limits(limits=1):
            direct = model.predict_proba(inputs)[:, 1]
        payloads = [json.loads(value) for value in main.payload_json]
        metrics["maximum_probability_error"] = float(np.max(np.abs(direct - np.array([p["charged_off_probability"] for p in payloads]))))
        assert metrics["maximum_probability_error"] < 1e-12
        assert all(p["flagged_risk"] == bool(value >= reference["selected_threshold"]) for p, value in zip(payloads, direct))
        metrics["checkpoint_query_id_preserved"] = (runtime / "spark-before.ready").read_text() == (runtime / "spark-after.ready").read_text()
        assert metrics["checkpoint_query_id_preserved"]
        output = Producer({"bootstrap.servers": args.bootstrap_servers, "enable.idempotence": True})
        first_features = json.loads(inputs.head(50).to_json(orient="records", double_precision=15))
        for index, fields in enumerate(first_features):
            event = {"event_id": payloads[index]["event_id"], "run_id": main_run,
                     "emitted_at_ms": payloads[index]["emitted_at_ms"], "features": fields}
            output.produce(topics[0], key=event["event_id"], value=json.dumps(event, allow_nan=False))
            output.produce(topics[1], key=event["event_id"], value=json.dumps(payloads[index], allow_nan=False))
        conflict = dict(payloads[0], model_sha256="deliberate-conflict-fixture")
        output.produce(topics[1], key=conflict["event_id"], value=json.dumps(conflict, allow_nan=False))
        assert output.flush(30) == 0
        base_deliveries = args.rows + 100 + metrics["natural_duplicate_deliveries_before_injection"]
        wait(lambda: count("deliveries") >= base_deliveries + 101 and count("conflicts") == 1 and samples[-1]["checkpoint_lag"] == 0,
             [sink, spark], "Duplicate and conflict fixtures")
        (runtime / "sink.stop").touch();sink.wait(timeout=20)
        assert sink.returncode == 0
        (runtime / "sink.stop").unlink()
        for event in payloads[:10]:
            output.produce(topics[1], key=event["event_id"], value=json.dumps(event, allow_nan=False))
        assert output.flush(30) == 0
        crashing_sink = start_sink("sink-crash-window", crash=True)
        crashing_sink.wait(timeout=45)
        assert crashing_sink.returncode == 73
        metrics["sink_crashed_after_sqlite_commit_before_kafka_commit"] = True
        deliveries_before_restart = count("deliveries")
        pending = connection.execute("SELECT COUNT(*) FROM log_outbox WHERE exported=0").fetchone()[0]
        assert pending >= 10
        sink_restarted = time.monotonic()
        sink = start_sink("sink-after")
        wait(lambda: connection.execute("SELECT COUNT(*) FROM log_outbox WHERE exported=0").fetchone()[0] == 0,
             [sink, spark], "Sink outbox recovery", timeout=60)
        metrics["sink_restart_to_outbox_drained_seconds"] = time.monotonic() - sink_restarted
        wait(sink_caught_up, [sink, spark], "Sink retried offsets committed", timeout=60)
        metrics["sink_restart_to_kafka_offsets_caught_up_seconds"] = time.monotonic() - sink_restarted
        time.sleep(2)
        assert count("deliveries") == deliveries_before_restart
        assert count("scores") == args.rows + 100
        print(json.dumps({"phase": "sink_recovered_after_database_commit", "ledger_rows": count("deliveries")}), flush=True)
        metrics["stored_main_unique_rows"] = count("scores", main_run)
        metrics["stored_total_unique_rows_including_warmup"] = count("scores")
        metrics["stored_delivery_rows"] = count("deliveries")
        metrics["suppressed_duplicate_deliveries"] = connection.execute("SELECT COUNT(*) FROM deliveries WHERE outcome='duplicate'").fetchone()[0]
        metrics["deliberately_injected_duplicate_deliveries"] = 110
        metrics["conflicts_flagged_without_overwrite"] = count("conflicts")
        metrics["sqlite_outbox_pending_after_restart"] = 0
        metrics["sink_retry_did_not_duplicate_delivery_ledger"] = True
        metrics["missing_main_scores"] = args.rows - count("scores", main_run)
        metrics["end_checkpoint_lag"] = samples[-1]["checkpoint_lag"]
        assert metrics["suppressed_duplicate_deliveries"] >= 110
        assert metrics["conflicts_flagged_without_overwrite"] == 1 and metrics["missing_main_scores"] == 0
        assert metrics["end_checkpoint_lag"] == 0
        metrics["peak_checkpoint_lag"] = max(row["checkpoint_lag"] for row in samples)
        main["end_to_end_latency_ms"] = main.first_received_at_ms.to_numpy() - np.array([p["emitted_at_ms"] for p in payloads])
        for percentile in [50, 95, 99]:
            metrics[f"end_to_end_p{percentile}_ms"] = float(np.percentile(main.end_to_end_latency_ms, percentile))
        last_ack = json.loads((result / (main_run + ".json")).read_text())["last_acknowledged_at_ms"]
        metrics["drain_after_last_producer_ack_seconds"] = max(0, (main.first_received_at_ms.max() - last_ack) / 1000)
        main.drop(columns="payload_json").to_csv(result / "stored_main_scores.csv", index=False)
        pd.read_sql_query("SELECT * FROM deliveries", connection).to_csv(result / "deliveries.csv.gz", index=False)
        pd.read_sql_query("SELECT * FROM conflicts", connection).to_csv(result / "conflicts.csv", index=False)
    finally:
        (runtime / "spark.stop").touch();(runtime / "sink.stop").touch()
        for process in processes:
            if process.poll() is None:
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.terminate();process.wait(timeout=15)
        monitor.close();store_offsets.close();connection.close()
        for handle in handles:
            handle.close()
    pd.DataFrame(samples).to_csv(result / "backlog.csv", index=False)
    expected_log_ids = set()
    for path in [spark_log, sink_log, test_log]:
        contents = path.read_text();(result / path.name).write_text(contents)
        expected_log_ids.update(json.loads(line)["log_id"] for line in contents.splitlines())
    metrics["elk_verified"] = False
    (result / "functional_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    if not args.skip_elk:
        deadline = time.monotonic() + 90
        while True:
            requests.post("http://127.0.0.1:19200/credit-risk-monitoring-*/_refresh", timeout=10).raise_for_status()
            query = {"size": 10000, "sort": [{"log_id": "asc"}],
                "query": {"bool": {"should": [{"term": {"pipeline_id": batch}}, {"term": {"run_id": main_run}},
                    {"term": {"run_id": batch + "-warmup"}}, {"term": {"group_id": batch + "-store"}}], "minimum_should_match": 1}}, "track_total_hits": True}
            indexed = set()
            while True:
                response = requests.post("http://127.0.0.1:19200/credit-risk-monitoring-*/_search", json=query, timeout=30)
                response.raise_for_status();page = response.json()
                if not indexed:
                    documents = page
                hits = page["hits"]["hits"]
                indexed.update(hit["_source"]["log_id"] for hit in hits)
                if len(hits) < 10000:
                    break
                query["search_after"] = hits[-1]["sort"]
            if expected_log_ids <= indexed:
                break
            if time.monotonic() > deadline:
                raise TimeoutError(f"ELK did not index {len(expected_log_ids - indexed)} expected records")
            time.sleep(1)
        metrics["expected_unique_monitoring_logs"] = len(expected_log_ids)
        metrics["indexed_monitoring_logs"] = documents["hits"]["total"]["value"]
        assert metrics["indexed_monitoring_logs"] == len(expected_log_ids)
        metrics["elk_verified"] = True
        (result / "elasticsearch_evidence.json").write_text(json.dumps({"total": documents["hits"]["total"],
            "sample_documents": documents["hits"]["hits"][:20]}, indent=2) + "\n")
    sources = ["scripts/15_replay_loans.py", "scripts/16_stream_score.py", "scripts/20_store_scores.py",
        "scripts/21_test_recovery.py", "scripts/22_setup_elk.py", "util/score_store.py", "util/logging.py",
        "util/streaming.py", "util/elk/logstash.conf", "util/elk/dashboard.ndjson", "docker-compose.yml", "requirements-streaming.lock"]
    metrics.update(status="passed", completed_at_utc=datetime.now(timezone.utc).isoformat(),
        result_directory=str(result.relative_to(ROOT)), database=str(database.relative_to(ROOT)),
        model_sha256=hashlib.sha256((ROOT / "models/selected_model.joblib").read_bytes()).hexdigest(),
        validation_parquet_sha256=hashlib.sha256((ROOT / "data/clean/modeling/validation.parquet").read_bytes()).hexdigest(),
        versions={name: importlib.metadata.version(name) for name in ["pyspark", "confluent-kafka", "scikit-learn", "numpy", "pandas"]},
        source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources})
    fig, ax = plt.subplots(figsize=(9, 4))
    sample_frame = pd.DataFrame(samples)
    ax.plot((sample_frame.sampled_at_ms - killed_at) / 1000, sample_frame.checkpoint_lag)
    ax.axvline(0, color="red", linestyle="--", label="Spark killed")
    ax.axvline((restarted_at-killed_at)/1000, color="green", linestyle="--", label="Restart launched")
    ax.set(xlabel="Seconds relative to Spark crash", ylabel="Input end minus Spark completed offsets", title="Recovery under active load")
    ax.legend();fig.tight_layout()
    for extension in ["png", "svg"]:
        fig.savefig(result / ("recovery_lag." + extension), dpi=160)
    plt.close(fig)
    mlflow.set_tracking_uri("sqlite:///" + str(ROOT / "models/mlflow.db"))
    mlflow.set_experiment("lendingclub_streaming_recovery")
    with mlflow.start_run(run_name=batch) as run:
        metrics["mlflow_run_id"] = run.info.run_id
        mlflow.log_params({"rows": args.rows, "rate": args.rate, "downtime_seconds": args.downtime,
            "model_sha256": metrics["model_sha256"], "spark_failure": "SIGKILL of owned process group",
            "sink_failure": "exit 73 after SQLite commit before Kafka commit"})
        mlflow.log_metrics({key: float(value) for key,value in metrics.items() if isinstance(value,(int,float))})
        mlflow.log_input(mlflow.data.from_pandas(inputs, source=str(ROOT / "data/clean/modeling/validation.parquet"),
            name="recovery_replay_features"), context="recovery_replay")
        (result / "manifest.json").write_text(json.dumps(metrics, indent=2) + "\n")
        (ROOT / "assets/results/recovery_latest.json").write_text(json.dumps(metrics, indent=2) + "\n")
        mlflow.log_artifacts(str(result), artifact_path="evidence")
        for path in sources:
            mlflow.log_artifact(str(ROOT / path), artifact_path="source")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
