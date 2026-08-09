from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path
from statistics import mean, median

import numpy as np

from hwm_solver.protocol.replay import iter_battle_decisions, parse_initial_entities

RSD_RE = re.compile(r"Srsd(\d{3})(\d{3})-1(\d)(\d{6})")
FEATURE_NAMES = [
    "intercept", "log_count", "log_max_count", "attack_100", "defense_100",
    "log_mana", "log_spell_effect", "log_spell_secondary", "multi_unit",
]


def _spell_params(entity):
    tok = entity.magic_blob.split("^", 1)[0].split("-")
    found = set()
    for i in range(0, len(tok) - 6, 7):
        if tok[i] != "raisedead":
            continue
        try:
            found.add((int(float(tok[i + 1])), float(tok[i + 3]), float(tok[i + 4])))
        except ValueError:
            continue
    if len(found) != 1:
        return None
    return next(iter(found))


def collect(corpus: Path):
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    battles = sorted((d for d in root.iterdir() if d.is_dir()), key=lambda p: int(p.name))
    rows = []
    for d in battles:
        initial, _ = parse_initial_entities((d / "init.txt").read_text(encoding="utf-8", errors="replace"))
        params = {uid: _spell_params(e) for uid, e in initial.items()}
        for row in iter_battle_decisions(d):
            m = RSD_RE.search(row["raw"])
            if not m:
                continue
            actor_uid, target_uid = int(m.group(1)), int(m.group(2))
            actor = next((e for e in row["state_before"] if int(e["uid"]) == actor_uid), None)
            target = next((e for e in row["state_before"] if int(e["uid"]) == target_uid), None)
            sp = params.get(actor_uid)
            if actor is None or target is None or sp is None:
                continue
            base_cost, effect, secondary = sp
            rows.append({
                "battle_id": int(d.name), "actor_creature_id": int(actor["creature_id"]),
                "actor_count": int(actor["count"]), "actor_max_count": int(actor["max_count"]),
                "actor_attack": float(actor["attack"]), "actor_defense": float(actor["defense"]),
                "actor_mana": int(actor["mana"]), "spell_base_cost": base_cost,
                "spell_effect": effect, "spell_secondary": secondary,
                "effective_cost": int(m.group(3)), "target_creature_id": int(target["creature_id"]),
                "observed_heal": int(m.group(4)),
            })
    return battles, rows


def _base_features(r: dict) -> np.ndarray:
    return np.asarray([
        1.0,
        math.log1p(max(0, r["actor_count"])),
        math.log1p(max(0, r["actor_max_count"])),
        r["actor_attack"] / 100.0,
        r["actor_defense"] / 100.0,
        math.log1p(max(0, r["actor_mana"])),
        math.log1p(max(0.0, r["spell_effect"])),
        math.log1p(max(0.0, r["spell_secondary"])),
        1.0 if r["actor_count"] > 1 else 0.0,
    ], dtype=np.float64)


def train(corpus: Path, out: Path, train_fraction: float = 0.8, ridge: float = 0.01, conservative_factor: float = 0.95):
    battles, rows = collect(corpus)
    cut = int(len(battles) * train_fraction)
    train_ids = {int(d.name) for d in battles[:cut]}
    train_rows = [r for r in rows if r["battle_id"] in train_ids]
    held_rows = [r for r in rows if r["battle_id"] not in train_ids]
    cids = sorted({r["actor_creature_id"] for r in train_rows})
    cid_index = {cid: i for i, cid in enumerate(cids)}

    def features(r):
        x = np.zeros((len(FEATURE_NAMES) + len(cids),), dtype=np.float64)
        x[:len(FEATURE_NAMES)] = _base_features(r)
        idx = cid_index.get(r["actor_creature_id"])
        if idx is not None:
            x[len(FEATURE_NAMES) + idx] = 1.0
        return x

    X = np.stack([features(r) for r in train_rows])
    y = np.log(np.asarray([max(1, r["observed_heal"]) for r in train_rows], dtype=np.float64))
    A = X.T @ X + ridge * np.eye(X.shape[1], dtype=np.float64)
    A[0, 0] -= ridge
    weights = np.linalg.solve(A, X.T @ y)

    def eval_rows(xs, factor):
        rel = []
        ratios = []
        for r in xs:
            pred = max(1.0, math.exp(float(features(r) @ weights)) * factor)
            actual = max(1.0, float(r["observed_heal"]))
            rel.append(abs(pred - actual) / actual)
            ratios.append(pred / actual)
        if not rel:
            return {}
        a = np.asarray(rel, dtype=np.float64)
        q = np.asarray(ratios, dtype=np.float64)
        return {
            "rows": len(xs), "median_relative_error": float(np.median(a)),
            "mean_relative_error": float(np.mean(a)), "p90_relative_error": float(np.quantile(a, 0.90)),
            "overestimate_rate": float(np.mean(q > 1.0)), "median_prediction_ratio": float(np.median(q)),
        }

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["kind", "key", "value"])
        for name, value in zip(FEATURE_NAMES, weights[:len(FEATURE_NAMES)]):
            w.writerow(["coef", name, f"{float(value):.12g}"])
        for cid, value in zip(cids, weights[len(FEATURE_NAMES):]):
            w.writerow(["cid", cid, f"{float(value):.12g}"])
        w.writerow(["meta", "conservative_factor", f"{conservative_factor:.12g}"])

    report = {
        "source": "new raw init.txt + turns0.txt only; historical parser/state dumps not used",
        "mechanic": "Raise Dead / Srsd",
        "observations": len(rows), "train_battles": cut, "heldout_battles": len(battles) - cut,
        "train_rows": len(train_rows), "heldout_rows": len(held_rows), "actor_creature_ids_train": len(cids),
        "model": "ridge log-linear + actor creature-id bias", "ridge": ridge,
        "raw_prediction_heldout": eval_rows(held_rows, 1.0),
        "conservative_factor": conservative_factor,
        "conservative_heldout": eval_rows(held_rows, conservative_factor),
        "note": "Speculative rollout model only. Observed Srsd uses authoritative heal6 from the wire payload exactly.",
        "out": str(out),
    }
    out.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("corpus", type=Path)
    p.add_argument("--out", type=Path, default=Path("models/raise_dead_model.csv"))
    p.add_argument("--train-fraction", type=float, default=0.8)
    p.add_argument("--ridge", type=float, default=0.01)
    p.add_argument("--conservative-factor", type=float, default=0.95)
    a = p.parse_args()
    print(json.dumps(train(a.corpus, a.out, a.train_fraction, a.ridge, a.conservative_factor), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
