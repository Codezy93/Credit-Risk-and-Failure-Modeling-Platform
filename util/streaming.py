"""Kafka JSON validation in Spark; the existing pipeline still owns preprocessing."""

from pyspark.sql import functions as F, types as T


def prepare_events(source, features, numeric, categorical):
    schema = T.StructType([
        T.StructField("event_id", T.StringType()),
        T.StructField("run_id", T.StringType()),
        T.StructField("emitted_at_ms", T.LongType()),
        T.StructField("features", T.MapType(T.StringType(), T.StringType())),
        T.StructField("_corrupt_record", T.StringType()),
    ])
    frame = source.select("topic", "partition", "offset",
        F.from_json(F.col("value").cast("string"), schema).alias("event"))
    frame = frame.select("topic", "partition", "offset", "event.*")
    for name in numeric:
        frame = frame.withColumn(name, F.element_at("features", F.lit(name)).try_cast("double"))
    for name in categorical:
        frame = frame.withColumn(name, F.element_at("features", F.lit(name)))
    errors = [
        F.when(F.col("_corrupt_record").isNotNull() | F.col("features").isNull(), "invalid_json_or_features"),
        F.when(F.col("event_id").isNull() | (F.length(F.trim("event_id")) == 0), "missing_event_id"),
        F.when(F.col("run_id").isNull() | (F.length(F.trim("run_id")) == 0), "missing_run_id"),
        F.when(F.col("emitted_at_ms").isNull() | (F.col("emitted_at_ms") <= 0), "invalid_emitted_at"),
        F.when(F.size(F.array_except(F.map_keys("features"), F.array(*[F.lit(x) for x in features]))) > 0,
               "unexpected_feature"),
        F.when(F.size(F.array_except(F.array(*[F.lit(x) for x in features]), F.map_keys("features"))) > 0,
               "missing_feature_key"),
    ]
    for name in numeric:
        raw = F.element_at("features", F.lit(name))
        invalid = raw.isNotNull() & (F.col(name).isNull() | F.isnan(name) | (F.abs(F.col(name)) == float("inf")))
        errors.append(F.when(invalid, F.lit(f"invalid_numeric:{name}")))
    return frame.withColumn("validation_error", F.concat_ws(",", *errors)).drop("features", "_corrupt_record")
