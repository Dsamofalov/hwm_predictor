from __future__ import annotations
import argparse,json
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from hwm_solver.protocol.replay import parse_initial_entities,parse_turns,_perspective_owner,_player_won,iter_compact_decisions,_spellbook_entries

def hp(e):
 c=max(0,int(e.get('count',0)));return 0 if c<=0 or e.get('is_hero') or not e.get('alive',True) else (c-1)*max(1,int(e.get('max_hp',1)))+max(0,int(e.get('top_hp',0)))
def load_registry(path):return {x['code']:x for x in json.loads(path.read_text(encoding='utf-8'))['abilities']}
def report(corpus:Path,registry:Path,out:Path|None=None,split=.8,stride=4):
 reg=load_registry(registry);root=corpus/'battles' if (corpus/'battles').is_dir() else corpus;bs=sorted((d for d in root.iterdir() if d.is_dir()),key=lambda p:int(p.name));bs=bs[int(len(bs)*split):]
 risks=[];weighted=defaultdict(float);seen=Counter();states=0
 for d in bs:
  init=(d/'init.txt').read_text(errors='replace');turns=(d/'turns0.txt').read_text(errors='replace');es,_=parse_initial_entities(init);owner=_perspective_owner(es);won=_player_won(init,es,owner)
  spellbooks={uid:_spellbook_entries(ent) for uid,ent in es.items()}
  for i,r in enumerate(iter_compact_decisions(d.name,es,parse_turns(turns),owner,player_won=won)):
   if i%stride:continue
   if r['side']!='PLAYER':continue
   st=r['state_before'];total=0.;num=0.;states+=1
   for e in st:
    eh=hp(e)
    if eh<=0 or e.get('is_hidden'):continue
    power=max(1.,eh)*(1+.01*max(0.,float(e.get('attack',0)))+.005*max(0.,float(e.get('defense',0))));er=0.
    for code in set(e.get('abilities',[]) or []):
     if code=='caster':
      book=spellbooks.get(int(e.get('uid',0)),[])
      supported=sum(1 for name,_,_ in book if name in {'magicfist','lighting','icebolt','magicarrow','swarm','raisedead'})
      rr=.60 if not book else max(.10,min(.85,.10+.75*(1-supported/len(book))))
     else:
      rr=float(reg.get(code,{}).get('risk_weight',.85))
     er=1-(1-er)*(1-.45*rr);weighted[code]+=power*.45*rr;seen[code]+=1
    num+=power*min(1.,er);total+=power
   risks.append(num/total if total else 0.)
 arr=np.asarray(risks)
 top=[]
 for code,w in sorted(weighted.items(),key=lambda kv:kv[1],reverse=True)[:40]:
  x=reg.get(code,{});top.append({'code':code,'name':x.get('name',code),'support':x.get('support','missing'),'risk_weight':x.get('risk_weight',.85),'state_occurrences':seen[code],'weighted_contribution':w,'categories':x.get('categories',[])})
 payload={'heldout_battles':len(bs),'sampled_player_states':states,'risk_mean':float(arr.mean()) if len(arr) else 0,'risk_p50':float(np.quantile(arr,.5)) if len(arr) else 0,'risk_p90':float(np.quantile(arr,.9)) if len(arr) else 0,'risk_p99':float(np.quantile(arr,.99)) if len(arr) else 0,'top_contributors':top}
 if out:out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
 return payload

def main():
 p=argparse.ArgumentParser();p.add_argument('corpus',type=Path);p.add_argument('--registry',type=Path,default=Path('data/catalog/ability_registry.json'));p.add_argument('--out',type=Path,default=Path('data/reports/ability-risk.json'));a=p.parse_args();print(json.dumps(report(a.corpus,a.registry,a.out),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
