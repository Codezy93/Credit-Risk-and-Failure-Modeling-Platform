"""Shared terminology for the resolved-loan classifier and loss illustrations."""

CLASSIFIER_TARGET = "Lifetime charge-off probability (resolved 36-month cohort)"

SCOPE_NOTE = """## Risk terminology and interpretation

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
"""

SCOPE_TAGS = {
    "risk_scope.classifier_target": CLASSIFIER_TARGET,
    "risk_scope.classifier_horizon": "lifetime outcome on resolved 36-month loans; not 12 months",
    "risk_scope.basel_pd_estimated": "false",
    "risk_scope.loss": "lifetime snapshot-loss proxy; not regulatory one-year EL",
    "risk_scope.capital": "illustrative assumed-one-year-PD sensitivity; no model-PD input",
}


def scope_description(existing=""):
    marker = "<!-- risk-terminology -->"
    original = existing.split(marker, 1)[0].rstrip()
    return original + "\n\n" + marker + "\n" + SCOPE_NOTE


def log_risk_scope():
    """Label new runs without changing predictions, parameters or metrics."""
    import mlflow

    mlflow.set_tags(SCOPE_TAGS)
    existing = mlflow.active_run().data.tags.get("mlflow.note.content", "")
    mlflow.set_tag("mlflow.note.content", scope_description(existing))
