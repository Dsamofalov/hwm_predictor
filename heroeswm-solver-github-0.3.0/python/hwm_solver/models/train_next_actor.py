from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from hwm_solver.protocol.replay import iter_battle_decisions

FEATURES = [
    "initiative",
    "atb",
    "speed",
    "recency",
    "log_count",
    "is_hero",
    "is_player",
    "same_side_as_current",
    "is_current_actor",
    "current_waited",
    "initiative_diff",
    "atb_diff",
    "control_delay",
]


def _feature(entity: dict, current: dict, next_index: int, last_acted: dict[int, int], current_action: str) -> np.ndarray:
    uid = int(entity["uid"])
    recency = next_index - last_acted[uid] if uid in last_acted else 25
    effects=set(entity.get("effects", []) or [])
    ini=float(entity.get("initiative",0.0))*(0.7 if "proc_cripple" in effects else 1.0)
    speed=float(entity.get("speed",0.0))*(0.5 if "proc_cripple" in effects else 1.0)
    current_effects=set(current.get("effects", []) or [])
    current_ini=float(current.get("initiative",0.0))*(0.7 if "proc_cripple" in current_effects else 1.0)
    return np.asarray(
        [
            ini / 30.0,
            float(entity.get("atb", 0.0)) / 100.0,
            speed / 20.0,
            min(recency, 30) / 30.0,
            math.log1p(max(0, int(entity.get("count", 0)))) / 8.0,
            1.0 if entity.get("is_hero") else 0.0,
            1.0 if int(entity.get("owner", 0)) == 1 else 0.0,
            1.0 if int(entity.get("owner", 0)) == int(current.get("owner", -1)) else 0.0,
            1.0 if uid == int(current["uid"]) else 0.0,
            1.0 if current_action == "WAIT" else 0.0,
            (ini - current_ini) / 30.0,
            (float(entity.get("atb", 0.0)) - float(current.get("atb", 0.0))) / 100.0,
            1.0 if ({"proc_shieldbash","proc_warding"} & effects) else 0.0,
        ],
        dtype=np.float64,
    )


def _battles(corpus: Path) -> list[Path]:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    return sorted((d for d in root.iterdir() if d.is_dir() and d.name.isdigit()), key=lambda d: int(d.name))


def _training_rows(battles: list[Path], negatives: int = 6) -> tuple[np.ndarray, np.ndarray, dict]:
    rng = random.Random(42)
    X: list[np.ndarray] = []
    y: list[int] = []
    transitions = skipped = 0
    for battle in battles:
        rows = list(iter_battle_decisions(battle))
        last_acted: dict[int, int] = {}
        for i, (row, nxt) in enumerate(zip(rows, rows[1:])):
            current = next((e for e in row["state_before"] if int(e["uid"]) == int(row["actor_uid"])), None)
            candidates = [e for e in row["state_after"] if bool(e.get("alive", True))]
            truth = int(nxt["actor_uid"])
            if current is None or not any(int(e["uid"]) == truth for e in candidates):
                skipped += 1
                last_acted[int(row["actor_uid"])] = i
                continue
            positive = next(e for e in candidates if int(e["uid"]) == truth)
            negatives_pool = [e for e in candidates if int(e["uid"]) != truth]
            rng.shuffle(negatives_pool)
            examples = [(positive, 1)] + [(e, 0) for e in negatives_pool[:negatives]]
            for entity, label in examples:
                X.append(_feature(entity, current, i + 1, last_acted, row["action_type"]))
                y.append(label)
            transitions += 1
            last_acted[int(row["actor_uid"])] = i
    return np.stack(X), np.asarray(y, dtype=np.int64), {"transitions": transitions, "skipped_truth_not_alive": skipped}


def _evaluate(battles: list[Path], scaler: StandardScaler, model: LogisticRegression) -> dict:
    n = top1 = top3 = bad = 0
    mrr = 0.0
    rr_top1 = rr_top3 = 0
    for battle in battles:
        rows = list(iter_battle_decisions(battle))
        last_acted: dict[int, int] = {}
        for i, (row, nxt) in enumerate(zip(rows, rows[1:])):
            current = next((e for e in row["state_before"] if int(e["uid"]) == int(row["actor_uid"])), None)
            candidates = [e for e in row["state_after"] if bool(e.get("alive", True))]
            truth = int(nxt["actor_uid"])
            if current is None or not any(int(e["uid"]) == truth for e in candidates):
                bad += 1
                last_acted[int(row["actor_uid"])] = i
                continue
            feats = np.stack([_feature(e, current, i + 1, last_acted, row["action_type"]) for e in candidates])
            probs = model.predict_proba(scaler.transform(feats))[:, 1]
            order = np.argsort(-probs)
            ids = [int(candidates[j]["uid"]) for j in order]
            rank = ids.index(truth) + 1
            n += 1
            top1 += rank == 1
            top3 += rank <= 3
            mrr += 1.0 / rank

            # Baseline used by the old C++ simulator: next alive uid with wrap-around.
            alive_ids = sorted(int(e["uid"]) for e in candidates)
            cur_uid = int(row["actor_uid"])
            if cur_uid in alive_ids:
                j = alive_ids.index(cur_uid)
                rr = alive_ids[j + 1 :] + alive_ids[: j + 1]
            else:
                rr = alive_ids
            rr_rank = rr.index(truth) + 1
            rr_top1 += rr_rank == 1
            rr_top3 += rr_rank <= 3
            last_acted[int(row["actor_uid"])] = i
    return {
        "rows": n,
        "truth_not_in_reconstructed_alive_set": bad,
        "top1": top1 / max(1, n),
        "top3": top3 / max(1, n),
        "mrr": mrr / max(1, n),
        "round_robin_top1": rr_top1 / max(1, n),
        "round_robin_top3": rr_top3 / max(1, n),
    }


def train(corpus: Path, out: Path, train_fraction: float = 0.8) -> dict:
    battles = _battles(corpus)
    cut = int(len(battles) * train_fraction)
    train_battles, test_battles = battles[:cut], battles[cut:]
    X, y, row_report = _training_rows(train_battles)
    scaler = StandardScaler().fit(X)
    model = LogisticRegression(C=0.5, max_iter=500, solver="lbfgs").fit(scaler.transform(X), y)
    metrics = _evaluate(test_battles, scaler, model)

    payload = {
        "schema_version": 1,
        "features": FEATURES,
        "train_battles": len(train_battles),
        "heldout_battles": len(test_battles),
        "training": row_report,
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "coef": model.coef_[0].tolist(),
        "intercept": float(model.intercept_[0]),
        "heldout_metrics": metrics,
        "note": "candidate next-actor linear ranker trained from raw C activation sequences only; old state parser not used; speculative rollout fallback, never authoritative live turn order",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with out.with_suffix(".csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["kind", *FEATURES])
        w.writerow(["mean", *payload["mean"]])
        w.writerow(["scale", *payload["scale"]])
        w.writerow(["coef", *payload["coef"]])
        w.writerow(["intercept", payload["intercept"], *([""] * (len(FEATURES) - 1))])
    return payload


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("corpus", type=Path)
    p.add_argument("--out", type=Path, default=Path("models/next_actor"))
    p.add_argument("--train-fraction", type=float, default=0.8)
    a = p.parse_args()
    print(json.dumps(train(a.corpus, a.out, a.train_fraction), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
