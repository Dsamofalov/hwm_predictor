from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import lsqr

from hwm_solver.models.train_damage_model import _collect


def _creature_residual_profiles(rows: list[dict], shrinkage: float = 20.0):
    by_type: dict[str, list[float]] = defaultdict(list)
    by_creature: dict[tuple[str, int], list[float]] = defaultdict(list)
    for r in rows:
        by_type[r["action_type"]].append(float(r["log_ratio"]))
        by_creature[(r["action_type"], int(r["creature_id"]))].append(float(r["log_ratio"]))
    global_log = {k: float(np.median(v)) for k, v in by_type.items()}
    out: dict[tuple[str, int], tuple[float, int]] = {}
    for (typ, cid), vals in by_creature.items():
        prior = global_log.get(typ, 0.0)
        n = len(vals)
        w = n / (n + shrinkage)
        out[(typ, cid)] = (w * float(np.median(vals)) + (1.0 - w) * prior, n)
    return global_log, out


def _ability_features(row: dict) -> list[tuple[str, str]]:
    # Role prefix is important: an offensive ability on the attacker is not the
    # same causal feature as the same tag on the target.
    return [("actor", str(x)) for x in row.get("actor_abilities", [])] + [
        ("target", str(x)) for x in row.get("target_abilities", [])
    ]


def _metrics(rows: list[dict], predict) -> dict:
    if not rows:
        return {}
    abs_log, ape = [], []
    for r in rows:
        p = max(1e-6, float(predict(r)))
        y = max(1e-6, float(r["observed"]))
        abs_log.append(abs(math.log(p) - math.log(y)))
        ape.append(abs(p-y)/y)
    return {
        "rows": len(rows),
        "median_abs_log_error": float(np.median(abs_log)),
        "mean_abs_log_error": float(np.mean(abs_log)),
        "median_absolute_percentage_error": float(np.median(ape)),
    }


def train(corpus: Path, out: Path, train_fraction: float = 0.8, min_support: int = 20, alpha: float = 80.0) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    battles = sorted((d for d in root.iterdir() if d.is_dir()), key=lambda p: int(p.name))
    cut = int(len(battles) * train_fraction)
    train_rows = _collect(battles[:cut])
    test_rows = _collect(battles[cut:])

    global_log, creature = _creature_residual_profiles(train_rows)

    def creature_log(r: dict) -> float:
        typ = r["action_type"]
        cid = int(r["creature_id"])
        return creature.get((typ, cid), (0.0, 0))[0]

    # Separate fits per action type keep ranged and melee semantics independent.
    models: dict[str, dict[tuple[str,str], float]] = {}
    supports: dict[str, Counter] = {}
    for typ in sorted({r["action_type"] for r in train_rows}):
        rows = [r for r in train_rows if r["action_type"] == typ]
        support = Counter(f for r in rows for f in set(_ability_features(r)))
        feats = sorted(f for f, n in support.items() if n >= min_support)
        supports[typ] = support
        index = {f:i for i,f in enumerate(feats)}
        rr, cc, vv, y = [], [], [], []
        for i, r in enumerate(rows):
            for f in set(_ability_features(r)):
                j=index.get(f)
                if j is not None:
                    rr.append(i); cc.append(j); vv.append(1.0)
            # Model only what remains after the exact baseline and creature-level profile.
            y.append(float(r["log_ratio"]) - creature_log(r))
        if not feats:
            models[typ] = {}
            continue
        X = sparse.csr_matrix((vv,(rr,cc)), shape=(len(rows),len(feats)), dtype=np.float64)
        coef = lsqr(X, np.asarray(y,dtype=np.float64), damp=math.sqrt(alpha), atol=1e-8, btol=1e-8, iter_lim=500)[0]
        # Cap individual residuals: this layer is deliberately a modest transfer
        # correction, never a license for MCTS to exploit a sparse-data perk.
        models[typ] = {f: float(np.clip(coef[j], -0.50, 0.50)) for f,j in index.items()}

    def ability_log(r: dict) -> float:
        m=models.get(r["action_type"],{})
        return float(sum(m.get(f,0.0) for f in set(_ability_features(r))))

    def p_generic(r): return r["expected"]
    def p_creature(r): return r["expected"] * math.exp(creature_log(r))
    def p_ability(r): return r["expected"] * math.exp(creature_log(r) + ability_log(r))

    # Rare/unseen creature slices are where ability transfer matters most.
    def train_count(r): return creature.get((r["action_type"], int(r["creature_id"])), (0.0,0))[1]
    slices = {
        "all": test_rows,
        "rare_creature_le_20": [r for r in test_rows if train_count(r) <= 20],
        "unseen_creature": [r for r in test_rows if train_count(r) == 0],
    }
    evaluation={}
    for name, rows in slices.items():
        evaluation[name]={
            "generic": _metrics(rows,p_generic),
            "creature": _metrics(rows,p_creature),
            "creature_plus_ability": _metrics(rows,p_ability),
        }

    out.parent.mkdir(parents=True, exist_ok=True)
    records=[]
    for typ, m in models.items():
        for (role, code), logcoef in sorted(m.items()):
            records.append({
                "action_type": typ,
                "role": role,
                "ability_code": code,
                "samples": supports[typ][(role,code)],
                "log_coefficient": logcoef,
                "multiplier": math.exp(logcoef),
            })
    with out.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["action_type","role","ability_code","samples","log_coefficient","multiplier"])
        w.writeheader()
        for r in records:
            w.writerow({k:(f"{v:.9f}" if isinstance(v,float) else v) for k,v in r.items()})

    report={
        "source":"independently decoded 866-battle raw corpus + exact physical baseline; old historical parser not used",
        "train_battles":cut,"heldout_battles":len(battles)-cut,
        "train_rows":len(train_rows),"heldout_rows":len(test_rows),
        "min_support":min_support,"ridge_alpha":alpha,"ability_coefficients":len(records),
        "evaluation":evaluation,"out":str(out),
        "note":"Ability coefficients are a regularized residual after exact mechanics + creature profile. Runtime should multiply them only once and keep unsupported perks in uncertainty accounting."
    }
    out.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('corpus',type=Path);p.add_argument('--out',type=Path,default=Path('models/ability_damage_model.csv'));p.add_argument('--train-fraction',type=float,default=.8);p.add_argument('--min-support',type=int,default=20);p.add_argument('--alpha',type=float,default=80.0);a=p.parse_args()
    print(json.dumps(train(a.corpus,a.out,a.train_fraction,a.min_support,a.alpha),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
