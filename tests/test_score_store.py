import json

from util.score_store import open_store, store_delivery, flush_outbox


def sample():
    return {"event_id": "run:0", "run_id": "run", "emitted_at_ms": 1000,
        "model_sha256": "abc", "status": "scored", "validation_error": None,
        "charged_off_probability": .2, "flagged_risk": True, "threshold": .15}


def test_duplicate_score_and_kafka_retry_survive_store_restart(tmp_path):
    database = tmp_path / "scores.sqlite"
    connection = open_store(database)
    with connection:
        assert store_delivery(connection, sample(), "scores", 0, 0, 2000) == "inserted"
    connection.close()
    connection = open_store(database)
    with connection:
        assert store_delivery(connection, sample(), "scores", 0, 0, 3000) == "retry"
        assert store_delivery(connection, dict(sample(), scored_at_ms=2500), "scores", 0, 1, 3000) == "duplicate"
    assert connection.execute("SELECT COUNT(*) FROM scores").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0] == 2
    log = tmp_path / "events.jsonl"
    assert flush_outbox(connection, log) == 2
    assert flush_outbox(connection, log) == 0
    assert len(log.read_text().splitlines()) == 2
    connection.close()


def test_conflicting_model_result_never_overwrites_first_score(tmp_path):
    connection = open_store(tmp_path / "scores.sqlite")
    with connection:
        store_delivery(connection, sample(), "scores", 0, 0, 2000)
        assert store_delivery(connection, dict(sample(), model_sha256="different"), "scores", 0, 1, 3000) == "conflict"
    stored = json.loads(connection.execute("SELECT payload_json FROM scores").fetchone()[0])
    assert stored["model_sha256"] == "abc"
    assert connection.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0] == 1
    connection.close()


def test_failed_transaction_creates_neither_score_nor_outbox(tmp_path):
    connection = open_store(tmp_path / "scores.sqlite")
    import pytest
    with pytest.raises(RuntimeError), connection:
        store_delivery(connection, sample(), "scores", 0, 0, 2000)
        raise RuntimeError("simulate transaction failure")
    assert connection.execute("SELECT COUNT(*) FROM scores").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM log_outbox").fetchone()[0] == 0
    connection.close()


def test_invalid_source_record_can_have_missing_run_id(tmp_path):
    connection = open_store(tmp_path / "scores.sqlite")
    event = dict(sample(), run_id=None, status="invalid", charged_off_probability=None,
                 flagged_risk=None, validation_error="missing_run_id")
    with connection:
        assert store_delivery(connection, event, "invalid", 0, 0, 2000) == "inserted"
    assert connection.execute("SELECT COUNT(*) FROM scores").fetchone()[0] == 1
    connection.close()


def test_outbox_reexport_keeps_stable_elasticsearch_document_id(tmp_path):
    connection = open_store(tmp_path / "scores.sqlite")
    with connection:
        store_delivery(connection, sample(), "scores", 0, 0, 2000)
    path = tmp_path / "events.jsonl"
    flush_outbox(connection, path)
    with connection:
        connection.execute("UPDATE log_outbox SET exported=0")
    flush_outbox(connection, path)
    entries = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(entries) == 2 and entries[0]["log_id"] == entries[1]["log_id"]
    assert connection.execute("SELECT COUNT(*) FROM scores").fetchone()[0] == 1
    connection.close()
