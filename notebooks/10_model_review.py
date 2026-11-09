"""Read measured results and explore the PD/loss/capital handoff in marimo."""

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import json
    from pathlib import Path
    import duckdb
    import marimo as mo
    import pandas as pd
    return Path, duckdb, json, mo, pd


@app.cell
def _(mo):
    mo.md("""
    # PD, loss modelling and illustrative capital

    Here I read completed experiments rather than fitting models each time the
    notebook opens. The 13 PD inputs remain unchanged. Later payment/recovery
    fields are used only to construct separate loss targets and diagnostics.

    The classification target is charged-off versus fully-paid among resolved
    36-month loans. It is not an observed one-year Basel default target. EAD/LGD
    are snapshot proxies; the capital panels use explicit assumed one-year PDs.
    """)
    return


@app.cell
def _(Path, json, pd):
    root = Path(__file__).resolve().parents[1]
    validation_manifest = json.loads((root / "assets/results/validation_hardening_latest.json").read_text())
    loss_manifest = json.loads((root / "assets/results/basel_loss_latest.json").read_text())
    validation_dir = root / validation_manifest["result_directory"]
    loss_dir = root / loss_manifest["result_directory"]
    component_metrics = pd.read_csv(loss_dir / "component_metrics.csv")
    return component_metrics, loss_dir, loss_manifest, root, validation_dir, validation_manifest


@app.cell
def _(mo, pd, root, validation_dir, validation_manifest):
    mo.vstack([
        mo.md(f"""## What did the PD experiment actually show?

        Batch `{validation_manifest['batch_run_id']}`. Bootstrap intervals describe
        fitted models on the observed 2014 cohort and exclude selection uncertainty.
        Calibration fits base models on 2011–2012 and the sigmoid on 2013; both
        versions are evaluated on 2014. Compare Brier, log loss and ECE together.
        """),
        mo.ui.table(pd.read_csv(validation_dir / "auc_confidence_intervals.csv")),
        mo.ui.table(pd.read_csv(validation_dir / "calibration_metrics.csv")),
        mo.image(root / validation_manifest["figure_directory"] / "calibration.png")
    ])
    return


@app.cell
def _(loss_dir, mo, pd):
    mo.vstack([mo.md("""## First check the loss population

    EAD proxy = funded − principal received. LGD proxy = 1 − net recoveries / EAD.
    Only charged-off loans train loss components. Zero denominators, missing
    inputs and out-of-range bounded targets are counted and excluded. Recovery
    above residual principal produces negative LGD and is quarantined, not clipped.
    The portfolio comparison uses the same eligible set for expected and observed loss.
    """), mo.ui.table(pd.read_csv(loss_dir / "loss_audit.csv"))])
    return


@app.cell
def _(component_metrics, duckdb, mo, root):
    _con = duckdb.connect()
    _con.register("component_metrics", component_metrics)
    _summary = _con.execute((root / "sql/36_notebook_loss_summary.sql").read_text()).df()
    _con.close()
    mo.vstack([mo.md("""## Do the loss models beat a mean baseline?

    These models fit on eligible 2011–2013 defaults and use 2014 for component
    selection by bounded MAE. A low R² is a useful result: extra model complexity
    may add little conditional severity information. Raw and bounded metrics,
    including any clipped predictions, are retained in the result CSV.
    """), mo.ui.table(_summary)])
    return


@app.cell
def _(loss_dir, loss_manifest, mo, pd, root):
    mo.vstack([mo.md("""## Combine PD × LGD × EAD

    EAD is predicted as funded amount × predicted EAD ratio. This expected-loss
    proxy multiplies conditional means and ignores residual EAD/LGD dependence.
    Compare it with snapshot loss on the eligible 2014 portfolio. Selection and
    evaluation share 2014, so these are retrospective research results.
    """), mo.ui.table(pd.read_csv(loss_dir / "portfolio_loss_metrics.csv")),
        mo.ui.table(pd.read_csv(loss_dir / "pd_unchanged_check.csv")),
        mo.image(root / loss_manifest["figure_directory"] / "loss_targets.png"),
        mo.image(root / loss_manifest["figure_directory"] / "loss_and_capital.png")])
    return


@app.cell
def _(loss_dir, loss_manifest, mo, pd):
    mo.vstack([mo.md(f"""## Capital sensitivity, with explicit assumptions

    Batch `{loss_manifest['batch_run_id']}`. The other-retail IRB function uses
    assumed one-year PDs and modelled loss proxies. These are scenario inputs,
    not annualised classifier predictions. Regulatory floors, buffers, provisions,
    downturn-LGD validation and retail eligibility approval are outside this demo.

    [BIS CRE31.16](https://www.bis.org/committees/bcbs/basel-framework/standard/cre/31/inforce/2023-01-01/published/2020-03-27)
    supplies the risk-weight function. Economic LGD also requires recovery timing,
    discounting and costs that this snapshot cannot fully supply.
    """), mo.ui.table(pd.read_csv(loss_dir / "capital_sensitivity.csv")),
        mo.ui.table(pd.read_csv(loss_dir / "portfolio_capital_scenarios.csv"))])
    return


@app.cell
def _(json, mo, pd, root):
    _ann_path = root / "assets/results/ann_experiments_latest.json"
    if _ann_path.exists():
        _ann_manifest = json.loads(_ann_path.read_text())
        _ann_results = root / _ann_manifest["result_directory"]
        _ann_output = mo.vstack([mo.md(f"""## ANN challengers

        Batch `{_ann_manifest['batch_run_id']}` compares two multilayer-perceptron
        classifiers and ANN EAD/LGD regressors using the same 13 predictors.
        Epoch selection fits on 2011–2012 and stops on 2013. The networks then
        refit on 2011–2013 for a fixed epoch budget before the 2014 comparison.
        2014 selects the ANN candidate, so it remains a research selection cohort.
        No 2015 rows or incumbent replacement are involved. Capital assumptions
        and the snapshot-loss limitations remain unchanged.
        """), mo.ui.table(pd.read_csv(_ann_results / "pd_comparison.csv")),
            mo.ui.table(pd.read_csv(_ann_results / "loss_comparison.csv")),
            mo.ui.table(pd.read_csv(_ann_results / "portfolio_loss_comparison.csv")),
            mo.ui.table(pd.read_csv(_ann_results / "dataset_roles.csv")),
            mo.image(root / _ann_manifest["figure_directory"] / "temporal_learning_curves.png"),
            mo.image(root / _ann_manifest["figure_directory"] / "ann_comparison.png")])
    else:
        _ann_output = mo.md("## ANN challengers\n\nRun `make ann` to generate neural-network comparisons.")
    _ann_output
    return


@app.cell
def _(json, mo, pd, root):
    _auc_path = root / "assets/results/auc_improvement_latest.json"
    if _auc_path.exists():
        _auc_manifest = json.loads(_auc_path.read_text())
        _auc_results = root / _auc_manifest["result_directory"]
        _protocol = _auc_manifest.get("protocol_version", 1)
        _auc_note = ("Protocol v2: fit 2011–2012, choose the tree count on 2013, then refit 2011–2013 "
            "with that count frozen and no eval_set. 2014 compares candidates only."
            if _protocol == 2 else "Historical protocol: 2014 was reused for stopping and selection.")
        _auc_items = [mo.md(f"""## XGBoost validation protocol

        {_auc_note}

        Batch `{_auc_manifest['batch_run_id']}`. These remain research estimates on
        previously explored cohorts. Added bureau timestamps remain uncertified;
        grade, subgrade and interest rate apply after underwriting. The incumbent
        and 2015 exploratory results are unchanged.
        """), mo.ui.table(pd.read_csv(_auc_results / "auc_comparison.csv"))]
        if _protocol == 2:
            _auc_items += [mo.ui.table(pd.read_csv(_auc_results / "temporal_roles.csv")),
                          mo.ui.table(pd.read_csv(_auc_results / "protocol_comparison.csv"))]
        _auc_output = mo.vstack(_auc_items)
    else:
        _auc_output = mo.md("## XGBoost validation protocol\n\nRun `make auc` to generate the comparison.")
    _auc_output
    return


@app.cell
def _(json, mo, pd, root):
    _review_path = root / "assets/results/validation_review_latest.json"
    if _review_path.exists():
        _review_manifest = json.loads(_review_path.read_text())
        _review_results = root / _review_manifest["result_directory"]
        _year_coefficients = pd.read_csv(_review_results / "year_coefficients.csv")
        _review_output = mo.vstack([mo.md(f"""## Logistic signs and remaining limitations

        Batch `{_review_manifest['batch_run_id']}` uses training-only yearly fits,
        univariate checks, and {_review_manifest['bootstrap_resamples']} bootstrap
        refits stratified by issue year and outcome. Every bootstrap refits learned
        preprocessing. Intervals condition on the observed year/class counts.

        Negative coefficients describe adjusted associations in this accepted,
        resolved population; they do not establish protective effects of adverse
        credit events. This logistic baseline is not a monotonic WoE scorecard.
        Feature-removal variants are compared on 2014 without promoting a model.
        """), mo.ui.table(pd.read_csv(_review_results / "univariate_vs_adjusted.csv")),
            mo.ui.table(pd.read_csv(_review_results / "coefficient_summary.csv")),
            mo.ui.table(_year_coefficients[_year_coefficients.feature.isin(["delinq_2yrs", "pub_rec_bankruptcies"])]),
            mo.ui.table(pd.read_csv(_review_results / "ablation_metrics.csv")),
            mo.ui.table(pd.read_csv(_review_results / "ablation_auc_interval.csv")),
            mo.image(root / _review_manifest["figure_directory"] / "coefficient_stability.png"),
            mo.md("### What this work still cannot establish"),
            mo.ui.table(pd.read_csv(_review_results / "limitations.csv"))])
    else:
        _review_output = mo.md("## Logistic signs\n\nRun `make review` for coefficient diagnostics and validation review.")
    _review_output
    return


if __name__ == "__main__":
    app.run()
