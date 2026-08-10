#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from hwm_solver.protocol.replay import iter_battle_decisions


def _by_uid(state: list[dict], uid: int) -> dict | None:
    return next((e for e in state if int(e.get("uid", -1)) == int(uid)), None)


def _friendly_hero_mana(state: list[dict], owner: int | None) -> int | None:
    if owner is None:
        return None
    heroes = [
        e for e in state
        if int(e.get("owner", -1)) == int(owner) and bool(e.get("is_hero"))
    ]
    if not heroes:
        return None
    return sum(int(e.get("mana", 0)) for e in heroes)


def _total_hp(entity: dict | None) -> int | None:
    if not entity:
        return None
    count = max(0, int(entity.get("count", 0)))
    if count <= 0:
        return 0
    max_hp = max(1, int(entity.get("max_hp", entity.get("max_hp_per_unit", 1))))
    top_hp = max(0, int(entity.get("top_hp", entity.get("top_unit_hp", max_hp))))
    return (count - 1) * max_hp + top_hp


def _effect_ids(entity: dict | None) -> list[str]:
    if not entity:
        return []
    out: list[str] = []
    for fx in entity.get("effects", []) or []:
        if isinstance(fx, dict):
            value = fx.get("id", fx.get("code", fx.get("name", "")))
        else:
            value = fx
        out.append(str(value))
    return sorted(out)


def _entity_snapshot(entity: dict | None) -> dict | None:
    if not entity:
        return None
    return {
        "uid": int(entity.get("uid", -1)),
        "owner": int(entity.get("owner", -1)),
        "creature_id": int(entity.get("creature_id", 0)),
        "alive": bool(entity.get("alive", True)),
        "count": int(entity.get("count", 0)),
        "top_hp": int(entity.get("top_hp", entity.get("top_unit_hp", 0))),
        "total_hp": _total_hp(entity),
        "mana": int(entity.get("mana", 0)),
        "speed": float(entity.get("speed", 0.0)),
        "initiative": float(entity.get("initiative", 0.0)),
        "atb": float(entity.get("atb", 0.0)),
        "x": int(entity.get("x", -1)),
        "y": int(entity.get("y", -1)),
        "effects": _effect_ids(entity),
        "abilities": sorted(str(x).lower() for x in (entity.get("abilities", []) or [])),
    }


def _entity_delta(before: dict | None, after: dict | None) -> dict | None:
    if before is None and after is None:
        return None
    b = _entity_snapshot(before)
    a = _entity_snapshot(after)
    if b is None:
        return {"spawned": True, "after": a}
    if a is None:
        return {"removed": True, "before": b}

    numeric = ("count", "top_hp", "total_hp", "mana", "speed", "initiative", "atb")
    delta = {key: a[key] - b[key] for key in numeric}
    delta["alive_changed"] = a["alive"] != b["alive"]
    delta["position_changed"] = (a["x"], a["y"]) != (b["x"], b["y"])
    delta["position_before"] = [b["x"], b["y"]]
    delta["position_after"] = [a["x"], a["y"]]
    before_fx, after_fx = set(b["effects"]), set(a["effects"])
    delta["effects_added"] = sorted(after_fx - before_fx)
    delta["effects_removed"] = sorted(before_fx - after_fx)
    return delta


def _count_delta(counter: Counter[str], value: object) -> None:
    counter[str(value)] += 1


def analyze_decisions(
    decisions: Iterable[dict], ability: str, *, row_limit: int = 100
) -> dict:
    """Summarize observed decisions made by stacks carrying ``ability``.

    This is deliberately a thin read-only layer over the canonical raw-corpus replay
    iterator. It does not decode new protocol semantics. Raw records/opcodes and the
    already-decoded before/after state are exposed so an ability can be proven from the
    same evidence pipeline before it is promoted to exact search.
    """
    ability = ability.strip().lower()
    action_types: Counter[str] = Counter()
    special_codes: Counter[str] = Counter()
    opcode_signatures: Counter[str] = Counter()
    mana_delta_pairs: Counter[str] = Counter()
    creature_ids: Counter[int] = Counter()
    target_count_deltas: Counter[str] = Counter()
    target_hp_deltas: Counter[str] = Counter()
    target_speed_deltas: Counter[str] = Counter()
    target_initiative_deltas: Counter[str] = Counter()
    target_atb_deltas: Counter[str] = Counter()
    target_position_deltas: Counter[str] = Counter()
    target_effect_additions: Counter[str] = Counter()
    target_effect_removals: Counter[str] = Counter()
    battles: set[str] = set()
    rows: list[dict] = []
    matched = 0
    candidates = 0

    for d in decisions:
        before = list(d.get("state_before") or [])
        after = list(d.get("state_after") or [])
        actor_uid = int(d.get("actor_uid", -1))
        actor_before = _by_uid(before, actor_uid)
        if not actor_before:
            continue
        abilities = {str(x).lower() for x in actor_before.get("abilities", [])}
        if ability not in abilities:
            continue

        matched += 1
        battle_id = str(d.get("battle_id", ""))
        battles.add(battle_id)
        action_type = str(d.get("action_type", "UNKNOWN"))
        action_types[action_type] += 1
        creature_id = int(actor_before.get("creature_id", 0))
        creature_ids[creature_id] += 1
        for code in d.get("special_codes") or []:
            special_codes[str(code)] += 1
        signature = ",".join(str(x) for x in (d.get("raw_opcodes") or [])) or "<none>"
        opcode_signatures[signature] += 1

        actor_after = _by_uid(after, actor_uid)
        target_uid_raw = d.get("target_uid")
        target_uid = int(target_uid_raw) if target_uid_raw is not None else None
        target_before = _by_uid(before, target_uid) if target_uid is not None else None
        target_after = _by_uid(after, target_uid) if target_uid is not None else None
        actor_state_delta = _entity_delta(actor_before, actor_after)
        target_state_delta = _entity_delta(target_before, target_after)

        if target_state_delta and not target_state_delta.get("spawned") and not target_state_delta.get("removed"):
            _count_delta(target_count_deltas, target_state_delta["count"])
            _count_delta(target_hp_deltas, target_state_delta["total_hp"])
            _count_delta(target_speed_deltas, target_state_delta["speed"])
            _count_delta(target_initiative_deltas, target_state_delta["initiative"])
            _count_delta(target_atb_deltas, target_state_delta["atb"])
            if target_state_delta["position_changed"]:
                dx = target_state_delta["position_after"][0] - target_state_delta["position_before"][0]
                dy = target_state_delta["position_after"][1] - target_state_delta["position_before"][1]
                _count_delta(target_position_deltas, f"{dx},{dy}")
            for fx in target_state_delta["effects_added"]:
                target_effect_additions[fx] += 1
            for fx in target_state_delta["effects_removed"]:
                target_effect_removals[fx] += 1

        owner = int(actor_before.get("owner", -1))
        actor_mana_before = int(actor_before.get("mana", 0))
        actor_mana_after = int(actor_after.get("mana", actor_mana_before)) if actor_after else None
        hero_mana_before = _friendly_hero_mana(before, owner)
        hero_mana_after = _friendly_hero_mana(after, owner)
        actor_delta = None if actor_mana_after is None else actor_mana_after - actor_mana_before
        hero_delta = None if hero_mana_before is None or hero_mana_after is None else hero_mana_after - hero_mana_before
        mana_delta_pairs[f"actor={actor_delta},hero={hero_delta}"] += 1

        target_changed = bool(target_state_delta and (
            target_state_delta.get("spawned")
            or target_state_delta.get("removed")
            or target_state_delta.get("alive_changed")
            or target_state_delta.get("position_changed")
            or target_state_delta.get("effects_added")
            or target_state_delta.get("effects_removed")
            or any(target_state_delta.get(k, 0) != 0 for k in ("count", "top_hp", "total_hp", "mana", "speed", "initiative", "atb"))
        ))
        is_candidate = bool(
            action_type in {"ABILITY", "CAST_OR_ABILITY"}
            or d.get("special_codes")
            or actor_delta not in {None, 0}
            or hero_delta not in {None, 0}
            or target_changed
            or any(op in {"Y_RECORD", "Z_RECORD", "X_RECORD", "SPECIAL"} for op in (d.get("raw_opcodes") or []))
        )
        if is_candidate:
            candidates += 1

        # Prefer mechanic-like rows; ordinary movement/attacks are useful only if room remains.
        if len(rows) < row_limit and (is_candidate or matched <= max(5, row_limit // 10)):
            rows.append({
                "battle_id": battle_id,
                "decision_index": int(d.get("decision_index", -1)),
                "server_turn": int(d.get("server_turn", -1)),
                "actor_uid": actor_uid,
                "actor_owner": owner,
                "actor_creature_id": creature_id,
                "actor_count": int(actor_before.get("count", 0)),
                "actor_mana_before": actor_mana_before,
                "actor_mana_after": actor_mana_after,
                "friendly_hero_mana_before": hero_mana_before,
                "friendly_hero_mana_after": hero_mana_after,
                "action_type": action_type,
                "target_uid": target_uid,
                "special_codes": list(d.get("special_codes") or []),
                "raw_opcodes": list(d.get("raw_opcodes") or []),
                "semantic_unresolved_opcodes": list(d.get("semantic_unresolved_opcodes") or []),
                "actor_before": _entity_snapshot(actor_before),
                "actor_after": _entity_snapshot(actor_after),
                "actor_delta": actor_state_delta,
                "target_before": _entity_snapshot(target_before),
                "target_after": _entity_snapshot(target_after),
                "target_delta": target_state_delta,
                "raw": str(d.get("raw", "")),
                "candidate": is_candidate,
            })

    return {
        "ability": ability,
        "matched_decisions": matched,
        "candidate_decisions": candidates,
        "battles": len(battles),
        "creature_ids": dict(creature_ids.most_common()),
        "action_types": dict(action_types.most_common()),
        "special_codes": dict(special_codes.most_common()),
        "opcode_signatures": dict(opcode_signatures.most_common()),
        "mana_delta_pairs": dict(mana_delta_pairs.most_common()),
        "target_deltas": {
            "count": dict(target_count_deltas.most_common()),
            "total_hp": dict(target_hp_deltas.most_common()),
            "speed": dict(target_speed_deltas.most_common()),
            "initiative": dict(target_initiative_deltas.most_common()),
            "atb": dict(target_atb_deltas.most_common()),
            "position": dict(target_position_deltas.most_common()),
            "effects_added": dict(target_effect_additions.most_common()),
            "effects_removed": dict(target_effect_removals.most_common()),
        },
        "rows": rows,
    }


def analyze_corpus(corpus: Path, ability: str, *, row_limit: int = 100) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    errors: list[str] = []

    def stream():
        if not root.is_dir():
            raise FileNotFoundError(root)
        dirs = [p for p in root.iterdir() if p.is_dir()]
        dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))
        for battle_dir in dirs:
            if not (battle_dir / "init.txt").exists() or not (battle_dir / "turns0.txt").exists():
                continue
            try:
                yield from iter_battle_decisions(battle_dir)
            except Exception as exc:  # research tool: keep scanning and report the exact battle
                errors.append(f"{battle_dir.name}:{type(exc).__name__}:{exc}")

    report = analyze_decisions(stream(), ability, row_limit=row_limit)
    report["corpus"] = str(corpus)
    report["errors"] = errors
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Inspect raw-corpus decisions made by carriers of one ability code.")
    ap.add_argument("corpus", type=Path, help="hwm_battles directory or its battles/ child")
    ap.add_argument("ability", help="raw ability code, e.g. manafeed")
    ap.add_argument("--rows", type=int, default=100, help="maximum detailed decision rows")
    ap.add_argument("--out", type=Path, help="optional JSON report path")
    args = ap.parse_args()

    report = analyze_corpus(args.corpus, args.ability, row_limit=max(0, args.rows))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, ensure_ascii=False, indent=2))
    if report["errors"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
