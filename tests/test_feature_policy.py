import copy
import subprocess
import sys

import pytest

from util import feature_policy


@pytest.mark.parametrize("scope", ["independent_baseline", "expanded_bureau_candidate", "post_underwriting"])
@pytest.mark.parametrize("feature", ["charged_off", "loan_status", "loan_id", "total_rec_prncp",
                                     "total_pymnt", "recoveries", "collection_recovery_fee",
                                     "last_fico_range_low", "last_credit_pull_d", "hardship_flag", "settlement_amount"])
def test_outcome_and_metadata_fields_are_rejected_in_every_scope(scope, feature):
    with pytest.raises(ValueError):
        feature_policy.validate_features([feature], scope)


def test_underwriting_outputs_require_their_own_scope():
    with pytest.raises(ValueError):
        feature_policy.validate_features(["int_rate"])
    assert feature_policy.validate_features(["grade", "sub_grade", "int_rate"], "post_underwriting")["deployment_approved"] is False


def test_unknown_features_are_not_implicitly_approved():
    with pytest.raises(ValueError):
        feature_policy.validate_features(["new_unreviewed_signal"])
    with pytest.raises(ValueError):
        feature_policy.validate_features(["dti", "dti"])


def test_deny_rules_override_an_accidentally_expanded_allowlist(monkeypatch):
    policy = copy.deepcopy(feature_policy.POLICY)
    policy["groups"]["baseline"].append("recoveries")
    monkeypatch.setattr(feature_policy, "POLICY", policy)
    with pytest.raises(ValueError):
        feature_policy.validate_features(["recoveries"])


def test_guard_stays_active_with_python_optimization():
    result = subprocess.run([sys.executable, "-O", "-c",
        "from util.feature_policy import validate_features; validate_features(['recoveries'])"],
        capture_output=True, text=True)
    assert result.returncode != 0
    assert "Forbidden" in result.stderr
