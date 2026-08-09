from __future__ import annotations
import argparse,csv,json
from collections import Counter,defaultdict
from pathlib import Path
from hwm_solver.protocol.replay import parse_initial_entities,parse_turns,_perspective_owner,_player_won,iter_compact_decisions

TYPES=["MOVE","MELEE_ATTACK","RANGED_ATTACK","WAIT","DEFEND","HERO_ACTION","CAST_OR_ABILITY","ABILITY","ATTACK"]

def _rows_for_battle(d:Path):
    init=(d/'init.txt').read_text(errors='replace'); turns=(d/'turns0.txt').read_text(errors='replace')
    es,_=parse_initial_entities(init);tr=parse_turns(turns);owner=_perspective_owner(es);won=_player_won(init,es,owner)
    yield from iter_compact_decisions(d.name,es,tr,owner,player_won=won)

def build(corpus:Path,out:Path,train_fraction:float=.8):
    root=corpus/'battles' if (corpus/'battles').is_dir() else corpus
    battles=sorted((x for x in root.iterdir() if x.is_dir()),key=lambda p:int(p.name));cut=int(len(battles)*train_fraction);train=battles[:cut];held=battles[cut:]
    counts=defaultdict(Counter);global_counts=defaultdict(Counter);rows=0
    for d in train:
        for r in _rows_for_battle(d):
            if r['action_type'] not in TYPES or r['has_unknown_command']:continue
            actor=next((e for e in r['state_before'] if int(e['uid'])==int(r['actor_uid'])),None)
            if not actor:continue
            side=r['side'];cid=int(actor['creature_id']);counts[(side,cid)][r['action_type']]+=1;global_counts[side][r['action_type']]+=1;rows+=1
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['side','creature_id','samples',*TYPES])
        for (side,cid),c in sorted(counts.items()):
            total=sum(c.values());alpha=.5;den=total+alpha*len(TYPES);w.writerow([side,cid,total,*[f'{(c[t]+alpha)/den:.9f}' for t in TYPES]])
        for side,c in sorted(global_counts.items()):
            total=sum(c.values());alpha=.5;den=total+alpha*len(TYPES);w.writerow([side,0,total,*[f'{(c[t]+alpha)/den:.9f}' for t in TYPES]])
    def dist(side,cid):
        c=counts.get((side,cid)) or global_counts.get(side,Counter());total=sum(c.values());alpha=.5;den=total+alpha*len(TYPES);return [(c[t]+alpha)/den for t in TYPES]
    metrics={}
    for side_filter in ('PLAYER','PVE'):
        n=top1=top3=0;nll=0.0
        for d in held:
            for r in _rows_for_battle(d):
                if r['side']!=side_filter or r['action_type'] not in TYPES or r['has_unknown_command']:continue
                actor=next((e for e in r['state_before'] if int(e['uid'])==int(r['actor_uid'])),None)
                if not actor:continue
                probs=dist(side_filter,int(actor['creature_id']));truth=TYPES.index(r['action_type']);order=sorted(range(len(TYPES)),key=lambda i:probs[i],reverse=True);n+=1;top1+=order[0]==truth;top3+=truth in order[:3];import math;nll-=math.log(max(1e-12,probs[truth]))
        metrics[side_filter]={'rows':n,'top1_action_type':top1/max(1,n),'top3_action_type':top3/max(1,n),'nll':nll/max(1,n)}
    report={'train_battles':len(train),'heldout_battles':len(held),'accepted_train_rows':rows,'creature_side_profiles':len(counts),'global':{s:dict(c) for s,c in global_counts.items()},'heldout_metrics':metrics,'out':str(out)}
    out.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');return report

def main():
    p=argparse.ArgumentParser();p.add_argument('corpus',type=Path);p.add_argument('--out',type=Path,default=Path('models/policy_priors.csv'));p.add_argument('--train-fraction',type=float,default=.8);a=p.parse_args();print(json.dumps(build(a.corpus,a.out,a.train_fraction),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
