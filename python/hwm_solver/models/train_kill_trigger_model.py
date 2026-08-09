from __future__ import annotations
import argparse,csv,json
from pathlib import Path
from collections import Counter
import numpy as np
from hwm_solver.protocol.replay import iter_battle_decisions

RULES={
    'enraged': {'wire':'enr','event':'friendly_stack_death','max_drift':0.03,'min_test':100},
    'bloodlust': {'wire':'blt','event':'enemy_stack_death_by_our_side','max_drift':0.05,'min_test':80},
}

def collect(battles):
    stats={k:Counter() for k in RULES};deltas={k:[] for k in RULES}
    for d in battles:
        for r in iter_battle_decisions(d):
            before={int(e['uid']):e for e in r['state_before']};after={int(e['uid']):e for e in r['state_after']}
            dead=[u for u,e in before.items() if e.get('alive',True) and not e.get('is_hero') and u in after and not after[u].get('alive',True)]
            if len(dead)!=1: continue
            du=dead[0];dead_owner=int(before[du].get('owner',0));actor_owner=int(before.get(int(r['actor_uid']),{}).get('owner',0))
            for uid,b in before.items():
                a=after.get(uid)
                if not a or not a.get('alive',True) or b.get('is_hero'): continue
                abilities=set(b.get('abilities') or []);bv=b.get('effect_values',{}) or {};av=a.get('effect_values',{}) or {}
                if ('enraged' in abilities or 'packenrage' in abilities) and int(b.get('owner',0))==dead_owner:
                    stats['enraged']['eligible']+=1;delta=float(av.get('enr',0) or 0)-float(bv.get('enr',0) or 0)
                    if delta>0:stats['enraged']['hits']+=1;deltas['enraged'].append(delta)
                if 'bloodlust' in abilities and actor_owner!=dead_owner and int(b.get('owner',0))==actor_owner:
                    stats['bloodlust']['eligible']+=1;delta=float(av.get('blt',0) or 0)-float(bv.get('blt',0) or 0)
                    if delta>0:stats['bloodlust']['hits']+=1;deltas['bloodlust'].append(delta)
    return stats,deltas

def train(corpus:Path,out:Path,split=.8):
    root=corpus/'battles' if (corpus/'battles').is_dir() else corpus
    battles=sorted((d for d in root.iterdir() if d.is_dir()),key=lambda p:int(p.name));cut=int(len(battles)*split)
    tr,td=collect(battles[:cut]);te,vd=collect(battles[cut:]);rows=[]
    for code,spec in RULES.items():
        tn,th=tr[code]['eligible'],tr[code]['hits'];vn,vh=te[code]['eligible'],te[code]['hits'];tp=th/tn if tn else 0.;vp=vh/vn if vn else 0.;drift=abs(tp-vp)
        # Lower-bound increment = 1 because every positive observed update is >=1.
        enabled=bool(tn>=200 and vn>=spec['min_test'] and drift<=spec['max_drift'] and tp>=.5)
        rows.append({'ability_code':code,'event':spec['event'],'train_n':tn,'train_hits':th,'train_probability':tp,'heldout_n':vn,'heldout_hits':vh,'heldout_probability':vp,'abs_drift':drift,'increment':1,'enabled':int(enabled),'train_delta_median':float(np.median(td[code])) if td[code] else 0,'heldout_delta_median':float(np.median(vd[code])) if vd[code] else 0})
    out.parent.mkdir(parents=True,exist_ok=True)
    fields=list(rows[0]);
    with out.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    report={'schema_version':1,'source':'new raw corpus only; old parser not used','split':split,'rows':rows,'note':'Only temporally stable kill-trigger probabilities are enabled. Increment is conservative observed lower bound.'}
    out.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');return report

def main():
    p=argparse.ArgumentParser();p.add_argument('corpus',type=Path);p.add_argument('--out',type=Path,default=Path('models/kill_trigger_model.csv'));a=p.parse_args();print(json.dumps(train(a.corpus,a.out),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
