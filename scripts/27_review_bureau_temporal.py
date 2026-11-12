"""Audit unresolved field timing and run three retrospective temporal comparisons."""

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
from time import perf_counter

import duckdb
import joblib
import mlflow
import mlflow.sklearn
from mlflow.models import infer_signature
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from threadpoolctl import threadpool_limits
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from util.bureau_review import chronological_fold
from util.feature_policy import validate_features, POLICY
from util.metrics import evaluate_model, paired_auc_bootstrap
from util.mlflow_evaluation import log_saved_model_evaluation, markdown_table
from util.modeling import build_models
from util.risk_scope import log_risk_scope


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    source_files = [Path(__file__),ROOT/'sql/39_bureau_temporal_population.sql',ROOT/'util/bureau_review.py',
        ROOT/'util/bureau_timing_evidence.json',ROOT/'util/feature_policy.json',ROOT/'util/modeling.py',
        ROOT/'util/metrics.py',ROOT/'util/mlflow_evaluation.py',ROOT/'util/risk_scope.py',ROOT/'requirements.lock']
    execution_hashes = {str(p.relative_to(ROOT)):sha(p) for p in source_files}
    reference_path = ROOT / 'assets/results/auc_improvement_latest.json'
    reference = json.loads(reference_path.read_text())
    base = reference['feature_sets']['base13']
    expanded = reference['feature_sets']['expanded_bureau']
    validate_features(base)
    validate_features(expanded, 'expanded_bureau_candidate')
    assert not set(POLICY['groups']['underwriting_outputs']).intersection(expanded)
    comparison = pd.read_csv(ROOT / reference['result_directory'] / 'auc_comparison.csv')
    prior = comparison[comparison.trial == 'expanded_bureau_regularized'].iloc[0]
    parameters = dict(n_estimators=int(prior.selected_estimators), max_depth=int(prior.max_depth),
        min_child_weight=int(prior.min_child_weight), reg_lambda=float(prior.reg_lambda), learning_rate=.05,
        subsample=.8, colsample_bytree=.8, objective='binary:logistic', eval_metric='auc',
        tree_method='hist', n_jobs=4, random_state=42)
    protected = [ROOT / 'models/selected_model.joblib', ROOT / 'assets/results/model_experiments_latest.json', reference_path]
    protected_hashes = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    clean = ROOT / 'data/clean/loans.parquet'
    raw = ROOT / 'data/raw/accepted_2007_to_2018Q4.csv'
    assert sha(clean) == reference['clean_source_sha256']
    assert sha(raw) == reference['raw_source_sha256']
    con = duckdb.connect()
    con.execute("SET memory_limit='1GB'")
    con.execute('SET threads=4')
    con.execute('SET VARIABLE clean_path=?', [str(clean)])
    con.execute('SET VARIABLE raw_path=?', [str(raw)])
    print('Reading retrospective 2011-2015 population', flush=True)
    con.execute((ROOT / 'sql/39_bureau_temporal_population.sql').read_text())
    population = con.execute('SELECT * FROM bureau_temporal_population ORDER BY issue_date, loan_id').df()
    con.close()
    assert population.loan_id.is_unique and population.source_parse_failures.sum() == 0
    assert len(population) == 603589 and set(population.issue_year) == set(range(2011, 2016))
    categories = ['home_ownership', 'purpose']
    for field in set(expanded) - set(categories):
        population[field] = population[field].astype(float)
    sources = json.loads((ROOT / 'util/bureau_timing_evidence.json').read_text())
    mlflow.set_tracking_uri('sqlite:///' + str(ROOT / 'models/mlflow.db'))
    experiment = mlflow.set_experiment('lendingclub_bureau_temporal_review')
    packages = ['scikit-learn', 'xgboost-cpu', 'numpy', 'pandas', 'mlflow', 'cloudpickle', 'scipy', 'joblib', 'threadpoolctl']
    versions = {p: importlib.metadata.version(p) for p in packages}
    requirements = [f'{p}=={v}' for p, v in versions.items()]
    with mlflow.start_run(run_name='field_timing_and_temporal_stability') as parent:
        log_risk_scope()
        batch = parent.info.run_id
        output = ROOT / 'assets/results/bureau_temporal' / batch
        models = ROOT / 'models/bureau_temporal' / batch
        output.mkdir(parents=True)
        models.mkdir(parents=True)
        audit, coverage = [], []
        for field in expanded:
            group = next(group for group, fields in POLICY['groups'].items() if field in fields)
            audit.append({'feature': field, 'group': group, 'added_to_baseline': field not in base,
                'source_time_certified': False, 'deployment_approved': False,
                'timing_status': 'inherits parent timing assumptions' if group == 'derived' else 'CSV snapshot timestamp/update mapping unverified',
                'evidence': 'general loan-request workflow only; no exact extract field lineage',
                'required_evidence': 'issuer field definition + measurement timestamp + immutable/update rule before intended scoring time'})
            for year, frame in population.groupby('issue_year'):
                coverage.append({'feature': field, 'issue_year': int(year), 'rows': len(frame),
                    'nonmissing': int(frame[field].notna().sum()), 'missing_pct': frame[field].isna().mean()*100,
                    'distinct_nonmissing': frame[field].nunique(dropna=True)})
        metrics, intervals, roles, native = [], [], [], []
        manifest = {'status':'running', 'batch_run_id':batch, 'experiment_id':experiment.experiment_id,
            'result_directory':str(output.relative_to(ROOT)), 'model_directory':str(models.relative_to(ROOT)),
            'feature_sets':{'base13':base,'expanded_bureau':expanded}, 'frozen_xgboost_parameters':parameters,
            'configuration_origin':'2014-informed historical expanded_bureau_regularized; reused without new tuning',
            'all_evaluation_years_previously_explored':True, 'point_in_time_label_backtest':False,
            'source_time_certified':False, 'promotion_approved':False, 'incumbent_replaced':False,
            'model_uris':{},'run_ids':{}, 'versions':versions, 'protected_sha256':protected_hashes}
        mlflow.set_tags({'promotion_approved':'false','source_time_certified':'false','research_scope':'post_hoc_temporal_stability'})
        mlflow.log_dict(sources, 'field_timing_evidence.json')
        mlflow.log_dict(parameters, 'frozen_xgboost_parameters.json')
        for year in [2013, 2014, 2015]:
            train, evaluation = chronological_fold(population, year)
            for role, frame in [('train',train),('evaluation',evaluation)]:
                roles.append({'evaluation_year':year,'role':role,'rows':len(frame),
                    'min_issue_date':str(frame.issue_date.min()),'max_issue_date':str(frame.issue_date.max()),
                    'charged_off':int(frame.charged_off.sum()),'positive_rate':frame.charged_off.mean()})
            predictions = {}
            for family, fields in [('hgb13',base),('xgb13',base),('xgb_expanded',expanded)]:
                numeric = [f for f in fields if f not in categories]
                if family == 'hgb13':
                    model = build_models(numeric,categories)['hist_gradient_boosting']
                else:
                    prepare = ColumnTransformer([('numeric','passthrough',numeric),
                        ('categories',Pipeline([('fill',SimpleImputer(strategy='constant',fill_value='Missing')),
                         ('encode',OneHotEncoder(handle_unknown='ignore',sparse_output=False))]),categories)],sparse_threshold=0)
                    model = Pipeline([('prepare',prepare),('model',XGBClassifier(**parameters))])
                name = f'{family}_{year}'
                print(f'Fitting {name}: {len(train):,} train / {len(evaluation):,} evaluation rows',flush=True)
                datasets = {}
                for role, frame in [('train',train),('evaluation',evaluation)]:
                    path = models / f'{name}_{role}.parquet'
                    frame[fields+['charged_off']].to_parquet(path,index=False)
                    datasets[role] = mlflow.data.from_pandas(frame[fields+['charged_off']],source=str(path),
                        targets='charged_off',name=f'{name}_{role}')
                with mlflow.start_run(run_name=name,nested=True) as run:
                    log_risk_scope()
                    mlflow.log_params({'evaluation_year':year,'feature_count':len(fields),'configuration_frozen':True,'tuning_on_this_fold':False})
                    for role, dataset in datasets.items():
                        mlflow.log_input(dataset,context=role)
                        mlflow.log_artifact(str(models/f'{name}_{role}.parquet'),artifact_path='datasets')
                    started = perf_counter()
                    model.fit(train[fields],train.charged_off)
                    seconds = perf_counter()-started
                    scores = model.predict_proba(evaluation[fields])[:,1]
                    predictions[family] = scores
                    values = evaluate_model(evaluation.charged_off,scores)
                    metrics.append({'model':family,'evaluation_year':year,'train_rows':len(train),
                        'fit_seconds':seconds,'mean_score':scores.mean(),**values})
                    mlflow.log_metrics({k:float(v) for k,v in values.items()},dataset=datasets['evaluation'])
                    joblib.dump(model,models/f'{name}.joblib')
                    np.testing.assert_allclose(joblib.load(models/f'{name}.joblib').predict_proba(evaluation[fields])[:,1],scores,atol=1e-12)
                    info = mlflow.sklearn.log_model(model,name='model',serialization_format='cloudpickle',
                        signature=infer_signature(train[fields].head(),model.predict_proba(train[fields].head())),
                        input_example=train[fields].head(),pyfunc_predict_fn='predict_proba',pip_requirements=requirements)
                    manifest['model_uris'][name] = info.model_uri
                    manifest['run_ids'][name] = run.info.run_id
                context = {'experiment_id':experiment.experiment_id,'features':fields,'model_uris':{name:info.model_uri},
                    'run_ids':{name:run.info.run_id},'selected_model':''}
                record = log_saved_model_evaluation(context,name,'evaluation',datasets['evaluation'])
                assert abs(record['roc_auc']-values['roc_auc']) < 1e-10
                native.append(record)
                print(f'{name}: AUC {values["roc_auc"]:.6f}',flush=True)
            bootstrap = paired_auc_bootstrap(evaluation.charged_off,predictions['xgb13'],predictions['xgb_expanded'],n_resamples=200,seed=42)
            bootstrap.to_csv(output/f'paired_bootstrap_{year}.csv',index=False)
            delta = evaluate_model(evaluation.charged_off,predictions['xgb_expanded'])['roc_auc']-evaluate_model(evaluation.charged_off,predictions['xgb13'])['roc_auc']
            # The helper records second minus first: expanded minus the matched base13 control.
            column = 'delta_b_minus_a'
            intervals.append({'evaluation_year':year,'auc_difference_expanded_minus_base13':delta,
                'lower_95':bootstrap[column].quantile(.025),'upper_95':bootstrap[column].quantile(.975),
                'scope':'paired fixed-model cohort bootstrap; excludes fitting/selection uncertainty'})
        tables = {'feature_timing_audit':pd.DataFrame(audit),'feature_coverage_by_year':pd.DataFrame(coverage),
            'temporal_metrics':pd.DataFrame(metrics),'paired_auc_intervals':pd.DataFrame(intervals),
            'temporal_roles':pd.DataFrame(roles),'native_evaluations':pd.DataFrame(native)}
        for name, table in tables.items():table.to_csv(output/f'{name}.csv',index=False)
        assert protected_hashes == {str(p.relative_to(ROOT)):sha(p) for p in protected}
        assert execution_hashes == {str(p.relative_to(ROOT)):sha(p) for p in source_files}
        assert sha(raw) == reference['raw_source_sha256'] and sha(clean) == reference['clean_source_sha256']
        manifest.update(status='complete',completed_at_utc=datetime.now(timezone.utc).isoformat(),
            input_sha256={'raw':reference['raw_source_sha256'],'clean':reference['clean_source_sha256']},
            source_sha256=execution_hashes, execution_script_sha256=execution_hashes['scripts/27_review_bureau_temporal.py'],
            results_sha256={p.name:sha(p) for p in output.glob('*.csv')},
            model_sha256={p.name:sha(p) for p in models.glob('*.joblib')},
            dataset_sha256={p.name:sha(p) for p in models.glob('*.parquet')})
        (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        (ROOT/'assets/results/bureau_temporal_latest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        mlflow.log_dict(manifest,'manifest.json')
        mlflow.log_artifacts(str(output),artifact_path='results')
        for path in source_files:mlflow.log_artifact(str(path),artifact_path='source')
        print('Completed research temporal review:',batch,flush=True)


if __name__ == '__main__':
    with threadpool_limits(limits=4):main()
