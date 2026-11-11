# First MLflow experiment comparison

## Risk terminology and interpretation

The classifier estimates lifetime charge-off probability in the resolved
36-month cohort: Charged Off = 1 and Fully Paid = 0. Other statuses are excluded.
This is conditional on the selected accepted-loan population and observed final
status. It is neither a 12-month forecast nor a Basel default probability.

EAD and LGD refer to retrospective snapshot proxies, not default-event EAD or
discounted economic LGD. The lifetime snapshot-loss proxy multiplies the
classifier score by predicted snapshot LGD and snapshot EAD. It is not a
regulatory one-year expected loss estimate.

Capital and RWA are illustrative sensitivities using explicitly assumed
one-year PDs, separate from the classifier score. The current capital scenarios
do not use or annualise the classifier prediction. The approximation
1 - (1 - p_lifetime) ** (1 / 3) would require constant annual hazard; it would
not establish a regulatory default definition or validate a 12-month PD.

Legacy names containing `pd`, `basel`, `expected_loss` or `default` are retained
for artifact/API compatibility. They do not change these definitions.


Completed: 2026-11-11T13:09:44+00:00. Batch run: `6ccea4b79b8343cd971273181d93f680`.

Four pipelines were fitted on 157,993 training loans and
compared on 162,570 validation loans. Selection used
validation **average precision**, with lower validation Brier score as the
tie-breaker. Average precision is the scikit-learn metric, not trapezoidal PR-AUC.
No cross-validation, hyperparameter search, or independent calibration fit was run.

## Comparison

| model | run_id | model_uri | train_average_precision | validation_average_precision | validation_roc_auc | train_roc_auc | train_gini | train_ks | validation_gini | validation_ks | validation_brier_score | validation_log_loss | fit_seconds | validation_batch_predict_seconds | model_bytes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hist_gradient_boosting | f64a19bc843546e380a742697cf0bf26 | models:/m-dc3900fe2e2e4bf093dea10d7c5250bc | 0.239525 | 0.216483 | 0.653889 | 0.684525 | 0.369051 | 0.265112 | 0.307779 | 0.222796 | 0.114375 | 0.382348 | 5.390043 | 2.407201 | 412,754 |
| random_forest | 736532a9047c44a6969455fdbdd89914 | models:/m-99c75b41427a4b89bb6693bf5b2e48d7 | 0.266368 | 0.213944 | 0.649133 | 0.711889 | 0.423779 | 0.307458 | 0.298265 | 0.216818 | 0.114923 | 0.384513 | 28.412081 | 2.801744 | 11,497,147 |
| logistic_regression | bc902aadabe74ecd828414077ff1f9e3 | models:/m-4bc0dd14ef2a45b4aa2abc5e76df4d85 | 0.199628 | 0.21028 | 0.646231 | 0.650936 | 0.301871 | 0.218646 | 0.292462 | 0.213711 | 0.114869 | 0.384341 | 2.407796 | 0.709517 | 7,242 |
| dummy_prior | f45285c555fd4585b30cbc8e018afe72 | models:/m-189e95283b334a11a20fcef059eb47a4 | 0.125195 | 0.137264 | 0.5 | 0.5 | 0 | 0 | 0 | 0 | 0.118568 | 0.400613 | 1.500485 | 0.628898 | 4,882 |

The selected pipeline is **hist_gradient_boosting**. It was not refitted on
validation. Only this model scored the 283,026 2015
loans. A decision threshold of **0.14785290** maximizes
validation F1; ties choose the lowest threshold. This is a benchmark choice,
not a cost-optimized approval policy. Default-0.5 results are also preserved.

## Selected-model evaluations

| model | split | policy | rows | observed_positive_rate | mean_predicted_probability | threshold | roc_auc | gini | ks | average_precision | brier_score | log_loss | ece_10_uniform_bins | accuracy | balanced_accuracy | precision | recall | specificity | f1 | predicted_positive_rate | tn | fp | fn | tp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hist_gradient_boosting | validation | validation_f1 | 162,570 | 0.137264 | 0.131767 | 0.147853 | 0.653889 | 0.307779 | 0.222796 | 0.216483 | 0.114375 | 0.382348 | 0.005851 | 0.651689 | 0.607648 | 0.207851 | 0.546942 | 0.668354 | 0.301228 | 0.361198 | 93,740 | 46,515 | 10,110 | 12,205 |
| hist_gradient_boosting | exploratory_test | default_0.5 | 283,026 | 0.148863 | 0.132223 | 0.5 | 0.65435 | 0.308701 | 0.223789 | 0.235027 | 0.122279 | 0.402502 | 0.01664 | 0.851137 | 0.5 | 0 | 0 | 1 | 0 | 0 | 240,894 | 0 | 42,132 | 0 |
| hist_gradient_boosting | exploratory_test | validation_f1 | 283,026 | 0.148863 | 0.132223 | 0.147853 | 0.65435 | 0.308701 | 0.223789 | 0.235027 | 0.122279 | 0.402502 | 0.01664 | 0.650467 | 0.606918 | 0.22352 | 0.544906 | 0.668929 | 0.317005 | 0.362903 | 161,141 | 79,753 | 19,174 | 22,958 |

At the frozen threshold, exploratory ROC-AUC is 0.654350, average
precision is 0.235027, and Brier score is 0.122279.
These metrics describe the selected resolved-loan population. Precision, recall,
F1, specificity, and confusion counts depend on the documented threshold.
All rates here are fractions from 0 to 1, not percentages. Calibration ECE uses
10 fixed uniform probability bins weighted by their counts; empty bins are omitted.
Small occupied bins remain in the CSV and should not be overinterpreted.
The calibration figure displays bins with at least 200 rows; all occupied bins
contribute to the saved table and ECE. Precision–recall plots use steps so a
constant-score dummy is not drawn as a misleading sloping line.

## Preprocessing and reproducibility

The feature contract uses 13 predictors. Each pipeline fits its own preprocessing
on training rows only. Logistic regression uses median imputation, log1p for
annual income/revolving balance, numeric scaling, indicators for all numeric
missingness, and one-hot categories with unknowns ignored. Random forest and the
dummy baseline use median imputation, numeric missingness flags, and one-hot
categories. Histogram gradient boosting retains numeric missing values and uses
native categorical splits after training-fitted ordinal encoding; unseen category
codes are negative and treated as missing. No class balancing or oversampling was
used. A missing numeric indicator is not a new source observation.

The dummy model predicts the training positive-class prior. The other configurations
are fixed first-pass choices: logistic C=1, max_iter=1000; random forest 150 trees,
depth 12, minimum leaf 50; histogram boosting 200 iterations, learning rate 0.05,
15 leaves, minimum leaf 50, L2=1, early stopping disabled. Random seeds are 42;
thread pools are limited to four. Full pipeline parameters, package versions,
dataset fingerprints, model URIs, run IDs, and the code fingerprint are in the
manifest and MLflow. A convergence warning fails the run instead of being hidden.

Recorded fit times include preprocessing. Batch prediction times are single
wall-clock observations, not a latency/throughput benchmark. No p95 inference
latency, confidence intervals, financial savings, or stress-test measurements
are claimed. MLflow uses a local SQLite database and local model artifacts.

## Files and loading

- [Latest manifest](../../../results/model_experiments_latest.json).
- [Full metrics](../../../results/experiments/6ccea4b79b8343cd971273181d93f680/train_validation_metrics.csv),
  [selected evaluations](../../../results/experiments/6ccea4b79b8343cd971273181d93f680/selected_model_metrics.csv),
  [calibration bins](../../../results/experiments/6ccea4b79b8343cd971273181d93f680/calibration_bins.csv), and
  [curve points](../../../results/experiments/6ccea4b79b8343cd971273181d93f680/curve_points.csv).
- [Validation curves](../../../figures/experiments/6ccea4b79b8343cd971273181d93f680/validation_curves.png),
  [comparison](../../../figures/experiments/6ccea4b79b8343cd971273181d93f680/model_comparison.png), and
  [selected confusion matrices](../../../figures/experiments/6ccea4b79b8343cd971273181d93f680/selected_model_confusion.png).

Models and tracking data are local and Git-ignored. `models/selected_model.joblib`
contains the full fitted pipeline; call `predict_proba(frame[features])[:, 1]` for
the charged-off score, then apply the recorded threshold for the F1 decision rule.
Numeric input columns are standardized to float64 before fitting/logging, allowing
missing numeric inputs without an integer-only MLflow schema. The prepared Parquet
files themselves are unchanged.
The native pipeline's `predict()` still uses its classifier's default rule; it
does not automatically apply the validation-selected threshold. MLflow pyfunc
returns the two probability columns in class order [0, 1]. Native joblib,
MLflow sklearn, and MLflow pyfunc reloads were checked against saved-model scores.
The selected artifact is a benchmark candidate, not a production-approved model.

Each rerun creates a new batch with archived result/figure/model directories.
The latest manifest, selected joblib, report, and statistics section point to the
most recent completed batch. Previous batches remain available in MLflow and the
archive directories. No loan-level predictions are published in the result CSVs.
Curves contain at most 256 points per curve for plotting; all scalar metrics and
threshold selection use the complete prediction arrays, not the plotted points.

At threshold 0.5 this model predicts no charged-off loans: accuracy is 0.851137, but recall is zero. The validation-selected threshold makes the sensitivity/false-positive trade-off explicit.

## Limits

2015 was inspected during EDA and remains exploratory. The target is charged off
among selected resolved 36-month loans, not fixed-horizon default probability.
Snapshot label timing prevents a historical deployment-backtest claim. The data
contains accepted loans only. Model explanations, protected-group bias evaluation,
economic stress scenarios, Kafka load testing, and ELK monitoring have not run.
No fairness or causality conclusion follows from these scores.

Run `python scripts/05_train_models.py` from the project root. Open the local UI
with `mlflow ui --backend-store-uri sqlite:///models/mlflow.db --host 127.0.0.1 --port 5000`.
See [MLflow tracking](https://mlflow.org/docs/latest/tracking/) and
[scikit-learn histogram boosting](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html)
for the underlying APIs.

<!-- native-mlflow-evaluation-visibility -->
## MLflow datasets and native evaluations

Dataset/evaluation logging repaired at 2026-11-11T13:11:38+00:00 without retraining,
model reselection, or threshold changes. The original integration attached dataset
inputs only to training runs and logged custom metrics/CSV artifacts. It omitted
comparison-run inputs, dataset-bound model metrics, and native classifier evaluations.

In experiment **lendingclub_resolved_36m**, expand `first_model_comparison`:

- On the comparison run, inspect dataset inputs for train, validation, and
  exploratory_test. Its `datasets/` artifacts contain the full prepared Parquet
  files, their manifest, and 200-row previews.
- Open any `evaluate_*` child run for native classification metrics, ROC, PR,
  lift, calibration, confusion-matrix plots, and a sampled row-evaluation table.
- On a logged model, select a dataset to inspect its linked metrics. All four
  models have train/validation metrics; only the selected model has exploratory
  evaluation metrics. Dataset names and digests are recorded explicitly.
- The comparison run also contains `evaluation/model_comparison_table.json`
  and `evaluation/native_evaluation_summary.json` for tabular comparison.

### Datasets

| dataset | digest | rows |
| --- | --- | --- |
| train | 3fc22603 | 157993 |
| validation | 722bf1f9 | 162570 |
| exploratory_test | 38c881ae | 283026 |

### Native evaluations

| model | split | evaluation_run_id | source_training_run_id | model_id | dataset_name | dataset_digest | decision_threshold | score | true_negatives | false_positives | false_negatives | true_positives | example_count | accuracy_score | recall_score | precision_score | f1_score | log_loss | roc_auc | precision_recall_auc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dummy_prior | validation | a0d755b7d949420c850bc0cdb17d64a8 | f45285c555fd4585b30cbc8e018afe72 | m-189e95283b334a11a20fcef059eb47a4 | validation | 722bf1f9 | 0.5 | 0.862736 | 140255 | 0 | 22315 | 0 | 162570 | 0.862736 | 0 | 0 | 0 | 0.400613 | 0.5 | 0.137264 |
| logistic_regression | validation | fcc1cc31f70b4ba087a4398b3b44c5b0 | bc902aadabe74ecd828414077ff1f9e3 | m-4bc0dd14ef2a45b4aa2abc5e76df4d85 | validation | 722bf1f9 | 0.5 | 0.862705 | 140241 | 14 | 22306 | 9 | 162570 | 0.862705 | 0.000403 | 0.391304 | 0.000806 | 0.384341 | 0.646231 | 0.21028 |
| random_forest | validation | d413640a8782473c96a3a803db1dd139 | 736532a9047c44a6969455fdbdd89914 | m-99c75b41427a4b89bb6693bf5b2e48d7 | validation | 722bf1f9 | 0.5 | 0.862736 | 140255 | 0 | 22315 | 0 | 162570 | 0.862736 | 0 | 0 | 0 | 0.384513 | 0.649133 | 0.213944 |
| hist_gradient_boosting | validation | 436a568b45af4ca1aa84c7586164ea87 | f64a19bc843546e380a742697cf0bf26 | m-dc3900fe2e2e4bf093dea10d7c5250bc | validation | 722bf1f9 | 0.5 | 0.862736 | 140255 | 0 | 22315 | 0 | 162570 | 0.862736 | 0 | 0 | 0 | 0.382348 | 0.653889 | 0.216483 |
| hist_gradient_boosting | exploratory_test | 0db9dc0169ae4a608652a608d4898989 | f64a19bc843546e380a742697cf0bf26 | m-dc3900fe2e2e4bf093dea10d7c5250bc | exploratory_test | 38c881ae | 0.5 | 0.851137 | 240894 | 0 | 42132 | 0 | 283026 | 0.851137 | 0 | 0 | 0 | 0.402502 | 0.65435 | 0.235027 |

Native evaluations use each sklearn classifier's default decision rule (0.5 for
these pipelines). They do not replace the frozen F1-policy results: the selected
threshold remains 0.14785290, with its original full-data
metrics bound to the relevant datasets on the selected training run. In this
MLflow version, binary `precision_recall_auc` matches the saved average-precision
values; ROC-AUC and all example counts were checked against the original results.

Every native metric uses the full split. The row-evaluation tables contain a
deterministic uniform sample of at most 1,000 positions, seed 42; they are previews,
not the metric population. Parent previews show the first 200 rows. No SHAP or
InterpretML explanation evaluation was enabled.

The [native evaluation CSV](../../../results/experiments/6ccea4b79b8343cd971273181d93f680/mlflow_native_evaluations.csv)
and statistics section 19 contain all evaluation IDs and metrics. Run
`python scripts/06_log_mlflow_evaluations.py` to verify or repair an existing
completed comparison. Running it again reuses the completed repair and creates
no duplicate evaluation runs. Future training calls this logging step automatically.

These are classic ML classifier evaluations. MLflow's separate GenAI evaluation
datasets/scorers are not used for this loan-classification benchmark.

