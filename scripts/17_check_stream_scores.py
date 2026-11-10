"""Verify one finite replay against direct predictions; this is not a load test."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

from confluent_kafka import Consumer, TopicPartition, OFFSET_BEGINNING
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-servers", default="localhost:9092")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--invalid-rows", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.run_id):
        parser.error("Use letters, digits, hyphens or underscores for the run ID.")
    if args.rows < 1 or args.invalid_rows < 0 or args.timeout <= 0:
        parser.error("Use positive rows/timeout and a nonnegative invalid count.")
    consumer = Consumer({"bootstrap.servers": args.bootstrap_servers,
        "group.id": f"verify-{args.run_id}-{time.time_ns()}", "enable.auto.commit": False})
    assignments = []
    for topic in ["loan-scores", "loan-invalid"]:
        metadata = consumer.list_topics(topic, timeout=15).topics[topic]
        if metadata.error:
            raise RuntimeError(str(metadata.error))
        assignments.extend(TopicPartition(topic, partition, OFFSET_BEGINNING) for partition in metadata.partitions)
    consumer.assign(assignments)
    records = []
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        message = consumer.poll(1)
        if message is None:
            continue
        if message.error():
            raise RuntimeError(str(message.error()))
        event = json.loads(message.value())
        if event.get("run_id") == args.run_id:
            event["output_topic"] = message.topic()
            records.append(event)
    consumer.close()
    outputs = pd.DataFrame(records)
    if outputs.empty:
        raise ValueError("No records found for this run ID.")
    duplicates = int(outputs.event_id.duplicated().sum())
    unique = outputs.drop_duplicates("event_id")
    scored = unique[unique.status == "scored"].copy()
    invalid = unique[unique.status == "invalid"]
    assert len(scored) == args.rows and len(invalid) == args.invalid_rows, (len(scored), len(invalid))
    expected_ids = [f"{args.run_id}:{index}" for index in range(args.rows)]
    assert set(scored.event_id) == set(expected_ids)
    scored = scored.set_index("event_id").loc[expected_ids]
    assert scored.output_topic.eq("loan-scores").all()
    assert invalid.output_topic.eq("loan-invalid").all()
    if len(invalid):
        assert invalid.charged_off_probability.isna().all() and invalid.flagged_risk.isna().all()
        assert invalid.validation_error.notna().all()
    reference = json.loads((ROOT / "assets/results/model_experiments_latest.json").read_text())
    frame = pd.read_parquet(ROOT / "data/clean/modeling/validation.parquet", columns=reference["features"]).head(args.rows)
    model_path = ROOT / "models/selected_model.joblib"
    model_sha = hashlib.sha256(model_path.read_bytes()).hexdigest()
    assert model_sha == reference["selected_joblib_sha256"]
    assert unique.model_sha256.eq(model_sha).all()
    model = joblib.load(model_path)
    with threadpool_limits(limits=1):
        direct = model.predict_proba(frame)[:, 1]
    error = float(np.max(np.abs(direct - scored.charged_off_probability.to_numpy())))
    assert error < 1e-12, error
    threshold = float(reference["selected_threshold"])
    np.testing.assert_allclose(scored.threshold, threshold, atol=0, rtol=0)
    assert (scored.flagged_risk.to_numpy() == (direct >= threshold)).all()
    result_dir = ROOT / "assets/results/streaming" / args.run_id
    result_dir.mkdir(parents=True, exist_ok=True)
    outputs.to_csv(result_dir / "output_records.csv", index=False)
    sources = ["scripts/15_replay_loans.py", "scripts/16_stream_score.py", "scripts/17_check_stream_scores.py",
               "util/streaming.py", "docker-compose.yml", "requirements-streaming.txt", "requirements-streaming.lock"]
    proof = {"status": "passed", "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id, "valid_unique_rows": len(scored), "invalid_unique_rows": len(invalid),
        "duplicate_output_records": duplicates, "maximum_probability_error": error,
        "risk_flags_match_direct_predictions": True, "incumbent_sha256": model_sha,
        "threshold": threshold, "stress_test": False,
        "source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources}}
    (result_dir / "verification.json").write_text(json.dumps(proof, indent=2) + "\n")
    progress = ROOT / "assets/results/streaming/last_query_progress.json"
    if progress.exists():
        (result_dir / "query_progress.json").write_text(progress.read_text())
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
