"""Explain the saved WoE bins, sign audit, point scale and evaluation results."""

import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from util.mlflow_evaluation import markdown_table


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    m=json.loads((ROOT/'assets/results/scorecard_latest.json').read_text())
    assert m['status']=='complete'
    result=ROOT/m['result_directory'];models=ROOT/m['model_directory']
    for name,digest in m['results_sha256'].items():assert sha(result/name)==digest,name
    for name,digest in m['model_sha256'].items():assert sha(models/name)==digest,name
    metrics=pd.read_csv(result/'metrics.csv');iv=pd.read_csv(result/'iv_screen.csv')
    coefficients=pd.read_csv(result/'coefficients.csv');points=pd.read_csv(result/'points_table.csv')
    bins=pd.read_csv(result/'binning_tables.csv');intervals=pd.read_csv(result/'paired_auc_intervals.csv')
    u=iv[iv.model=='woe_unconstrained'].drop(columns='model').reset_index(drop=True)
    c=iv[iv.model=='woe_constrained'].drop(columns='model').reset_index(drop=True)
    pd.testing.assert_frame_equal(u,c)
    for _,frame in bins.groupby(['model','feature'],sort=False):
        ordered=frame[frame.ordered].sort_values('bin_id')
        sign=1 if frame.direction.iloc[0]=='ascending' else -1
        assert (sign*np.diff(ordered.event_rate)>=-1e-12).all()
        assert (sign*np.diff(ordered.smoothed_event_rate)>=-1e-12).all()
    selected=c.loc[c.selected,'feature'].tolist()
    bad_signs=coefficients[(coefficients.model=='woe_unconstrained') & ~coefficients.sign_check_passed].feature.tolist()
    assert coefficients[coefficients.model=='woe_constrained'].sign_check_passed.all()
    # Independently reconstruct scores using the exported CSV points, not the internal coefficient formula.
    parameter_rows=[]
    for name in ['woe_unconstrained','woe_constrained']:
        model=joblib.load(models/f'{name}.joblib')
        parameter_rows.append({'model':name,'selected_features':len(model.selected_features_),'intercept':model.intercept_[0],
            'factor':model.factor_,'offset':model.offset_,'optimizer_iterations':int(model.n_iter_[0])})
        table=points[points.model==name].set_index(['feature','bin_id'])
        for split in ['validation','exploratory_test']:
            x=pd.read_parquet(models/f'{split}.parquet')[m['features']]
            assignments=model.bin_assignments(x)
            reconstructed=np.zeros(len(x))
            for feature in assignments:
                index=pd.MultiIndex.from_arrays([[feature]*len(x),assignments[feature]])
                reconstructed+=table.reindex(index).points.to_numpy()
            np.testing.assert_allclose(reconstructed,model.score_points(x),atol=1e-9)
    figure_dir=ROOT/'assets/figures/scorecard'/m['batch_run_id'];figure_dir.mkdir(parents=True,exist_ok=True)
    figure,axes=plt.subplots(1,2,figsize=(12,5))
    ordered=c.sort_values('train_iv');axes[0].barh(ordered.feature,ordered.train_iv,color=np.where(ordered.selected,'#0072B2','#bbbbbb'))
    axes[0].axvline(.02,color='black',linestyle='--');axes[0].set(xlabel='Training IV',title='Training-only IV screen; threshold 0.02')
    scores=pd.read_parquet(models/'woe_constrained_validation_scores.parquet')
    edges=np.linspace(scores.score_points.min(),scores.score_points.max(),26)
    for target,label in [(0,'Fully paid'),(1,'Charged off')]:
        axes[1].hist(scores.loc[scores.charged_off==target,'score_points'],bins=edges,density=True,alpha=.5,label=label)
    axes[1].set(xlabel='Unrounded scorecard points; higher implies lower model risk',ylabel='Within-class density',title='Explored 2014 validation score distribution');axes[1].legend()
    figure.tight_layout();figure.savefig(figure_dir/'scorecard_review.png',dpi=160);plt.close(figure)
    public='https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/'
    raw='https://raw.githubusercontent.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/main/'
    metric_table=metrics[['model','split','roc_auc','gini','ks','average_precision','brier_score','observed_positive_rate','mean_predicted_probability']]
    table=points[points.model=='woe_constrained'][['feature','bin','count','good','bad','event_rate','woe','coefficient','points']]
    test_note=''
    if (result/'test_results.xml').exists():
        totals={key:0 for key in ['tests','failures','errors','skipped']}
        for suite in ET.parse(result/'test_results.xml').getroot().iter('testsuite'):
            for key in totals:totals[key]+=int(suite.get(key,0))
        test_note=f"Local suite: **{totals['tests']} tests**, {totals['failures']} failures, {totals['errors']} errors, {totals['skipped']} skips. [JUnit]({public}{result.relative_to(ROOT)}/test_results.xml)."
    report=f'''# WoE logistic scorecard challengers

Batch `{m['batch_run_id']}`, completed {m['completed_at_utc']}.
These are new **research challengers**, not a replacement for the incumbent.
The original plain logistic regression remains a separate reference model.
The target remains [lifetime charge-off among resolved 36-month loans](risk_terminology.md).

## Binning and selection

Bins, missing-value effects, categorical risk order, IV screening and coefficients
are fitted on **2011–2013 training rows only**. 2014 is explored validation; 2015
is explored later-year evaluation. No new holdout or point-in-time backtest is claimed.
No validation labels choose bins, feature retention, directions or coefficients.

Numeric variables start with up to six quantile/discrete bins. Adjacent bins are
pooled for support and monotonicity of both raw and smoothed training event rates.
A zero-inflated variable retains a zero-versus-positive split where quantiles
collapse. Support pooling targets 5% of nonmissing rows and 20 examples of each
class where mergeable; a single remaining bin and missing bins can be exceptions.
Missing is a separate group outside numeric ordering. This is a transparent
heuristic, **not optimal binning** or OptBinning.

Directions for nine numeric fields are predeclared domain constraints. Revolving
balance and open-account directions choose the larger training IV of ascending
and descending pooling. Categories are grouped for rare training levels and then
ordered by training event rate; this is not a natural ordering of category names.
New categories get neutral WoE zero; never-observed missing values also get zero.
These are explicit fallback assumptions, not evidence about new groups.

WoE = log(smoothed good share / smoothed bad share), with 0.5 added to each class
count in occupied bins. IV is the sum of (good share − bad share) × WoE.
Only variables with **training IV ≥ 0.02** enter the logistic fit. Full training
counts and bin contributions are saved, including excluded variables.

{markdown_table(c)}

Selected features: **{', '.join(selected)}**. Delinquency and bankruptcy are not
silently assigned favorable economic effects: their actual IV decisions appear
above. Pooling and screening are modeling choices that can discard weak or
nonconforming signals; they do not establish causality or universal risk direction.

## Coefficients and sign checks

Both models minimize the same L2 logistic objective (C=1), with the same L-BFGS-B
optimizer, initialization and tolerances. The constrained fit additionally bounds
WoE coefficients at zero from above. The intercept is unpenalized and unconstrained.
No one-hot reference ambiguity is introduced: each retained variable has one
WoE coefficient.

Under this good/bad WoE convention a nonpositive coefficient is the expected
relationship. Positive unconstrained WoE coefficients, if present, are reported,
not silently flipped. Current unconstrained sign failures: **{bad_signs or 'none'}**.
Constrained signs are enforced by design; passing them is not regulatory validation
or proof that the assumed raw-variable direction is economically correct. Numeric
score monotonicity applies within regular bins, holding other inputs fixed; it does
not order missing values or prove monotone observed risk in future cohorts.

{markdown_table(coefficients)}

{markdown_table(pd.DataFrame(parameter_rows))}

## Points scaling and exported rules

Base **600 points at model-implied good:bad odds 50:1**, with **PDO = 20**.
Factor = 20 / ln(2); offset = 600 − factor × ln(50).
Score = offset − factor × fitted bad-event log-odds.
Doubling good:bad odds adds 20 points. Higher scores imply lower fitted charge-off
probability. The anchor is not a guarantee of observed default rates or a FICO scale.

Unrounded per-feature points distribute the offset and intercept equally across
retained variables. Adding their exported bin points reproduces the full model
score, including explicit missing and unseen-category fallback rows. No clipping
or rounding is used. Both saved-model probabilities and point sums were verified
on the complete cohorts; the exported CSV lookup was independently checked on
all validation and exploratory rows for both challengers.

Below is the constrained card's complete points table. The
[CSV]({public}{result.relative_to(ROOT)}/points_table.csv) includes both cards at full precision.

{markdown_table(table)}

![Scorecard IV screen and score distribution]({raw}{figure_dir.relative_to(ROOT)}/scorecard_review.png)

## Evaluation and trade-offs

{markdown_table(metric_table)}

Both challenger variants were predeclared; no model is promoted from these results.
A monotone scorecard is not guaranteed to beat the original logistic regression or
boosting. The IV cutoff can remove jointly useful weak predictors; coarse bins
can lose ranking information. When unconstrained coefficients already have the
expected signs, the bounds may be inactive and need not improve discrimination.
Raw probabilities are not separately calibrated here. The default 0.5 classification
threshold is a reproducible diagnostic, not an approval or cost-optimized policy.

{markdown_table(intervals)}

Intervals compare each scorecard with the fixed original logistic model using
200 paired class-stratified resamples. They exclude binning/fit/selection uncertainty,
borrower dependence and macroeconomic variation. There is no significance claim
that these are universally better models. Per-bin counts and event rates for
train/validation/exploratory cohorts are in
[bin outcomes]({public}{result.relative_to(ROOT)}/bin_outcomes_by_split.csv);
validation event-rate monotonicity is not forced.

## Reproduce and inspect

{test_note}

Run `make scorecard` to fit the challengers, log real datasets/models/native
evaluations to MLflow and export reports. `make scorecard-report` reads saved
results without fitting. Current weights and input/metric/source hashes are in
[the manifest]({public}{result.relative_to(ROOT)}/manifest.json).
[All bins]({public}{result.relative_to(ROOT)}/binning_tables.csv),
[IV screen]({public}{result.relative_to(ROOT)}/iv_screen.csv),
[coefficient audit]({public}{result.relative_to(ROOT)}/coefficients.csv), and
[native evaluations]({public}{result.relative_to(ROOT)}/native_evaluations.csv) remain inspectable.
Historical failed/diagnostic runs remain recorded with their execution-time sources.
No dependencies, incumbent artifacts, raw data or prepared datasets were changed.

For related ordered-fit concepts see [scikit-learn isotonic regression](https://scikit-learn.org/stable/modules/isotonic.html).
The bounded optimizer is documented by [SciPy L-BFGS-B](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-lbfgsb.html).
'''
    (ROOT/'docs/scorecard.md').write_text(report)
    marker,end='<!-- scorecard-statistics -->','<!-- end-scorecard-statistics -->'
    path=ROOT/'assets/statistics.md';text=path.read_text()
    if marker in text:
        start,rest=text.split(marker,1);_,tail=rest.split(end,1);text=start+tail.lstrip('\n')
    section=report.replace('# WoE logistic scorecard challengers','## WoE logistic scorecard challengers',1).replace('(risk_terminology.md)','(../docs/risk_terminology.md)')
    index=text.index('<!-- bureau-temporal-statistics -->')
    path.write_text(text[:index]+marker+'\n'+section+'\n'+end+'\n\n'+text[index:])
    print('Scorecard report and exported-point reconstruction checks completed.')


if __name__=='__main__':main()
