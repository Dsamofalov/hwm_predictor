from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, parse_initial_entities, parse_tooltips


ABILITY = "gribbomb"


def _normalize(value: object) -> str:
    return " ".join(html.unescape(str(value or "")).split())


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("abilities") or [])}


def _by_uid(state: list[dict], uid: int) -> dict | None:
    return next((e for e in state if int(e.get("uid", -1)) == int(uid)), None)


def _claims(description: str) -> dict:
    lower = description.lower()
    percentages = [int(x) for x in re.findall(r"(\d+)\s*%", description)]
    integers = [int(x) for x in re.findall(r"\b(\d+)\b", description)]
    return {
        "percentages": percentages,
        "integers": integers,
        "mentions_death": any(x in lower for x in ("гибел", "смерт", "погиб", "death", "dies", "killed")),
        "mentions_attack": any(x in lower for x in ("атак", "удар", "attack", "hit")),
        "mentions_damage": any(x in lower for x in ("урон", "damage")),
        "mentions_adjacent": any(x in lower for x in ("сосед", "рядом", "adjacent", "nearby")),
        "mentions_enemy": any(x in lower for x in ("враг", "противник", "enemy")),
        "mentions_spore": any(x in lower for x in ("спор", "spore")),
        "mentions_explosion": any(x in lower for x in ("взрыв", "explos", "bomb")),
    }


def _counter(c: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in c.most_common()}


def _cmd_shape(commands) -> str:
    return "->".join(c.opcode if c.opcode != "SPECIAL" else f"SPECIAL:{c.code}" for c in commands)


def _related_commands(commands, carrier_uids: set[int]) -> list[dict]:
    rows = []
    for i, c in enumerate(commands):
        actor = int(c.actor_uid) if c.actor_uid is not None else None
        target = int(c.target_uid) if c.target_uid is not None else None
        if actor not in carrier_uids and target not in carrier_uids:
            continue
        rows.append(
            {
                "index": i,
                "opcode": str(c.opcode),
                "code": str(c.code),
                "actor_uid": actor,
                "target_uid": target,
                "amount": int(c.amount) if c.amount is not None else None,
                "x": int(c.x) if c.x is not None else None,
                "y": int(c.y) if c.y is not None else None,
                "raw": str(c.raw),
            }
        )
    return rows


def analyze_corpus(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    if not root.is_dir():
        raise FileNotFoundError(root)

    battle_dirs = [p for p in root.iterdir() if p.is_dir()]
    battle_dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))

    parse_errors: list[str] = []
    carrier_battles: set[str] = set()
    carrier_uids: dict[str, set[int]] = {}
    carrier_entities = 0
    carrier_creatures: Counter[int] = Counter()
    carrier_ability_sets: Counter[str] = Counter()
    carrier_owners: Counter[int] = Counter()
    tooltip_battles = 0
    tooltip_names: Counter[str] = Counter()
    tooltip_descriptions: Counter[str] = Counter()
    tooltip_claims: Counter[str] = Counter()
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

        name = _normalize((tooltips.get("abil_names") or {}).get(ABILITY))
        description = _normalize((tooltips.get("abil_desc") or {}).get(ABILITY))
        if name or description:
            tooltip_battles += 1
            if name:
                tooltip_names[name] += 1
            if description:
                tooltip_descriptions[description] += 1
                tooltip_claims[json.dumps(_claims(description), ensure_ascii=False, sort_keys=True)] += 1

        battle_carriers = []
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
            battle_carriers.append(
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
            carrier_battles.add(battle_dir.name)
            carrier_uids[battle_dir.name] = uids
            if len(init_examples) < 20:
                init_examples.append(
                    {
                        "battle_id": battle_dir.name,
                        "carriers": battle_carriers,
                        "tooltip_name": name,
                        "tooltip_description": description,
                        "tooltip_claims": _claims(description) if description else {},
                    }
                )

    actor_actions: Counter[str] = Counter()
    actor_decisions = 0
    involved_decisions = 0
    involved_shapes: Counter[str] = Counter()
    carrier_special_codes: Counter[str] = Counter()
    carrier_special_shapes: Counter[str] = Counter()
    carrier_damage_hits = 0
    carrier_damage_targets: Counter[int] = Counter()
    incoming_damage_hits = 0
    death_transitions = 0
    death_shapes: Counter[str] = Counter()
    death_carrier_sourced_damage_hits = 0
    death_carrier_sourced_specials: Counter[str] = Counter()
    death_nonactive_carrier_damage_hits = 0
    death_examples: list[dict] = []
    actor_examples: list[dict] = []

    for battle_dir in battle_dirs:
        uids = carrier_uids.get(battle_dir.name)
        if not uids:
            continue
        try:
            for decision in iter_battle_decisions(battle_dir):
                battle_id = str(decision.get("battle_id", battle_dir.name))
                actor_uid = int(decision.get("actor_uid", -1))
                before = list(decision.get("state_before") or [])
                after = list(decision.get("state_after") or [])
                commands = parse_commands(str(decision.get("raw", "")))
                related = _related_commands(commands, uids)

                if actor_uid in uids:
                    actor_decisions += 1
                    actor_actions[str(decision.get("action_type", ""))] += 1
                    if len(actor_examples) < 30:
                        actor = _by_uid(before, actor_uid)
                        actor_examples.append(
                            {
                                "battle_id": battle_id,
                                "decision_index": int(decision.get("decision_index", -1)),
                                "server_turn": int(decision.get("server_turn", -1)),
                                "action_type": str(decision.get("action_type", "")),
                                "actor_uid": actor_uid,
                                "actor_creature_id": int(actor.get("creature_id", -1)) if actor else None,
                                "actor_abilities": sorted(_abilities(actor)),
                                "shape": _cmd_shape(commands),
                                "raw": str(decision.get("raw", "")),
                            }
                        )

                has_carrier_event = actor_uid in uids or bool(related)
                if has_carrier_event:
                    involved_decisions += 1
                    involved_shapes[_cmd_shape(commands)] += 1

                for c in commands:
                    source = int(c.actor_uid) if c.actor_uid is not None else None
                    target = int(c.target_uid) if c.target_uid is not None else None
                    if c.opcode == "SPECIAL" and source in uids:
                        carrier_special_codes[str(c.code)] += 1
                        carrier_special_shapes[str(c.raw)] += 1
                    if c.opcode == "DAMAGE" and source in uids:
                        carrier_damage_hits += 1
                        if target is not None:
                            carrier_damage_targets[target] += 1
                    if c.opcode == "DAMAGE" and target in uids:
                        incoming_damage_hits += 1

                dead_now = []
                for uid in uids:
                    b = _by_uid(before, uid)
                    a = _by_uid(after, uid)
                    if b and bool(b.get("alive", False)) and (a is None or not bool(a.get("alive", False))):
                        dead_now.append(uid)
                if not dead_now:
                    continue

                death_transitions += len(dead_now)
                death_shapes[_cmd_shape(commands)] += 1
                sourced_damage = [
                    c for c in commands
                    if c.opcode == "DAMAGE" and c.actor_uid is not None and int(c.actor_uid) in set(dead_now)
                ]
                sourced_specials = [
                    c for c in commands
                    if c.opcode == "SPECIAL" and c.actor_uid is not None and int(c.actor_uid) in set(dead_now)
                ]
                death_carrier_sourced_damage_hits += len(sourced_damage)
                death_nonactive_carrier_damage_hits += sum(int(int(c.actor_uid) != actor_uid) for c in sourced_damage)
                for c in sourced_specials:
                    death_carrier_sourced_specials[str(c.code)] += 1

                if len(death_examples) < 60:
                    death_examples.append(
                        {
                            "battle_id": battle_id,
                            "decision_index": int(decision.get("decision_index", -1)),
                            "server_turn": int(decision.get("server_turn", -1)),
                            "active_actor_uid": actor_uid,
                            "active_action_type": str(decision.get("action_type", "")),
                            "dead_carrier_uids": dead_now,
                            "shape": _cmd_shape(commands),
                            "carrier_sourced_damage": [
                                {
                                    "source_uid": int(c.actor_uid),
                                    "target_uid": int(c.target_uid) if c.target_uid is not None else None,
                                    "amount": int(c.amount or 0),
                                    "raw": str(c.raw),
                                }
                                for c in sourced_damage
                            ],
                            "carrier_sourced_specials": [str(c.raw) for c in sourced_specials],
                            "related_commands": related,
                            "raw": str(decision.get("raw", "")),
                        }
                    )
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_init_tooltip_and_turn_event_discovery",
        "corpus_battle_dirs": len(battle_dirs),
        "parse_errors": parse_errors,
        "carrier_battles": len(carrier_battles),
        "carrier_entities": carrier_entities,
        "carrier_creatures": _counter(carrier_creatures),
        "carrier_ability_sets": _counter(carrier_ability_sets),
        "carrier_owners": _counter(carrier_owners),
        "tooltip_battles": tooltip_battles,
        "tooltip_names": _counter(tooltip_names),
        "tooltip_descriptions": _counter(tooltip_descriptions),
        "tooltip_claim_shapes": [
            {"count": int(count), "claims": json.loads(raw)}
            for raw, count in tooltip_claims.most_common()
        ],
        "actor_decisions": actor_decisions,
        "actor_action_types": _counter(actor_actions),
        "involved_decisions": involved_decisions,
        "involved_command_shapes": _counter(involved_shapes),
        "carrier_special_codes": _counter(carrier_special_codes),
        "carrier_special_raw_shapes": dict(carrier_special_shapes.most_common(40)),
        "carrier_damage_hits": carrier_damage_hits,
        "carrier_damage_targets": _counter(carrier_damage_targets),
        "incoming_damage_hits": incoming_damage_hits,
        "death": {
            "carrier_death_transitions": death_transitions,
            "command_shapes": _counter(death_shapes),
            "carrier_sourced_damage_hits": death_carrier_sourced_damage_hits,
            "nonactive_dead_carrier_sourced_damage_hits": death_nonactive_carrier_damage_hits,
            "carrier_sourced_special_codes": _counter(death_carrier_sourced_specials),
            "examples": death_examples,
        },
        "init_examples": init_examples,
        "actor_examples": actor_examples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Gribbomb raw corpus evidence.")
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
