"""Data-boundary checks that remain active when Python assertions are disabled."""

import pandas as pd


def validate_periods(periods):
    """Check ordered, disjoint loan-ID/date populations in insertion order."""
    seen = set()
    previous_end = None
    for name, frame in periods.items():
        if frame.empty:
            raise ValueError(f"Empty period: {name}")
        if frame.loan_id.isna().any() or frame.loan_id.duplicated().any():
            raise ValueError(f"Missing or duplicate loan IDs in {name}")
        ids = set(frame.loan_id)
        if seen.intersection(ids):
            raise ValueError(f"Loan IDs overlap across periods: {name}")
        dates = pd.to_datetime(frame.issue_date, errors="raise")
        if dates.isna().any():
            raise ValueError(f"Missing issue dates in {name}")
        if previous_end is not None and dates.min() <= previous_end:
            raise ValueError(f"Overlapping or reversed issue dates: {name}")
        previous_end = dates.max()
        seen.update(ids)


def validate_model_population(frame):
    names = ["train", "validation", "exploratory_test"]
    if set(frame.split) != set(names):
        raise ValueError("The model population must contain exactly the three declared splits.")
    if frame.charged_off.isna().any() or not frame.charged_off.isin([0, 1]).all():
        raise ValueError("Model labels must be nonmissing binary outcomes.")
    expected = frame.loan_status.map({"Fully Paid": 0, "Charged Off": 1})
    if expected.isna().any() or not (expected == frame.charged_off).all():
        raise ValueError("A label contradicts the exact resolved-loan target definition.")
    years = pd.to_datetime(frame.issue_date).dt.year
    declared = years.map({2011: "train", 2012: "train", 2013: "train",
                          2014: "validation", 2015: "exploratory_test"})
    if declared.isna().any() or not (declared == frame.split).all():
        raise ValueError("A row violates the declared temporal split.")
    validate_periods({name: frame[frame.split == name] for name in names})
