import argparse,json,statistics
from pathlib import Path
from hwm_solver.protocol.decoder import decode
def main():
 p=argparse.ArgumentParser();p.add_argument("raw",type=Path);a=p.parse_args();rows=[]
 for f in sorted(a.raw.glob("*.txt")):
  d=decode(f.read_text(encoding="utf-8",errors="replace"),f.stem);rows.append(d)
 cov=[x.coverage for x in rows];print(json.dumps({"files":len(rows),"training_safe":sum(x.training_safe for x in rows),"coverage_mean":statistics.fmean(cov) if cov else 0,"coverage_min":min(cov) if cov else 0,"coverage_max":max(cov) if cov else 0,"unknown_records":sum(len(x.unknown) for x in rows)},indent=2))
if __name__=="__main__":main()
