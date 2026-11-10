# Reproducibility verification

Notebook sources now live in `notebooks/`. Historical verification records retain
their execution-time `scripts/` paths and hashes; current commands use the new folder.

The core workflow was executed successfully on the real accepted-loans CSV in a
separate checkout using an isolated Python 3.14.9 environment on Linux x86_64.
Dependencies were installed from the complete SHA-256 lock and passed `uv pip check`.
The existing project datasets and incumbent model were preserved.

```bash
make all RAW_DATA=/absolute/path/to/accepted_2007_to_2018Q4.csv
```

Use `BOOTSTRAP_PYTHON=/path/to/python3.14` if needed. The command runs fixture
tests, uses the local CSV, exports three marimo notebooks, prepares data, trains
the baseline comparison, logs native MLflow evaluations, and runs validation
hardening. A local `.csv.gz` also works. The local-data tests explicitly prevent
Kaggle imports, covering environments where the dataset host is blocked.

The core validation stage had **72 passing tests**, with no failures. The full workflow
started when the suite had 70 tests; the two added prepared-data export tests were
subsequently run with the complete suite in the same isolated environment.

The repeated workflow reproduced:

- All six prepared predictor/target and metadata file hashes exactly.
- Eight historical train/validation metric rows, including full-threshold KS.
- All 500 paired bootstrap rows and all five AUC/Gini interval rows.
- Four separate-year calibration metric rows.
- All three headless notebook HTML exports.

Numerical table comparisons used relative tolerance `1e-9` and absolute tolerance
`1e-12`. The main validation batch's four logged models loaded successfully; its
four native evaluation runs finished and each used all 162,570 evaluation rows.
CSV hashes and the unchanged incumbent hash were checked.

The optional seven-trial XGBoost search was not rerun during this verification.
`make full` includes it. Its previously measured results remain historical research
snapshots. At that verification, Kafka, ELK, InterpretML and bias evaluation were
still future stages. The completed interpretation and segment audit is recorded below.

The first validation-hardening logging attempt failed under MLflow's default model
serializer. It remains recorded as a failed run. The completed workflow uses the
same explicit cloudpickle format as the baseline trainer. Model artifacts should
be loaded from this project's trusted local runs.

The original validation report had a later reporting revision, recorded with separate
execution and reporting hashes. To close that evidence gap, the committed
`scripts/08_validate_models.py` was rerun unchanged. Its current file hash,
`HEAD` file hash, execution hash, and manifest source hash now all equal
`34e3be3c4c298f15e3a6266aba3aa515373e88b7aa61265c952d1f5f11837a25`.

The fresh batch is `62955be6d71845418f95174c621c98d2`. All seven comparable numerical
CSV tables reproduce the prior reference results at the same tolerances. All eight
result CSV hashes, four saved model hashes, four logged models, and four native
evaluation runs were checked. The 72 tests passed again; the incumbent is unchanged.

[Fresh committed-script verification](../assets/results/validation_hardening_fresh_verification.json).

Machine-readable evidence and source hashes are in the
[verification record](../assets/results/validation_hardening_verification.json).
Full metrics, coefficients, bin counts, and intervals are in the
[validation report](validation_hardening.md) and
[statistics reference, section 21](../assets/statistics.md#21-validation-hardening).

## EAD/LGD experiment and updated notebooks

The later loss stage was executed directly on the existing hashed prepared data.
The final experiment's executed script matches its current source hash, and all
model, input-dataset, and result hashes were verified. Four component models and
four native MLflow regression evaluations were checked; each evaluation used
22,308 eligible validation defaults. The saved bundle reproduced scores for all
162,563 eligible validation loans. PD predictions remained identical.

At completion of the loss stage, the suite had 82 passing tests. All three updated EDA notebooks exported
successfully in the isolated workspace using identical notebook sources, the same
raw CSV, and copies of the final measured model results. Their HTML exports were
written back to `docs/`. The new model-review notebook exported directly in the
project. This notebook work did not overwrite the project's clean or prepared data.

The workflow now appends the loss experiment and model-review export. `make loss`
runs those stages using existing prepared data and the incumbent. The earlier
full-core verification retains its original date and source fingerprints.

See the [loss/notebook verification record](../assets/results/basel_loss_verification.json)
and [experiment report](basel_loss_experiment.md). Capital outputs are assumed-PD
scenarios; no one-year PD estimation or regulatory compliance claim is made.

## ANN challengers

The ANN stage adds two PD classifiers and EAD/LGD regressors. Epoch selection uses
2013 after fitting on 2011–2012. The selected epoch budgets are then frozen for
refitting on 2011–2013; 2014 compares candidates. No 2015 rows enter the experiment.
At completion of the ANN stage, the suite had **85 passing tests**.

All four saved/logged ANN pipelines reproduced their full validation predictions.
Four native MLflow evaluations finished and matched the custom aggregate metrics.
The saved learning curves match the fixed refit epoch counts. The ANN bundle's
full 162,563-loan loss total reproduced, and the updated model-review notebook
exported successfully. Source, dataset, result, and model hashes were checked.
Incumbent PD and reference loss-bundle artifacts stayed unchanged.

The loss report writer was updated to preserve the later ANN statistics section.
Its experiment was rerun from the unchanged modelling logic, and its current
script hash matches that fresh execution. Numerical loss/audit results matched
the earlier reference. The ANN manifest retains the exact historical loss batch
used for its comparison rather than silently switching references.

See the [ANN verification record](../assets/results/ann_experiments_verification.json)
and [ANN experiment report](ann_experiments.md). `make ann` reruns the ANN stage;
`make full` now includes both optional XGBoost and ANN research stages.

## Temporal XGBoost and coefficient validation review

XGBoost protocol v2 separates 2013 stopping from 2014 candidate selection. The
seven final pipelines refit on 2011–2013 using frozen tree counts and no eval_set.
All counts, role-specific dataset hashes, stopping curves and previous/current
protocol comparisons are archived. This does not make the previously explored
2014 cohort a fresh holdout.

The coefficient review refits whole pipelines in 200 year/outcome-stratified
bootstrap samples, records yearly and univariate associations, and compares four
feature-removal variants on 2014. Its paired interval concerns two fixed fitted
models and does not include model-selection or training uncertainty.

At completion of the validation review, the suite had **93 passing tests**. Current script/source hashes match
both executions. The updated model-review notebook includes both batch IDs and
the remaining model-use limitations. No incumbent artifact or 2015 evaluation
result was changed. Reproduce these review stages using `make review`.

See the [validation gap review](validation_gaps.md) and
[verification record](../assets/results/validation_gaps_verification.json).

## InterpretML and descriptive segment audit

The incumbent is explained using InterpretML 0.7.8 and its SHAP backend. Direct
dependencies and the complete hash lock were updated and checked for conflicts
in the isolated Python 3.14 environment. Existing scikit-learn and NumPy versions
were retained. Historical training records keep their original dependency hashes;
the interpretation run records the new lock and actual runtime versions.

The current suite has **101 passing tests**, including reversible category-code
checks, a real InterpretML SHAP reconstruction test, Wilson interval checks,
single-class/undefined-rate handling, zero-flag policy warnings and SQL group
boundary/missingness checks. The explanation adapter decodes training-defined
category codes before every prediction; it does not change model inputs.

`make interpret` uses the existing hashed train/validation/exploratory datasets,
unchanged incumbent, clean state metadata and canonical source header. Training
income quartiles and explanation backgrounds use training data only. All 2014
and 2015 loans remain in the segment metrics; complete/training-known cases form
the separately labelled explanation sample. No model or threshold is refitted.

Use the [interpretation/bias report](interpret_bias.md) and
[verification record](../assets/results/interpret_bias_verification.json). The
model-review notebook displays both explanations and disparity tables. Protected
attributes are not inferred, and absent structured attributes prevent a
protected-group fairness assessment or legal/compliance conclusion.

## Kafka/PySpark correctness check

The optional streaming environment preserves every core dependency version and
adds PySpark 4.1.2, Py4J and confluent-kafka 2.16.1. All 102 tests passed there,
including the optional Spark validation test; the core environment remains
separate. Java 21.0.13+9 was used for Spark. Dependency conflict checks passed.

A real Kafka broker accepted 100 application replays and three invalid fixtures.
All valid scores exactly matched direct frozen-model predictions. The invalid
fixtures were rejected, and a clean checkpoint restart read no additional input
and wrote no additional output. Sources and the prepared input file are hashed
in [the streaming manifest](../assets/results/streaming_latest.json).
This finite correctness check is not a stress test or a failure-injection test.

MLflow run: `fe86cfd3742d47ec8ad81f248e623566` in `lendingclub_streaming_smoke`.
See [the streaming guide](streaming.md) for repeatable commands and at-least-once
delivery limitations.

## Paced Kafka/PySpark load measurements

The current streaming environment passed 105 tests, including three new tests
for latency/throughput denominators, duplicate accounting, incomplete results and
Spark checkpoint offsets across idle batches. Regression tests finished before
the first measured traffic stage. A separate 100-row warmup precedes the stages.

The recorded 100/500/2,000 messages/s stages processed 78,000 events. Every score
and flag matched direct model predictions. All stages drained their checkpoint
lag to zero. Source files, model and prepared data fingerprints are recorded; the
report checks them and recomputes output counts, latency percentiles and peak lag
from saved evidence. Historical smoke-test fingerprints retain their execution
versions; the current streaming scripts add isolated output topics and continuous
progress/controlled-stop support. No model metrics or model binary were changed.

See [the load report](load_testing.md), [current manifest](../assets/results/load_test_latest.json)
and [verification](../assets/results/load_test_verification.json). One MLflow
parent and three stage children finished in `lendingclub_streaming_load_tests`.
Only finite local loads were measured; no failure-injection or ELK claim is made.

## Recovery, durable deduplication and ELK

The current optional streaming runtime is pinned to Spark 4.1.4 with the matching
Kafka connector. The 4.1.2 runtime used for the historical smoke/load benchmarks
crashed in Kafka progress reporting when restarting an uncommitted batch, matching
[SPARK-55271](https://issues.apache.org/jira/browse/SPARK-55271). The patch changes
only the streaming runtime; core dependency versions and the model are unchanged.
Historical fingerprints remain snapshots of their actual execution versions.

The complete suite passed **110 tests** in the patched streaming environment.
New checks cover persisted event deduplication, same-offset retries, conflicting
results, transactional rollback, invalid records with missing run IDs and stable
monitoring document IDs across outbox re-exports. The real failure experiment
additionally checks the storage-consumer group offsets after restart, not just
the database and outbox.

The independent [recovery verification](../assets/results/recovery_verification.json)
reconciles SQLite outcomes, model preservation, Spark checkpoint offsets, every
output partition's committed group lag, indexed delivery counts and the eight
Kibana dashboard references. Source/input/result hashes and the latest MLflow
replay dataset are recorded. The experiment uses isolated topics, group,
checkpoint and database. Earlier failed startup attempts remain diagnostic
artifacts, and the run rejected by the post-run offset audit is marked FAILED
in local MLflow. Only the successful latest batch is used for reported metrics.

See [the recovery and monitoring report](recovery_monitoring.md) and
[current manifest](../assets/results/recovery_latest.json). Kafka data was
preserved when introducing the persistent broker mount. Elastic 8.17.3 is a
local demo with loopback ports and disabled Elasticsearch security; external
notifications and broker failover are not implemented.
