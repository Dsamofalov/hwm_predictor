from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, parse_initial_entities, parse_tooltips


ABILITY = "deathwail"


def _normalize(value: object) -> str:
    return " ".join(html.unescape(str(value or "")).split())


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("abilities") or [])}


def _by_uid(state: list[dict], uid: int | None) -> dict | None:
    if uid is None:
        return None
    return next((e for e in state if int(e.get("uid", -1)) == int(uid)), None)


def _cells(entity: dict) -> set[tuple[int, int]]:
    x, y = int(entity.get("x", 0)), int(entity.get("y", 0))
    side = 2 if "big" in _abilities(entity) else 1
    return {(x + dx, y + dy) for dx in range(side) for dy in range(side)}


def _distance(a: dict, b: dict) -> int:
    return min(
        max(abs(ax - bx), abs(ay - by))
        for ax, ay in _cells(a)
        for bx, by in _cells(b)
    )


def _claims(description: str) -> dict:
    lower = description.lower()
    return {
        "percentages": [int(x) for x in re.findall(r"(\d+)\s*%", description)],
        "integers": [int(x) for x in re.findall(r"\b(\d+)\b", description)],
        "mentions_living": any(x in lower for x in ("жив", "living")),
        "mentions_enemy": any(x in lower for x in ("противник", "враг", "enemy")),
        "mentions_three_cells": any(x in lower for x in ("трех клет", "трёх клет", "three cells")),
        "mentions_morale": any(x in lower for x in ("боевого дух", "morale")),
        "mentions_distance": any(x in lower for x in ("расстоя", "distance")),
        "mentions_15": bool(re.search(r"\b15\b", description)),
        "mentions_half": any(x in lower for x in ("полов", "half")),
        "mentions_quarter": any(x in lower for x in ("четверт", "quarter")),
    }


def _counter(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in counter.most_common()}


def _reference_damage(count: int, morale: float, distance: int) -> float | None:
    if distance not in {1, 2, 3}:
        return None
    base = max(0.0, 15.0 - float(morale)) * max(0, int(count))
    factor = {1: 1.0, 2: 0.5, 3: 0.25}[distance]
    return base * factor


def analyze_corpus(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    if not root.is_dir():
        raise FileNotFoundError(root)
    battle_dirs = [p for p in root.iterdir() if p.is_dir()]
    battle_dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))

    parse_errors: list[str] = []
    carrier_uids: dict[str, set[int]] = {}
    initial_morale: dict[tuple[str, int], float] = {}
    carrier_entities = 0
    carrier_creatures: Counter[int] = Counter()
    carrier_ability_sets: Counter[str] = Counter()
    tooltip_battles = 0
    tooltip_names: Counter[str] = Counter()
    tooltip_descriptions: Counter[str] = Counter()
    tooltip_claim_shapes: Counter[str] = Counter()
    init_examples: list[dict] = []

    for battle_dir in battle_dirs:
        init_path = battle_dir / "init.txt"
        if not init_path.exists():
            continue
        try:
            payload = init_path.read_text(encoding="utf-8", errors="replace")
            entities, warnings = parse_initial_entities(payload)
            tooltips = parse_tooltips(payload)
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:init:{type(exc).__name__}:{exc}")
            continue
        if warnings:
            parse_errors.extend(f"{battle_dir.name}:init_warning:{w}" for w in warnings)

        for entity in entities.values():
            initial_morale[(battle_dir.name, int(entity.uid))] = float(entity.morale_raw)

        uids: set[int] = set()
        rows: list[dict] = []
        for entity in entities.values():
            abilities = {str(x).lower() for x in entity.abilities}
            if ABILITY not in abilities:
                continue
            uid = int(entity.uid)
            uids.add(uid)
            carrier_entities += 1
            carrier_creatures[int(entity.creature_id)] += 1
            carrier_ability_sets[",".join(sorted(abilities)) or "<none>"] += 1
            rows.append(
                {
                    "uid": uid,
                    "owner": int(entity.owner),
                    "creature_id": int(entity.creature_id),
                    "count": int(entity.count),
                    "morale_raw": float(entity.morale_raw),
                    "abilities": sorted(abilities),
                }
            )
        if not uids:
            continue
        carrier_uids[battle_dir.name] = uids

        name = _normalize((tooltips.get("abil_names") or {}).get(ABILITY))
        description = _normalize((tooltips.get("abil_desc") or {}).get(ABILITY))
        if name or description:
            tooltip_battles += 1
            if name:
                tooltip_names[name] += 1
            if description:
                tooltip_descriptions[description] += 1
                tooltip_claim_shapes[json.dumps(_claims(description), ensure_ascii=False, sort_keys=True)] += 1
        if len(init_examples) < 20:
            init_examples.append(
                {
                    "battle_id": battle_dir.name,
                    "carriers": rows,
                    "tooltip_name": name,
                    "tooltip_description": description,
                    "tooltip_claims": _claims(description) if description else {},
                }
            )

    carrier_decisions = 0
    carrier_action_types: Counter[str] = Counter()
    carrier_special_codes: Counter[str] = Counter()
    outgoing_damage_decisions = 0
    multi_target_damage_decisions = 0
    damage_hits = 0
    target_owner_relations: Counter[str] = Counter()
    target_distance: Counter[int] = Counter()
    target_ability_sets: Counter[str] = Counter()
    formula_exact_integer = 0
    formula_floor_match = 0
    formula_round_match = 0
    formula_ceil_match = 0
    formula_comparable_hits = 0
    formula_abs_error: Counter[str] = Counter()
    code_damage_context: dict[str, Counter[str]] = defaultdict(Counter)
    examples: list[dict] = []

    for battle_dir in battle_dirs:
        carriers = carrier_uids.get(battle_dir.name)
        if not carriers:
            continue
        try:
            for decision in iter_battle_decisions(battle_dir):
                actor_uid = int(decision.get("actor_uid", -1))
                if actor_uid not in carriers:
                    continue
                carrier_decisions += 1
                action_type = str(decision.get("action_type", ""))
                carrier_action_types[action_type] += 1
                before = list(decision.get("state_before") or [])
                actor = _by_uid(before, actor_uid)
                if not actor:
                    continue
                commands = parse_commands(str(decision.get("raw", "")))
                specials = [
                    c for c in commands
                    if c.opcode == "SPECIAL" and c.actor_uid is not None and int(c.actor_uid) == actor_uid
                ]
                for c in specials:
                    carrier_special_codes[str(c.code)] += 1
                damages = [
                    c for c in commands
                    if c.opcode == "DAMAGE"
                    and c.actor_uid is not None and int(c.actor_uid) == actor_uid
                    and c.target_uid is not None
                ]
                if not damages:
                    continue
                outgoing_damage_decisions += 1
                if len({int(c.target_uid) for c in damages}) > 1:
                    multi_target_damage_decisions += 1
                code_key = ",".join(sorted({str(c.code) for c in specials})) or "<none>"
                code_damage_context[code_key][f"hits={len(damages)}"] += 1

                hit_rows = []
                for c in damages:
                    damage_hits += 1
                    target_uid = int(c.target_uid)
                    target = _by_uid(before, target_uid)
                    if not target:
                        continue
                    owner_relation = (
                        "same_owner"
                        if int(target.get("owner", -1)) == int(actor.get("owner", -2))
                        else "other_owner"
                    )
                    target_owner_relations[owner_relation] += 1
                    distance = _distance(actor, target)
                    target_distance[distance] += 1
                    abilities = sorted(_abilities(target))
                    target_ability_sets[",".join(abilities) or "<none>"] += 1
                    morale = initial_morale.get((battle_id := str(decision.get("battle_id", battle_dir.name)), target_uid))
                    amount = int(c.amount or 0)
                    candidate = _reference_damage(int(actor.get("count", 0)), morale, distance) if morale is not None else None
                    if candidate is not None:
                        formula_comparable_hits += 1
                        if candidate.is_integer() and int(candidate) == amount:
                            formula_exact_integer += 1
                        import math
                        if math.floor(candidate) == amount:
                            formula_floor_match += 1
                        if round(candidate) == amount:
                            formula_round_match += 1
                        if math.ceil(candidate) == amount:
                            formula_ceil_match += 1
                        formula_abs_error[f"{abs(amount - candidate):.3f}"] += 1
                    hit_rows.append(
                        {
                            "target_uid": target_uid,
                            "target_owner": int(target.get("owner", -1)),
                            "target_creature_id": int(target.get("creature_id", -1)),
                            "target_abilities": abilities,
                            "distance": distance,
                            "initial_morale_raw": morale,
                            "damage": amount,
                            "reference_candidate": candidate,
                            "raw": str(c.raw),
                        }
                    )
                if len(examples) < 80:
                    examples.append(
                        {
                            "battle_id": str(decision.get("battle_id", battle_dir.name)),
                            "decision_index": int(decision.get("decision_index", -1)),
                            "server_turn": int(decision.get("server_turn", -1)),
                            "action_type": action_type,
                            "actor_uid": actor_uid,
                            "actor_owner": int(actor.get("owner", -1)),
                            "actor_creature_id": int(actor.get("creature_id", -1)),
                            "actor_count": int(actor.get("count", 0)),
                            "actor_abilities": sorted(_abilities(actor)),
                            "specials": [str(c.raw) for c in specials],
                            "damage": hit_rows,
                            "raw": str(decision.get("raw", "")),
                        }
                    )
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_activation_multitarget_geometry_and_formula_falsification",
        "corpus_battle_dirs": len(battle_dirs),
        "carrier_battles": len(carrier_uids),
        "carrier_entities": carrier_entities,
        "carrier_creatures": _counter(carrier_creatures),
        "carrier_ability_sets": _counter(carrier_ability_sets),
        "tooltip_battles": tooltip_battles,
        "tooltip_names": _counter(tooltip_names),
        "tooltip_descriptions": _counter(tooltip_descriptions),
        "tooltip_claim_shapes": [
            {"count": int(count), "claims": json.loads(raw)}
            for raw, count in tooltip_claim_shapes.most_common()
        ],
        "carrier_decisions": carrier_decisions,
        "carrier_action_types": _counter(carrier_action_types),
        "carrier_special_codes": _counter(carrier_special_codes),
        "outgoing_damage_decisions": outgoing_damage_decisions,
        "multi_target_damage_decisions": multi_target_damage_decisions,
        "damage_hits": damage_hits,
        "target_owner_relations": _counter(target_owner_relations),
        "target_distance": _counter(target_distance),
        "target_ability_sets": dict(target_ability_sets.most_common(40)),
        "code_damage_context": {
            code: _counter(counter) for code, counter in sorted(code_damage_context.items())
        },
        "reference_formula": {
            "definition": "(15 - initial target morale_raw) * carrier count * {1:1,2:0.5,3:0.25}",
            "status": "falsification_candidate_only",
            "comparable_hits": formula_comparable_hits,
            "exact_integer_matches": formula_exact_integer,
            "floor_matches": formula_floor_match,
            "round_matches": formula_round_match,
            "ceil_matches": formula_ceil_match,
            "absolute_error": _counter(formula_abs_error),
        },
        "examples": examples,
        "init_examples": init_examples,
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "The historical/reference damage equation is only a falsification candidate. Exact Death Wail support "
            "requires an isolated carrier activation wire, server tooltip agreement, complete target-set geometry, "
            "and corpus-perfect or independently explained damage semantics. Initial morale_raw is not promoted to a "
            "new canonical runtime field by this analyzer."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Death Wail activation and damage-formula evidence.")
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = analyze_corpus(args.corpus)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 2 if report["parse_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
