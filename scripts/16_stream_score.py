"""Kafka -> PySpark validation and distributed scoring -> Kafka output topics."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-servers", default="localhost:9092")
    parser.add_argument("--input-topic", default="loan-applications")
    parser.add_argument("--output-topic", default="loan-scores")
    parser.add_argument("--invalid-topic", default="loan-invalid")
    parser.add_argument("--progress-dir", type=Path)
    parser.add_argument("--ready-file", type=Path)
    parser.add_argument("--stop-file", type=Path)
    parser.add_argument("--pipeline-id", default="loan-scoring")
    parser.add_argument("--log-file", type=Path, default=ROOT / "models/streaming/logs/spark.jsonl")
    parser.add_argument("--master", default="local[2]")
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "data/clean/streaming/checkpoint")
    parser.add_argument("--max-offsets", type=int, default=10000)
    parser.add_argument("--available-now", action="store_true", help="Drain existing records and exit.")
    args = parser.parse_args()
    if args.max_offsets < 1:
        parser.error("max-offsets must be positive.")
    if len({args.input_topic, args.output_topic, args.invalid_topic}) != 3:
        parser.error("Input, score and invalid topics must be different.")
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    from pyspark.sql import SparkSession
    from util.feature_policy import validate_features
    from util.streaming import prepare_events
    from util.logging import write_event
    from util.load_test import committed_offsets
    from confluent_kafka import Consumer, TopicPartition, KafkaException

    data = json.loads((ROOT / "assets/results/model_data_manifest.json").read_text())
    reference = json.loads((ROOT / "assets/results/model_experiments_latest.json").read_text())
    features, numeric, categorical = data["features"], data["numeric_features"], data["categorical_features"]
    validate_features(features)
    model_path = ROOT / "models/selected_model.joblib"
    model_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    if model_hash != reference["selected_joblib_sha256"]:
        raise ValueError("Incumbent model hash does not match its training manifest.")
    import pandas as pd
    metrics = pd.read_csv(ROOT / reference["result_directory"] / "selected_model_metrics.csv")
    threshold = float(metrics[(metrics.split == "validation") & (metrics.policy == "validation_f1")].iloc[0].threshold)
    contract = {"model_sha256": model_hash, "features": features, "threshold": threshold,
                "bootstrap_servers": args.bootstrap_servers, "input_topic": args.input_topic,
                "output_topic": args.output_topic, "invalid_topic": args.invalid_topic}
    args.checkpoint.mkdir(parents=True, exist_ok=True)
    contract_path = args.checkpoint / "scoring_contract.json"
    if contract_path.exists():
        previous = json.loads(contract_path.read_text())
        previous.setdefault("output_topic", "loan-scores")
        previous.setdefault("invalid_topic", "loan-invalid")
        if previous != contract:
            raise ValueError("Checkpoint belongs to another scoring contract. Use a new checkpoint directory.")
    contract_path.write_text(json.dumps(contract, indent=2) + "\n")
    spark = (SparkSession.builder.appName("lendingclub-stream-scoring").master(args.master)
             .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.13:4.1.4")
             .config("spark.jars.ivy", str(ROOT / "models/streaming/ivy"))
             .config("spark.sql.warehouse.dir", str(ROOT / "models/streaming/warehouse"))
             .config("spark.sql.shuffle.partitions", "3")
             .config("spark.sql.execution.arrow.maxRecordsPerBatch", "1000").getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    spark.sparkContext.addFile(str(model_path))
    source = (spark.readStream.format("kafka").option("kafka.bootstrap.servers", args.bootstrap_servers)
              .option("subscribe", args.input_topic).option("startingOffsets", "earliest")
              .option("maxOffsetsPerTrigger", args.max_offsets).option("failOnDataLoss", "true").load())
    prepared = prepare_events(source, features, numeric, categorical)
    output_topic, invalid_topic = args.output_topic, args.invalid_topic

    def score_batches(batches):
        import json
        import time
        import joblib
        import numpy as np
        import pandas as pd
        from pyspark import SparkFiles
        from threadpoolctl import threadpool_limits

        model = joblib.load(SparkFiles.get("selected_model.joblib"))
        for batch in batches:
            valid = batch.validation_error.eq("")
            probabilities = np.full(len(batch), np.nan)
            inputs = batch.loc[valid, features].copy()
            for name in categorical:
                inputs[name] = inputs[name].where(inputs[name].notna(), np.nan)
            if valid.any():
                with threadpool_limits(limits=1):
                    probabilities[valid.to_numpy()] = model.predict_proba(inputs)[:, 1]
            scored_at = time.time_ns() // 1_000_000
            rows = []
            for index, (_, row) in enumerate(batch.iterrows()):
                okay = bool(valid.iloc[index])
                event_id = row.event_id if pd.notna(row.event_id) else f"{row.topic}:{row.partition}:{row.offset}"
                payload = {"event_id": event_id, "run_id": row.run_id if pd.notna(row.run_id) else None,
                    "source_topic": row.topic, "source_partition": int(row.partition), "source_offset": int(row.offset),
                    "model_sha256": model_hash, "scored_at_ms": scored_at,
                    "emitted_at_ms": int(row.emitted_at_ms) if pd.notna(row.emitted_at_ms) else None,
                    "status": "scored" if okay else "invalid", "validation_error": row.validation_error or None,
                    "charged_off_probability": float(probabilities[index]) if okay else None,
                    "flagged_risk": bool(probabilities[index] >= threshold) if okay else None,
                    "threshold": threshold}
                rows.append((event_id, json.dumps(payload, allow_nan=False), output_topic if okay else invalid_topic))
            yield pd.DataFrame(rows, columns=["key", "value", "topic"])

    scored = prepared.mapInPandas(score_batches, schema="key string, value string, topic string")
    writer = (scored.writeStream.format("kafka").option("kafka.bootstrap.servers", args.bootstrap_servers)
              .option("checkpointLocation", str(args.checkpoint.resolve())))
    writer = writer.trigger(availableNow=True) if args.available_now else writer.trigger(processingTime="2 seconds")
    query = writer.start()
    monitor = Consumer({"bootstrap.servers": args.bootstrap_servers, "group.id": "monitor-" + str(query.id),
                        "enable.auto.commit": False})
    write_event(args.log_file, "query_started", component="spark", pipeline_id=args.pipeline_id,
                query_id=str(query.id), process_id=os.getpid(), model_sha256=model_hash)
    if args.ready_file:
        args.ready_file.parent.mkdir(parents=True, exist_ok=True)
        args.ready_file.write_text(str(query.id))
    saved = set()
    try:
        while True:
            finished = query.awaitTermination(1)
            for item in query.recentProgress:
                progress = json.loads(item.json)
                key = (progress["runId"], progress["batchId"], progress["timestamp"])
                if key not in saved:
                    if args.progress_dir:
                        args.progress_dir.mkdir(parents=True, exist_ok=True)
                        name = f"{len(saved):06d}.json"
                        temporary = args.progress_dir / (name + ".tmp")
                        temporary.write_text(json.dumps(progress, indent=2) + "\n")
                        temporary.replace(args.progress_dir / name)
                    completed = committed_offsets([progress], args.input_topic)
                    lag = None
                    try:
                        lag = sum(max(0, monitor.get_watermark_offsets(TopicPartition(args.input_topic, int(p)), timeout=3)[1] - end)
                                  for p, end in completed.items())
                    except KafkaException as error:
                        write_event(args.log_file, "monitor_error", component="spark", pipeline_id=args.pipeline_id,
                                    message=str(error))
                    write_event(args.log_file, "spark_progress", component="spark", pipeline_id=args.pipeline_id,
                        log_id=f"spark:{progress['id']}:{progress['runId']}:{progress['batchId']}:{progress['timestamp']}",
                        query_id=str(query.id), checkpoint_lag=lag, input_rows=progress["numInputRows"],
                        batch_duration_ms=progress.get("durationMs", {}).get("triggerExecution", 0),
                        input_rows_per_second=progress.get("inputRowsPerSecond", 0),
                        processed_rows_per_second=progress.get("processedRowsPerSecond", 0))
                    saved.add(key)
            if finished or (args.stop_file and args.stop_file.exists()):
                break
    finally:
        if query.isActive:
            query.stop()
        monitor.close()
        write_event(args.log_file, "query_stopped", component="spark", pipeline_id=args.pipeline_id, query_id=str(query.id))
    progress_dir = ROOT / "assets/results/streaming"
    progress_dir.mkdir(parents=True, exist_ok=True)
    progress = [json.loads(item.json) for item in query.recentProgress]
    (progress_dir / "last_query_progress.json").write_text(json.dumps(progress, indent=2) + "\n")
    spark.stop()


if __name__ == "__main__":
    main()
