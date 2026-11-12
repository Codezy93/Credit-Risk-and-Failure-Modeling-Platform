import pandas as pd
import pytest

from util.bureau_review import chronological_fold


def population():
    years = [2011, 2012, 2013, 2014, 2015]
    return pd.DataFrame([{"loan_id": year * 10 + outcome, "issue_year": year,
        "issue_date": f"{year}-01-01", "charged_off": outcome} for year in years for outcome in [0, 1]])


def test_research_fold_never_trains_on_evaluation_or_later_years():
    for year in [2013, 2014, 2015]:
        train, evaluation = chronological_fold(population(), year)
        assert set(train.issue_year) == set(range(2011, year))
        assert set(evaluation.issue_year) == {year}
        assert set(train.loan_id).isdisjoint(evaluation.loan_id)


def test_reject_duplicate_loans_and_false_year_metadata():
    duplicate = population()
    duplicate.loc[9, "loan_id"] = duplicate.loc[0, "loan_id"]
    with pytest.raises(ValueError, match="unique"):
        chronological_fold(duplicate, 2015)
    wrong_year = population()
    wrong_year.loc[0, "issue_date"] = "2015-01-01"
    with pytest.raises(ValueError, match="disagree"):
        chronological_fold(wrong_year, 2015)


def test_unmatured_future_year_is_not_silently_added():
    with pytest.raises(ValueError, match="predeclared"):
        chronological_fold(population(), 2016)
