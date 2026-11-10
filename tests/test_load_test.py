from util.load_test import summarize_stage, committed_offsets


def test_load_metrics_count_first_delivery_and_include_drain():
    base = {"status": "scored", "emitted_at_ms": 1000, "scored_at_ms": 1500}
    records = [dict(base, event_id="a", received_at_ms=2000),
               dict(base, event_id="b", received_at_ms=3000),
               dict(base, event_id="a", received_at_ms=4000)]
    producer = {"first_emitted_at_ms": 1000, "last_emitted_at_ms": 2000,
                "last_acknowledged_at_ms": 2100, "delivered": 2, "delivery_errors": 0}
    metrics = summarize_stage(records, producer, 2, [{"checkpoint_lag": 2}])
    assert metrics["duplicate_records"] == 1
    assert metrics["completed_rows_per_second"] == 1
    assert metrics["end_to_end_p50_ms"] == 1500
    assert metrics["drain_after_last_ack_seconds"] == .9
    assert metrics["counts_reconciled"]


def test_incomplete_and_invalid_outputs_are_not_success():
    records = [{"event_id": "a", "status": "invalid", "received_at_ms": 3000}]
    producer = {"first_emitted_at_ms": 1000, "last_emitted_at_ms": 2000,
                "last_acknowledged_at_ms": 2100, "delivered": 2, "delivery_errors": 0}
    result = summarize_stage(records, producer, 2, [])
    assert result["missing_rows"] == 1 and result["invalid_rows"] == 1
    assert not result["counts_reconciled"] and result["end_to_end_p99_ms"] is None


def test_checkpoint_offsets_preserve_progress_across_idle_batches():
    progress = [{"sources": [{"endOffset": {"input": {"0": 12, "1": 9}}}]},
                {"sources": [{"endOffset": None}]},
                {"sources": [{"endOffset": '{"input":{"0":14,"1":9}}'}]}]
    assert committed_offsets(progress, "input") == {"0": 14, "1": 9}
