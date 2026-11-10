"""Durable score deduplication and a transactional monitoring outbox."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3


def open_store(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS scores (
            event_id TEXT PRIMARY KEY, run_id TEXT, logical_sha256 TEXT NOT NULL,
            payload_json TEXT NOT NULL, first_received_at_ms INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS deliveries (
            delivery_id TEXT PRIMARY KEY, event_id TEXT NOT NULL, outcome TEXT NOT NULL,
            received_at_ms INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS conflicts (
            delivery_id TEXT PRIMARY KEY, event_id TEXT NOT NULL,
            existing_sha256 TEXT NOT NULL, incoming_sha256 TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS log_outbox (
            delivery_id TEXT PRIMARY KEY, log_json TEXT NOT NULL, exported INTEGER NOT NULL DEFAULT 0);
    """)
    return connection


def store_delivery(connection, event, topic, partition, offset, received_at_ms):
    """Call inside the caller's transaction; Kafka offsets are committed afterwards."""
    delivery_id = f"{topic}:{partition}:{offset}"
    if connection.execute("SELECT 1 FROM deliveries WHERE delivery_id=?", (delivery_id,)).fetchone():
        return "retry"
    keys = ["event_id", "run_id", "emitted_at_ms", "model_sha256", "status", "validation_error",
            "charged_off_probability", "flagged_risk", "threshold"]
    logical = {key: event[key] for key in keys}
    digest = hashlib.sha256(json.dumps(logical, sort_keys=True, allow_nan=False).encode()).hexdigest()
    existing = connection.execute("SELECT logical_sha256 FROM scores WHERE event_id=?", (event["event_id"],)).fetchone()
    if existing is None:
        connection.execute("INSERT INTO scores VALUES (?,?,?,?,?)",
            (event["event_id"], event["run_id"], digest, json.dumps(event, allow_nan=False), received_at_ms))
        outcome = "inserted"
    elif existing[0] == digest:
        outcome = "duplicate"
    else:
        outcome = "conflict"
        connection.execute("INSERT INTO conflicts VALUES (?,?,?,?)", (delivery_id, event["event_id"], existing[0], digest))
    connection.execute("INSERT INTO deliveries VALUES (?,?,?,?)", (delivery_id, event["event_id"], outcome, received_at_ms))
    log = {"@timestamp": datetime.fromtimestamp(received_at_ms / 1000, timezone.utc).isoformat(),
        "log_id": "delivery:" + delivery_id, "event_type": "score_delivery", "component": "score_store",
        "event_id": event["event_id"], "run_id": event["run_id"], "outcome": outcome,
        "status": event["status"], "model_sha256": event["model_sha256"],
        "charged_off_probability": event["charged_off_probability"], "flagged_risk": event["flagged_risk"],
        "end_to_end_latency_ms": received_at_ms - event["emitted_at_ms"] if event["emitted_at_ms"] else None,
        "validation_error": event["validation_error"], "source_topic": topic,
        "source_partition": partition, "source_offset": offset}
    connection.execute("INSERT INTO log_outbox(delivery_id,log_json) VALUES (?,?)", (delivery_id, json.dumps(log, allow_nan=False)))
    return outcome


def flush_outbox(connection, path):
    rows = connection.execute("SELECT delivery_id,log_json FROM log_outbox WHERE exported=0 ORDER BY rowid LIMIT 5000").fetchall()
    if not rows:
        return 0
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("a") as stream:
        for _, payload in rows:
            stream.write(payload + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    with connection:
        connection.executemany("UPDATE log_outbox SET exported=1 WHERE delivery_id=?", [(row[0],) for row in rows])
    return len(rows)
