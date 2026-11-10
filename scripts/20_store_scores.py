"""Consume scored/invalid Kafka outputs into a deduplicated SQLite store."""

import argparse
import json
import os
from pathlib import Path
import sys
import time

from confluent_kafka import Consumer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from util.logging import write_event
from util.score_store import open_store, store_delivery, flush_outbox


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-servers", default="localhost:9092")
    parser.add_argument("--topics", nargs="+", default=["loan-scores", "loan-invalid"])
    parser.add_argument("--group-id", default="loan-score-storage")
    parser.add_argument("--database", type=Path, default=ROOT / "models/streaming/scores.sqlite")
    parser.add_argument("--log-file", type=Path, default=ROOT / "models/streaming/logs/score-store.jsonl")
    parser.add_argument("--ready-file", type=Path)
    parser.add_argument("--stop-file", type=Path)
    parser.add_argument("--crash-after-store", action="store_true", help="Recovery-test fault: exit after DB commit, before Kafka commit.")
    args = parser.parse_args()
    connection = open_store(args.database)
    consumer = Consumer({"bootstrap.servers": args.bootstrap_servers, "group.id": args.group_id,
        "auto.offset.reset": "earliest", "enable.auto.commit": False, "enable.auto.offset.store": False,
        "session.timeout.ms": 10000, "heartbeat.interval.ms": 3000})
    consumer.subscribe(args.topics)
    write_event(args.log_file, "sink_started", component="score_store", group_id=args.group_id)
    if args.ready_file:
        args.ready_file.parent.mkdir(parents=True, exist_ok=True)
        args.ready_file.write_text(args.group_id)
    try:
        while not (args.stop_file and args.stop_file.exists()):
            messages = consumer.consume(500, timeout=.25)
            with connection:
                for message in messages:
                    if message.error():
                        raise RuntimeError(str(message.error()))
                    store_delivery(connection, json.loads(message.value()), message.topic(), message.partition(),
                                   message.offset(), time.time_ns() // 1_000_000)
            if messages and args.crash_after_store:
                os._exit(73)
            # Database and outbox are durable before advancing Kafka consumer offsets.
            flush_outbox(connection, args.log_file)
            for message in messages:
                consumer.store_offsets(message=message)
            if messages:
                consumer.commit(asynchronous=False)
    finally:
        flush_outbox(connection, args.log_file)
        consumer.close()
        connection.close()
        write_event(args.log_file, "sink_stopped", component="score_store", group_id=args.group_id)


if __name__ == "__main__":
    main()
