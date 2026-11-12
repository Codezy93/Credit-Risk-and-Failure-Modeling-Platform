"""Summarize the timing gate and saved temporal research results."""

import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from util.mlflow_evaluation import markdown_table


def main():
    manifest = json.loads((ROOT/'assets/results/bureau_temporal_latest.json').read_text())
    assert manifest['status'] == 'complete' and not manifest['promotion_approved']
    result = ROOT/manifest['result_directory']
    for name,digest in manifest['results_sha256'].items():
        assert hashlib.sha256((result/name).read_bytes()).hexdigest() == digest,name
    metrics = pd.read_csv(result/'temporal_metrics.csv')
    intervals = pd.read_csv(result/'paired_auc_intervals.csv')
    roles = pd.read_csv(result/'temporal_roles.csv')
    audit = pd.read_csv(result/'feature_timing_audit.csv')
    figure_dir = ROOT/'assets/figures/bureau_temporal'/manifest['batch_run_id']
    figure_dir.mkdir(parents=True,exist_ok=True)
    figure,axes = plt.subplots(1,2,figsize=(12,4))
    for name,frame in metrics.groupby('model',sort=False):
        axes[0].plot(frame.evaluation_year,frame.roc_auc,'o-',label=name)
    axes[0].set(xlabel='Explored evaluation year',ylabel='ROC-AUC',title='Retrospective temporal stability',xticks=[2013,2014,2015])
    axes[0].legend()
    axes[1].vlines(intervals.evaluation_year,intervals.lower_95,intervals.upper_95)
    axes[1].scatter(intervals.evaluation_year,intervals.auc_difference_expanded_minus_base13)
    axes[1].axhline(0,color='gray',linestyle='--')
    axes[1].set(xlabel='Explored evaluation year',ylabel='AUC difference',title='Expanded minus matched XGB13; paired 95% intervals',xticks=[2013,2014,2015])
    figure.tight_layout()
    figure.savefig(figure_dir/'temporal_stability.png',dpi=160)
    plt.close(figure)
    public='https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/'
    raw='https://raw.githubusercontent.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/main/'
    test_note = ''
    if (result/'test_results.xml').exists():
        totals = {key:0 for key in ['tests','failures','errors','skipped']}
        for suite in ET.parse(result/'test_results.xml').getroot().iter('testsuite'):
            for key in totals: totals[key] += int(suite.get(key,0))
        test_note = (f"Local suite: **{totals['tests']} tests**, {totals['failures']} failures, "
            f"{totals['errors']} errors and {totals['skipped']} skips. "
            f"[JUnit]({public}{result.relative_to(ROOT)}/test_results.xml).")
    summary=metrics[['evaluation_year','model','train_rows','rows','roc_auc','gini','ks','average_precision','brier_score','observed_positive_rate','mean_score']]
    additions=int(audit.added_to_baseline.sum())
    report=f'''# Expanded bureau timing and temporal review

Batch `{manifest['batch_run_id']}`, completed {manifest['completed_at_utc']}.
**Decision: research only; no promotion.** The incumbent artifact and original
model/research manifest pointers are unchanged.

## Field timing audit

All **{len(audit)} input features** have explicit timing-audit entries, including
**{additions} additions** to the 13-feature baseline. **Zero** have issuer-certified
per-field measurement/update lineage for this exact CSV. Policy allowlisting
prevents known later-outcome predictors; it does not certify availability.
Derived variables inherit their parents' timing uncertainty. Grade, subgrade and
interest rate are excluded from this comparison.

The filed [loan-request credit-report authorization](https://www.sec.gov/Archives/edgar/data/1409970/000095012309014424/c86710exv10w11.htm)
provides general evidence that reports were obtained for loan requests. It does
not map this extract's field values to measurement times. The
[April 2019 borrower agreement, section 6](https://www.sec.gov/Archives/edgar/data/1409970/000140997019000563/lc33119ex101.htm)
also authorizes periodic reports during the relationship. Those later terms do
not establish that any specific 2011–2015 CSV value was updated. Neither document
certifies the historical CSV snapshot. Unknown timing is not proof of leakage.

[Field audit]({public}{result.relative_to(ROOT)}/feature_timing_audit.csv) and
[year-by-year feature coverage]({public}{result.relative_to(ROOT)}/feature_coverage_by_year.csv)
record every field and missingness pattern. Coverage can reveal schema/cohort
changes; it is not timestamp evidence. Promotion requires an issuer/source
mapping of measurement time, first availability and update/immutability rules
for every input and its dependencies, before the intended scoring time.

## Predeclared research windows

{markdown_table(roles)}

Evaluation years 2013, 2014 and 2015 were already explored. Training rows precede
evaluation rows, preprocessing fits on training only, and loan IDs are unique and
disjoint across each split. Borrower-level disjointness is not established.
Lifetime outcome labels were not necessarily known at the later origination
date, so these are **not point-in-time deployment backtests** or fresh holdouts.
Only resolved accepted 36-month loans are included; later, less-mature cohorts
are not added merely to obtain another test year.

Both XGBoost controls use exactly the same frozen parameters and
**{manifest['frozen_xgboost_parameters']['n_estimators']} trees**, without an eval_set or new tuning.
The tree budget was originally chosen using **2013 stopping data**; the
configuration and 58-feature contract were selected in earlier **2014-informed
research**. Thus 2013 reuses stopping data and 2014 reuses selection data. The
windows were fixed before this rerun, not before the project originally explored
them. These are descriptive, hindsight-informed comparisons, not independent
validation. HGB13 uses the original fixed 200-iteration
configuration but is refitted within each window. Its 2015 value is therefore
not the unchanged incumbent's original 2015 score.

## Measured results

{markdown_table(summary)}

![Temporal stability and paired AUC intervals]({raw}{figure_dir.relative_to(ROOT)}/temporal_stability.png)

The matched XGB13 control separates added-field gains from a change of algorithm
or tree budget. Compare all windows, average precision, Brier and mean score
against observed prevalence; ranking lift alone does not establish calibration.
No new winner or threshold is chosen from these results.

## Conditional uncertainty

{markdown_table(intervals)}

Intervals use 200 paired, class-stratified resamples of each evaluation cohort,
seed 42. They condition on fitted models and omit training/configuration/feature
selection uncertainty, macroeconomic variation and possible borrower dependence.
Windows share observations and are not independent replications; no pooled
significance claim is made. Even consistently positive intervals would not
resolve the timing gate.

## Artifacts and next evidence

{test_note}

Nine saved pipelines, role-specific datasets and nine native MLflow evaluation
runs are recorded in `lendingclub_bureau_temporal_review`. Native full-cohort AUCs
were checked against custom metrics; saved pipelines reproduce full-cohort scores.
The manifest pins source, input, result, dataset and model hashes.

[Manifest]({public}{result.relative_to(ROOT)}/manifest.json),
[metrics]({public}{result.relative_to(ROOT)}/temporal_metrics.csv), and
[native evaluations]({public}{result.relative_to(ROOT)}/native_evaluations.csv).
Run `make bureau-review` with the existing raw and clean data to repeat.

The remaining gate is an exact as-of data contract plus genuinely unused,
sufficiently mature evaluation data and label-availability evidence. Additional
retrospective windows support a stability discussion, not deployment approval.
The [lifetime charge-off target](risk_terminology.md) and the independent
[loss-proxy limitations](loss_model_limitations.md) remain unchanged.
'''
    (ROOT/'docs/bureau_temporal_review.md').write_text(report)
    marker,end='<!-- bureau-temporal-statistics -->','<!-- end-bureau-temporal-statistics -->'
    path=ROOT/'assets/statistics.md';text=path.read_text()
    if marker in text:
        start,rest=text.split(marker,1);_,tail=rest.split(end,1);text=start+tail.lstrip('\n')
    section=report.replace('# Expanded bureau timing and temporal review','## Expanded bureau timing and temporal review',1)
    section=section.replace('(risk_terminology.md)','(../docs/risk_terminology.md)').replace('(loss_model_limitations.md)','(../docs/loss_model_limitations.md)')
    index=text.index('<!-- loss-limitations-statistics -->')
    path.write_text(text[:index]+marker+'\n'+section+'\n'+end+'\n\n'+text[index:])
    print('Bureau timing and temporal research report written; promotion remains disabled.')


if __name__=='__main__':main()
