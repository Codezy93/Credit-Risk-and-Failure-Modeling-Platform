"""Compare two training-only WoE scorecards without replacing the incumbent."""

from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import warnings

import joblib
import mlflow
import mlflow.sklearn
from mlflow.models import infer_signature
import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from util.feature_policy import validate_features
from util.metrics import evaluate_model,paired_auc_bootstrap
from util.mlflow_evaluation import log_saved_model_evaluation
from util.risk_scope import log_risk_scope
from util.scorecard import WOEScorecard,DIRECTIONS
from util.validation import validate_periods


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    warnings.simplefilter('error',ConvergenceWarning)
    sources=[Path(__file__),ROOT/'util/scorecard.py',ROOT/'util/feature_policy.py',ROOT/'util/feature_policy.json',
        ROOT/'util/metrics.py',ROOT/'util/mlflow_evaluation.py',ROOT/'util/risk_scope.py',ROOT/'requirements.lock']
    source_hashes={str(p.relative_to(ROOT)):sha(p) for p in sources}
    data=json.loads((ROOT/'assets/results/model_data_manifest.json').read_text())
    reference=json.loads((ROOT/'assets/results/model_experiments_latest.json').read_text())
    features=data['features'];validate_features(features)
    protected=[ROOT/'models/selected_model.joblib',ROOT/reference['model_directory']/'logistic_regression.joblib',
        ROOT/'assets/results/model_experiments_latest.json']
    protected_hashes={str(p.relative_to(ROOT)):sha(p) for p in protected}
    frames,metadata,inputs={},{},{}
    for item in data['artifacts']:
        path=ROOT/item['path'];assert sha(path)==item['sha256'],path
        inputs[item['path']]=item['sha256']
        target=metadata if item['kind']=='metadata' else frames
        target[item['split']]=pd.read_parquet(path)
    validate_periods(metadata)
    for split,years in [('train',{2011,2012,2013}),('validation',{2014}),('exploratory_test',{2015})]:
        assert set(metadata[split].issue_year)==years
        frames[split][data['numeric_features']]=frames[split][data['numeric_features']].astype(float)
    mlflow.set_tracking_uri('sqlite:///'+str(ROOT/'models/mlflow.db'))
    experiment=mlflow.set_experiment('lendingclub_woe_scorecards')
    versions={p:importlib.metadata.version(p) for p in ['scikit-learn','numpy','pandas','scipy','joblib','mlflow','cloudpickle']}
    with mlflow.start_run(run_name='woe_scorecard_challengers') as parent:
        log_risk_scope()
        batch=parent.info.run_id
        output=ROOT/'assets/results/scorecard'/batch
        models=ROOT/'models/scorecard'/batch
        output.mkdir(parents=True);models.mkdir(parents=True)
        manifest={'status':'running','batch_run_id':batch,'experiment_id':experiment.experiment_id,
            'features':features,'numeric_directions':DIRECTIONS,'iv_min':.02,'smoothing':.5,
            'regular_bins':'at most six quantile/discrete bins, then adjacent support/monotonic pooling',
            'minimum_support':'5% nonmissing training rows and 20 examples per class where mergeable; missing separate',
            'categorical_bins':'rare training levels grouped, then ordered by training event rate; unseen WoE=0',
            'woe_definition':'log(smoothed good share / smoothed bad share); expected logistic coefficient <= 0',
            'optimizer':'same L-BFGS-B objective, initialization and tolerances; only coefficient bounds differ',
            'scaling':{'base_points':600,'good_to_bad_odds':50,'pdo':20,'rounding':False},
            'training_years':[2011,2012,2013],'validation_years':[2014],'exploratory_years':[2015],
            'binning_iv_coefficients_fit_on_train_only':True,'new_holdout':False,'incumbent_replaced':False,
            'regulatory_approval':False,'model_uris':{},'run_ids':{},'selected_model':'',
            'result_directory':str(output.relative_to(ROOT)),'model_directory':str(models.relative_to(ROOT)),
            'input_sha256':inputs,'protected_sha256':protected_hashes,'versions':versions}
        datasets={}
        for split,frame in frames.items():
            path=models/f'{split}.parquet';frame[features+['charged_off']].to_parquet(path,index=False)
            datasets[split]=mlflow.data.from_pandas(frame[features+['charged_off']],source=str(path),targets='charged_off',name=split)
            mlflow.log_input(datasets[split],context=split)
            mlflow.log_artifact(str(path),artifact_path='datasets')
        metrics,native,coefficients,bins,iv,points,profiles,intervals=[],[],[],[],[],[],[],[]
        predictions={}
        for name,path in [('original_logistic',protected[1]),('incumbent_hgb',protected[0])]:
            model=joblib.load(path)
            for split,frame in frames.items():
                values=model.predict_proba(frame[features])[:,1];predictions[(name,split)]=values
                metrics.append({'model':name,'split':split,**evaluate_model(frame.charged_off,values)})
        for constrained in [False,True]:
            name='woe_constrained' if constrained else 'woe_unconstrained'
            print(f'Fitting {name} on training data only',flush=True)
            with mlflow.start_run(run_name=name,nested=True) as run:
                log_risk_scope()
                mlflow.log_params({'iv_min':.02,'C':1.,'sign_constrained':constrained,'bins_fit_on':'2011-2013',
                    'pdo':20,'base_score':600,'good_to_bad_odds':50})
                for split,dataset in datasets.items():mlflow.log_input(dataset,context=split)
                model=WOEScorecard(features,data['categorical_features'],constrained=constrained).fit(frames['train'][features],frames['train'].charged_off)
                before=model.binning_table_.copy(deep=True)
                joblib.dump(model,models/f'{name}.joblib')
                info=mlflow.sklearn.log_model(model,name='model',serialization_format='cloudpickle',code_paths=[str(ROOT/'util')],
                    input_example=frames['train'][features].head(),
                    signature=infer_signature(frames['train'][features].head(),model.predict_proba(frames['train'][features].head())),
                    pyfunc_predict_fn='predict_proba',pip_requirements=[f'{p}=={v}' for p,v in versions.items()])
                manifest['model_uris'][name]=info.model_uri;manifest['run_ids'][name]=run.info.run_id
                for table,collection in [(model.binning_table_,bins),(model.feature_table_,iv),
                                          (model.coefficient_table(),coefficients),(model.points_table(),points)]:
                    table=table.copy();table.insert(0,'model',name);collection.append(table)
                for split,frame in frames.items():
                    x=frame[features];values=model.predict_proba(x)[:,1];predictions[(name,split)]=values
                    np.testing.assert_allclose(joblib.load(models/f'{name}.joblib').predict_proba(x)[:,1],values,atol=1e-12)
                    score=model.score_points(x);contributions=model.point_contributions(x)
                    np.testing.assert_allclose(contributions.sum(axis=1),score,atol=1e-9)
                    np.testing.assert_allclose(score,model.offset_-model.factor_*model.decision_function(x),atol=1e-10)
                    values_metrics=evaluate_model(frame.charged_off,values)
                    metrics.append({'model':name,'split':split,**values_metrics})
                    mlflow.log_metrics({f'{split}_{k}':float(v) for k,v in values_metrics.items()},dataset=datasets[split],model_id=info.model_uri.split('/')[-1])
                    pd.DataFrame({'lifetime_chargeoff_probability':values,'score_points':score,'charged_off':frame.charged_off}).to_parquet(models/f'{name}_{split}_scores.parquet',index=False)
                    assignments=model.bin_assignments(x)
                    for feature in assignments:
                        grouped=pd.DataFrame({'bin_id':assignments[feature].to_numpy(),'charged_off':frame.charged_off.to_numpy()}).groupby('bin_id').charged_off.agg(['count','sum','mean']).reset_index()
                        grouped['feature']=feature;grouped['split']=split;grouped['model']=name;profiles.append(grouped)
                pd.testing.assert_frame_equal(before,model.binning_table_)
                if constrained:assert model.coefficient_table().sign_check_passed.all()
                print(name,'selected:',model.selected_features_,'sign audit:',model.coefficient_table().to_dict('records'),flush=True)
            for split in ['validation','exploratory_test']:
                record=log_saved_model_evaluation(manifest,name,split,datasets[split])
                expected=evaluate_model(frames[split].charged_off,predictions[(name,split)])
                assert abs(record['roc_auc']-expected['roc_auc'])<1e-10
                native.append(record)
                boot=paired_auc_bootstrap(frames[split].charged_off,predictions[('original_logistic',split)],predictions[(name,split)],n_resamples=200,seed=42)
                boot.to_csv(output/f'{name}_{split}_bootstrap.csv',index=False)
                intervals.append({'model':name,'split':split,'reference':'original_logistic',
                    'auc_difference':expected['roc_auc']-evaluate_model(frames[split].charged_off,predictions[('original_logistic',split)])['roc_auc'],
                    'lower_95':boot.delta_b_minus_a.quantile(.025),'upper_95':boot.delta_b_minus_a.quantile(.975)})
        tables={'metrics':pd.DataFrame(metrics),'native_evaluations':pd.DataFrame(native),
            'binning_tables':pd.concat(bins,ignore_index=True),'iv_screen':pd.concat(iv,ignore_index=True),
            'coefficients':pd.concat(coefficients,ignore_index=True),'points_table':pd.concat(points,ignore_index=True),
            'bin_outcomes_by_split':pd.concat(profiles,ignore_index=True),'paired_auc_intervals':pd.DataFrame(intervals)}
        for name,table in tables.items():table.to_csv(output/f'{name}.csv',index=False)
        assert source_hashes=={str(p.relative_to(ROOT)):sha(p) for p in sources}
        assert protected_hashes=={str(p.relative_to(ROOT)):sha(p) for p in protected}
        assert all(sha(ROOT/path)==digest for path,digest in inputs.items())
        manifest.update(status='complete',completed_at_utc=datetime.now(timezone.utc).isoformat(),
            source_sha256=source_hashes,execution_script_sha256=source_hashes['scripts/29_train_scorecards.py'],
            results_sha256={p.name:sha(p) for p in output.glob('*.csv')},
            model_sha256={p.name:sha(p) for p in models.glob('*.joblib')},
            dataset_sha256={p.name:sha(p) for p in models.glob('*.parquet')},
            scoring_checks='full-cohort saved-model predictions and additive point sums verified; bins unchanged during inference')
        (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        (ROOT/'assets/results/scorecard_latest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        mlflow.log_dict(manifest,'manifest.json');mlflow.log_artifacts(str(output),artifact_path='results')
        for path in sources:mlflow.log_artifact(str(path),artifact_path='source')
        print('Scorecard comparison complete:',batch,flush=True)


if __name__=='__main__':
    with threadpool_limits(limits=4):main()
