"""Training-only monotone bins, WoE logistic regression and additive points."""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.utils.validation import check_is_fitted

from util.feature_policy import validate_features

# These concern empirical event rates in regular numeric bins, not missing values.
DIRECTIONS = {'loan_amnt':'ascending','annual_inc':'descending','dti':'ascending',
    'revol_util':'ascending','fico_mid':'descending','credit_history_years':'descending',
    'emp_length_years':'descending','delinq_2yrs':'ascending','pub_rec_bankruptcies':'ascending'}


def _rate(group, smooth=False):
    alpha = .5 if smooth else 0
    return (group['bad'] + alpha) / (group['count'] + 2*alpha)


def _merge(groups, index):
    left, right = groups[index:index+2]
    merged = {'count':left['count']+right['count'],'bad':left['bad']+right['bad'],
        'members':left['members']+right['members']}
    if 'upper' in right: merged['upper'] = right['upper']
    return groups[:index]+[merged]+groups[index+2:]


def _pool(groups, direction, minimum):
    groups = [dict(g) for g in groups]
    while len(groups)>1:
        weak = next((i for i,g in enumerate(groups) if g['count']<minimum or min(g['bad'],g['count']-g['bad'])<20),None)
        if weak is None: break
        neighbors = [i for i in [weak-1,weak+1] if 0<=i<len(groups)]
        neighbor = min(neighbors,key=lambda i:abs(_rate(groups[i])-_rate(groups[weak])))
        groups = _merge(groups,min(weak,neighbor))
    while len(groups)>1:
        violation = None
        for i in range(len(groups)-1):
            differences = [_rate(groups[i+1],smooth)-_rate(groups[i],smooth) for smooth in [False,True]]
            if (direction=='ascending' and min(differences)<-1e-12) or (direction=='descending' and max(differences)>1e-12):
                violation = i
                break
        if violation is None: break
        groups = _merge(groups,violation)
    return groups


def _woe(groups):
    occupied = [g for g in groups if g['count']]
    good = sum(g['count']-g['bad'] for g in occupied)
    bad = sum(g['bad'] for g in occupied)
    bins = len(occupied)
    result = []
    for g in groups:
        if g['count']:
            good_share = (g['count']-g['bad']+.5)/(good+.5*bins)
            bad_share = (g['bad']+.5)/(bad+.5*bins)
            value = np.log(good_share/bad_share)
            iv = (good_share-bad_share)*value
        else: value,iv = 0.,0.
        result.append((float(value),float(iv)))
    return result


def _fit_bins(series, y, categorical, direction):
    missing = series.isna().to_numpy()
    x = series[~missing]
    labels = y[~missing]
    groups = []
    if categorical:
        x = x.astype(str)
        counts = x.value_counts()
        rare = set(counts[counts < .05*len(x)].index)
        mapped = x.map(lambda value:'__RARE__' if value in rare else value)
        for value in mapped.unique():
            mask = mapped.to_numpy()==value
            members = list(rare) if value=='__RARE__' else [value]
            groups.append({'members':sorted(members),'count':int(mask.sum()),'bad':int(labels[mask].sum())})
        groups.sort(key=_rate)
        # Merge adjacent risk-ordered groups until at most six remain.
        while len(groups)>6:
            i = min(range(len(groups)-1),key=lambda i:abs(_rate(groups[i+1])-_rate(groups[i])))
            groups = _merge(groups,i)
        directions = ['ascending']
    else:
        x = x.to_numpy(dtype=float)
        if np.isinf(x).any(): raise ValueError('Numeric scorecard inputs must be finite or missing.')
        unique = np.unique(x)
        cuts = (unique[:-1]+np.diff(unique)/2) if len(unique)<=6 else np.unique(np.quantile(x,np.arange(1,6)/6))
        cuts = cuts[(cuts>unique[0]) & (cuts<unique[-1])] if len(unique) else np.array([])
        if len(unique)>1 and len(cuts)==0: cuts=np.array([unique[0]+(unique[1]-unique[0])/2])
        ids = np.searchsorted(cuts,x,side='right')
        for i in range(len(cuts)+1):
            mask = ids==i
            if mask.any():groups.append({'members':[i],'upper':float(cuts[i]) if i<len(cuts) else np.inf,
                'count':int(mask.sum()),'bad':int(labels[mask].sum())})
        directions = [direction] if direction else ['ascending','descending']
    missing_group = {'members':['Missing'],'count':int(missing.sum()),'bad':int(y[missing].sum())}
    alternatives = []
    for order in directions:
        pooled = _pool(groups,order,max(1,int(np.ceil(.05*len(x)))))
        values = _woe(pooled+[missing_group])
        alternatives.append((sum(iv for _,iv in values),order,pooled,values))
    iv,order,groups,values = max(alternatives,key=lambda item:item[0])
    spec = {'categorical':categorical,'direction':order,'iv':iv,'woe':np.array([v for v,_ in values]),
        'missing_id':len(groups),'cuts':np.array([g['upper'] for g in groups[:-1]]) if not categorical else None,
        'category_bins':{member:i for i,g in enumerate(groups) for member in g['members']} if categorical else None}
    rows=[]
    lower=-np.inf
    for i,(g,(value,contribution)) in enumerate(zip(groups+[missing_group],values)):
        lower_bound,upper_bound=np.nan,np.nan
        if i==len(groups): label='Missing'
        elif categorical: label=' | '.join(g['members'])
        else:
            lower_bound,upper_bound=lower,g['upper']
            label=f'[{lower!r}, {g["upper"]!r})'
            lower=g['upper']
        rows.append({'bin_id':i,'bin':label,'lower_bound':lower_bound,'upper_bound':upper_bound,'ordered':i<len(groups),'count':g['count'],
            'good':g['count']-g['bad'],'bad':g['bad'],'event_rate':_rate(g) if g['count'] else np.nan,
            'smoothed_event_rate':_rate(g,True) if g['count'] else np.nan,'woe':value,'iv':contribution})
    return spec,rows


class WOEScorecard(ClassifierMixin,BaseEstimator):
    def __init__(self,features,categorical,iv_min=.02,constrained=False,C=1.):
        self.features=features
        self.categorical=categorical
        self.iv_min=iv_min
        self.constrained=constrained
        self.C=C

    def fit(self,X,y):
        validate_features(list(self.features))
        if list(X.columns)!=list(self.features): raise ValueError('Use the ordered feature contract.')
        y=np.asarray(y,dtype=float)
        if len(y)!=len(X) or not np.isfinite(y).all() or set(np.unique(y))!={0,1}:
            raise ValueError('Training requires aligned nonmissing binary outcomes.')
        self.classes_=np.array([0,1])
        self.n_features_in_=len(self.features)
        self.feature_names_in_=np.asarray(self.features,dtype=object)
        self.bins_,table,summary={},[],[]
        for name in self.features:
            categorical=name in self.categorical
            spec,rows=_fit_bins(X[name],y,categorical,DIRECTIONS.get(name))
            self.bins_[name]=spec
            selected=spec['iv']>=self.iv_min
            summary.append({'feature':name,'train_iv':spec['iv'],'selected':selected,
                'direction':spec['direction'],'direction_basis':'training risk order' if categorical else
                ('predeclared domain constraint' if name in DIRECTIONS else 'training-IV choice between ascending/descending')})
            if categorical:
                rows.append({'bin_id':len(rows),'bin':'Unseen category (neutral WoE)','ordered':False,
                    'count':0,'good':0,'bad':0,'event_rate':np.nan,'smoothed_event_rate':np.nan,'woe':0.,'iv':0.})
            for row in rows:table.append({'feature':name,'selected':selected,'direction':spec['direction'],**row})
        self.feature_table_=pd.DataFrame(summary)
        self.binning_table_=pd.DataFrame(table)
        self.selected_features_=self.feature_table_.loc[self.feature_table_.selected,'feature'].tolist()
        if not self.selected_features_:raise ValueError('No features pass the training IV screen.')
        woe=self.transform_woe(X)
        def objective(theta):
            intercept,beta=theta[0],theta[1:]
            eta=intercept+woe@beta
            residual=expit(eta)-y
            loss=np.logaddexp(0,eta).sum()-y@eta+.5/self.C*(beta@beta)
            gradient=np.r_[residual.sum(),woe.T@residual+beta/self.C]
            return loss,gradient
        initial=np.r_[np.log(y.mean()/(1-y.mean())),np.zeros(woe.shape[1])]
        bounds=[(None,None)]+[(None,0) if self.constrained else (None,None)]*woe.shape[1]
        result=minimize(objective,initial,jac=True,method='L-BFGS-B',bounds=bounds,
            options={'maxiter':1000,'ftol':1e-12,'gtol':1e-6})
        if not result.success:raise ValueError(f'Logistic fit failed: {result.message}')
        self.intercept_=np.array([result.x[0]])
        self.coef_=result.x[1:].reshape(1,-1)
        self.n_iter_=np.array([result.nit])
        self.factor_=20/np.log(2)
        self.offset_=600-self.factor_*np.log(50)
        return self

    def bin_assignments(self,X):
        check_is_fitted(self,'selected_features_')
        if list(X.columns)!=list(self.features):raise ValueError('Use the ordered feature contract.')
        columns={}
        for name in self.selected_features_:
            spec=self.bins_[name]
            missing=X[name].isna().to_numpy()
            if spec['categorical']:
                ids=X[name].astype(str).map(spec['category_bins']).fillna(len(spec['woe'])).to_numpy(dtype=int,copy=True)
            else:
                data=X[name].to_numpy(dtype=float)
                if np.isinf(data).any():raise ValueError('Numeric scorecard inputs must be finite or missing.')
                ids=np.searchsorted(spec['cuts'],data,side='right')
            ids[missing]=spec['missing_id']
            columns[name]=ids
        return pd.DataFrame(columns,index=X.index)

    def transform_woe(self,X):
        assignments=self.bin_assignments(X)
        return np.column_stack([np.r_[self.bins_[name]['woe'],0.][assignments[name]] for name in self.selected_features_])

    def decision_function(self,X):
        check_is_fitted(self,'coef_')
        return self.intercept_[0]+self.transform_woe(X)@self.coef_[0]

    def predict_proba(self,X):
        p=expit(self.decision_function(X))
        return np.column_stack([1-p,p])

    def predict(self,X):return (self.predict_proba(X)[:,1]>=.5).astype(int)

    def score_points(self,X):return self.offset_-self.factor_*self.decision_function(X)

    def point_contributions(self,X):
        count=len(self.selected_features_)
        points=(self.offset_-self.factor_*self.intercept_[0])/count-self.factor_*self.transform_woe(X)*self.coef_[0]
        return pd.DataFrame(points,columns=self.selected_features_,index=X.index)

    def points_table(self):
        table=self.binning_table_[self.binning_table_.selected].copy()
        coefficients=dict(zip(self.selected_features_,self.coef_[0]))
        table['coefficient']=table.feature.map(coefficients)
        table['points']=(self.offset_-self.factor_*self.intercept_[0])/len(coefficients)-self.factor_*table.woe*table.coefficient
        return table

    def coefficient_table(self):
        return pd.DataFrame({'feature':self.selected_features_,'coefficient':self.coef_[0],
            'expected_woe_sign':'nonpositive','sign_check_passed':self.coef_[0]<=1e-10,
            'zero_effect':np.abs(self.coef_[0])<1e-8})
