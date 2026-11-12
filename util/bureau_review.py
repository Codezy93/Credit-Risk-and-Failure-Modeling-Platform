"""Chronological research folds; these do not establish label availability."""

import pandas as pd


def chronological_fold(population, evaluation_year):
    if evaluation_year not in [2013, 2014, 2015]:
        raise ValueError("Use the predeclared explored research years 2013, 2014 or 2015.")
    if population.loan_id.duplicated().any():
        raise ValueError("Loan IDs must be unique before splitting.")
    if not (pd.to_datetime(population.issue_date).dt.year == population.issue_year).all():
        raise ValueError("Issue dates and issue years disagree.")
    train = population[population.issue_year.between(2011, evaluation_year - 1)].copy()
    evaluation = population[population.issue_year == evaluation_year].copy()
    for frame in [train, evaluation]:
        if set(frame.charged_off.unique()) != {0, 1}:
            raise ValueError("Each fold population must contain both binary outcomes.")
    if train.issue_date.max() >= evaluation.issue_date.min():
        raise ValueError("Training and evaluation dates overlap.")
    return train, evaluation
