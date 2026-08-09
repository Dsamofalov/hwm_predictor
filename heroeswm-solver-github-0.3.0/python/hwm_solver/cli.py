import argparse,json
from pathlib import Path
from hwm_solver.corpus.urls import load_urls,write_manifest
from hwm_solver.corpus.collector import collect
from hwm_solver.corpus.har import import_har
from hwm_solver.dataset.build import build
from hwm_solver.dataset.real import build_real_dataset
from hwm_solver.protocol.decoder import decode
from hwm_solver.protocol.analyze import write_analysis
from hwm_solver.knowledge.build_catalog import build_catalog
from hwm_solver.knowledge.external_catalog import build_reference_catalog, write_reference_catalog
def main():
 p=argparse.ArgumentParser(prog='hwm');sp=p.add_subparsers(dest='cmd',required=True);q=sp.add_parser('manifest');q.add_argument('urls',type=Path);q.add_argument('out',type=Path);q=sp.add_parser('collect');q.add_argument('urls',type=Path);q.add_argument('out',type=Path);q.add_argument('--delay',type=float,default=2);q.add_argument('--limit',type=int);q.add_argument('--enable',action='store_true');q=sp.add_parser('inspect');q.add_argument('payload',type=Path);q.add_argument('--battle-id',default='');q=sp.add_parser('dataset');q.add_argument('raw',type=Path);q.add_argument('out',type=Path);q=sp.add_parser('build-real-dataset');q.add_argument('corpus',type=Path);q.add_argument('out',type=Path);q.add_argument('--include-unknown-commands',action='store_true');q=sp.add_parser('analyze');q.add_argument('raw',type=Path);q.add_argument('--out',type=Path,default=Path('data/reports/protocol-analysis.json'));q.add_argument('--top',type=int,default=50);q=sp.add_parser('import-har');q.add_argument('har',type=Path);q.add_argument('out',type=Path);q=sp.add_parser('build-catalog');q.add_argument('corpus',type=Path);q.add_argument('--out',type=Path,default=Path('data/catalog/generated.json'));q.add_argument('--reference-creatures-html',type=Path);q.add_argument('--hwm-daily-html',type=Path);q=sp.add_parser('build-reference-catalog');q.add_argument('creatures_html',type=Path);q.add_argument('--hwm-daily-html',type=Path);q.add_argument('--out',type=Path,default=Path('data/reference/external_catalog.json'));a=p.parse_args()
 if a.cmd=='manifest':print(json.dumps(write_manifest(load_urls(a.urls),a.out),indent=2))
 elif a.cmd=='collect':print(json.dumps(collect(a.urls,a.out,a.delay,a.limit,a.enable),indent=2))
 elif a.cmd=='inspect':
  d=decode(a.payload.read_text(encoding='utf-8',errors='replace'),a.battle_id);print(json.dumps({'battle_id':d.battle_id,'halfturn':d.halfturn,'entity_hints':d.entity_hints,'coverage':d.coverage,'training_safe':d.training_safe,'events':[vars(x) for x in d.events[:50]],'unknown_count':len(d.unknown)},indent=2))
 elif a.cmd=='dataset':print(json.dumps(build(a.raw,a.out),indent=2))
 elif a.cmd=='build-real-dataset':print(json.dumps(build_real_dataset(a.corpus,a.out,include_unknown_commands=a.include_unknown_commands),ensure_ascii=False,indent=2))
 elif a.cmd=='analyze':print(json.dumps(write_analysis(a.raw,a.out,a.top),ensure_ascii=False,indent=2))
 elif a.cmd=='import-har':print(json.dumps(import_har(a.har,a.out),ensure_ascii=False,indent=2))
 elif a.cmd=='build-catalog':print(json.dumps(build_catalog(a.corpus,a.out,a.reference_creatures_html,a.hwm_daily_html),ensure_ascii=False,indent=2))
 elif a.cmd=='build-reference-catalog':
  payload=build_reference_catalog(a.creatures_html,a.hwm_daily_html);write_reference_catalog(payload,a.out);print(json.dumps(payload['coverage'],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
