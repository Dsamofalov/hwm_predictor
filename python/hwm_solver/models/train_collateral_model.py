from __future__ import annotations
import argparse,csv,json
from pathlib import Path
from hwm_solver.models.train_damage_model import _rows
from hwm_solver.protocol.replay import parse_commands

RULES={
 'fire_breath':('MELEE_ATTACK','behind',4),
 'acid_breath':('MELEE_ATTACK','behind',4),
 'icedbreath':('MELEE_ATTACK','behind',4),
 'deathcloud':('RANGED_ATTACK','target_adjacent',8),
 'spray':('MELEE_ATTACK','actor_adjacent',2),
 'threehead':('MELEE_ATTACK','actor_adjacent',2),
 'six_heads':('MELEE_ATTACK','actor_adjacent',5),
}

def cells(e):
 w=2 if 'big' in set(e.get('abilities',[])) else 1
 return {(int(e['x'])+dx,int(e['y'])+dy) for dx in range(w) for dy in range(w)}
def near(a,b):return any(max(abs(x-u),abs(y-v))<=1 for x,y in a for u,v in b)
def sgn(x):return (x>0)-(x<0)
def candidates(zone,r,a,t,state):
 if zone=='actor_adjacent':
  ax=int(r.get('destination_x') if r.get('destination_x') is not None else a['x']);ay=int(r.get('destination_y') if r.get('destination_y') is not None else a['y']);w=2 if 'big' in set(a.get('abilities',[])) else 1;z={(ax+dx,ay+dy) for dx in range(w) for dy in range(w)}
  return {int(e['uid']) for e in state if int(e['uid'])!=int(t['uid']) and e.get('alive',True) and near(z,cells(e))}
 if zone=='target_adjacent':
  z=cells(t);return {int(e['uid']) for e in state if int(e['uid'])!=int(t['uid']) and e.get('alive',True) and near(z,cells(e))}
 if zone=='behind':
  ax=int(r.get('destination_x') if r.get('destination_x') is not None else a['x']);ay=int(r.get('destination_y') if r.get('destination_y') is not None else a['y']);tc=cells(t);tx=sum(x for x,y in tc)/len(tc);ty=sum(y for x,y in tc)/len(tc);dx,dy=sgn(tx-ax),sgn(ty-ay);z={(x+dx,y+dy) for x,y in tc}-tc
  return {int(e['uid']) for e in state if int(e['uid'])!=int(t['uid']) and e.get('alive',True) and cells(e)&z}
 return set()

def train(corpus:Path,out:Path,train_fraction=.8):
 root=corpus/'battles' if (corpus/'battles').is_dir() else corpus;battles=sorted((d for d in root.iterdir() if d.is_dir()),key=lambda p:int(p.name));cut=int(len(battles)*train_fraction)
 def collect(ds):
  st={c:{'decisions':0,'candidate_opportunities':0,'actual_secondary':0,'true_candidate_hits':0,'missed_secondary':0,'exact_sets':0} for c in RULES}
  for d in ds:
   for r in _rows(d):
    if r.get('target_uid') is None:continue
    state=r['state_before'];a=next((e for e in state if int(e['uid'])==int(r['actor_uid'])),None);t=next((e for e in state if int(e['uid'])==int(r['target_uid'])),None)
    if not a or not t:continue
    abs=set(a.get('abilities',[]))
    for code,(action,zone,cap) in RULES.items():
     if code not in abs or r['action_type']!=action:continue
     actual={int(c.target_uid) for c in parse_commands(r['raw']) if c.opcode=='DAMAGE' and c.actor_uid==int(r['actor_uid']) and c.target_uid is not None and int(c.target_uid)!=int(r['target_uid']) and int(c.amount or 0)>0}
     cand=candidates(zone,r,a,t,state);x=st[code];x['decisions']+=1;x['candidate_opportunities']+=len(cand);x['actual_secondary']+=len(actual);x['true_candidate_hits']+=len(actual&cand);x['missed_secondary']+=len(actual-cand);x['exact_sets']+=actual==cand
  for code,x in st.items():
   x['candidate_hit_probability']=x['true_candidate_hits']/max(1,x['candidate_opportunities']);x['recall']=x['true_candidate_hits']/max(1,x['actual_secondary']);x['exact_set_rate']=x['exact_sets']/max(1,x['decisions'])
  return st
 tr=collect(battles[:cut]);te=collect(battles[cut:]);rows=[]
 for code,(action,zone,cap) in RULES.items():
  # Use train probability only. Held-out is diagnostics and never feeds runtime parameters.
  p_train=tr[code]['candidate_hit_probability'];p_test=te[code]['candidate_hit_probability'];held=te[code]['decisions']
  stable_prob=(p_train>0 and 0.5 <= p_test/p_train <= 1.5) if held else False
  enabled=bool(tr[code]['decisions']>=50 and held>=20 and stable_prob and te[code]['recall']>=0.45)
  rows.append({'ability_code':code,'action_type':action,'zone':zone,'max_secondary':cap,'enabled':int(enabled),'train_decisions':tr[code]['decisions'],'candidate_hit_probability':p_train,'train_recall':tr[code]['recall'],'heldout_decisions':held,'heldout_precision':p_test,'heldout_recall':te[code]['recall'],'heldout_exact_set_rate':te[code]['exact_set_rate']})
 out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 report={'source':'raw replay collateral DAMAGE targets only; old parser not used','train_battles':cut,'heldout_battles':len(battles)-cut,'rules':rows,'out':str(out)};out.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');return report

def main():
 p=argparse.ArgumentParser();p.add_argument('corpus',type=Path);p.add_argument('--out',type=Path,default=Path('models/collateral_model.csv'));a=p.parse_args();print(json.dumps(train(a.corpus,a.out),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
