# Validation gap review

Snapshot: 2026-11-09T02:27:57.619270+00:00.

The implementation gaps in stopping/selection separation and coefficient diagnostics have been addressed. This does not certify a deployment or regulatory model. The incumbent histogram-boosting artifact and its previously recorded 2015 exploratory metrics remain unchanged.

## XGBoost stopping and selection

Protocol v2 uses 57,571 loans from 2011–2012 for the stopping fit and 100,422 loans from 2013 to choose each tree budget. It then refits each encoder and model on all 157,993 training loans for the frozen number of trees, with no eval_set or early stopping. The 162,570 loans from 2014 compare candidates only. Numeric missingness is retained; learned category encoding uses only the relevant fit population.

Best current expanded-bureau AUC: **0.683258**. Separately scoped post-underwriting AUC: **0.690065**. Neither replaces the incumbent. The 2014 cohort remains previously explored selection data, so this fixes a reuse mechanism rather than creating a fresh holdout. Seven models and seven native evaluations are archived in batch `2d9a9d65b9004aa1ade7337465576f17`.

[Full XGBoost report](auc_improvement.md) includes all stopping curves, dataset roles, frozen tree budgets, old/new protocol comparisons, model/source hashes and availability caveats.

## Negative logistic coefficients

The univariate coefficients are positive for both questioned features, while the full adjusted coefficients are negative. Adjusted signs change across years: delinquency is positive in 2011 and negative in 2012–2013; bankruptcies are positive in 2011–2012 and negative in 2013. The pooled conditional effects are mostly stable under within-year/outcome bootstrap resampling. These findings are consistent with conditioning and cohort composition, but do not identify a causal mechanism.

| feature | point_coefficient | estimable_resamples | median | lower_95 | upper_95 | negative_fraction | positive_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- |
| delinq_2yrs | -0.018985 | 200 | -0.019517 | -0.034436 | -0.004122 | 0.985 | 0.015 |
| pub_rec_bankruptcies | -0.043006 | 200 | -0.043608 | -0.055997 | -0.027713 | 1 | 0 |

The review refitted the entire preprocessing/model pipeline in each of 200 bootstrap samples. Intervals condition on the observed year/class counts, exclude repeat-borrower/macro/model-selection uncertainty and are not classical unpenalized coefficient tests.

| model | roc_auc | average_precision | brier_score |
| --- | --- | --- | --- |
| full_reference_refit | 0.646231 | 0.21028 | 0.114869 |
| drop_delinq | 0.646438 | 0.21039 | 0.114856 |
| drop_bankruptcies | 0.646646 | 0.210386 | 0.114846 |
| drop_both | 0.646776 | 0.210494 | 0.114838 |

| comparison | point_difference | lower_95 | upper_95 |
| --- | --- | --- | --- |
| drop_both_minus_full_logistic | 0.000545 | 0.000061 | 0.000995 |

The small improvement after removing both is an exploratory logistic challenger result, not a reason to alter the incumbent boosting model. Retain the original logistic model as a documented historical baseline. Do not describe it as a WoE scorecard or interpret negative adverse-history coefficients as protective effects. A monotonic lending scorecard would require separate constraints and validation.

[Coefficient report](coefficient_validation.md), batch `da3c8ad1bee14f60ac5156def8b04b14`, contains univariate comparisons, year-specific fits, all 200 resamples, pooled/year/FICO outcome buckets, correlations, four removal variants, native evaluations and paired uncertainty.

## Data and capital limits that remain

| item | status | finding |
| --- | --- | --- |
| target | limitation | Charged-off versus fully-paid among resolved 36-month accepted loans; no fixed one-year default horizon. |
| test | limitation | 2015 was previously explored and is not read in this review; no fresh holdout exists. |
| label timing | limitation | Snapshot training labels may not have been known at later origination dates; not a point-in-time backtest. |
| bureau timing | limitation | Added bureau-field collection/update times remain uncertified; expanded results are research only. |
| logistic interpretation | reviewed | Year, bootstrap, univariate and removal checks recorded; negative conditional coefficients are not causal protective effects or scorecard approval. |
| loss targets | proxy only | EAD is residual snapshot principal; LGD uses snapshot net recoveries without event-time/discounted economic-loss validation. |
| capital | illustrative only | Capital uses assumed one-year PD scenarios; no regulatory floors, buffers, downturn-LGD validation or compliance claim. |

The EAD/LGD/expected-loss reports and model-review notebook use the same proxy terminology. Capital/RWA calculations consume assumed one-year PD scenarios, not the resolved-loan classifier score. No regulatory validation or approval is claimed. These limits require additional data and evidence; changing a label or intercept would not resolve them.

## Reproduce

Run `make review` after core preparation/training. This runs the test suite, corrected seven-trial XGBoost search, coefficient review and model-review HTML export. No 2015 rows are read by these review scripts. The reports and `assets/statistics.md` retain earlier stage snapshots.

## Verification

93 tests passed. All seven saved XGBoost tree budgets, source/data/result/model hashes, eleven full logged-model prediction checks and native evaluations, bootstrap summaries and notebook output were verified. [Machine-readable evidence](../assets/results/validation_gaps_verification.json).
