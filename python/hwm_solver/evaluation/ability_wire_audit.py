from __future__ import annotations
import argparse, json, re
from collections import Counter, defaultdict
from pathlib import Path
from hwm_solver.protocol.replay import iter_battle_decisions

DEFAULT = [
    'cursingattack','festeringaura','shieldbash','incorporeal','weakeningstrike',
    'stoning','cripplingwound','entroots','ferociouswound','blinding_attack','torpor',
]
S_RE=re.compile(r'S([A-Za-z_]{3})')


def audit(corpus: Path, out: Path, abilities: list[str], train_fraction: float=.8):
    root=corpus/'battles' if (corpus/'battles').is_dir() else corpus
    battles=sorted([d for d in root.iterdir() if d.is_dir()], key=lambda p:int(p.name))
    cut=int(len(battles)*train_fraction)
    split={d.name:('train' if i<cut else 'heldout') for i,d in enumerate(battles)}
    stats={a:{'train':Counter(),'heldout':Counter()} for a in abilities}
    examples={a:[] for a in abilities}
    decisions=0
    for bi,d in enumerate(battles,1):
        sp=split[d.name]
        for row in iter_battle_decisions(d):
            decisions+=1
            actor=next((e for e in row['state_before'] if int(e['uid'])==int(row['actor_uid'])),None)
            if not actor: continue
            aset=set(actor.get('abilities',[]) or [])
            matched=aset.intersection(abilities)
            if not matched: continue
            raw=row.get('raw','')
            scodes=S_RE.findall(raw)
            for a in matched:
                c=stats[a][sp]
                c['decisions']+=1
                c['action:'+str(row.get('action_type'))]+=1
                if row.get('target_uid') is not None: c['has_target']+=1
                for op in row.get('raw_opcodes',[]): c['opcode:'+str(op)]+=1
                for code in scodes: c['S:'+code]+=1
                # A few short record families with independent semantics in this corpus.
                for marker in ('o','W','&','A','B','b','r','s','h','p','k','x','Y','z'):
                    if marker in raw: c['contains:'+marker]+=1
                if len(examples[a])<20:
                    examples[a].append({'battle_id':d.name,'split':sp,'decision':row['decision_index'],'action':row['action_type'],'actor_uid':row['actor_uid'],'target_uid':row.get('target_uid'),'raw':raw[:1200]})
    payload={'schema_version':1,'corpus_battles':len(battles),'decisions':decisions,'train_fraction':train_fraction,'abilities':{},'examples':examples}
    for a,parts in stats.items():
        payload['abilities'][a]={k:dict(v.most_common()) for k,v in parts.items()}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    return payload

def main():
    ap=argparse.ArgumentParser();ap.add_argument('corpus',type=Path);ap.add_argument('--out',type=Path,default=Path('data/reports/ability-wire-audit.json'));ap.add_argument('--abilities',nargs='*',default=DEFAULT);ap.add_argument('--train-fraction',type=float,default=.8);a=ap.parse_args()
    p=audit(a.corpus,a.out,a.abilities,a.train_fraction)
    print(json.dumps({'battles':p['corpus_battles'],'decisions':p['decisions'],'out':str(a.out)},ensure_ascii=False))
    for code,s in p['abilities'].items():
        print('\n'+code)
        for split in ('train','heldout'):
            d=s[split]; print(split,'n=',d.get('decisions',0),'top=',sorted([(k,v) for k,v in d.items() if k.startswith('S:')],key=lambda x:-x[1])[:8])
if __name__=='__main__':main()
