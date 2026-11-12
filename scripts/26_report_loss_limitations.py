"""Describe saved loss-component results without refitting or rewriting them."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = ROOT / "assets/results/basel_loss_latest.json"
    manifest = json.loads(manifest_path.read_text())
    result_dir = ROOT / manifest["result_directory"]
    model_dir = ROOT / manifest["model_directory"]
    inputs = [manifest_path, *sorted(result_dir.glob("*.csv")), *sorted(model_dir.glob("*.joblib"))]
    before = {str(p.relative_to(ROOT)): digest(p) for p in inputs}
    for name, expected in manifest["results_sha256"].items():
        assert digest(result_dir / name) == expected, name
    for name, expected in manifest["model_sha256"].items():
        assert digest(model_dir / name) == expected, name
    metrics = pd.read_csv(result_dir / "component_metrics.csv")
    portfolio = pd.read_csv(result_dir / "portfolio_loss_metrics.csv")
    validation = metrics[metrics.split == "validation"].copy()
    constants = {}
    for component in ["ead", "lgd"]:
        model = joblib.load(model_dir / f"{component}_mean.joblib").named_steps["model"]
        assert model.strategy == "mean"
        constant = float(model.constant_.ravel()[0])
        recorded = metrics[(metrics.model == f"{component}_mean") & (metrics.split == "train")].iloc[0]
        assert abs(constant - recorded.observed_mean) < 1e-12
        constants[component] = constant
        baseline = validation[validation.model == f"{component}_mean"].iloc[0]
        mask = validation.component == component
        validation.loc[mask, "mae_improvement_over_mean_pct"] = (
            baseline.bounded_mae - validation.loc[mask, "bounded_mae"]) / baseline.bounded_mae * 100
    validation["selected"] = validation.apply(
        lambda row: manifest["selected_components"][row.component] == row.model, axis=1)
    assert manifest["selected_components"] == {"ead": "ead_boosting", "lgd": "lgd_mean"}, "Review the report narrative for the new selection."
    by_model = validation.set_index("model")
    training = metrics[metrics.split == "train"].set_index("model")
    selected = portfolio[portfolio.method == "selected_components"].iloc[0]
    baseline_portfolio = portfolio[portfolio.method == "mean_baseline"].iloc[0]
    lines = ["| Component | Predictor | Selected | Validation MAE | Validation R² | MAE improvement over training-mean baseline |",
        "| --- | --- | --- | --- | --- | --- |"]
    for row in validation.itertuples():
        label = "Snapshot EAD ratio" if row.component == "ead" else "Snapshot LGD"
        lines.append(f"| {label}" +
            f" | {row.model} | {'yes' if row.selected else 'no'} | {row.bounded_mae:.6f} | {row.bounded_r2:.6f} | {row.mae_improvement_over_mean_pct:.3f}% |")
    report = f'''# Loss-model limitations

Source batch: `{manifest['batch_run_id']}`. This is a reporting update based on
saved metrics and model constants; no models were fitted and no metric CSVs changed.

## What the selected components actually are

The selected LGD component is **a constant training-cohort loan-average snapshot
LGD of {constants['lgd']:.9f} ({constants['lgd']:.2%})**. It is a `DummyRegressor(strategy="mean")`,
not a borrower-specific severity model. The average is unweighted across the
{int(training.loc["lgd_mean", "rows"]):,} eligible charged-off training loans, not exposure-weighted. Every loan
receives this same predicted LGD.

The validation cohort's observed mean LGD is **{by_model.loc["lgd_mean", "observed_mean"]:.9f} ({by_model.loc["lgd_mean", "observed_mean"]:.2%})**. That is a
different statistic: it is not the constant fitted on the training cohort.

The mean EAD-ratio baseline similarly predicts the training mean,
**{constants['ead']:.9f} ({constants['ead']:.2%})**, rather than the observed validation mean
**{by_model.loc["ead_mean", "observed_mean"]:.9f} ({by_model.loc["ead_mean", "observed_mean"]:.2%})**. The selected EAD component is the boosting regressor,
not this constant baseline. Its validation average prediction is {by_model.loc["ead_boosting", "predicted_mean"]:.9f}.
All of these quantities are snapshot proxies, not event-time regulatory parameters.

## Validation against the mean baselines

Both components are evaluated on the same **{int(by_model.loc["ead_mean", "rows"]):,} eligible charged-off 2014 loans**.
Selection used bounded MAE on this already-explored cohort. MAE is measured in
fractions of the target, not dollars: 0.20 is about 20 percentage points.
Positive improvement means lower MAE than the corresponding training-mean baseline.

{chr(10).join(lines)}

EAD boosting reduces MAE by only about **{by_model.loc["ead_boosting", "mae_improvement_over_mean_pct"]:.2f}%** and explains approximately
**{by_model.loc["ead_boosting", "bounded_r2"]:.2%} of validation target variance** (R² = {by_model.loc["ead_boosting", "bounded_r2"]:.6f}). Its training R² is
{training.loc["ead_boosting", "bounded_r2"]:.6f}, so most of the apparent training fit does not carry into validation.
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

On the **{int(selected.rows):,} eligible validation loans**, selected components estimate
**${selected.expected_loss_proxy_total:,.2f}** against observed snapshot loss of
**${selected.observed_loss_proxy_total:,.2f}**: aggregate relative error
**{selected.portfolio_relative_error:.2%}**. The mean/mean baseline has a smaller aggregate
error (**{baseline_portfolio.portfolio_relative_error:.2%}**), despite slightly worse loan-level
dollar MAE (${baseline_portfolio.loan_dollar_mae:,.2f} versus ${selected.loan_dollar_mae:,.2f}).
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
'''
    (ROOT / "docs/loss_model_limitations.md").write_text(report)
    marker, end = "<!-- loss-limitations-statistics -->", "<!-- end-loss-limitations-statistics -->"
    statistics = ROOT / "assets/statistics.md"
    text = statistics.read_text()
    if marker in text:
        start, rest = text.split(marker, 1)
        _, tail = rest.split(end, 1)
        text = start + tail.lstrip("\n")
    statistics_report = report.replace("(risk_terminology.md)", "(../docs/risk_terminology.md)")
    statistics_report = statistics_report.replace("(basel_loss_experiment.md)", "(../docs/basel_loss_experiment.md)")
    section = marker + "\n" + statistics_report.replace("# Loss-model limitations", "## Loss-model limitations", 1)
    section += "\n" + end + "\n\n"
    position = text.index("<!-- current-experiment-refresh-statistics -->")
    statistics.write_text(text[:position] + section + text[position:])
    assert before == {str(p.relative_to(ROOT)): digest(p) for p in inputs}
    summary = {"status": "passed", "reported_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_loss_batch": manifest["batch_run_id"], "scope": "Reporting only; no model or metric changes",
        "training_mean_lgd": constants["lgd"], "training_mean_ead_ratio": constants["ead"],
        "selected_components": manifest["selected_components"],
        "validation_comparison": validation.to_dict(orient="records"),
        "portfolio_comparison": portfolio.to_dict(orient="records"),
        "input_sha256": before, "inputs_unchanged": True,
        "report_sha256": digest(ROOT / "docs/loss_model_limitations.md"),
        "script_sha256": digest(Path(__file__))}
    (ROOT / "assets/results/loss_model_limitations.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"Loss limitations reported; LGD constant {constants['lgd']:.9f}; saved evidence unchanged.")


if __name__ == "__main__":
    main()
