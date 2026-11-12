# Risk terminology

## Classification target

The classifier estimates **lifetime charge-off probability (resolved 36-month
cohort)**. The positive label is `Charged Off`; the negative label is
`Fully Paid`. Other statuses are excluded, including `Default` and late statuses.
The model population is accepted, resolved 36-month loans from the documented
issue-year windows. Sixty-month loans are outside this benchmark.

This is a conditional final-outcome probability, not an unconditional forecast
for every accepted loan. It is not a 12-month probability, a 90-days-past-due
target, or a Basel default probability. The nominal 36-month term does not give
every loan an identical observed outcome horizon: loans can prepay and final
resolution can occur at different times.

ROC-AUC, average precision and calibration diagnostics in the classification
reports refer to this target. Changing its name does not change any metric.

## Snapshot loss proxies

| Name in this project | Meaning | Important limitation |
| --- | --- | --- |
| Snapshot EAD proxy | Funded principal minus principal received, measured from the extract | Not exposure observed at the default event |
| Snapshot EAD ratio | Snapshot EAD divided by funded amount | Retrospective target, modelled on eligible charged-off loans |
| Snapshot LGD proxy | One minus net recoveries divided by snapshot EAD | Not discounted economic LGD; recovery dates and indirect costs are unavailable |
| Lifetime snapshot-loss proxy | Lifetime charge-off score × predicted snapshot LGD × predicted snapshot EAD | Not regulatory one-year expected loss |

The loss composition multiplies conditional means and ignores residual dependence
between exposure and loss severity. It is compared with realised snapshot loss
on the same eligible retrospective portfolio. That comparison does not validate
a forward-looking regulatory expected-loss model.

The selected LGD component is a training-mean baseline. The EAD regressor has
little explanatory power. Their labels describe the quantities being
approximated, not evidence of strong predictive performance. See the
[component results](basel_loss_experiment.md) and
[loss-model limitations](loss_model_limitations.md), which distinguish the fitted
training mean from the validation observed mean.

## Illustrative capital scenarios

The other-retail risk-weight function takes an **assumed one-year PD**. The
portfolio scenarios use 1%, 3% and 5%; the sensitivity grid also includes 0.5%.
These inputs are assumptions, not predictions from the charge-off classifier.
Capital and RWA outputs are illustrative sensitivities, not measured regulatory
requirements. Retail eligibility and the documented regulatory adjustments
remain outside the experiment.

The approximation `1 - (1 - p_lifetime) ** (1 / 3)` assumes constant annual
hazard over three years. It does not fix the different default definition,
resolved-loan selection or outcome timing. This project does not use it to
convert its scores into validated one-year PDs.

## Legacy names and historical evidence

Identifiers such as `pd_model`, `pd_score_resolved_outcome`, `ann_pd`,
`expected_loss_proxy`, `util.basel` and `lendingclub_basel_loss_proxies` remain
for compatibility. In classifier artifacts, `PD` is a legacy name for the
lifetime charge-off score. In capital scenario tables, `pd_one_year_assumed`
means the separate assumed annual input.

Historical manifests, metrics and logged report artifacts retain their
execution-time wording and fingerprints. Current documentation and additive
MLflow scope tags/descriptions clarify their interpretation; the terminology-only annotations do not
represent a retraining or re-evaluation. A separate [experiment refresh](experiment_refresh.md)
now records new run IDs and fresh artifacts. The 2015 sample remains exploratory.

The three EDA HTML exports retain their saved outputs and carry a terminology
notice. Their updated Python notebook sources include the scope clarification.
The model-review HTML is re-exported from the updated source using saved result
files; it does not refit models.

To annotate an existing local MLflow database, run:

```bash
.venv-locked/bin/python scripts/24_update_risk_terminology.py
```

The script updates experiment/run descriptions and `risk_scope.*` tags, and
verifies that run metrics, parameters, status/times, result CSVs, latest stage
manifests and model binaries remain unchanged. It writes a verification record
under `assets/results/`. New runs receive the same scope labels automatically.
