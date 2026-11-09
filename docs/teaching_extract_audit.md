# External teaching extract: postcode audit

Measured on a public copy of `lending_club_loan_two.csv`: 396,030 rows, 27 columns, charged-off share 19.6129%, 10 postcodes. [Pinned source](https://raw.githubusercontent.com/dicksondurosakin/Loan-Prediction/9efa1b357ab5b4c10e96e4a49aace5364c2d682d/lending_club_loan_two.csv); SHA-256 `fb1dd172c4a3bbc9c2db55ea0863c266e76008e937ff970af89902ba65e140fb`. The reviewer supplied no file hash, so exact identity with their upload is unverified. No claim is made to have inspected their 120 notebook cells.

## What was tested

Postcodes are the final five digits of address, preserving leading zeros. The crosstab uses all rows as a descriptive audit. Postcode-only probabilities are learned on the training partition, then scored on the held-out partition.

The controlled XGBoost ablation uses an identical stratified random 80/20 split (seed 42), fixed 300-tree settings, and train-only imputation/one-hot encoding. It uses 14 numeric and 8 categorical origination/underwriting features, including grade and interest rate, with postcode as the sole additional column in the second model. Direct address, employment title, loan title and outcome fields are excluded from predictors. Employment length and credit-history age are derived deterministically. There is no early stopping or tuning on the holdout.

This is a diagnostic of this teaching extract, not a reproduction of the unseen notebook's XGBoost settings or an estimate of how much of its exact 0.905 result is caused by postcode. A strong target association does not reveal how the added addresses were constructed. It does make this postcode-based result unsuitable as a real-world benchmark for the project.

## postcode status counts

| audit_postcode | Charged Off | Fully Paid | rows | charged_off_rate |
| --- | --- | --- | --- | --- |
| 00813 | 0 | 45824 | 45824 | 0 |
| 05113 | 0 | 45402 | 45402 | 0 |
| 11650 | 11226 | 0 | 11226 | 1 |
| 22690 | 10954 | 45573 | 56527 | 0.193784 |
| 29597 | 0 | 45471 | 45471 | 0 |
| 30723 | 11021 | 45525 | 56546 | 0.194903 |
| 48052 | 11192 | 44725 | 55917 | 0.200154 |
| 70466 | 11148 | 45837 | 56985 | 0.19563 |
| 86630 | 10981 | 0 | 10981 | 1 |
| 93700 | 11151 | 0 | 11151 | 1 |

## score comparison

| model | rows | observed_positive_rate | mean_predicted_probability | threshold | roc_auc | gini | ks | average_precision | brier_score | log_loss | ece_10_uniform_bins | accuracy | balanced_accuracy | precision | recall | specificity | f1 | predicted_positive_rate | tn | fp | fn | tp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| postcode_rate_only | 79206 | 0.196134 | 0.197386 | 0.5 | 0.839645 | 0.67929 | 0.43958 | 0.648067 | 0.089547 | 0.281644 | 0.001252 | 0.888847 | 0.71664 | 1 | 0.43328 | 1 | 0.604599 | 0.084981 | 63671 | 0 | 8804 | 6731 |
| xgboost_without_postcode | 79206 | 0.196134 | 0.196134 | 0.5 | 0.720239 | 0.440477 | 0.325019 | 0.388707 | 0.141352 | 0.444722 | 0.004106 | 0.807628 | 0.529252 | 0.577847 | 0.071194 | 0.98731 | 0.126769 | 0.024165 | 62863 | 808 | 14429 | 1106 |
| xgboost_with_postcode | 79206 | 0.196134 | 0.196947 | 0.5 | 0.907122 | 0.814244 | 0.606579 | 0.782005 | 0.080906 | 0.255262 | 0.004119 | 0.890526 | 0.727953 | 0.961166 | 0.460444 | 0.995461 | 0.622623 | 0.093958 | 63382 | 289 | 8382 | 7153 |

## schema comparison

| teaching_column | present_in_project_source |
| --- | --- |
| loan_amnt | True |
| term | True |
| int_rate | True |
| installment | True |
| grade | True |
| sub_grade | True |
| emp_title | True |
| emp_length | True |
| home_ownership | True |
| annual_inc | True |
| verification_status | True |
| issue_d | True |
| loan_status | True |
| purpose | True |
| title | True |
| dti | True |
| earliest_cr_line | True |
| open_acc | True |
| pub_rec | True |
| revol_bal | True |
| revol_util | True |
| total_acc | True |
| initial_list_status | True |
| application_type | True |
| mort_acc | True |
| pub_rec_bankruptcies | True |
| address | False |

## native evaluations

| model | split | evaluation_run_id | source_training_run_id | model_id | dataset_name | dataset_digest | decision_threshold | score | true_negatives | false_positives | false_negatives | true_positives | example_count | accuracy_score | recall_score | precision_score | f1_score | log_loss | roc_auc | precision_recall_auc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| xgboost_without_postcode | test | 6c02d1d5eb184624a1aa6feaec9b4880 | 02f4d580e39c467ca47c888ed4b83e09 | m-06e0fff21f1747cfb89feb0ff3ea782c | teaching_xgboost_without_postcode_test | ae8b3401 | 0.5 | 0.807628 | 62863 | 808 | 14429 | 1106 | 79206 | 0.807628 | 0.071194 | 0.577847 | 0.126769 | 0.444722 | 0.720239 | 0.388707 |
| xgboost_with_postcode | test | ca1230c0f32e45c1aecb10de535e4ed4 | d73edd725dd14614811de8857e5fb20e | m-35ba9182295f4d74affb97a3afa6bb46 | teaching_xgboost_with_postcode_test | 7c66283d | 0.5 | 0.890526 | 63382 | 289 | 8382 | 7153 | 79206 | 0.890526 | 0.460444 | 0.961166 | 0.622623 | 0.255262 | 0.907122 | 0.782005 |

## Corrections to the comparison

Our all-status charged-off share is 11.8796%, but among ordinary Fully Paid/Charged Off loans it is 19.9626%, comparable in population definition to this teaching file's resolved-only share. The project model cohorts still differ: 2014 validation is 13.7264% charged off and exploratory 2015 is 14.8863%. Comparing a resolved-only share against all statuses is misleading.

ROC-AUC computed on hard 0/1 predictions is mathematically defined and equals balanced accuracy for a binary decision rule. It is not the probability-score ranking AUC used by our experiments. The earlier 0.6913 research result was also selection-influenced: 2014 was reused for early stopping and candidate selection. Only the original selected model has the separately reported 2015 exploratory AUC of 0.6544. No fresh-holdout claim is appropriate.

The current project data, feature policy, model artifacts, and model selection remain unchanged. The downloaded teaching file and audit model/data artifacts are ignored by Git. MLflow experiment: `lendingclub_teaching_extract_audit`, batch `6191324074c14b32a83b0430e4c16078`.

[Scikit-learn score-based ROC-AUC documentation](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.roc_auc_score.html).

## Reproduce this isolated audit

The teaching CSV stays separate from the accepted-loans project data. Restore the pinned public copy and its download record, then run the audit in the locked environment:

```python
import json
from pathlib import Path
from urllib.request import urlretrieve

m = json.loads(Path("assets/results/teaching_extract_audit_latest.json").read_text())
folder = Path("data/raw/teaching_extract")
folder.mkdir(parents=True, exist_ok=True)
urlretrieve(m["source"]["url"], folder / "lending_club_loan_two.csv")
(folder / "source.json").write_text(json.dumps(m["source"]))
```

Run `.venv-locked/bin/python scripts/12_audit_teaching_extract.py`. The script verifies the source hash before fitting. It is intentionally excluded from the core modelling workflow.

[Verification record](../assets/results/teaching_extract_audit_verification.json) checks the full holdout predictions, source/model/result hashes, finished native MLflow evaluations and unchanged incumbent. The existing 85-test suite also passes.

The earlier XGBoost protocol has since been superseded by the [temporal stopping review](validation_gaps.md): stopping uses 2013, comparison uses 2014, and the current post-underwriting research AUC is 0.690065. The teaching-data audit numbers above remain unchanged.
