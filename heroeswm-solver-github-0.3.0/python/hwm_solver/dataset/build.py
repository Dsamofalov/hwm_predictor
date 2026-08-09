from pathlib import Path
import json,random
from hwm_solver.protocol.decoder import decode
def build(raw_dir:Path,out_dir:Path,seed:int=1337):
    out_dir.mkdir(parents=True,exist_ok=True);ok=[];bad=[]
    for p in sorted(raw_dir.glob("*.txt")):
        d=decode(p.read_text(encoding="utf-8",errors="replace"),p.stem);r={"battle_id":p.stem,"halfturn":d.halfturn,"entity_hints":d.entity_hints,"coverage":d.coverage,"training_safe":d.training_safe,"raw_sha256":d.raw_sha256};(ok if d.training_safe else bad).append(r)
    random.Random(seed).shuffle(ok);n=len(ok);a=int(n*.8);b=int(n*.9);splits={"train":ok[:a],"val":ok[a:b],"test":ok[b:]}
    for name,rows in splits.items():(out_dir/f"{name}.jsonl").write_text(''.join(json.dumps(x)+"\n" for x in rows),encoding="utf-8")
    (out_dir/'rejected.jsonl').write_text(''.join(json.dumps(x)+"\n" for x in bad),encoding='utf-8');report={"raw_files":n+len(bad),"accepted":n,"rejected":len(bad),"splits":{k:len(v) for k,v in splits.items()},"note":"No real targets emitted until decoder coverage >= 90%."};(out_dir/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');return report
