import joblib
import numpy as np
import pandas as pd
import pytest
from scipy.special import expit
from sklearn.base import clone

from util.scorecard import WOEScorecard


@pytest.fixture
def training():
    rng=np.random.default_rng(42)
    n=4000
    fico=rng.uniform(600,800,n)
    dti=rng.uniform(0,40,n)
    purpose=rng.choice(['credit_card','debt_consolidation'],n)
    y=rng.binomial(1,expit((680-fico)/30+.025*dti+1.5*(purpose=='debt_consolidation')-1))
    frame=pd.DataFrame({'fico_mid':fico,'dti':dti,'purpose':purpose,'loan_amnt':10000.})
    frame.loc[::31,'fico_mid']=np.nan
    return frame,y


def fit(frame,y,constrained=True):
    return WOEScorecard(list(frame.columns),['purpose'],constrained=constrained).fit(frame,y)


def test_bins_are_monotone_and_count_training_rows(training):
    frame,y=training
    model=fit(frame,y)
    for feature,rows in model.binning_table_.groupby('feature',sort=False):
        assert rows['count'].sum()==len(frame)
        regular=rows[rows.ordered]
        direction=model.bins_[feature]['direction']
        sign=1 if direction=='ascending' else -1
        assert (sign*np.diff(regular.event_rate)>=-1e-12).all()
        assert (sign*np.diff(regular.smoothed_event_rate)>=-1e-12).all()
        assert (sign*np.diff(regular.woe)<=1e-12).all()
    assert 'loan_amnt' not in model.selected_features_
    assert (model.feature_table_.set_index('feature').loc[model.selected_features_,'train_iv']>=.02).all()
    assert np.isfinite(model.transform_woe(frame)).all()


def test_transform_does_not_relearn_and_unknown_categories_are_neutral(training):
    frame,y=training
    model=fit(frame,y)
    original=model.binning_table_.copy(deep=True)
    future=frame.head(3).copy()
    future['purpose']='never_seen'
    future['fico_mid']=[-1000,2000,np.nan]
    transformed=model.transform_woe(future)
    assert 'purpose' in model.selected_features_
    np.testing.assert_array_equal(transformed[:,model.selected_features_.index('purpose')],0.)
    assert np.isfinite(model.predict_proba(future)).all()
    pd.testing.assert_frame_equal(original,model.binning_table_)


def test_points_scaling_and_full_additivity(training,tmp_path):
    frame,y=training
    model=fit(frame,y)
    p=1/51
    score=model.offset_-model.factor_*np.log(p/(1-p))
    assert score==pytest.approx(600)
    p_double=1/101
    assert model.offset_-model.factor_*np.log(p_double/(1-p_double))==pytest.approx(620)
    np.testing.assert_allclose(model.point_contributions(frame).sum(axis=1),model.score_points(frame),atol=1e-10)
    probabilities=model.predict_proba(frame)[:,1]
    np.testing.assert_allclose(model.score_points(frame),model.offset_-model.factor_*np.log(probabilities/(1-probabilities)),atol=1e-9)
    assert (model.coef_<=1e-10).all()
    assert model.coefficient_table().sign_check_passed.all()
    joblib.dump(model,tmp_path/'scorecard.joblib')
    np.testing.assert_allclose(joblib.load(tmp_path/'scorecard.joblib').predict_proba(frame),model.predict_proba(frame))
    assert clone(model).get_params()['constrained']


def test_unconstrained_fit_is_audited_not_silently_flipped(training):
    frame,y=training
    model=fit(frame,y,constrained=False)
    np.testing.assert_array_equal(model.coefficient_table().sign_check_passed.to_numpy(),model.coef_[0]<=1e-10)
    assert not model.constrained


def test_outcome_columns_and_bad_labels_are_rejected(training):
    frame,y=training
    with pytest.raises(ValueError,match='Forbidden'):
        WOEScorecard(['charged_off'],[]).fit(pd.DataFrame({'charged_off':y}),y)
    with pytest.raises(ValueError,match='binary'):
        fit(frame,np.ones(len(frame)))


def test_inactive_sign_constraints_agree_with_unbounded_fit(training):
    frame,y=training
    unbounded=fit(frame,y,constrained=False)
    bounded=fit(frame,y,constrained=True)
    assert (unbounded.coef_<0).all()
    np.testing.assert_allclose(unbounded.predict_proba(frame),bounded.predict_proba(frame),atol=1e-5)


def test_sign_bound_handles_a_conditional_sign_reversal():
    rng=np.random.default_rng(53)
    z=rng.normal(size=12000)
    proxy=z+rng.normal(scale=.5,size=len(z))
    y=rng.binomial(1,expit(4*z-2.8*proxy-.7))
    frame=pd.DataFrame({'dti':25+4*z,'loan_amnt':20000+2000*proxy})
    unbounded=WOEScorecard(list(frame),[],constrained=False).fit(frame,y)
    bounded=WOEScorecard(list(frame),[],constrained=True).fit(frame,y)
    assert (unbounded.coef_>0).any()
    assert (bounded.coef_<=0).all()
    assert bounded.coefficient_table().zero_effect.any()
