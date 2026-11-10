"""Measured replay rates and collector-observed latency, with explicit denominators."""

import numpy as np
import pandas as pd


def summarize_stage(records, producer, expected_rows, backlog):
    frame = pd.DataFrame(records)
    unique = frame.drop_duplicates("event_id", keep="first") if len(frame) else frame
    valid = unique[unique.status == "scored"] if len(unique) else unique
    first = producer["first_emitted_at_ms"]
    last = producer["last_emitted_at_ms"]
    end = int(unique.received_at_ms.max()) if len(unique) else producer["last_acknowledged_at_ms"]
    duration = (last - first) / 1000
    elapsed = (end - first) / 1000
    result = {"expected_rows": expected_rows, "delivered_rows": producer["delivered"],
        "received_records": len(frame), "unique_outputs": len(unique), "scored_rows": len(valid),
        "invalid_rows": len(unique) - len(valid), "missing_rows": expected_rows - len(unique),
        "duplicate_records": len(frame) - len(unique), "delivery_errors": producer["delivery_errors"],
        "emission_seconds": duration, "emit_to_last_receive_seconds": elapsed,
        "actual_emission_rows_per_second": (expected_rows - 1) / duration if duration > 0 else None,
        "completed_rows_per_second": len(valid) / elapsed if elapsed > 0 else None,
        "drain_after_last_ack_seconds": max(0, (end - producer["last_acknowledged_at_ms"]) / 1000),
        "pending_at_last_emission": expected_rows - int((unique.received_at_ms <= last).sum()) if len(unique) else expected_rows,
        "peak_sampled_checkpoint_lag": max((row["checkpoint_lag"] for row in backlog), default=0)}
    for label, column in [("end_to_end", "received_at_ms"), ("emit_to_worker_score", "scored_at_ms")]:
        values = valid[column].to_numpy() - valid.emitted_at_ms.to_numpy() if len(valid) else np.array([])
        result[f"{label}_negative_latency_count"] = int((values < 0).sum())
        for percentile in [50, 95, 99]:
            result[f"{label}_p{percentile}_ms"] = float(np.percentile(values, percentile)) if len(values) else None
    result["counts_reconciled"] = bool(result["missing_rows"] == 0 and result["invalid_rows"] == 0
        and producer["delivered"] == expected_rows and producer["delivery_errors"] == 0)
    return result


def committed_offsets(progress, topic):
    """End offsets from completed Spark progress, not Kafka consumer-group offsets."""
    import json
    offsets = {}
    for item in progress:
        for source in item.get("sources", []):
            end = source.get("endOffset") or {}
            if isinstance(end, str):
                end = json.loads(end)
            for partition, offset in end.get(topic, {}).items():
                offsets[str(partition)] = max(offsets.get(str(partition), 0), int(offset))
    return offsets
