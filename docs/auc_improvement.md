# AUC improvement experiments

Completed: 2026-11-09T02:25:10+00:00. MLflow experiment:
**lendingclub_auc_ablation**, parent run `2d9a9d65b9004aa1ade7337465576f17`.

## Result

The best independent-scope candidate reached **0.683258 validation ROC-AUC**,
compared with **0.653889** for the original histogram-boosting pipeline.
The separately scoped post-underwriting comparison reached
**0.690065**.
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
  Protocol v2 fits stopping candidates on 2011–2012 and chooses their tree counts
  using **2013 only**, with patience 60 and at most 1,200 trees. Each encoder and
  classifier then refits from scratch on 2011–2013 using the frozen tree budget,
  with **no eval_set and no early stopping**. **2014 only compares candidates**.
  The earlier protocol reused 2014 for stopping; its archived results remain
  historical snapshots. This correction does not make the already-explored 2014
  cohort a fresh holdout or remove candidate-selection optimism.
- Numeric missingness is retained for XGBoost. One-hot encoders learn categories
  on 2011–2012 for stopping, then 2011–2013 for the fixed-budget refit, and ignore
  unknown labels. Candidate/constant-column decisions use final training rows
  only; no 2014 outcome enters those decisions. The fitted encoder and model
  are saved as one sklearn pipeline. There is no resampling, target relabeling,
  hard-loan deletion, or inclusion of payment/recovery/settlement/updated-FICO data.
- Cohorts remain 157,993 training loans (2011–2013) and 162,570 validation loans
  (2014), all 36-month, ordinary resolved outcomes. IDs and row order were checked
  against the original split metadata. Each trial has dataset-linked metrics,
  a native classifier evaluation, plots, and a 1,000-row evaluation preview in MLflow.

Inner fit: **57,571** loans (2011–2012). Stopping: **100,422** loans (2013).
The stopping set is included in the later refit and is not an independent final
evaluation. Full roles, every stopping iteration and the old/new protocol
comparison are saved in `temporal_roles.csv`, `stopping_learning_curves.csv` and
`protocol_comparison.csv`. The previous batch is `709d47fa0d5348f391bdef42dbb6174c`.

## Comparison

| trial | feature_set | scoring_point | run_id | model_uri | feature_count | max_depth | min_child_weight | reg_lambda | train_roc_auc | validation_roc_auc | train_average_precision | validation_average_precision | validation_brier_score | validation_log_loss | validation_gini | validation_ks | best_iteration | selected_estimators | stopping_2013_auc | fit_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| post_underwriting_shallow | post_underwriting | post_underwriting | 51f2c63878104a30a75964ee3f047c13 | models:/m-3bc4f16ab0f3460684c1b6812112a9d6 | 61 | 3 | 30 | 10 | 0.708713 | 0.690065 | 0.263211 | 0.24955 | 0.112306 | 0.374075 | 0.380131 | 0.279367 | 466 | 467 | 0.679069 | 145.740727 |
| post_underwriting_deep | post_underwriting | post_underwriting | 569f1fa286c54bfaafc892945b31c414 | models:/m-f16b8fe5cde24831997ad9eccc8b115a | 61 | 7 | 100 | 30 | 0.727874 | 0.68996 | 0.28838 | 0.249193 | 0.11233 | 0.374088 | 0.379921 | 0.277057 | 175 | 176 | 0.679411 | 53.641419 |
| post_underwriting_regularized | post_underwriting | post_underwriting | afc569464c7542bba6c290751ea7f06d | models:/m-2dc5b35647084769befdb002ee0425d1 | 61 | 5 | 100 | 20 | 0.71104 | 0.689326 | 0.266179 | 0.248583 | 0.112394 | 0.374325 | 0.378653 | 0.277141 | 191 | 192 | 0.679043 | 70.971681 |
| expanded_bureau_regularized | expanded_bureau | independent_risk_candidate | 09f50de76751430aa734180f514efbcb | models:/m-c62c25f1c59044f89da4509b49bbca23 | 58 | 5 | 100 | 20 | 0.72374 | 0.683258 | 0.283063 | 0.244568 | 0.112495 | 0.374871 | 0.366515 | 0.266477 | 334 | 335 | 0.67164 | 50.699564 |
| expanded_bureau_deep | expanded_bureau | independent_risk_candidate | 2b3a72e455e2482c8728e7fd9cfcd525 | models:/m-82d964be765a42f0be2d3fe4db452fea | 58 | 7 | 100 | 30 | 0.72878 | 0.68262 | 0.289768 | 0.243275 | 0.112548 | 0.375037 | 0.36524 | 0.267201 | 187 | 188 | 0.672002 | 33.954283 |
| expanded_bureau_shallow | expanded_bureau | independent_risk_candidate | a52ec036c0ec41b38acaf98081d83505 | models:/m-bca2a5b9c6194f2fa70b07ff6b8b6c3d | 58 | 3 | 30 | 10 | 0.705816 | 0.682039 | 0.259148 | 0.243372 | 0.112575 | 0.375211 | 0.364077 | 0.264744 | 421 | 422 | 0.672849 | 58.740758 |
| base13_shallow | base13 | independent_risk_candidate | 56ce404489974a1cbcbfbc0bd6e8e43f | models:/m-58dc71ca98c1494692b28bfd1b4990ba | 13 | 3 | 30 | 10 | 0.672629 | 0.654746 | 0.223609 | 0.217557 | 0.114318 | 0.382094 | 0.309492 | 0.22481 | 371 | 372 | 0.64582 | 21.435134 |

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

[Latest manifest](https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/assets/results/auc_improvement_latest.json),
[feature/profile and comparison CSVs](https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/assets/results/auc_experiments/2d9a9d65b9004aa1ade7337465576f17/auc_comparison.csv),
[availability audit](https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/assets/results/auc_experiments/2d9a9d65b9004aa1ade7337465576f17/feature_availability.csv), and
[figure](https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/assets/figures/auc_experiments/2d9a9d65b9004aa1ade7337465576f17/auc_comparison.png).

XGBoost API references: [CPU installation](https://xgboost.readthedocs.io/en/stable/install.html)
and [Python API/early stopping](https://xgboost.readthedocs.io/en/stable/python/python_api.html).
