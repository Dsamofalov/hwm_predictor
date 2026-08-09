from __future__ import annotations
import argparse,json,math
from collections import Counter
from pathlib import Path
import numpy as np
from scipy import sparse
from scipy.optimize import minimize
from sklearn.metrics import brier_score_loss,roc_auc_score,log_loss
from hwm_solver.protocol.replay import parse_initial_entities,parse_turns,_perspective_owner,_player_won,iter_compact_decisions
from hwm_solver.models.train_value_linear import state_features
from hwm_solver.knowledge.build_catalog import fnv1a32


def _entity_hp(e):
    if e.get('is_hero') or not e.get('alive',True): return 0.0
    c=max(0,int(e.get('count',0)));mh=max(1,int(e.get('max_hp',1)));top=max(0,int(e.get('top_hp',0)))
    return max(0.0,(c-1)*mh+top) if c else 0.0

def _ability_map(state,owner):
    sides={True:[],False:[]}
    for e in state:
        if e.get('is_hero') or not e.get('alive',True): continue
        ours=owner is not None and int(e.get('owner',0))==owner
        hp=_entity_hp(e); power=hp*(1.0+0.02*max(0.0,float(e.get('attack',0)))+0.01*max(0.0,float(e.get('defense',0))))
        sides[ours].append((e,power))
    out={}
    for ours,rows in sides.items():
        total=max(1e-9,sum(p for _,p in rows));sign=1.0 if ours else -1.0
        for e,p in rows:
            w=sign*p/total
            for code in set(e.get('abilities',[]) or []): out[code]=out.get(code,0.0)+w
    return out

def _baseline(model,x):
    mean=np.asarray(model['mean']);scale=np.asarray(model['scale']);coef=np.asarray(model['coef']);z=float(model['intercept'])+float(np.dot(coef,(x-mean)/scale));return z

def battle_rows(d,max_per_battle=40):
    init=(d/'init.txt').read_text(errors='replace');turns=(d/'turns0.txt').read_text(errors='replace');es,_=parse_initial_entities(init);tr=parse_turns(turns);owner=_perspective_owner(es);won=_player_won(init,es,owner)
    if won is None:return []
    rows=[]
    for r in iter_compact_decisions(d.name,es,tr,owner,player_won=won):
        if r['has_unknown_command'] or r['action_type']=='FORCED_EVENT':continue
        rows.append((state_features(r['state_before'],owner,int(r['actor_uid']),int(r['decision_index'])),_ability_map(r['state_before'],owner),float(won),int(d.name)))
    if len(rows)>max_per_battle:
        idx=np.linspace(0,len(rows)-1,max_per_battle).round().astype(int);rows=[rows[i] for i in idx]
    return rows

def _sigmoid(z):
    z=np.clip(z,-30,30);return 1/(1+np.exp(-z))

def _report(rows, logits):
    y=np.asarray([r[2] for r in rows]);p=_sigmoid(logits);by={}
    for pr,(_,_,yy,b) in zip(p,rows):by.setdefault(b,[[],yy])[0].append(float(pr))
    bp=np.asarray([np.mean(v[0]) for v in by.values()]);byy=np.asarray([v[1] for v in by.values()])
    return {'rows':len(rows),'battles':len(by),'brier_rows':float(brier_score_loss(y,p)),'brier_battles':float(brier_score_loss(byy,bp)),'auc_battles':float(roc_auc_score(byy,bp)) if len(set(byy))>1 else None,'logloss_battles':float(log_loss(byy,bp,labels=[0,1]))}

def train(corpus:Path,baseline_path:Path,out:Path,min_support=30):
    base=json.loads(baseline_path.read_text());root=corpus/'battles' if (corpus/'battles').is_dir() else corpus;battles=sorted((d for d in root.iterdir() if d.is_dir()),key=lambda p:int(p.name));n=len(battles);c1=int(.8*n);c2=int(.9*n)
    groups={'train':[],'val':[],'test':[]}
    for i,d in enumerate(battles):groups['train' if i<c1 else ('val' if i<c2 else 'test')].extend(battle_rows(d))
    support=Counter(code for _,am,_,_ in groups['train'] for code,v in am.items() if abs(v)>1e-12)
    vocab=sorted(c for c,n in support.items() if n>=min_support);idx={c:i for i,c in enumerate(vocab)}
    mats={};base_logits={}
    for split,rows in groups.items():
        rr=[];cc=[];vv=[];bl=[]
        for i,(x,am,_,_) in enumerate(rows):
            bl.append(_baseline(base,x))
            for code,v in am.items():
                j=idx.get(code)
                if j is not None:rr.append(i);cc.append(j);vv.append(v)
        mats[split]=sparse.csr_matrix((vv,(rr,cc)),shape=(len(rows),len(vocab)));base_logits[split]=np.asarray(bl)
    y=np.asarray([r[2] for r in groups['train']]);bc=Counter(r[3] for r in groups['train']);weights=np.asarray([1/bc[r[3]] for r in groups['train']]);weights/=weights.mean();X=mats['train'];z0=base_logits['train']
    def fit(alpha):
        def fg(b):
            z=z0+X@b;p=_sigmoid(z);loss=np.sum(weights*(np.logaddexp(0,z)-y*z))/len(y)+0.5*alpha*np.dot(b,b)/len(y);g=np.asarray(X.T@(weights*(p-y))).ravel()/len(y)+alpha*b/len(y);return loss,g
        return minimize(lambda b:fg(b),np.zeros(len(vocab)),jac=True,method='L-BFGS-B',options={'maxiter':160,'ftol':1e-9}).x
    trials=[]
    for alpha in (80.0,200.0,500.0,1000.0,3000.0):
        b=fit(alpha);val=_report(groups['val'],base_logits['val']+mats['val']@b);trials.append((val['brier_battles'],val['logloss_battles'],alpha,b,val))
    _,_,alpha,b,val=min(trials,key=lambda x:(x[0],x[1]))
    metrics={}
    for split in groups:
        metrics[split]={'baseline':_report(groups[split],base_logits[split]),'ability':_report(groups[split],base_logits[split]+mats[split]@b)}
    coeff=[{'ability_id':fnv1a32(code),'code':code,'samples':support[code],'coefficient':float(v)} for code,v in zip(vocab,b) if abs(v)>=1e-5]
    payload={'schema_version':1,'source':'raw corpus only; ability composition residual on top of fixed battle-balanced numeric value baseline','baseline':str(baseline_path),'min_support':min_support,'alpha':alpha,'coefficients':coeff,'metrics':metrics}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    csvp=out.with_suffix('.csv')
    import csv
    with csvp.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['ability_id','code','samples','coefficient']);w.writeheader();w.writerows(coeff)
    return payload

def main():
    p=argparse.ArgumentParser();p.add_argument('corpus',type=Path);p.add_argument('--baseline',type=Path,default=Path('models/value_linear.json'));p.add_argument('--out',type=Path,default=Path('models/ability_value.json'));a=p.parse_args();print(json.dumps(train(a.corpus,a.baseline,a.out),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
