from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

from hwm_solver.models.train_proc_model import _shield_features
from hwm_solver.protocol.replay import (
    _perspective_owner,
    _player_won,
    iter_compact_decisions,
    parse_initial_entities,
    parse_turns,
)


def _collect(dirs: list[Path], ability: str, signal: str, action_types: set[str]):
    x: list[np.ndarray] = []
    y: list[int] = []
    meta: list[tuple[int, str]] = []
    for battle in dirs:
        init = (battle / "init.txt").read_text(errors="replace")
        turns = (battle / "turns0.txt").read_text(errors="replace")
        entities, _ = parse_initial_entities(init)
        owner = _perspective_owner(entities)
        won = _player_won(init, entities, owner)
        for row in iter_compact_decisions(
            battle.name, entities, parse_turns(turns), owner, player_won=won
        ):
            by_uid = {int(e["uid"]): e for e in row["state_before"]}
            actor = by_uid.get(int(row["actor_uid"]))
            target = by_uid.get(int(row["target_uid"])) if row.get("target_uid") is not None else None
            if not actor or not target:
                continue
            if ability not in set(actor.get("abilities") or []):
                continue
            if row["action_type"] not in action_types:
                continue
            x.append(_shield_features(actor, target))
            y.append(int(signal in set(row.get("special_codes") or [])))
            meta.append((int(actor.get("creature_id", 0)), str(row["action_type"])))
    X = np.stack(x) if x else np.zeros((0, 9), dtype=np.float64)
    return X, np.asarray(y, dtype=np.int64), meta


def _rates(meta: list[tuple[int, str]], y: np.ndarray) -> list[dict]:
    buckets: dict[tuple[int, str], list[int]] = defaultdict(lambda: [0, 0])
    for key, hit in zip(meta, y, strict=True):
        buckets[key][0] += 1
        buckets[key][1] += int(hit)
    out = []
    for (creature_id, action_type), (n, hits) in buckets.items():
        out.append({
            "creature_id": creature_id,
            "action_type": action_type,
            "n": n,
            "hits": hits,
            "rate": hits / n if n else 0.0,
        })
    return sorted(out, key=lambda r: (-r["n"], r["creature_id"], r["action_type"]))


def report(
    corpus: Path,
    ability: str,
    signal: str,
    action_types: set[str],
    *,
    split: float = 0.8,
) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    battles = sorted(
        (d for d in root.iterdir() if d.is_dir()),
        key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name),
    )
    cut = int(len(battles) * split)
    Xtr, ytr, mtr = _collect(battles[:cut], ability, signal, action_types)
    Xte, yte, mte = _collect(battles[cut:], ability, signal, action_types)

    payload: dict = {
        "ability": ability,
        "signal": signal,
        "action_types": sorted(action_types),
        "split": split,
        "train_n": int(len(ytr)),
        "train_hits": int(ytr.sum()) if len(ytr) else 0,
        "train_rate": float(ytr.mean()) if len(ytr) else 0.0,
        "heldout_n": int(len(yte)),
        "heldout_hits": int(yte.sum()) if len(yte) else 0,
        "heldout_rate": float(yte.mean()) if len(yte) else 0.0,
        "train_buckets": _rates(mtr, ytr),
        "heldout_buckets": _rates(mte, yte),
        "model": {"eligible": False},
    }
    if len(ytr) < 50 or len(yte) < 30 or len(np.unique(ytr)) != 2 or len(np.unique(yte)) != 2:
        payload["model"]["reason"] = "insufficient_binary_temporal_sample"
        return payload

    scaler = StandardScaler().fit(Xtr)
    model = LogisticRegression(C=0.5, max_iter=2000, solver="lbfgs").fit(
        scaler.transform(Xtr), ytr
    )
    prob = model.predict_proba(scaler.transform(Xte))[:, 1]
    baseline = np.full(len(yte), float(ytr.mean()))
    brier = float(brier_score_loss(yte, prob))
    base_brier = float(brier_score_loss(yte, baseline))
    auc = float(roc_auc_score(yte, prob))
    ll = float(log_loss(yte, prob))
    base_ll = float(log_loss(yte, baseline))
    payload["model"] = {
        "eligible": True,
        "heldout_brier": brier,
        "baseline_brier": base_brier,
        "brier_improvement": base_brier - brier,
        "heldout_auc": auc,
        "heldout_logloss": ll,
        "baseline_logloss": base_ll,
        "passes_gate": bool(brier + 0.005 < base_brier and auc >= 0.60),
        "intercept": float(model.intercept_[0]),
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "coef": model.coef_[0].tolist(),
    }
    return payload


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("corpus", type=Path)
    p.add_argument("ability")
    p.add_argument("signal")
    p.add_argument("--types", default="MELEE_ATTACK,RANGED_ATTACK")
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    payload = report(
        args.corpus,
        args.ability,
        args.signal,
        {x.strip() for x in args.types.split(",") if x.strip()},
    )
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
