# AUC improvement experiments

Completed: 2026-11-08T16:44:45+00:00. MLflow experiment:
**lendingclub_auc_ablation**, parent run `709d47fa0d5348f391bdef42dbb6174c`.

## Result

The best independent-scope candidate reached **0.684553 validation ROC-AUC**,
compared with **0.653889** for the original histogram-boosting pipeline.
The separately scoped post-underwriting comparison reached
**0.691254**.
Independent-scope target 0.80 reached: **False**.
Post-underwriting target 0.80 reached: **False**.

No 2015 dataset was loaded or scored. The original selected model, its threshold,
and original experiment manifest are unchanged. These are validation candidates;
they are not newly measured test results or deployment-approved replacements.

## What changed

- XGBoost on the original 13 predictors separates the model-family effect from
  adding information. The expanded set adds 42 candidate credit-report fields
  and four deterministic ratios/flags. Training-only constants/all-missing fields
  are removed, as listed in the manifest.
- A separate post-underwriting set adds assigned grade, subgrade, and interest
  rate. Those incorporate existing underwriting; their score does not represent
  an independent pre-pricing application model.
- A bounded seven-trial search uses shallow, regularized, and deeper trees.
  Early stopping uses validation ROC-AUC with patience 60 and at most 1,200 trees.
  Both stopping and model comparison reuse 2014 validation, so the best validation
  number is subject to selection optimism. It is not an untouched estimate.
- Numeric missingness is retained for XGBoost. One-hot encoders learn categories
  only on training rows and ignore unknown labels. The fitted encoder and model
  are saved as one sklearn pipeline. There is no resampling, target relabeling,
  hard-loan deletion, or inclusion of payment/recovery/settlement/updated-FICO data.
- Cohorts remain 157,993 training loans (2011–2013) and 162,570 validation loans
  (2014), all 36-month, ordinary resolved outcomes. IDs and row order were checked
  against the original split metadata. Each trial has dataset-linked metrics,
  a native classifier evaluation, plots, and a 1,000-row evaluation preview in MLflow.

## Comparison

| trial | feature_set | scoring_point | run_id | model_uri | feature_count | max_depth | min_child_weight | reg_lambda | train_roc_auc | validation_roc_auc | train_average_precision | validation_average_precision | validation_brier_score | validation_log_loss | best_iteration | fit_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| post_underwriting_regularized | post_underwriting | post_underwriting | 488c69d6d6c84b7caeaa505f2d011c34 | models:/m-dec4faa7348d402482ce8335d4de9d0b | 61 | 5 | 100 | 20 | 0.733505 | 0.691254 | 0.296785 | 0.250611 | 0.112163 | 0.373518 | 430 | 81.206909 |
| post_underwriting_shallow | post_underwriting | post_underwriting | ed74c9ba21804b21bc46b3dcd916904b | models:/m-bb0f9341b64c46ad9b8902649a276d82 | 61 | 3 | 30 | 10 | 0.715804 | 0.690859 | 0.271854 | 0.250467 | 0.112224 | 0.373796 | 633 | 128.567778 |
| post_underwriting_deep | post_underwriting | post_underwriting | 70187acc73f84d67a7d17303cfb0a22d | models:/m-5b79dddaa3554956a4b709793f06cb4c | 61 | 7 | 100 | 30 | 0.75078 | 0.690816 | 0.322179 | 0.250383 | 0.112186 | 0.373662 | 324 | 64.001626 |
| expanded_bureau_deep | expanded_bureau | independent_risk_candidate | 57900240ac0240aba47094e6010aa0a3 | models:/m-db6a86fa5e74439ca0710b9bc43cca52 | 58 | 7 | 100 | 30 | 0.751578 | 0.684553 | 0.324037 | 0.244488 | 0.11245 | 0.374625 | 350 | 44.962758 |
| expanded_bureau_shallow | expanded_bureau | independent_risk_candidate | 6a20281cbf374e1d8265b1becf0f2626 | models:/m-eed7cf1743f643048889e6d971cba8a2 | 58 | 3 | 30 | 10 | 0.721208 | 0.683984 | 0.278409 | 0.244959 | 0.112478 | 0.374822 | 829 | 86.172015 |
| expanded_bureau_regularized | expanded_bureau | independent_risk_candidate | 2709a777e41d4fc2be69f91bbd5be0c1 | models:/m-2fcf39b1759849628e67843e707ebae3 | 58 | 5 | 100 | 20 | 0.733836 | 0.683864 | 0.296992 | 0.244796 | 0.112483 | 0.374803 | 454 | 53.83068 |
| base13_shallow | base13 | independent_risk_candidate | 50cc37c3ddd34b9b942b112c0b644cdd | models:/m-1cee12e712864cdbb3170a73e1ff3a33 | 13 | 3 | 30 | 10 | 0.678768 | 0.655817 | 0.229416 | 0.218011 | 0.114275 | 0.3819 | 549 | 23.194086 |

Training AUC can be much higher than validation AUC. Changing a probability
threshold affects confusion counts, not ROC-AUC; calibration also does not create
new ranking information. An arbitrary 0.80 is a goal, not a defensible promise.
No performance gains from a later-outcome feature would count as an improvement.

## Feature availability limits

The additional fields are bureau/snapshot candidates, not a source-certified
point-in-time contract. Earlier EDA conservatively left these fields out. Their
availability has now been recorded explicitly in a separate experiment audit;
the original dictionary and production-candidate contract were not silently changed.
Historical loan-listing SDK implementations contain many corresponding bureau
attributes, but that does not prove the exact collection/update time in this CSV.
Any apparent gain requires as-of verification before an application-time claim.
The pricing ablation additionally requires scoring after underwriting.

Source implementation evidence: [historical loan API model](https://pkg.go.dev/github.com/TONKPILS/LENDINGCLUB).
This is not an official LendingClub dictionary. Exact additional-field timing
remains unverified and is marked false in the manifest. The original benchmark
also remains resolved-loan, accepted-only and retrospective, not fixed-horizon
default probability or a historical deployment simulation.

## Reproduction and artifacts

Run `python scripts/07_improve_auc.py`. It executes SQL files 32–33 and never
reads the 2015 model split. Model selection is by validation ROC-AUC for this
experiment, distinct from the original AP-selected baseline. Each run archives
its parameters, versions, raw/clean hashes, feature sets, dataset hashes, pipeline
artifacts, metrics, and native evaluation records. No confidence interval or
protected-group fairness evaluation was computed.

[Latest manifest](../assets/results/auc_improvement_latest.json),
[feature/profile and comparison CSVs](../assets/results/auc_experiments/709d47fa0d5348f391bdef42dbb6174c/auc_comparison.csv),
[availability audit](../assets/results/auc_experiments/709d47fa0d5348f391bdef42dbb6174c/feature_availability.csv), and
[figure](../assets/figures/auc_experiments/709d47fa0d5348f391bdef42dbb6174c/auc_comparison.png).

XGBoost API references: [CPU installation](https://xgboost.readthedocs.io/en/stable/install.html)
and [Python API/early stopping](https://xgboost.readthedocs.io/en/stable/python/python_api.html).
