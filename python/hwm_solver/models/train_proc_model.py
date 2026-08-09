from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

from hwm_solver.protocol.replay import (
    parse_initial_entities,
    parse_turns,
    _perspective_owner,
    _player_won,
    iter_compact_decisions,
    parse_commands,
)

RULES={
 'entroots':          {'signal':'ent','types':{'MELEE_ATTACK'},'effect':'root','max_drift':.05,'min_test':30},
 'ferociouswound':   {'signal':'fdc','types':{'MELEE_ATTACK'},'effect':'ferocious_wound','max_drift':.10,'min_test':30},
 'blinding_attack':  {'signal':'bld','types':{'MELEE_ATTACK','RANGED_ATTACK'},'effect':'blind','max_drift':.08,'min_test':50},
 'torpor':            {'signal':'tor','types':{'MELEE_ATTACK'},'effect':'torpor','max_drift':.05,'min_test':30},
 'stoning':           {'signal':'sta','types':{'MELEE_ATTACK'},'effect':'stone','max_drift':.10,'min_test':30},
 'cripplingwound':    {'signal':'wnd','types':{'MELEE_ATTACK','RANGED_ATTACK'},'effect':'cripple','max_drift':.10,'min_test':30},
 'cursingattack':      {'signal':'sff','types':{'MELEE_ATTACK','RANGED_ATTACK'},'effect':'suffering','max_drift':.05,'min_test':50},
 'wardingarrows':      {'signal':'T_RECORD','types':{'RANGED_ATTACK'},'effect':'atb_delay','max_drift':.08,'min_test':50},
}

# Shield Bash is different from the Sxxx proc families above. The supplied new raw corpus
# exposes an independent `o<actor_uid>` marker. Conditioned on a shieldbash melee attacker,
# this marker is 119/119 precise; no marker is observed against mechanical targets. Its raw
# frequency drifts with army composition, so we fit a small conditional probability model
# and require temporal held-out Brier/AUC improvement before production enablement.
SHIELDBASH_FEATURES = [
    'log_actor_hp','log_target_hp','log_actor_count','log_target_count',
    'actor_attack','target_defense','actor_speed','target_speed','target_big',
]


def _stack_hp(e: dict) -> int:
    c=max(0,int(e.get('count',0))); mh=max(1,int(e.get('max_hp',1)))
    if c<=0:return 0
    return (c-1)*mh+max(1,int(e.get('top_hp',mh)))


def _shield_features(actor:dict,target:dict)->np.ndarray:
    return np.asarray([
        math.log1p(max(1,_stack_hp(actor))), math.log1p(max(1,_stack_hp(target))),
        math.log1p(max(1,int(actor.get('count',0)))), math.log1p(max(1,int(target.get('count',0)))),
        float(actor.get('attack',0)), float(target.get('defense',0)),
        float(actor.get('speed',0)), float(target.get('speed',0)),
        1.0 if 'big' in set(target.get('abilities') or []) else 0.0,
    ],dtype=np.float64)


def collect(dirs):
    out={k:[0,0] for k in RULES}
    shield_x=[];shield_y=[];stone_x=[];stone_y=[]
    for d in dirs:
        init=(d/'init.txt').read_text(errors='replace'); turns=(d/'turns0.txt').read_text(errors='replace')
        es,_=parse_initial_entities(init);owner=_perspective_owner(es);won=_player_won(init,es,owner)
        for r in iter_compact_decisions(d.name,es,parse_turns(turns),owner,player_won=won):
            by={int(e['uid']):e for e in r['state_before']};actor=by.get(int(r['actor_uid']));target=by.get(int(r['target_uid'])) if r.get('target_uid') is not None else None
            if not actor:continue
            abilities=set(actor.get('abilities') or []);signals=set(r['special_codes']);cmds=parse_commands(r['raw'])
            for code,spec in RULES.items():
                if code not in abilities or r['action_type'] not in spec['types']:continue
                if code in {'blinding_attack','torpor'}:
                    if not target:continue
                    ta=set(target.get('abilities') or [])
                    if ta.intersection({'undead','elemental','mechanical'}):continue
                hit = spec['signal'] in signals
                if code=='wardingarrows':
                    hit = bool(target) and any(c.opcode=='T_RECORD' and c.raw[1:4]==f"{int(r['actor_uid']):03d}" and c.raw[4:7]==f"{int(r['target_uid']):03d}" for c in cmds)
                out[code][0]+=1;out[code][1]+=int(hit)
                if code=='stoning' and target:
                    stone_x.append(_shield_features(actor,target));stone_y.append(int(hit))
            if 'shieldbash' in abilities and r['action_type']=='MELEE_ATTACK' and target:
                if 'mechanical' in set(target.get('abilities') or []):
                    continue
                marker=f"o{int(r['actor_uid']):03d}"
                hit=any(c.opcode=='OPAQUE_SHORT' and c.raw==marker for c in cmds)
                shield_x.append(_shield_features(actor,target));shield_y.append(int(hit))
    X=np.stack(shield_x) if shield_x else np.zeros((0,len(SHIELDBASH_FEATURES)),dtype=np.float64)
    y=np.asarray(shield_y,dtype=np.int64)
    SX=np.stack(stone_x) if stone_x else np.zeros((0,len(SHIELDBASH_FEATURES)),dtype=np.float64)
    Sy=np.asarray(stone_y,dtype=np.int64)
    return out,(X,y),(SX,Sy)


def _join(values):
    return '|'.join(f'{float(x):.12g}' for x in values)


def train(corpus:Path,out:Path,split=.8):
    root=corpus/'battles' if (corpus/'battles').is_dir() else corpus
    battles=sorted((d for d in root.iterdir() if d.is_dir()),key=lambda p:int(p.name));cut=int(len(battles)*split)
    tr,tr_sh,tr_st=collect(battles[:cut]);te,te_sh,te_st=collect(battles[cut:]);rows=[]
    for code,spec in RULES.items():
        tn,th=tr[code];vn,vh=te[code];tp=th/tn if tn else 0.;vp=vh/vn if vn else 0.
        enabled=bool(tn>=50 and vn>=spec['min_test'] and abs(tp-vp)<=spec['max_drift'] and (tp>=.03))
        rows.append({'ability_code':code,'action_types':'|'.join(sorted(spec['types'])),'effect':spec['effect'],'signal':spec['signal'],
         'train_n':tn,'train_hits':th,'train_probability':tp,'heldout_n':vn,'heldout_hits':vh,'heldout_probability':vp,
         'abs_drift':abs(tp-vp),'enabled':int(enabled),'model_type':'constant','conditional_intercept':'',
         'conditional_mean':'','conditional_scale':'','conditional_coef':'','heldout_brier':'','baseline_brier':'','heldout_auc':''})

    # Stoning has a stable wire marker but a composition-dependent raw frequency.
    # Fit a tiny conditional model and enable it only if temporal held-out quality beats
    # the train-frequency baseline.  This keeps the effect semantics exact while the
    # chance remains learned.
    stoning_metrics={'train_n':len(tr_st[1]),'heldout_n':len(te_st[1])}
    SXtr,Sytr=tr_st;SXte,Syte=te_st
    if len(Sytr)>=50 and len(Syte)>=30 and len(np.unique(Sytr))==2 and len(np.unique(Syte))==2:
        sscaler=StandardScaler().fit(SXtr)
        smodel=LogisticRegression(C=.5,max_iter=2000,solver='lbfgs').fit(sscaler.transform(SXtr),Sytr)
        sp=smodel.predict_proba(sscaler.transform(SXte))[:,1];sbase=np.full(len(Syte),float(Sytr.mean()))
        sb=float(brier_score_loss(Syte,sp));sbb=float(brier_score_loss(Syte,sbase));sauc=float(roc_auc_score(Syte,sp))
        senabled=bool(sb+0.005<sbb and sauc>=0.60)
        stoning_metrics.update({'heldout_brier':sb,'baseline_brier':sbb,'heldout_auc':sauc,'enabled':senabled})
        if senabled:
            for row in rows:
                if row['ability_code']=='stoning':
                    row.update({'enabled':1,'model_type':'logistic','conditional_intercept':f'{float(smodel.intercept_[0]):.12g}',
                        'conditional_mean':_join(sscaler.mean_),'conditional_scale':_join(sscaler.scale_),'conditional_coef':_join(smodel.coef_[0]),
                        'heldout_brier':sb,'baseline_brier':sbb,'heldout_auc':sauc})
                    break
    else:
        stoning_metrics.update({'enabled':False,'reason':'insufficient_binary_temporal_sample'})

    Xtr,ytr=tr_sh;Xte,yte=te_sh
    shield_metrics={'train_n':len(ytr),'heldout_n':len(yte)}
    if len(ytr)>=100 and len(yte)>=30 and len(np.unique(ytr))==2 and len(np.unique(yte))==2:
        scaler=StandardScaler().fit(Xtr)
        model=LogisticRegression(C=.5,max_iter=2000,solver='lbfgs').fit(scaler.transform(Xtr),ytr)
        p=model.predict_proba(scaler.transform(Xte))[:,1]
        base=np.full(len(yte),float(ytr.mean()))
        brier=float(brier_score_loss(yte,p)); base_brier=float(brier_score_loss(yte,base))
        auc=float(roc_auc_score(yte,p)); ll=float(log_loss(yte,p)); base_ll=float(log_loss(yte,base))
        enabled=bool(brier+0.01<base_brier and auc>=0.60)
        shield_metrics.update({'heldout_brier':brier,'baseline_brier':base_brier,'heldout_auc':auc,'heldout_logloss':ll,'baseline_logloss':base_ll,'enabled':enabled})
        rows.append({'ability_code':'shieldbash','action_types':'MELEE_ATTACK','effect':'stun_delay','signal':'o<actor>',
         'train_n':len(ytr),'train_hits':int(ytr.sum()),'train_probability':float(ytr.mean()),'heldout_n':len(yte),'heldout_hits':int(yte.sum()),'heldout_probability':float(yte.mean()),
         'abs_drift':abs(float(ytr.mean()-yte.mean())),'enabled':int(enabled),'model_type':'logistic','conditional_intercept':f'{float(model.intercept_[0]):.12g}',
         'conditional_mean':_join(scaler.mean_),'conditional_scale':_join(scaler.scale_),'conditional_coef':_join(model.coef_[0]),
         'heldout_brier':brier,'baseline_brier':base_brier,'heldout_auc':auc})
    else:
        shield_metrics.update({'enabled':False,'reason':'insufficient_binary_temporal_sample'})

    fields=['ability_code','action_types','effect','signal','train_n','train_hits','train_probability','heldout_n','heldout_hits','heldout_probability','abs_drift','enabled',
            'model_type','conditional_intercept','conditional_mean','conditional_scale','conditional_coef','heldout_brier','baseline_brier','heldout_auc']
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    payload={'schema_version':2,'split':split,'authority':'proc markers/probabilities fitted on first 80% raw battles; production enable gate uses last 20% only',
             'shieldbash_features':SHIELDBASH_FEATURES,'shieldbash_metrics':shield_metrics,'stoning_metrics':stoning_metrics,'rules':rows}
    out.with_suffix('.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    return payload


def main():
    p=argparse.ArgumentParser();p.add_argument('corpus',type=Path);p.add_argument('--out',type=Path,default=Path('models/proc_model.csv'));a=p.parse_args();print(json.dumps(train(a.corpus,a.out),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
