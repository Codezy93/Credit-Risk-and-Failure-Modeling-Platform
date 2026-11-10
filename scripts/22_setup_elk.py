"""Install the local monitoring template/dashboard, or check operational thresholds."""

import argparse
import json
from pathlib import Path
import time

import requests

ROOT = Path(__file__).resolve().parents[1]


def install(elasticsearch, kibana):
    properties = {name: {"type": "keyword"} for name in ["log_id", "event_type", "component", "event_id",
        "run_id", "pipeline_id", "group_id", "outcome", "status", "model_sha256", "query_id", "source_topic", "validation_error"]}
    properties.update({"@timestamp": {"type": "date"}, "flagged_risk": {"type": "boolean"}})
    for name in ["end_to_end_latency_ms", "charged_off_probability", "checkpoint_lag", "input_rows",
                 "batch_duration_ms", "processed_rows_per_second", "input_rows_per_second"]:
        properties[name] = {"type": "double"}
    response = requests.put(elasticsearch + "/_index_template/credit-risk-monitoring", json={
        "index_patterns": ["credit-risk-monitoring-*"], "template": {"settings": {"number_of_shards": 1,
        "number_of_replicas": 0}, "mappings": {"properties": properties}}}, timeout=15)
    response.raise_for_status()
    objects = [{"id": "credit-risk-monitoring", "type": "index-pattern", "attributes": {
        "title": "credit-risk-monitoring-*", "timeFieldName": "@timestamp"}}]
    panels = []
    specifications = [
        ("stored", "Unique stored results", "metric", "event_type:score_delivery AND outcome:inserted", "count", None),
        ("duplicates", "Suppressed duplicate deliveries", "metric", "event_type:score_delivery AND outcome:duplicate", "count", None),
        ("conflicts", "Conflicting event IDs", "metric", "event_type:score_delivery AND outcome:conflict", "count", None),
        ("latency", "Stored-score p95 latency (ms)", "metric", "event_type:score_delivery AND outcome:inserted AND status:scored", "percentiles", "end_to_end_latency_ms"),
        ("throughput", "Stored results per minute", "histogram", "event_type:score_delivery AND outcome:inserted", "count", None),
        ("lag", "Peak sampled checkpoint lag", "histogram", "event_type:spark_progress", "max", "checkpoint_lag"),
        ("risk", "Mean charged-off probability", "histogram", "event_type:score_delivery AND outcome:inserted AND status:scored", "avg", "charged_off_probability"),
        ("errors", "Errors and invalid outputs", "histogram", "event_type:monitor_error OR (event_type:score_delivery AND (status:invalid OR outcome:conflict))", "count", None),
    ]
    for index, (name, title, kind, query, aggregation, field) in enumerate(specifications):
        identifier = "credit-risk-" + name
        params = {"field": field} if field else {}
        if aggregation == "percentiles":
            params["percents"] = [95]
        aggs = [{"id": "1", "enabled": True, "type": aggregation, "schema": "metric", "params": params}]
        if kind == "histogram":
            aggs.append({"id": "2", "enabled": True, "type": "date_histogram", "schema": "segment",
                         "params": {"field": "@timestamp", "interval": "auto", "min_doc_count": 1}})
        objects.append({"id": identifier, "type": "visualization", "attributes": {
            "title": title, "uiStateJSON": "{}", "description": "Local Kafka/PySpark monitoring",
            "visState": json.dumps({"title": title, "type": kind, "params": {"addLegend": False}, "aggs": aggs}),
            "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"query": query, "language": "kuery"},
                "filter": [], "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"})}},
            "references": [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": "credit-risk-monitoring"}]})
        panels.append({"panelIndex": str(index + 1), "type": "visualization", "panelRefName": f"panel_{index}",
            "gridData": {"x": (index % 2) * 24, "y": (index // 2) * 14, "w": 24, "h": 14, "i": str(index + 1)},
            "embeddableConfig": {}})
    objects.append({"id": "credit-risk-streaming", "type": "dashboard", "attributes": {
        "title": "Credit risk streaming operations", "description": "Replay, deduplication, checkpoint lag and operational errors. No fairness or drift certification.",
        "panelsJSON": json.dumps(panels), "optionsJSON": json.dumps({"useMargins": True, "syncColors": False, "hidePanelTitles": False}),
        "timeRestore": True, "timeFrom": "now-1h", "timeTo": "now", "version": 1,
        "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"language": "kuery", "query": ""}, "filter": []})}},
        "references": [{"name": f"panel_{index}", "type": "visualization", "id": "credit-risk-" + spec[0]} for index, spec in enumerate(specifications)]})
    payload = "\n".join(json.dumps(obj) for obj in objects) + "\n"
    (ROOT / "util/elk/dashboard.ndjson").write_text(payload)
    response = requests.post(kibana + "/api/saved_objects/_import?overwrite=true", headers={"kbn-xsrf": "true"},
        files={"file": ("dashboard.ndjson", payload, "application/ndjson")}, timeout=60)
    response.raise_for_status()
    result = response.json()
    if not result.get("success"):
        raise RuntimeError(json.dumps(result))
    print(json.dumps({"imported_objects": result["successCount"], "dashboard": kibana + "/app/dashboards#/view/credit-risk-streaming"}, indent=2))


def check(elasticsearch, expect_running):
    response = requests.post(elasticsearch + "/credit-risk-monitoring-*/_search", json={"size": 0,
        "query": {"range": {"@timestamp": {"gte": "now-5m"}}}, "aggs": {
        "errors": {"filter": {"bool": {"should": [{"term": {"outcome": "conflict"}}, {"term": {"event_type": "monitor_error"}}], "minimum_should_match": 1}}},
        "invalid": {"filter": {"term": {"status": "invalid"}}},
        "latency": {"filter": {"bool": {"must": [{"term": {"outcome": "inserted"}}, {"term": {"status": "scored"}}]}},
            "aggs": {"p95": {"percentiles": {"field": "end_to_end_latency_ms", "percents": [95]}}}},
        "latest_progress": {"filter": {"term": {"event_type": "spark_progress"}}, "aggs": {
            "latest": {"top_hits": {"size": 1, "sort": [{"@timestamp": "desc"}]}}}}}}, timeout=15)
    response.raise_for_status()
    data = response.json()["aggregations"]
    alerts = []
    if data["errors"]["doc_count"]:
        alerts.append("conflicting_event_ids")
    if data["invalid"]["doc_count"]:
        alerts.append("invalid_outputs")
    p95 = data["latency"]["p95"]["values"]["95.0"]
    if p95 is not None and p95 > 10000:
        alerts.append("p95_latency_above_10_seconds")
    latest = data["latest_progress"]["latest"]["hits"]["hits"]
    if latest and latest[0]["_source"].get("checkpoint_lag", 0) > 10000:
        alerts.append("checkpoint_lag_above_10000")
    if expect_running:
        from datetime import datetime
        age = time.time() - datetime.fromisoformat(latest[0]["_source"]["@timestamp"].replace("Z", "+00:00")).timestamp() if latest else float("inf")
        if age > 30:
            alerts.append("no_progress_for_30_seconds")
    print(json.dumps({"status": "warning" if alerts else "ok", "window": "5 minutes", "alerts": alerts,
        "checks_are_on_demand": True, "external_notifications_sent": False}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--elasticsearch", default="http://127.0.0.1:19200")
    parser.add_argument("--kibana", default="http://127.0.0.1:15601")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--expect-running", action="store_true")
    args = parser.parse_args()
    if args.check:
        check(args.elasticsearch, args.expect_running)
    else:
        install(args.elasticsearch, args.kibana)


if __name__ == "__main__":
    main()
