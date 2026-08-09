from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import median

import numpy as np

from hwm_solver.protocol.replay import (
    _perspective_owner,
    _player_won,
    iter_compact_decisions,
    parse_commands,
    parse_initial_entities,
    parse_turns,
)

ATTACK_TYPES = {"MELEE_ATTACK", "RANGED_ATTACK"}


def _rows(battle_dir: Path):
    init = (battle_dir / "init.txt").read_text(encoding="utf-8", errors="replace")
    turns_text = (battle_dir / "turns0.txt").read_text(encoding="utf-8", errors="replace")
    entities, _ = parse_initial_entities(init)
    turns = parse_turns(turns_text)
    owner = _perspective_owner(entities)
    won = _player_won(init, entities, owner)
    yield from iter_compact_decisions(battle_dir.name, entities, turns, owner, player_won=won)


def _percent_tag(abilities: set[str], prefix: str) -> float:
    # Exact numeric variants observed in the raw/reference catalogs.  The bare
    # `ignoredefence`/`ignoreattack` tags are intentionally not guessed.
    for pct in (95, 90, 80, 75, 60, 50, 40, 30, 25, 20, 15, 10):
        if f"{prefix}{pct}" in abilities:
            return pct / 100.0
    return 0.0


def _fire_multiplier(entity: dict) -> float:
    abilities=set(entity.get("abilities", []) or [])
    if "ifire" in abilities:
        return 0.0
    m=1.0-_percent_tag(abilities,"fireproof")
    if "demoniclineage" in abilities:
        m*=0.75
    if "fireprskin" in abilities:
        m*=0.80
    return max(0.0,m)


def _effect_magnitude(entity: dict, wire: str) -> float:
    best = 0.0
    for fx in entity.get("effects", []) or []:
        # The compact dataset stores many legacy effect markers as bare wire
        # strings without magnitudes.  Do not invent a numeric strength for
        # those; the residual model is allowed to absorb the remaining effect.
        if not isinstance(fx, dict):
            continue
        if str(fx.get("code", fx.get("wire", ""))) == wire and int(fx.get("duration", 1) or 0) > 0:
            try:
                best = max(best, float(fx.get("magnitude", 0) or 0))
            except (TypeError, ValueError):
                pass
    return best


def _footprint_cells(entity: dict) -> set[tuple[int,int]]:
    abilities=set(entity.get("abilities", []) or [])
    w=h=2 if "big" in abilities else 1
    x,y=int(entity.get("x",0)),int(entity.get("y",0))
    return {(x+dx,y+dy) for dx in range(w) for dy in range(h)}

def _adjacent(a: dict,b: dict) -> bool:
    ac=_footprint_cells(a); bc=_footprint_cells(b)
    return any(max(abs(ax-bx),abs(ay-by))==1 for ax,ay in ac for bx,by in bc)

def _shieldother_ranged_multiplier(state: list[dict], target: dict, ranged: bool) -> float:
    if not ranged or "lshield" in set(target.get("abilities", []) or []):
        return 1.0
    owner = int(target.get("owner", 0) or 0)
    uid = int(target.get("uid", -1))
    for src in state:
        if int(src.get("uid", -2)) == uid or not src.get("alive", True):
            continue
        if int(src.get("owner", 0) or 0) != owner:
            continue
        if "shieldother" in set(src.get("abilities", []) or []) and _adjacent(src, target):
            return 0.75
    return 1.0

def _festering_sources(state: list[dict], entity: dict) -> int:
    if "undead" in set(entity.get("abilities", []) or []):
        return 0
    uid=int(entity.get("uid",-1)); n=0
    for src in state:
        if int(src.get("uid",-2))==uid or not src.get("alive",True):
            continue
        if "festeringaura" in set(src.get("abilities", []) or []) and _adjacent(src,entity):
            n+=1
    return n

def _expected_damage(row: dict, actor: dict, target: dict) -> float:
    count = max(0.0, float(actor.get("count", 0)))
    mn = float(actor.get("min_damage", 0)) + float((actor.get("effect_values", {}) or {}).get("tob",0) or 0)
    mx = max(mn, float(actor.get("max_damage", 0)))

    # Match the C++ exact-core status algebra where those effects have already
    # been independently decoded.  Most raw rows have no active status effect,
    # but keeping this here prevents the residual from relearning exact magic.
    bless_curse = (_effect_magnitude(actor, "bls") - _effect_magnitude(actor, "crs")) / 100.0
    if bless_curse > 0:
        mn = min(mx, mn + (mx - mn) * bless_curse)
    elif bless_curse < 0:
        mx = max(mn, mx - (mx - mn) * (-bless_curse))

    base = count * (mx if "accuracy" in set(actor.get("abilities", [])) else (mn + mx) * 0.5)
    actor_abilities = set(actor.get("abilities", []))
    target_abilities = set(target.get("abilities", []))

    state = row.get("state_before", []) or []
    vals=actor.get("effect_values", {}) or {}
    attack = float(actor.get("attack", 0)) + _effect_magnitude(actor, "rgm") + float(vals.get("enr",0) or 0) + float(vals.get("blt",0) or 0) + float(vals.get("btt",0) or 0) - 4.0*_festering_sources(state,actor)
    defense = float(target.get("defense", 0)) + _effect_magnitude(target, "stn") - 4.0*_festering_sources(state,target)
    attack=max(0.0,attack); defense=max(0.0,defense)
    if target.get("defending"):
        defense *= 1.50 if "takeroots" in target_abilities else 1.30
    ignore_def = _percent_tag(actor_abilities, "ignoredefence")
    ranged = row["action_type"] == "RANGED_ATTACK"
    if ranged and "armorpiercing" in actor_abilities:
        ignore_def = max(ignore_def, 0.50)
    if ranged and "forcearrow" in actor_abilities:
        ignore_def = max(ignore_def, 0.20)
    defense *= 1.0 - ignore_def
    attack *= 1.0 - _percent_tag(target_abilities, "ignoreattack")
    mult = 1.0 + 0.05 * (attack - defense) if attack >= defense else 1.0 / (1.0 + 0.05 * (defense - attack))

    origin_x, origin_y = int(actor.get("x", 0)), int(actor.get("y", 0))
    ax = int(row.get("destination_x") if row.get("destination_x") is not None else origin_x)
    ay = int(row.get("destination_y") if row.get("destination_y") is not None else origin_y)
    tx, ty = int(target.get("x", 0)), int(target.get("y", 0))
    distance = max(abs(ax - tx), abs(ay - ty))
    moved = max(abs(ax - origin_x), abs(ay - origin_y))

    if not ranged and moved > 0 and "ridercharge" in actor_abilities:
        # This applies to target Defence, not final damage; reconstruct the
        # multiplier with the additionally reduced defence.
        rider_ignore = min(1.0, 0.20 * moved)
        base_def = max(0.0, float(target.get("defense", 0)) + _effect_magnitude(target, "stn") - 4.0*_festering_sources(state,target)) * (1.30 if target.get("defending") else 1.0)
        rider_def = base_def * (1.0 - max(ignore_def, rider_ignore))
        rider_atk = attack
        rider_mult = 1.0 + 0.05*(rider_atk-rider_def) if rider_atk>=rider_def else 1.0/(1.0+0.05*(rider_def-rider_atk))
        mult = rider_mult
    if ranged and "norangepenalty" not in actor_abilities and distance > 6:
        mult *= 0.5
    if ranged:
        confusion = min(1.0, max(0.0, _effect_magnitude(actor, "cnf") / 100.0))
        deflect = min(1.0, max(0.0, _effect_magnitude(target, "dfm") / 100.0))
        mult *= (1.0 - confusion) * (1.0 - deflect)
        if "rangepenalty" in actor_abilities:
            mult *= 0.5
        if "diamondarmor" in target_abilities:
            mult *= 0.10
        if "shielded" in target_abilities:
            mult *= 0.75
        if "lshield" in target_abilities or "hollowbones" in target_abilities:
            mult *= 0.50
    elif "shooter" in actor_abilities and not ({"nopenalty", "nomeleepenalty"} & actor_abilities):
        mult *= 0.5

    if "immaterial" in target_abilities:
        mult *= 0.65
    if "giantkiller" in actor_abilities and "big" in target_abilities:
        mult *= 2.0
    if not ranged and moved == 0 and "safeposition" in actor_abilities:
        mult *= 1.50
    if not ranged and moved > 0 and "shieldwall" in target_abilities:
        mult *= max(0.10, 1.0 - 0.10 * min(9, moved))
    if not ranged and moved > 0 and "charge" in actor_abilities:
        mult *= 1.0 + 0.10 * moved
    if not ranged and moved > 0 and "jousting" in actor_abilities:
        mult *= 1.0 + 0.05 * moved
    if not ranged and moved > 0 and "agilesteed" in actor_abilities:
        mult *= max(0.0, 1.0 - 0.05 * moved)
    if not ranged and moved > 0 and "blindingcharge" in actor_abilities:
        mult *= 1.0 + 0.10 * moved
    if not ranged and "brittle" in target_abilities:
        mult *= 1.25
    if "deadflesh" in target_abilities:
        mult *= 0.80
    if "lifeguardmembrane" in target_abilities:
        mult *= 0.85
    if not ranged and "pleasureinpain" in target_abilities:
        mult *= 0.90
    if not ranged and "raptureinagony" in target_abilities:
        mult *= 0.80
    if "bloodfrenzy" in actor_abilities and (
        _effect_magnitude(target, "proc_ferocious_speed") > 0.0
        or _effect_magnitude(target, "proc_ferocious_dot") > 0.0
    ):
        mult *= 1.30
    mult *= _shieldother_ranged_multiplier(state, target, ranged)

    # Exact observed/control-state damage modifiers.  Keep the training
    # baseline aligned with the C++ simulator so the residual cannot relearn
    # mechanics that runtime already applies deterministically.
    if _effect_magnitude(target, "proc_stone") > 0.0:
        mult *= 0.50
    if _effect_magnitude(target, "proc_entrenchment") > 0.0:
        mult *= 0.50

    hits = 1
    if ranged and "doubleshoot" in actor_abilities:
        hits = min(2, max(0, int(actor.get("shots", 0))))
    elif not ranged and "triplestrike" in actor_abilities:
        hits = 3
    elif not ranged and "doublestrike" in actor_abilities:
        hits = 2

    # Match the simulator for Death Strike and Weakening Strike rather than
    # asking the residual model to relearn exact mechanics.  For multi-hit
    # weakening attacks, later hits see the -4 Defence applied after hit #1.
    per_hit = base * mult
    top_hp = max(1.0, float(target.get("top_hp", target.get("hp", target.get("max_hp", 1))) or 1))
    max_hp_unit = max(1.0, float(target.get("max_hp", target.get("max_hp_per_unit", 1)) or 1))
    total = 0.0
    for hit in range(max(1, hits)):
        hit_damage = per_hit
        if "deathstrike" in actor_abilities and max_hp_unit < 400:
            hit_damage = max(hit_damage, top_hp if hit == 0 else max_hp_unit)
        total += hit_damage
        if hit == 0 and hits > 1 and "weakeningstrike" in actor_abilities and "armoured" not in target_abilities and "organicarmor" not in target_abilities:
            lowered_def = max(0.0, defense - 4.0)
            lowered_mult = 1.0 + 0.05 * (attack - lowered_def) if attack >= lowered_def else 1.0 / (1.0 + 0.05 * (lowered_def - attack))
            # Preserve passive multipliers by replacing only the attack/defence component.
            if mult > 0:
                base_ad = 1.0 + 0.05 * (attack - defense) if attack >= defense else 1.0 / (1.0 + 0.05 * (defense - attack))
                per_hit = per_hit * lowered_mult / max(1e-9, base_ad)
    if "fireattack" in actor_abilities:
        total += 5.0 * count * _fire_multiplier(target)
    return max(1e-6, total)


def _observed_damage(row: dict) -> int:
    a = int(row["actor_uid"])
    t = int(row["target_uid"])
    return sum(
        int(c.amount or 0)
        for c in parse_commands(row["raw"])
        if c.opcode == "DAMAGE" and c.actor_uid == a and c.target_uid == t and int(c.amount or 0) > 0
    )


def _collect(battles: list[Path]):
    samples: list[dict] = []
    for d in battles:
        for row in _rows(d):
            if row["action_type"] not in ATTACK_TYPES or row.get("target_uid") is None:
                continue
            actor = next((e for e in row["state_before"] if int(e["uid"]) == int(row["actor_uid"])), None)
            target = next((e for e in row["state_before"] if int(e["uid"]) == int(row["target_uid"])), None)
            if not actor or not target or not actor.get("alive", True) or not target.get("alive", True):
                continue
            expected = _expected_damage(row, actor, target)
            observed = _observed_damage(row)
            if observed <= 0 or expected <= 0:
                continue
            ratio = float(np.clip(observed / expected, 0.05, 20.0))
            samples.append({
                "battle_id": int(d.name),
                "creature_id": int(actor.get("creature_id", 0)),
                "action_type": row["action_type"],
                "expected": expected,
                "observed": observed,
                "ratio": ratio,
                "log_ratio": math.log(ratio),
                "actor_abilities": sorted(set(actor.get("abilities", []))),
                "target_abilities": sorted(set(target.get("abilities", []))),
                "semantic_unresolved_before": int(row.get("semantic_unresolved_records_before", 0)),
            })
    return samples


def train(corpus: Path, out: Path, train_fraction: float = 0.8, shrinkage: float = 20.0) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    battles = sorted((d for d in root.iterdir() if d.is_dir()), key=lambda p: int(p.name))
    cut = int(len(battles) * train_fraction)
    train_b, held_b = battles[:cut], battles[cut:]
    train_rows = _collect(train_b)
    held_rows = _collect(held_b)

    global_logs: dict[str, list[float]] = defaultdict(list)
    creature_logs: dict[tuple[str, int], list[float]] = defaultdict(list)
    for r in train_rows:
        global_logs[r["action_type"]].append(r["log_ratio"])
        creature_logs[(r["action_type"], r["creature_id"])].append(r["log_ratio"])

    global_median = {k: float(median(v)) for k, v in global_logs.items() if v}
    rows_out: list[dict] = []
    for (typ, cid), vals in sorted(creature_logs.items()):
        n = len(vals)
        local = float(median(vals))
        prior = global_median.get(typ, 0.0)
        weight = n / (n + shrinkage)
        shrunk = weight * local + (1.0 - weight) * prior
        arr = np.asarray(vals, dtype=np.float64)
        rows_out.append({
            "action_type": typ,
            "creature_id": cid,
            "samples": n,
            "multiplier": math.exp(shrunk),
            "q10": math.exp(float(np.quantile(arr, 0.10))),
            "q50": math.exp(float(np.quantile(arr, 0.50))),
            "q90": math.exp(float(np.quantile(arr, 0.90))),
        })
    for typ, vals in sorted(global_logs.items()):
        arr = np.asarray(vals, dtype=np.float64)
        rows_out.append({
            "action_type": typ,
            "creature_id": 0,
            "samples": len(vals),
            "multiplier": math.exp(global_median[typ]),
            "q10": math.exp(float(np.quantile(arr, 0.10))),
            "q50": math.exp(float(np.quantile(arr, 0.50))),
            "q90": math.exp(float(np.quantile(arr, 0.90))),
        })

    lookup = {(r["action_type"], r["creature_id"]): r["multiplier"] for r in rows_out}
    def pred(row: dict, learned: bool):
        if not learned:
            return row["expected"]
        m = lookup.get((row["action_type"], row["creature_id"]), lookup.get((row["action_type"], 0), 1.0))
        return row["expected"] * m

    def metrics(rows: list[dict]):
        if not rows:
            return {}
        outm = {}
        for learned in (False, True):
            abs_log = []
            ape = []
            for r in rows:
                p = max(1e-6, pred(r, learned))
                y = max(1e-6, float(r["observed"]))
                abs_log.append(abs(math.log(p) - math.log(y)))
                ape.append(abs(p-y)/y)
            outm["learned" if learned else "generic"] = {
                "median_abs_log_error": float(np.median(abs_log)),
                "mean_abs_log_error": float(np.mean(abs_log)),
                "median_absolute_percentage_error": float(np.median(ape)),
            }
        return outm

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["action_type", "creature_id", "samples", "multiplier", "q10", "q50", "q90"])
        w.writeheader()
        for r in rows_out:
            w.writerow({k: (f"{v:.9f}" if isinstance(v, float) else v) for k, v in r.items()})

    report = {
        "source": "independently decoded raw init.txt + turns0.txt; old historical parser not used",
        "train_battles": len(train_b),
        "heldout_battles": len(held_b),
        "train_attack_rows": len(train_rows),
        "heldout_attack_rows": len(held_rows),
        "profiles": len(rows_out),
        "global_multiplier": {k: math.exp(v) for k, v in global_median.items()},
        "heldout_metrics": metrics(held_rows),
        "out": str(out),
        "note": "Robust multiplicative residual on top of generic damage formula; intended for speculative rollouts only.",
    }
    out.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("corpus", type=Path)
    p.add_argument("--out", type=Path, default=Path("models/damage_model.csv"))
    p.add_argument("--train-fraction", type=float, default=0.8)
    a = p.parse_args()
    print(json.dumps(train(a.corpus, a.out, a.train_fraction), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
