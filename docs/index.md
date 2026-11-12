# Credit Risk and Failure Modeling

Terminology: [lifetime charge-off probability, snapshot loss proxies and illustrative capital](risk_terminology.md).

This project uses LendingClub accepted-loan data to study credit risk and test
a streaming scoring pipeline. The reports below describe the data decisions,
model experiments, validation limits and measured system behavior.

## Data

Start with [download and setup](data_setup.md), then read the
[EDA and cleaning report](eda_summary.md). SQL handles staging, cleaning and
analysis; marimo notebooks display the saved tables and figures.
The [data dictionary](data_dictionary.md) describes the cleaned fields.

The raw file contains 2,260,701 rows and 151 columns. Cleaning leaves
2,260,668 loans and 26 columns. The [model dataset report](model_data.md)
defines the resolved 36-month loan population and temporal splits.

## Models and results

The [MLflow benchmark](model_experiments.md) compares a dummy baseline,
logistic regression, random forest and histogram gradient boosting.
The selected gradient-boosting model has validation ROC-AUC **0.653889**
and exploratory 2015 ROC-AUC **0.654350**. The 2015 population was examined
during EDA, so it is not an untouched holdout.

Further reports cover [XGBoost](auc_improvement.md),
[neural networks](ann_experiments.md), [EAD/LGD and loss proxies](basel_loss_experiment.md),
and [InterpretML and segment disparities](interpret_bias.md).
Research challengers do not replace the selected model.

The target is charged off versus fully paid among resolved loans. It is not a
regulatory default definition. Loss and capital estimates are illustrative
snapshot proxies. Protected-group fairness remains unassessed.

## Validation and streaming

The [validation report](validation_hardening.md) covers uncertainty,
calibration and exact diagnostics. The [validation gap review](validation_gaps.md)
records the remaining limitations.

[Kafka and PySpark](streaming.md) replay and score loan events.
The [load tests](load_testing.md) measure completion and latency;
the [recovery and monitoring report](recovery_monitoring.md) covers failure recovery,
durable deduplication and ELK. These are local experiments, not production capacity claims.

## Reproduce

See the [reproducibility report](reproducibility.md) for commands and verified runs.
The [statistics reference](https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/assets/statistics.md)
contains detailed counts, metrics and stage-specific evidence.

This documentation displays saved project results. Reading it does not train
models or connect to MLflow, Kafka or Elasticsearch.

The [latest experiment refresh](experiment_refresh.md) records the current-code reruns,
full pytest results and source/result fingerprints.

The [WoE scorecard challengers](scorecard.md) add training-only bins, IV screening,
sign audits and points tables. They are less discriminating than the incumbent
and remain research models.
