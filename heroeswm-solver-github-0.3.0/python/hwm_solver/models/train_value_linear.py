from __future__ import annotations
import argparse,csv,json,math
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss,roc_auc_score,log_loss
from sklearn.preprocessing import StandardScaler
from hwm_solver.protocol.replay import parse_initial_entities,parse_turns,_perspective_owner,_player_won,iter_compact_decisions

FEATURES=[
 'log_hp_ratio','log_count_ratio','log_damage_ratio','attack_diff','defense_diff','speed_diff','initiative_diff',
 'alive_stack_diff','shooter_diff','hero_mana_diff','actor_is_player','progress_log','our_hp_log','enemy_hp_log'
]

def state_features(state:list[dict],owner:int|None,actor_uid:int,decision_index:int):
    def agg(ours:bool):
        xs=[e for e in state if bool(e.get('alive',True)) and ((int(e.get('owner',0))==owner)==ours)] if owner is not None else []
        hp=sum(max(0,(int(e.get('count',0))-1)*max(1,int(e.get('max_hp',1)))+int(e.get('top_hp',0))) for e in xs if not e.get('is_hero'))
        cnt=sum(max(0,int(e.get('count',0))) for e in xs if not e.get('is_hero'))
        dmg=sum(max(0,int(e.get('count',0)))*(float(e.get('min_damage',0))+float(e.get('max_damage',0)))/2 for e in xs if not e.get('is_hero'))
        def eff_attack(e):
            vals=e.get('effect_values',{}) or {}
            return float(e.get('attack',0))+float(vals.get('enr',0) or 0)+float(vals.get('blt',0) or 0)
        def eff_speed(e):
            return float(e.get('speed',0))*(0.5 if 'proc_cripple' in set(e.get('effects',[]) or []) else 1.0)
        def eff_ini(e):
            return float(e.get('initiative',0))*(0.7 if 'proc_cripple' in set(e.get('effects',[]) or []) else 1.0)
        atk=sum(eff_attack(e) for e in xs if not e.get('is_hero'))/max(1,sum(not e.get('is_hero') for e in xs))
        de=sum(float(e.get('defense',0)) for e in xs if not e.get('is_hero'))/max(1,sum(not e.get('is_hero') for e in xs))
        sp=sum(eff_speed(e) for e in xs if not e.get('is_hero'))/max(1,sum(not e.get('is_hero') for e in xs))
        ini=sum(eff_ini(e) for e in xs if not e.get('is_hero'))/max(1,sum(not e.get('is_hero') for e in xs))
        stacks=sum(not e.get('is_hero') for e in xs);shoot=sum((int(e.get('shots',0))>0 or 'shooter' in set(e.get('abilities',[]))) for e in xs)
        mana=sum(int(e.get('mana',0)) for e in xs if e.get('is_hero'))
        return hp,cnt,dmg,atk,de,sp,ini,stacks,shoot,mana
    a=agg(True);b=agg(False);actor=next((e for e in state if int(e['uid'])==actor_uid),None);actor_player=1.0 if actor and owner is not None and int(actor.get('owner',0))==owner else 0.0
    eps=1.0
    return np.asarray([
      math.log((a[0]+eps)/(b[0]+eps)),math.log((a[1]+eps)/(b[1]+eps)),math.log((a[2]+eps)/(b[2]+eps)),
      (a[3]-b[3])/100,(a[4]-b[4])/100,(a[5]-b[5])/20,(a[6]-b[6])/30,
      (a[7]-b[7])/10,(a[8]-b[8])/10,(a[9]-b[9])/100,actor_player,math.log1p(decision_index)/5,
      math.log1p(a[0])/15,math.log1p(b[0])/15
    ],dtype=np.float64)

def battle_rows(d:Path,max_per_battle:int=40):
    init=(d/'init.txt').read_text(errors='replace');turns=(d/'turns0.txt').read_text(errors='replace');es,_=parse_initial_entities(init);tr=parse_turns(turns);owner=_perspective_owner(es);won=_player_won(init,es,owner)
    if won is None:return [],None
    rows=[]
    for r in iter_compact_decisions(d.name,es,tr,owner,player_won=won):
        if r['has_unknown_command'] or r['action_type']=='FORCED_EVENT':continue
        rows.append((state_features(r['state_before'],owner,int(r['actor_uid']),int(r['decision_index'])),float(won)))
    if len(rows)>max_per_battle:
        idx=np.linspace(0,len(rows)-1,max_per_battle).round().astype(int);rows=[rows[i] for i in idx]
    return rows,won

def main():
 p=argparse.ArgumentParser();p.add_argument('corpus',type=Path);p.add_argument('--out',type=Path,default=Path('models/value_linear.json'));a=p.parse_args();root=a.corpus/'battles' if (a.corpus/'battles').is_dir() else a.corpus;battles=sorted((d for d in root.iterdir() if d.is_dir()),key=lambda d:int(d.name));n=len(battles);cut1=int(.8*n);cut2=int(.9*n)
 data={k:[] for k in ['train','val','test']};labels={k:[] for k in data};bids={k:[] for k in data}
 for i,d in enumerate(battles):
  split='train' if i<cut1 else ('val' if i<cut2 else 'test');rows,won=battle_rows(d)
  for x,y in rows:data[split].append(x);labels[split].append(y);bids[split].append(int(d.name))
 Xtr=np.stack(data['train']);ytr=np.asarray(labels['train']);sc=StandardScaler().fit(Xtr);X=sc.transform(Xtr)
 # Every battle contributes total weight 1 regardless of duration.
 bc=Counter(bids['train']);w=np.asarray([1/bc[b] for b in bids['train']]);w/=w.mean()
 model=LogisticRegression(C=.35,max_iter=2000,solver='lbfgs').fit(X,ytr,sample_weight=w)
 metrics={}
 for split in ['train','val','test']:
  xx=sc.transform(np.stack(data[split]));yy=np.asarray(labels[split]);pr=model.predict_proba(xx)[:,1]
  # report both row and battle-balanced averages
  by={}
  for p,y,b in zip(pr,yy,bids[split]):by.setdefault(b,[[],y])[0].append(float(p))
  bp=np.asarray([np.mean(v[0]) for v in by.values()]);byy=np.asarray([v[1] for v in by.values()])
  metrics[split]={'rows':len(yy),'battles':len(by),'brier_rows':float(brier_score_loss(yy,pr)),'brier_battles':float(brier_score_loss(byy,bp)),'constant_brier_battles':float(np.mean((byy-byy.mean())**2)),'auc_battles':float(roc_auc_score(byy,bp)) if len(set(byy))>1 else None,'logloss_battles':float(log_loss(byy,bp,labels=[0,1]))}
 payload={'schema_version':2,'features':FEATURES,'mean':sc.mean_.tolist(),'scale':sc.scale_.tolist(),'coef':model.coef_[0].tolist(),'intercept':float(model.intercept_[0]),'metrics':metrics,'note':'battle-balanced logistic value baseline; corrected owner=1 player perspective; raw protocol only; semantically unresolved mechanics remain explicit dataset uncertainty and old state parser is not used'}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(payload,indent=2),encoding='utf-8')
 csv_out=a.out.with_suffix('.csv')
 with csv_out.open('w',newline='',encoding='utf-8') as f:
  w=csv.writer(f);w.writerow(['kind',*FEATURES]);w.writerow(['mean',*payload['mean']]);w.writerow(['scale',*payload['scale']]);w.writerow(['coef',*payload['coef']]);w.writerow(['intercept',payload['intercept'],*(['']*(len(FEATURES)-1))])
 print(json.dumps(payload,indent=2))
if __name__=='__main__':main()
