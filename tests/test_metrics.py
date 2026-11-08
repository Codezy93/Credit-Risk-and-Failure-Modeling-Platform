import numpy as np
import pytest
from scipy.stats import ks_2samp

from util.metrics import calibration_table, evaluate_model, paired_auc_bootstrap


def test_known_auc_gini_ks_and_confusion_counts():
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.4, 0.35, 0.8])
    result = evaluate_model(y, p)
    assert result["roc_auc"] == 0.75
    assert result["gini"] == 0.5
    assert result["ks"] == 0.5
    assert result["ks"] == ks_2samp(p[y == 0], p[y == 1]).statistic
    assert result["average_precision"] == pytest.approx(5 / 6)
    assert result["brier_score"] == pytest.approx(0.158125)
    assert [result[k] for k in ["tn", "fp", "fn", "tp"]] == [2, 0, 1, 1]


def test_constant_scores_are_chance_ranking_regardless_of_imbalance():
    result = evaluate_model([0] * 9 + [1], [0.1] * 10)
    assert result["roc_auc"] == 0.5
    assert result["gini"] == result["ks"] == 0
    assert result["average_precision"] == 0.1


def test_ties_and_reversed_scores_have_defined_ks_direction():
    tied = evaluate_model([0, 1, 0, 1], [0.2, 0.2, 0.8, 0.8])
    assert tied["roc_auc"] == 0.5 and tied["ks"] == 0
    reverse = evaluate_model([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1])
    assert reverse["roc_auc"] == 0 and reverse["gini"] == -1
    assert reverse["ks"] == 1  # Two-sided separation; AUC supplies the direction.


def test_zero_and_one_probabilities_stay_in_valid_calibration_bins():
    bins = calibration_table([0, 1, 0, 1], [0, 1, 0, 1])
    assert bins.bin.tolist() == [0, 9]
    assert bins.rows.tolist() == [2, 2]
    assert np.isfinite(evaluate_model([0, 1], [0, 1])["log_loss"])


@pytest.mark.parametrize("scores", [[0.1, np.nan], [0.1, np.inf], [-0.1, 0.8], [0.1, 1.1]])
def test_invalid_probabilities_fail(scores):
    with pytest.raises(ValueError):
        evaluate_model([0, 1], scores)


def test_single_class_and_misaligned_scores_fail():
    with pytest.raises(ValueError):
        evaluate_model([0, 0], [0.1, 0.2])
    with pytest.raises(ValueError):
        evaluate_model([0, 1], [0.1])


def test_paired_bootstrap_identical_models_have_exact_zero_difference():
    sample = paired_auc_bootstrap([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8], [0.1, 0.4, 0.35, 0.8], 30)
    assert (sample.delta_b_minus_a == 0).all()
    assert len(sample) == 30


def test_stratified_bootstrap_preserves_both_classes_and_is_repeatable():
    args = ([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1], [0.1, 0.2, 0.8, 0.9])
    first = paired_auc_bootstrap(*args, n_resamples=20, seed=42)
    assert first.equals(paired_auc_bootstrap(*args, n_resamples=20, seed=42))
    assert (first.auc_a == 0).all() and (first.auc_b == 1).all()
    assert (first.delta_b_minus_a == 1).all()
