"""Replay prepared loan features as Kafka messages, without outcomes or loan IDs."""

import argparse
import json
from pathlib import Path
import time
import uuid

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-servers", default="localhost:9092")
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--rate", type=float, default=100, help="Messages/second; 0 sends without pacing.")
    parser.add_argument("--run-id", default=uuid.uuid4().hex)
    parser.add_argument("--topic", default="loan-applications")
    parser.add_argument("--output-topic", default="loan-scores")
    parser.add_argument("--invalid-topic", default="loan-invalid")
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--invalid-fixtures", action="store_true", help="Append three invalid schema fixtures.")
    args = parser.parse_args()
    if args.rows < 1 or args.rate < 0:
        parser.error("Use positive rows and a nonnegative rate.")
    admin = AdminClient({"bootstrap.servers": args.bootstrap_servers})
    existing = admin.list_topics(timeout=15).topics
    topics = [args.topic, args.output_topic, args.invalid_topic]
    if len(set(topics)) != 3:
        parser.error("Input, score and invalid topics must be different.")
    new_topics = [NewTopic(t, num_partitions=3, replication_factor=1) for t in topics if t not in existing]
    if new_topics:
        for future in admin.create_topics(new_topics).values():
            future.result()
    manifest = json.loads((ROOT / "assets/results/model_data_manifest.json").read_text())
    frame = pd.read_parquet(ROOT / "data/clean/modeling/validation.parquet", columns=manifest["features"])
    if args.rows > len(frame):
        parser.error(f"This replay supports at most {len(frame)} distinct rows per run.")
    producer = Producer({"bootstrap.servers": args.bootstrap_servers, "enable.idempotence": True,
                         "acks": "all", "linger.ms": 5})
    failures = []
    delivery_times = []

    def delivered(error, message):
        if error:
            failures.append(str(error))
        delivery_times.append(time.time_ns() // 1_000_000)

    records = json.loads(frame.head(args.rows).to_json(orient="records", double_precision=15))
    events = [(str(index), features) for index, features in enumerate(records)]
    if args.invalid_fixtures:
        base = records[0]
        invalid = [dict(base, annual_inc="bad-number"), dict(base, loan_status="Charged Off"),
                   {name: value for name, value in base.items() if name != "fico_mid"}]
        events.extend((f"invalid-{index}", features) for index, features in enumerate(invalid))
    started = time.monotonic()
    first_emitted = time.time_ns() // 1_000_000
    for index, (suffix, features) in enumerate(events):
        if args.rate:
            time.sleep(max(0, started + index / args.rate - time.monotonic()))
        event_id = f"{args.run_id}:{suffix}"
        event = {"event_id": event_id, "run_id": args.run_id,
                 "emitted_at_ms": time.time_ns() // 1_000_000, "features": features}
        producer.produce(args.topic, key=event_id, value=json.dumps(event, allow_nan=False), on_delivery=delivered)
        producer.poll(0)
    remaining = producer.flush(60)
    if remaining or failures:
        raise RuntimeError(f"Undelivered: {remaining}; delivery errors: {failures[:5]}")
    summary = {"run_id": args.run_id, "delivered": len(events),
                      "valid_rows": args.rows, "invalid_fixtures": len(events) - args.rows,
                      "delivery_errors": len(failures), "first_emitted_at_ms": first_emitted,
                      "last_emitted_at_ms": event["emitted_at_ms"],
                      "last_acknowledged_at_ms": max(delivery_times),
                      "elapsed_seconds": time.monotonic() - started}
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
