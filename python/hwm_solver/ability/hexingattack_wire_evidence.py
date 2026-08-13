from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from hwm_solver.ability.childofthelight_spellwire_evidence import _spellbook_entries
from hwm_solver.protocol.replay import iter_battle_decisions, parse_initial_entities


ABILITY = "hexingattack"
ATTACK_TYPES = {"MELEE_ATTACK", "RANGED_ATTACK"}
CANDIDATE_CODES = ("crs", "slw", "sff", "ray")
WIRE_RE = re.compile(r"S(crs|slw|sff|ray)(\d{15})(?!\d)")


def _counter(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in counter.most_common()}


def _nested(counters: dict[str, Counter]) -> dict[str, dict[str, int]]:
    return {code: _counter(counter) for code, counter in sorted(counters.items())}


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("abilities") or [])}


def _by_uid(state: list[dict], uid: int) -> dict | None:
    return next((e for e in state if int(e.get("uid", -1)) == int(uid)), None)


def analyze_wire_collisions(corpus: Path) -> dict:
    """Inventory candidate Hexing status wires over the whole raw corpus.

    The four three-letter codes are selected only because three are already decoded status
    wires observed after Hexing-carrier attacks and raw ``Sray`` is the unresolved fourth
    candidate in those same attack windows.  This auditor deliberately does not translate
    ``ray`` to a spell name.  It reports fixed-width layout, source/target agreement,
    source ability collisions, zero-vs-positive field populations and raw server spellbook
    context so semantic attribution can be decided from evidence rather than mnemonics.
    """
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    if not root.is_dir():
        raise FileNotFoundError(root)
    battle_dirs = [p for p in root.iterdir() if p.is_dir()]
    battle_dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))

    parse_errors: list[str] = []
    initial: dict[tuple[str, int], object] = {}
    spellbooks: dict[tuple[str, int], list[dict]] = {}

    for battle_dir in battle_dirs:
        init_path = battle_dir / "init.txt"
        if not init_path.exists():
            continue
        try:
            entities, warnings = parse_initial_entities(
                init_path.read_text(encoding="utf-8", errors="replace")
            )
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:init:{type(exc).__name__}:{exc}")
            continue
        if warnings:
            parse_errors.extend(f"{battle_dir.name}:init_warning:{w}" for w in warnings)
        for uid, entity in entities.items():
            initial[(battle_dir.name, int(uid))] = entity
            spellbooks[(battle_dir.name, int(uid))] = _spellbook_entries(entity.magic_blob)

    records: Counter[str] = Counter()
    field2_shapes: dict[str, Counter[str]] = defaultdict(Counter)
    field4_shapes: dict[str, Counter[str]] = defaultdict(Counter)
    field3_shapes: dict[str, Counter[str]] = defaultdict(Counter)
    action_types: dict[str, Counter[str]] = defaultdict(Counter)
    source_ability_sets: dict[str, Counter[str]] = defaultdict(Counter)
    source_creatures: dict[str, Counter[str]] = defaultdict(Counter)
    source_spellbook_names: dict[str, Counter[str]] = defaultdict(Counter)
    positive_exact_cost_spellbook_names: dict[str, Counter[str]] = defaultdict(Counter)
    positive_compatible_cost_spellbook_names: dict[str, Counter[str]] = defaultdict(Counter)
    positive_spellbook_entry_shapes: dict[str, Counter[str]] = defaultdict(Counter)

    source_present: Counter[str] = Counter()
    target_present: Counter[str] = Counter()
    source_hexing: Counter[str] = Counter()
    decision_actor_match: Counter[str] = Counter()
    decision_target_match: Counter[str] = Counter()
    attack_bound: Counter[str] = Counter()
    hexing_attack_bound: Counter[str] = Counter()
    nonhexing_attack_bound: Counter[str] = Counter()
    zero_field2: Counter[str] = Counter()
    positive_field2: Counter[str] = Counter()
    other_owner: Counter[str] = Counter()
    same_owner: Counter[str] = Counter()
    examples: dict[str, list[dict]] = defaultdict(list)
    positive_examples: dict[str, list[dict]] = defaultdict(list)

    for battle_dir in battle_dirs:
        try:
            decisions = iter_battle_decisions(battle_dir)
            for decision in decisions:
                raw = str(decision.get("raw", ""))
                matches = list(WIRE_RE.finditer(raw))
                if not matches:
                    continue
                before = list(decision.get("state_before") or [])
                action_type = str(decision.get("action_type", ""))
                decision_actor = decision.get("actor_uid")
                decision_target = decision.get("target_uid")

                for match in matches:
                    code = match.group(1)
                    payload = match.group(2)
                    actor_uid = int(payload[:3])
                    target_uid = int(payload[3:6])
                    field2 = int(payload[6:8])
                    field4 = int(payload[8:12])
                    field3 = int(payload[12:15])
                    records[code] += 1
                    field2_shapes[code][f"{field2:02d}"] += 1
                    field4_shapes[code][f"{field4:04d}"] += 1
                    field3_shapes[code][f"{field3:03d}"] += 1
                    action_types[code][action_type or "<none>"] += 1
                    if field2 == 0:
                        zero_field2[code] += 1
                    else:
                        positive_field2[code] += 1

                    actor = _by_uid(before, actor_uid)
                    target = _by_uid(before, target_uid)
                    actor_abilities = _abilities(actor)
                    target_abilities = _abilities(target)
                    if actor is not None:
                        source_present[code] += 1
                        source_ability_sets[code][",".join(sorted(actor_abilities)) or "<none>"] += 1
                        source_creatures[code][str(int(actor.get("creature_id", -1)))] += 1
                    if target is not None:
                        target_present[code] += 1
                    if ABILITY in actor_abilities:
                        source_hexing[code] += 1
                    if actor is not None and target is not None:
                        if int(actor.get("owner", -1)) == int(target.get("owner", -2)):
                            same_owner[code] += 1
                        else:
                            other_owner[code] += 1

                    actor_matches = decision_actor is not None and int(decision_actor) == actor_uid
                    target_matches = decision_target is not None and int(decision_target) == target_uid
                    if actor_matches:
                        decision_actor_match[code] += 1
                    if target_matches:
                        decision_target_match[code] += 1
                    is_attack_bound = action_type in ATTACK_TYPES and actor_matches and target_matches
                    if is_attack_bound:
                        attack_bound[code] += 1
                        if ABILITY in actor_abilities:
                            hexing_attack_bound[code] += 1
                        else:
                            nonhexing_attack_bound[code] += 1

                    entries = spellbooks.get((battle_dir.name, actor_uid), [])
                    for entry in entries:
                        source_spellbook_names[code][str(entry["name"])] += 1
                        if field2 > 0 and int(entry["cost"]) == field2:
                            positive_exact_cost_spellbook_names[code][str(entry["name"])] += 1
                        if field2 > 0 and field2 <= int(entry["cost"]):
                            positive_compatible_cost_spellbook_names[code][str(entry["name"])] += 1
                    if field2 > 0:
                        for entry in entries:
                            shape = json.dumps(
                                {
                                    "name": str(entry["name"]),
                                    "cost": int(entry["cost"]),
                                    "effect": float(entry["effect"]),
                                    "school": str(entry["school"]),
                                },
                                ensure_ascii=False,
                                sort_keys=True,
                            )
                            positive_spellbook_entry_shapes[code][shape] += 1

                    row = {
                        "battle_id": str(decision.get("battle_id", battle_dir.name)),
                        "decision_index": int(decision.get("decision_index", -1)),
                        "server_turn": int(decision.get("server_turn", -1)),
                        "action_type": action_type,
                        "decision_actor_uid": int(decision_actor) if decision_actor is not None else None,
                        "decision_target_uid": int(decision_target) if decision_target is not None else None,
                        "actor_uid": actor_uid,
                        "target_uid": target_uid,
                        "actor_abilities": sorted(actor_abilities),
                        "target_abilities": sorted(target_abilities),
                        "actor_creature_id": int(actor.get("creature_id", -1)) if actor else None,
                        "field2": field2,
                        "field4": field4,
                        "field3": field3,
                        "attack_bound": is_attack_bound,
                        "raw_record": match.group(0),
                        "source_spellbook": [
                            {
                                "name": str(entry["name"]),
                                "cost": int(entry["cost"]),
                                "effect": float(entry["effect"]),
                                "school": str(entry["school"]),
                            }
                            for entry in entries
                        ],
                    }
                    if len(examples[code]) < 30:
                        examples[code].append(row)
                    if field2 > 0 and len(positive_examples[code]) < 30:
                        positive_examples[code].append(row)
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "whole_corpus_raw_candidate_status_wire_collision_inventory",
        "candidate_codes": list(CANDIDATE_CODES),
        "corpus_battle_dirs": len(battle_dirs),
        "records": _counter(records),
        "field2_shapes": _nested(field2_shapes),
        "field4_shapes": _nested(field4_shapes),
        "field3_shapes": _nested(field3_shapes),
        "action_types": _nested(action_types),
        "source_present": _counter(source_present),
        "target_present": _counter(target_present),
        "source_hexing": _counter(source_hexing),
        "decision_actor_match": _counter(decision_actor_match),
        "decision_target_match": _counter(decision_target_match),
        "attack_bound": _counter(attack_bound),
        "hexing_attack_bound": _counter(hexing_attack_bound),
        "nonhexing_attack_bound": _counter(nonhexing_attack_bound),
        "zero_field2": _counter(zero_field2),
        "positive_field2": _counter(positive_field2),
        "other_owner": _counter(other_owner),
        "same_owner": _counter(same_owner),
        "source_ability_sets": _nested(source_ability_sets),
        "source_creatures": _nested(source_creatures),
        "source_spellbook_names": _nested(source_spellbook_names),
        "positive_exact_cost_spellbook_names": _nested(positive_exact_cost_spellbook_names),
        "positive_compatible_cost_spellbook_names": _nested(positive_compatible_cost_spellbook_names),
        "positive_spellbook_entry_shapes": _nested(positive_spellbook_entry_shapes),
        "examples": {code: rows for code, rows in sorted(examples.items())},
        "positive_examples": {code: rows for code, rows in sorted(positive_examples.items())},
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "The fixed-width fields are reported structurally. field2/field4/field3 are not assigned spell semantics "
            "for raw ray. A ray record is not called Disrupting Ray unless independent normal-cast/spellbook controls "
            "and collision evidence justify that identity. Zero-cost attack-bound frequency is not a proc probability."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit whole-corpus Hexing candidate wire collisions.")
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = analyze_wire_collisions(args.corpus)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 2 if report["parse_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
