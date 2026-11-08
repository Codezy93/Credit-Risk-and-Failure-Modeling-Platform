import pandas as pd
import pytest

from util.validation import validate_model_population, validate_periods


def population():
    return pd.DataFrame({"loan_id": [1, 2, 3],
        "issue_date": pd.to_datetime(["2012-01-01", "2014-01-01", "2015-01-01"]),
        "loan_status": ["Fully Paid", "Charged Off", "Fully Paid"],
        "charged_off": [0, 1, 0], "split": ["train", "validation", "exploratory_test"]})


def test_valid_population_passes():
    validate_model_population(population())


@pytest.mark.parametrize("change", ["duplicate_id", "wrong_label", "wrong_split", "missing_label"])
def test_invalid_population_fails_before_export(change):
    frame = population()
    if change == "duplicate_id":
        frame.loc[1, "loan_id"] = 1
    elif change == "wrong_label":
        frame.loc[0, "charged_off"] = 1
    elif change == "wrong_split":
        frame.loc[2, "split"] = "validation"
    else:
        frame.loc[0, "charged_off"] = float("nan")
    with pytest.raises(ValueError):
        validate_model_population(frame)


def test_periods_reject_overlapping_ids_and_reversed_dates():
    frame = population()
    with pytest.raises(ValueError):
        validate_periods({"fit": frame.iloc[:1], "calibrate": frame.iloc[:1]})
    with pytest.raises(ValueError):
        validate_periods({"fit": frame.iloc[1:2], "calibrate": frame.iloc[:1]})
