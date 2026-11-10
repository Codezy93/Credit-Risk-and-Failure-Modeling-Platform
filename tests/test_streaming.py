"""Optional Spark tests: use the streaming environment and Java 17/21."""

import pytest

pytest.importorskip("pyspark")
import json
from pyspark.sql import SparkSession
from util.streaming import prepare_events


def test_spark_validation_preserves_missing_values_and_rejects_bad_payloads():
    spark = SparkSession.builder.master("local[1]").appName("stream-validation-test").getOrCreate()
    event = {"event_id": "test:0", "run_id": "test", "emitted_at_ms": 123,
             "features": {"annual_inc": 60000, "purpose": "credit_card"}}
    missing = dict(event, features={"annual_inc": None, "purpose": None})
    bad_number = dict(event, features={"annual_inc": "oops", "purpose": "credit_card"})
    outcome = dict(event, features={**event["features"], "loan_status": "Charged Off"})
    missing_key = dict(event, features={"purpose": "credit_card"})
    raw = [json.dumps(x) for x in [event, missing, bad_number, outcome, missing_key]] + ["{broken"]
    source = spark.createDataFrame([("input", 0, i, value) for i, value in enumerate(raw)],
                                   "topic string, partition int, offset long, value string")
    rows = prepare_events(source, ["annual_inc", "purpose"], ["annual_inc"], ["purpose"]).orderBy("offset").collect()
    assert rows[0].validation_error == "" and rows[0].annual_inc == 60000
    assert rows[1].validation_error == "" and rows[1].annual_inc is None
    assert "invalid_numeric:annual_inc" in rows[2].validation_error
    assert "unexpected_feature" in rows[3].validation_error
    assert "missing_feature_key" in rows[4].validation_error
    assert "invalid_json_or_features" in rows[5].validation_error
    spark.stop()
