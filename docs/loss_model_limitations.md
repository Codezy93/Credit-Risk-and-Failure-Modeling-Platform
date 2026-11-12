# Loss-model limitations

Source batch: `bc7fbb6777cd4365b1a93a4d97fd872f`. This is a reporting update based on
saved metrics and model constants; no models were fitted and no metric CSVs changed.

## What the selected components actually are

The selected LGD component is **a constant training-cohort loan-average snapshot
LGD of 0.893671383 (89.37%)**. It is a `DummyRegressor(strategy="mean")`,
not a borrower-specific severity model. The average is unweighted across the
19,757 eligible charged-off training loans, not exposure-weighted. Every loan
receives this same predicted LGD.

The validation cohort's observed mean LGD is **0.888369323 (88.84%)**. That is a
different statistic: it is not the constant fitted on the training cohort.

The mean EAD-ratio baseline similarly predicts the training mean,
**0.581647648 (58.16%)**, rather than the observed validation mean
**0.570638717 (57.06%)**. The selected EAD component is the boosting regressor,
not this constant baseline. Its validation average prediction is 0.582186573.
All of these quantities are snapshot proxies, not event-time regulatory parameters.

## Validation against the mean baselines

Both components are evaluated on the same **22,308 eligible charged-off 2014 loans**.
Selection used bounded MAE on this already-explored cohort. MAE is measured in
fractions of the target, not dollars: 0.20 is about 20 percentage points.
Positive improvement means lower MAE than the corresponding training-mean baseline.

| Component | Predictor | Selected | Validation MAE | Validation R² | MAE improvement over training-mean baseline |
| --- | --- | --- | --- | --- | --- |
| Snapshot EAD ratio | ead_mean | no | 0.203347 | -0.002078 | 0.000% |
| Snapshot EAD ratio | ead_boosting | yes | 0.202030 | 0.004710 | 0.648% |
| Snapshot LGD | lgd_mean | yes | 0.075857 | -0.001920 | 0.000% |
| Snapshot LGD | lgd_boosting | no | 0.076627 | -0.001047 | -1.014% |

EAD boosting reduces MAE by only about **0.65%** and explains approximately
**0.47% of validation target variance** (R² = 0.004710). Its training R² is
0.081607, so most of the apparent training fit does not carry into validation.
This is little demonstrated loan-level exposure information.

LGD boosting has **worse MAE** than the mean baseline, so the constant is selected.
Its R² is slightly less negative than the constant's, but both are below zero.
R² uses the validation cohort's own observed mean as its reference; a constant
learned from training can therefore have negative validation R². These diagnostics
do not establish useful borrower-level severity discrimination. No confidence
interval or independent selection cohort establishes that the small EAD gain is robust.

## Consequences for expected loss

The lifetime snapshot-loss proxy multiplies the lifetime charge-off score,
predicted snapshot EAD and predicted snapshot LGD. A constant LGD means it has
**no borrower-specific severity differentiation**; variation comes from the
classifier, weak EAD predictions and funded-amount exposure scaling.

On the **162,563 eligible validation loans**, selected components estimate
**$132,522,640.71** against observed snapshot loss of
**$136,945,537.92**: aggregate relative error
**-3.23%**. The mean/mean baseline has a smaller aggregate
error (**-2.44%**), despite slightly worse loan-level
dollar MAE ($1,397.95 versus $1,389.34).
Component MAE selection does not guarantee portfolio-total calibration.
Aggregate error can conceal offsetting loan-level errors; it is not evidence of
accurate individual loss forecasts.

Classifier calibration error, weak EAD prediction and constant LGD all constrain
the composition. Multiplying conditional means also ignores residual EAD/LGD
dependence. Selection and evaluation share 2014, and recovery maturity, discounting,
indirect costs and default-event exposure are unavailable. There is no validated
one-year expected-loss or regulatory-capital estimate here. Capital panels remain
assumed-one-year-PD sensitivities using these uncertain loss-proxy inputs.

The supported description is **a lifetime snapshot-loss illustration with a
training-average LGD baseline and a weak EAD-ratio regressor**. See
[risk terminology](risk_terminology.md) and the [full loss report](basel_loss_experiment.md).
