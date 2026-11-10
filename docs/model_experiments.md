# First MLflow experiment comparison

Completed: 2026-11-08T15:45:23+00:00. Batch run: `72061e0a7a1e4d68addcc79a2aae631d`.

Four pipelines were fitted on 157,993 training loans and
compared on 162,570 validation loans. Selection used
validation **average precision**, with lower validation Brier score as the
tie-breaker. Average precision is the scikit-learn metric, not trapezoidal PR-AUC.
No cross-validation, hyperparameter search, or independent calibration fit was run.

## Comparison

| model | run_id | model_uri | train_average_precision | validation_average_precision | validation_roc_auc | validation_brier_score | validation_log_loss | fit_seconds | validation_batch_predict_seconds | model_bytes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hist_gradient_boosting | 2bb4ea9b1159440bb0b51b66925247f3 | models:/m-c0cd1df22fa24744b5d207306fd84ac1 | 0.239525 | 0.216483 | 0.653889 | 0.114375 | 0.382348 | 2.025974 | 0.765676 | 412,754 |
| random_forest | 9b8a327a8a694086819d1818c141ba76 | models:/m-d5af0b19e25b4b169c0f5b3414373ad9 | 0.266368 | 0.213944 | 0.649133 | 0.114923 | 0.384513 | 13.763563 | 0.92611 | 11,497,147 |
| logistic_regression | b6cd84c99ba24a8f854b2b7941ee3b88 | models:/m-9b48e925f4a54600a0eeeacf7eb183c1 | 0.199628 | 0.21028 | 0.646231 | 0.114869 | 0.384341 | 0.958238 | 0.273507 | 7,242 |
| dummy_prior | e017e1e02bb743669f6f3f8e804a1c36 | models:/m-c6c8b6403be04d378ecd4ee0149b6fdd | 0.125195 | 0.137264 | 0.5 | 0.118568 | 0.400613 | 0.555652 | 0.235392 | 4,882 |

The selected pipeline is **hist_gradient_boosting**. It was not refitted on
validation. Only this model scored the 283,026 2015
loans. A decision threshold of **0.14785290** maximizes
validation F1; ties choose the lowest threshold. This is a benchmark choice,
not a cost-optimized approval policy. Default-0.5 results are also preserved.

## Selected-model evaluations

| model | split | policy | rows | observed_positive_rate | threshold | roc_auc | average_precision | brier_score | log_loss | ece_10_uniform_bins | accuracy | balanced_accuracy | precision | recall | specificity | f1 | predicted_positive_rate | tn | fp | fn | tp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hist_gradient_boosting | validation | validation_f1 | 162,570 | 0.137264 | 0.147853 | 0.653889 | 0.216483 | 0.114375 | 0.382348 | 0.005851 | 0.651689 | 0.607648 | 0.207851 | 0.546942 | 0.668354 | 0.301228 | 0.361198 | 93,740 | 46,515 | 10,110 | 12,205 |
| hist_gradient_boosting | exploratory_test | default_0.5 | 283,026 | 0.148863 | 0.5 | 0.65435 | 0.235027 | 0.122279 | 0.402502 | 0.01664 | 0.851137 | 0.5 | 0 | 0 | 1 | 0 | 0 | 240,894 | 0 | 42,132 | 0 |
| hist_gradient_boosting | exploratory_test | validation_f1 | 283,026 | 0.148863 | 0.147853 | 0.65435 | 0.235027 | 0.122279 | 0.402502 | 0.01664 | 0.650467 | 0.606918 | 0.22352 | 0.544906 | 0.668929 | 0.317005 | 0.362903 | 161,141 | 79,753 | 19,174 | 22,958 |

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

- [Latest manifest](https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/assets/results/model_experiments_latest.json).
- [Full metrics](https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/assets/results/experiments/72061e0a7a1e4d68addcc79a2aae631d/train_validation_metrics.csv),
  [selected evaluations](https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/assets/results/experiments/72061e0a7a1e4d68addcc79a2aae631d/selected_model_metrics.csv),
  [calibration bins](https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/assets/results/experiments/72061e0a7a1e4d68addcc79a2aae631d/calibration_bins.csv), and
  [curve points](https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/assets/results/experiments/72061e0a7a1e4d68addcc79a2aae631d/curve_points.csv).
- [Validation curves](https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/assets/figures/experiments/72061e0a7a1e4d68addcc79a2aae631d/validation_curves.png),
  [comparison](https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/assets/figures/experiments/72061e0a7a1e4d68addcc79a2aae631d/model_comparison.png), and
  [selected confusion matrices](https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/assets/figures/experiments/72061e0a7a1e4d68addcc79a2aae631d/selected_model_confusion.png).

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

Dataset/evaluation logging repaired at 2026-11-08T16:15:06+00:00 without retraining,
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
| dummy_prior | validation | 76124a42a3c84a639a451e8c0bf94edd | e017e1e02bb743669f6f3f8e804a1c36 | m-c6c8b6403be04d378ecd4ee0149b6fdd | validation | 722bf1f9 | 0.5 | 0.862736 | 140255 | 0 | 22315 | 0 | 162570 | 0.862736 | 0 | 0 | 0 | 0.400613 | 0.5 | 0.137264 |
| logistic_regression | validation | 737b3f235d1949e5a15552a9ce68d142 | b6cd84c99ba24a8f854b2b7941ee3b88 | m-9b48e925f4a54600a0eeeacf7eb183c1 | validation | 722bf1f9 | 0.5 | 0.862705 | 140241 | 14 | 22306 | 9 | 162570 | 0.862705 | 0.000403 | 0.391304 | 0.000806 | 0.384341 | 0.646231 | 0.21028 |
| random_forest | validation | 8dcf18dc8f7744c7950bb7c0e29fba88 | 9b8a327a8a694086819d1818c141ba76 | m-d5af0b19e25b4b169c0f5b3414373ad9 | validation | 722bf1f9 | 0.5 | 0.862736 | 140255 | 0 | 22315 | 0 | 162570 | 0.862736 | 0 | 0 | 0 | 0.384513 | 0.649133 | 0.213944 |
| hist_gradient_boosting | validation | 19d602239b3a43a595bcd17d8a39fc4a | 2bb4ea9b1159440bb0b51b66925247f3 | m-c0cd1df22fa24744b5d207306fd84ac1 | validation | 722bf1f9 | 0.5 | 0.862736 | 140255 | 0 | 22315 | 0 | 162570 | 0.862736 | 0 | 0 | 0 | 0.382348 | 0.653889 | 0.216483 |
| hist_gradient_boosting | exploratory_test | 0ba9fd0f56b8480f842795151fbfabb2 | 2bb4ea9b1159440bb0b51b66925247f3 | m-c0cd1df22fa24744b5d207306fd84ac1 | exploratory_test | 38c881ae | 0.5 | 0.851137 | 240894 | 0 | 42132 | 0 | 283026 | 0.851137 | 0 | 0 | 0 | 0.402502 | 0.65435 | 0.235027 |

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

The [native evaluation CSV](https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/assets/results/experiments/72061e0a7a1e4d68addcc79a2aae631d/mlflow_native_evaluations.csv)
and statistics section 19 contain all evaluation IDs and metrics. Run
`python scripts/06_log_mlflow_evaluations.py` to verify or repair an existing
completed comparison. Running it again reuses the completed repair and creates
no duplicate evaluation runs. Future training calls this logging step automatically.

These are classic ML classifier evaluations. MLflow's separate GenAI evaluation
datasets/scorers are not used for this loan-classification benchmark.

