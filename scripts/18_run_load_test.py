"""Run isolated, paced Kafka/Spark load stages and retain measured evidence."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
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
from confluent_kafka import Consumer, TopicPartition, OFFSET_BEGINNING
from confluent_kafka.admin import AdminClient, NewTopic
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from util.risk_scope import log_risk_scope
from util.load_test import summarize_stage, committed_offsets


def progress_rows(directory):
    return [json.loads(path.read_text()) for path in sorted(directory.glob("*.json"))]


def run_stage(name, rate, rows, consumer, spark, args, topics, directory, cumulative):
    stage_dir = directory / name
    stage_dir.mkdir()
    run_id = f"{directory.name}-{name}"
    command = [sys.executable, str(ROOT / "scripts/15_replay_loans.py"),
        "--bootstrap-servers", args.bootstrap_servers, "--topic", topics[0],
        "--output-topic", topics[1], "--invalid-topic", topics[2],
        "--rows", str(rows), "--rate", str(rate), "--run-id", run_id,
        "--summary", str(stage_dir / "producer.json")]
    records, backlog = [], []
    seen = set()
    started = time.monotonic()
    next_sample = started
    producer_finished = None
    with (stage_dir / "producer.log").open("w") as log:
        producer = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        try:
            while True:
                if spark.poll() is not None:
                    raise RuntimeError(f"Spark exited: {spark.returncode}. See spark.log.")
                for message in consumer.consume(num_messages=1000, timeout=.1):
                    received = time.time_ns() // 1_000_000
                    if message.error():
                        raise RuntimeError(str(message.error()))
                    event = json.loads(message.value())
                    if event.get("run_id") != run_id:
                        continue
                    event.update(received_at_ms=received, output_topic=message.topic())
                    records.append(event)
                    seen.add(event["event_id"])
                now = time.monotonic()
                if now >= next_sample:
                    committed = committed_offsets(progress_rows(directory / "progress"), topics[0])
                    ends = {str(p): consumer.get_watermark_offsets(TopicPartition(topics[0], p), timeout=5)[1]
                            for p in range(3)}
                    backlog.append({"sampled_at_ms": time.time_ns() // 1_000_000,
                        "source_log_end": sum(ends.values()), "spark_completed_end": sum(committed.values()),
                        "checkpoint_lag": sum(max(0, end - committed.get(p, 0)) for p, end in ends.items()),
                        "unique_outputs_received": len(seen)})
                    next_sample = now + 1
                if producer.poll() is not None:
                    if producer.returncode != 0:
                        raise RuntimeError(f"Replay failed; see {stage_dir / 'producer.log'}")
                    if producer_finished is None:
                        producer_finished = now
                    if len(seen) >= rows and backlog[-1]["spark_completed_end"] >= cumulative + rows:
                        break
                    if now - producer_finished > args.drain_timeout:
                        break
                if now - started > args.duration + args.drain_timeout + 120:
                    raise TimeoutError("Replay exceeded the overall stage deadline.")
        finally:
            if producer.poll() is None:
                producer.terminate()
                producer.wait(timeout=15)
    # Read briefly after drain so late duplicate outputs are included.
    until = time.monotonic() + 2
    while time.monotonic() < until:
        for message in consumer.consume(1000, timeout=.1):
            if message.error():
                raise RuntimeError(str(message.error()))
            event = json.loads(message.value())
            if event.get("run_id") == run_id:
                event.update(received_at_ms=time.time_ns() // 1_000_000, output_topic=message.topic())
                records.append(event)
    production = json.loads((stage_dir / "producer.json").read_text())
    result = summarize_stage(records, production, rows, backlog)
    result.update(stage=name, run_id=run_id, target_rows_per_second=rate,
                  configured_duration_seconds=args.duration, end_checkpoint_lag=backlog[-1]["checkpoint_lag"])
    outputs = pd.DataFrame(records)
    if outputs.empty:
        outputs = pd.DataFrame(columns=["event_id", "status", "charged_off_probability", "flagged_risk", "model_sha256", "output_topic"])
    outputs.to_csv(stage_dir / "output_records.csv.gz", index=False, compression="gzip")
    pd.DataFrame(backlog).to_csv(stage_dir / "backlog.csv", index=False)
    # Every ID must be expected; verify all delivered probabilities against the frozen model.
    reference = json.loads((ROOT / "assets/results/model_experiments_latest.json").read_text())
    expected_ids = [f"{run_id}:{index}" for index in range(rows)]
    assert set(outputs.event_id) <= set(expected_ids)
    unique = outputs.drop_duplicates("event_id").set_index("event_id")
    valid = unique[unique.status == "scored"]
    positions = [int(value.rsplit(":", 1)[1]) for value in valid.index]
    inputs = pd.read_parquet(ROOT / "data/clean/modeling/validation.parquet", columns=reference["features"]).iloc[positions]
    model = joblib.load(ROOT / "models/selected_model.joblib")
    with threadpool_limits(limits=1):
        direct = model.predict_proba(inputs)[:, 1] if len(inputs) else np.array([])
    error = float(np.max(np.abs(direct - valid.charged_off_probability.to_numpy()))) if len(valid) else None
    result["maximum_probability_error"] = error
    result["probabilities_match"] = bool(error is not None and error < 1e-12)
    result["risk_flags_match"] = bool((valid.flagged_risk.to_numpy() == (direct >= reference["selected_threshold"])).all())
    result["model_hashes_match"] = bool(unique.model_sha256.eq(reference["selected_joblib_sha256"]).all())
    result["expected_output_topics"] = bool(valid.output_topic.eq(topics[1]).all())
    (stage_dir / "metrics.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-servers", default="localhost:9092")
    parser.add_argument("--rates", nargs="+", type=int, default=[100, 500, 2000])
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--drain-timeout", type=int, default=120)
    args = parser.parse_args()
    if args.duration < 5 or args.drain_timeout < 1 or any(rate < 1 for rate in args.rates):
        parser.error("Use duration >=5, positive rates and positive drain timeout.")
    manifest = json.loads((ROOT / "assets/results/model_data_manifest.json").read_text())
    validation_rows = next(item["rows"] for item in manifest["artifacts"]
                           if item["split"] == "validation" and item["kind"] == "features_and_target")
    if max(args.rates) * args.duration > validation_rows:
        parser.error("Each stage must fit within the distinct validation rows.")
    batch = datetime.now(timezone.utc).strftime("load-%Y%m%dT%H%M%S-") + uuid.uuid4().hex[:6]
    directory = ROOT / "assets/results/load_test" / batch
    directory.mkdir(parents=True)
    runtime = ROOT / "models/streaming/load_tests" / batch
    runtime.mkdir(parents=True)
    topics = [f"{batch}-{suffix}" for suffix in ["input", "scores", "invalid"]]
    admin = AdminClient({"bootstrap.servers": args.bootstrap_servers})
    for future in admin.create_topics([NewTopic(t, num_partitions=3, replication_factor=1) for t in topics]).values():
        future.result()
    consumer = Consumer({"bootstrap.servers": args.bootstrap_servers, "group.id": batch,
                         "enable.auto.commit": False})
    consumer.assign([TopicPartition(topic, p, OFFSET_BEGINNING) for topic in topics[1:] for p in range(3)])
    stop = runtime / "stop"
    command = [sys.executable, str(ROOT / "scripts/16_stream_score.py"),
        "--bootstrap-servers", args.bootstrap_servers, "--input-topic", topics[0],
        "--output-topic", topics[1], "--invalid-topic", topics[2],
        "--checkpoint", str(runtime / "checkpoint"), "--ready-file", str(runtime / "ready"),
        "--stop-file", str(stop), "--progress-dir", str(directory / "progress")]
    stages = []
    with (directory / "spark.log").open("w") as log:
        spark = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 180
            while not (runtime / "ready").exists():
                if spark.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError(f"Spark did not start; see {directory / 'spark.log'}")
                time.sleep(.5)
            warmup = run_stage("warmup", 100, 100, consumer, spark, args, topics, directory, 0)
            if not warmup["counts_reconciled"]:
                raise RuntimeError("Warmup did not reconcile; inspect its saved evidence.")
            cumulative = 100
            for index, rate in enumerate(args.rates):
                rows = rate * args.duration
                result = run_stage(f"stage-{index+1}-{rate}rps", rate, rows, consumer, spark, args, topics, directory, cumulative)
                stages.append(result)
                cumulative += rows
                if not result["counts_reconciled"]:
                    break
        finally:
            stop.touch()
            try:
                spark.wait(timeout=30)
            except subprocess.TimeoutExpired:
                spark.terminate()
                spark.wait(timeout=15)
            consumer.close()
    if spark.returncode != 0:
        raise RuntimeError(f"Spark shutdown failed; see {directory / 'spark.log'}")
    results = pd.DataFrame(stages)
    results.to_csv(directory / "stage_metrics.csv", index=False)
    sources = ["scripts/15_replay_loans.py", "scripts/16_stream_score.py", "scripts/18_run_load_test.py",
        "util/streaming.py", "util/load_test.py", "docker-compose.yml", "requirements-streaming.lock"]
    docker = json.loads(subprocess.check_output(["docker", "info", "--format", '{"cpus":{{.NCPU}},"memory_bytes":{{.MemTotal}}}']))
    java = subprocess.run([str(Path(os.environ["JAVA_HOME"]) / "bin/java"), "-version"],capture_output=True,text=True,check=True).stderr
    model_sha = hashlib.sha256((ROOT / "models/selected_model.joblib").read_bytes()).hexdigest()
    output = {"batch_id": batch, "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if len(stages)==len(args.rates) and all(s["counts_reconciled"] and s["probabilities_match"] and s["risk_flags_match"] and s["model_hashes_match"] for s in stages) else "incomplete",
        "rates": args.rates, "duration_seconds_per_stage": args.duration, "warmup_rows": 100,
        "topics": topics, "result_directory": str(directory.relative_to(ROOT)),
        "model_sha256": model_sha, "python": platform.python_version(), "platform": platform.platform(),
        "logical_cpus": os.cpu_count(), "docker_resources": docker, "java": java,
        "host_memory_kib": int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:'))),
        "cpu_model": next(line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),
        "versions": {p:importlib.metadata.version(p) for p in ["pyspark","confluent-kafka","pandas","numpy","scikit-learn"]},
        "spark": {"master":"local[2]","trigger_seconds":2,"max_offsets_per_trigger":10000,"arrow_batch_rows":1000,"topic_partitions":3,"model_threads_per_worker":1},
        "source_sha256": {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
        "validation_parquet_sha256": hashlib.sha256((ROOT/'data/clean/modeling/validation.parquet').read_bytes()).hexdigest(),
        "failure_injection_tested":False,"elk_monitoring_implemented":False,
        "latency_boundary":"producer emission to collector receipt of Kafka output; same-host wall clocks",
        "lag_definition":"sampled Kafka input end offsets minus Spark completed progress end offsets; includes in-flight batch",
        "limits":"One warmed run per rate, 30-second defaults, shared local machine, repeated validation cohort across stages; not a production capacity guarantee."}
    plot_results(results, directory)
    mlflow.set_tracking_uri("sqlite:///"+str(ROOT/'models/mlflow.db'))
    mlflow.set_experiment("lendingclub_streaming_load_tests")
    with mlflow.start_run(run_name=batch) as parent:
        log_risk_scope()
        output["mlflow_run_id"] = parent.info.run_id
        mlflow.log_params({"duration_seconds":args.duration,"rates":str(args.rates),"model_sha256":model_sha,"spark_master":"local[2]","failure_injection":False})
        for stage in stages:
            with mlflow.start_run(run_name=stage["stage"],nested=True):
                log_risk_scope()
                mlflow.log_params({"target_rows_per_second":stage["target_rows_per_second"],"expected_rows":stage["expected_rows"]})
                mlflow.log_metrics({key:float(value) for key,value in stage.items() if isinstance(value,(int,float)) and value is not None and np.isfinite(value)})
                mlflow.log_artifacts(str(directory/stage["stage"]))
        (directory/"manifest.json").write_text(json.dumps(output,indent=2)+"\n")
        (ROOT/'assets/results/load_test_latest.json').write_text(json.dumps(output,indent=2)+"\n")
        mlflow.log_artifacts(str(directory),artifact_path="evidence")
        for path in sources:
            mlflow.log_artifact(str(ROOT/path),artifact_path="source")
    print(json.dumps(output,indent=2),flush=True)


def plot_results(results, directory):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].plot(results.target_rows_per_second, results.completed_rows_per_second, "o-", label="Including drain")
    axes[0].plot(results.target_rows_per_second, results.actual_emission_rows_per_second, "o--", label="Actual emission")
    axes[0].set(xlabel="Target input (messages/s)", ylabel="Messages/s", title="Emission and completion rates")
    axes[0].legend()
    for p in [50,95,99]:
        axes[1].plot(results.target_rows_per_second,results[f"end_to_end_p{p}_ms"]/1000,"o-",label=f"p{p}")
    axes[1].set(xlabel="Target input (messages/s)",ylabel="Latency (seconds)",title="Emission to Kafka output receipt")
    axes[1].legend();fig.tight_layout()
    for extension in ["png","svg"]:
        fig.savefig(directory/f"load_results.{extension}",dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
