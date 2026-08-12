from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, parse_initial_entities, parse_tooltips


ABILITY = "portal"


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("abilities") or [])}


def _by_uid(state: list[dict], uid: int) -> dict | None:
    return next((e for e in state if int(e.get("uid", -1)) == int(uid)), None)


def _counter(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in counter.most_common()}


def analyze_corpus(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    if not root.is_dir():
        raise FileNotFoundError(root)
    battle_dirs = [p for p in root.iterdir() if p.is_dir()]
    battle_dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))

    parse_errors: list[str] = []
    carrier_uids: dict[str, set[int]] = {}
    carrier_entities = 0
    carrier_creatures: Counter[int] = Counter()
    carrier_ability_sets: Counter[str] = Counter()
    carrier_owners: Counter[int] = Counter()
    tooltip_battles = 0
    tooltip_names: Counter[str] = Counter()
    tooltip_descriptions: Counter[str] = Counter()
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

        name = str((tooltips.get("abil_names") or {}).get(ABILITY) or "").strip()
        description = str((tooltips.get("abil_desc") or {}).get(ABILITY) or "").strip()
        if name or description:
            tooltip_battles += 1
            if name:
                tooltip_names[name] += 1
            if description:
                tooltip_descriptions[description] += 1

        rows = []
        uids: set[int] = set()
        for entity in entities.values():
            abilities = {str(x).lower() for x in entity.abilities}
            if ABILITY not in abilities:
                continue
            uid = int(entity.uid)
            uids.add(uid)
            carrier_entities += 1
            carrier_creatures[int(entity.creature_id)] += 1
            carrier_owners[int(entity.owner)] += 1
            carrier_ability_sets[",".join(sorted(abilities)) or "<none>"] += 1
            rows.append(
                {
                    "uid": uid,
                    "owner": int(entity.owner),
                    "creature_id": int(entity.creature_id),
                    "count": int(entity.count),
                    "x": int(entity.x),
                    "y": int(entity.y),
                    "abilities": sorted(abilities),
                }
            )
        if uids:
            carrier_uids[battle_dir.name] = uids
            if len(init_examples) < 30:
                init_examples.append(
                    {
                        "battle_id": battle_dir.name,
                        "carriers": rows,
                        "tooltip_name": name,
                        "tooltip_description": description,
                    }
                )

    carrier_decisions = 0
    carrier_action_types: Counter[str] = Counter()
    carrier_outgoing_damage = 0
    carrier_incoming_damage = 0
    carrier_source_specials: Counter[str] = Counter()
    carrier_target_specials: Counter[str] = Counter()
    carrier_related_opcodes: Counter[str] = Counter()
    carrier_death_transitions = 0
    carrier_position_changes = 0
    carrier_count_changes = 0
    active_examples: list[dict] = []
    related_examples: list[dict] = []

    for battle_dir in battle_dirs:
        carriers = carrier_uids.get(battle_dir.name)
        if not carriers:
            continue
        try:
            for decision in iter_battle_decisions(battle_dir):
                actor_uid = int(decision.get("actor_uid", -1))
                before = list(decision.get("state_before") or [])
                after = list(decision.get("state_after") or [])
                commands = parse_commands(str(decision.get("raw", "")))
                if actor_uid in carriers:
                    carrier_decisions += 1
                    carrier_action_types[str(decision.get("action_type", ""))] += 1
                    if len(active_examples) < 50:
                        actor_before = _by_uid(before, actor_uid)
                        active_examples.append(
                            {
                                "battle_id": str(decision.get("battle_id", battle_dir.name)),
                                "decision_index": int(decision.get("decision_index", -1)),
                                "server_turn": int(decision.get("server_turn", -1)),
                                "action_type": str(decision.get("action_type", "")),
                                "actor_uid": actor_uid,
                                "actor_creature_id": int(actor_before.get("creature_id", -1)) if actor_before else None,
                                "actor_abilities": sorted(_abilities(actor_before)),
                                "raw": str(decision.get("raw", "")),
                            }
                        )

                related = []
                for command in commands:
                    source_uid = int(command.actor_uid) if command.actor_uid is not None else None
                    target_uid = int(command.target_uid) if command.target_uid is not None else None
                    if source_uid not in carriers and target_uid not in carriers:
                        continue
                    carrier_related_opcodes[str(command.opcode)] += 1
                    if command.opcode == "DAMAGE":
                        if source_uid in carriers and target_uid not in carriers:
                            carrier_outgoing_damage += 1
                        if target_uid in carriers and source_uid not in carriers:
                            carrier_incoming_damage += 1
                    if command.opcode == "SPECIAL":
                        if source_uid in carriers:
                            carrier_source_specials[str(command.code)] += 1
                        if target_uid in carriers:
                            carrier_target_specials[str(command.code)] += 1
                    related.append(
                        {
                            "opcode": str(command.opcode),
                            "code": str(command.code),
                            "actor_uid": source_uid,
                            "target_uid": target_uid,
                            "amount": int(command.amount) if command.amount is not None else None,
                            "x": int(command.x) if command.x is not None else None,
                            "y": int(command.y) if command.y is not None else None,
                            "raw": str(command.raw),
                        }
                    )

                for uid in carriers:
                    b = _by_uid(before, uid)
                    a = _by_uid(after, uid)
                    if not b:
                        continue
                    if bool(b.get("alive", False)) and (a is None or not bool(a.get("alive", False))):
                        carrier_death_transitions += 1
                    if a is not None:
                        if (int(b.get("x", 0)), int(b.get("y", 0))) != (int(a.get("x", 0)), int(a.get("y", 0))):
                            carrier_position_changes += 1
                        if int(b.get("count", 0)) != int(a.get("count", 0)):
                            carrier_count_changes += 1

                if related and len(related_examples) < 80:
                    related_examples.append(
                        {
                            "battle_id": str(decision.get("battle_id", battle_dir.name)),
                            "decision_index": int(decision.get("decision_index", -1)),
                            "server_turn": int(decision.get("server_turn", -1)),
                            "active_actor_uid": actor_uid,
                            "action_type": str(decision.get("action_type", "")),
                            "related": related,
                            "raw": str(decision.get("raw", "")),
                        }
                    )
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_identity_behavior_and_related_wire",
        "corpus_battle_dirs": len(battle_dirs),
        "carrier_battles": len(carrier_uids),
        "carrier_entities": carrier_entities,
        "carrier_creatures": _counter(carrier_creatures),
        "carrier_ability_sets": _counter(carrier_ability_sets),
        "carrier_owners": _counter(carrier_owners),
        "tooltip_battles": tooltip_battles,
        "tooltip_names": _counter(tooltip_names),
        "tooltip_descriptions": _counter(tooltip_descriptions),
        "carrier_decisions": carrier_decisions,
        "carrier_action_types": _counter(carrier_action_types),
        "carrier_outgoing_damage_hits": carrier_outgoing_damage,
        "carrier_incoming_damage_hits": carrier_incoming_damage,
        "carrier_source_special_codes": _counter(carrier_source_specials),
        "carrier_target_special_codes": _counter(carrier_target_specials),
        "carrier_related_opcodes": _counter(carrier_related_opcodes),
        "carrier_death_transitions": carrier_death_transitions,
        "carrier_position_changes": carrier_position_changes,
        "carrier_count_changes": carrier_count_changes,
        "init_examples": init_examples,
        "active_examples": active_examples,
        "related_examples": related_examples,
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "Portal has no usable metadata description in the current registry. This probe therefore makes no semantic "
            "assumption: identity-only classification is allowed only if corpus behavior shows no independent action, "
            "wire, targeting or state-transition mechanic requiring search support."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Portal identity/behavior evidence.")
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
