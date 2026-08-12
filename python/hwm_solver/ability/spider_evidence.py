from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, parse_initial_entities, parse_tooltips


ABILITY = "spider"


def _normalize(value: object) -> str:
    return " ".join(html.unescape(str(value or "")).split())


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("abilities") or [])}


def _by_uid(state: list[dict], uid: int) -> dict | None:
    return next((e for e in state if int(e.get("uid", -1)) == int(uid)), None)


def _effects(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x) for x in (entity.get("effects") or [])}


def _claims(description: str) -> dict:
    lower = description.lower()
    return {
        "percentages": [int(x) for x in re.findall(r"(\d+)\s*%", description)],
        "integers": [int(x) for x in re.findall(r"\b(\d+)\b", description)],
        "mentions_enemy": any(x in lower for x in ("враг", "противник", "enemy")),
        "mentions_immobilize": any(x in lower for x in ("обездвиж", "неподвиж", "immobil", "root")),
        "mentions_multiple": any(x in lower for x in ("несколь", "multiple")),
        "mentions_until_move": any(
            x in lower for x in ("не двига", "двинет", "сдвин", "until it moves", "until the creature moves")
        ),
    }


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

        name = _normalize((tooltips.get("abil_names") or {}).get(ABILITY))
        description = _normalize((tooltips.get("abil_desc") or {}).get(ABILITY))
        if name or description:
            tooltip_battles += 1
            if name:
                tooltip_names[name] += 1
            if description:
                tooltip_descriptions[description] += 1
                tooltip_claim_shapes[json.dumps(_claims(description), ensure_ascii=False, sort_keys=True)] += 1

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
                    "x": int(entity.x),
                    "y": int(entity.y),
                    "abilities": sorted(abilities),
                }
            )
        if uids:
            carrier_uids[battle_dir.name] = uids
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
    carrier_move_decisions = 0
    carrier_special_codes: Counter[str] = Counter()
    carrier_special_target_counts: Counter[str] = Counter()
    code_target_added_effects: dict[str, Counter[str]] = defaultdict(Counter)
    code_target_removed_effects: dict[str, Counter[str]] = defaultdict(Counter)
    code_owner_relations: dict[str, Counter[str]] = defaultdict(Counter)
    source_target_specials = 0
    carrier_special_examples: list[dict] = []
    move_examples: list[dict] = []

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
                after = list(decision.get("state_after") or [])
                actor_before = _by_uid(before, actor_uid)
                actor_after = _by_uid(after, actor_uid)
                moved = bool(
                    actor_before
                    and actor_after
                    and (int(actor_before.get("x", 0)), int(actor_before.get("y", 0)))
                    != (int(actor_after.get("x", 0)), int(actor_after.get("y", 0)))
                )
                if moved:
                    carrier_move_decisions += 1
                    if len(move_examples) < 30:
                        move_examples.append(
                            {
                                "battle_id": str(decision.get("battle_id", battle_dir.name)),
                                "decision_index": int(decision.get("decision_index", -1)),
                                "server_turn": int(decision.get("server_turn", -1)),
                                "action_type": action_type,
                                "actor_uid": actor_uid,
                                "before_xy": [int(actor_before.get("x", 0)), int(actor_before.get("y", 0))],
                                "after_xy": [int(actor_after.get("x", 0)), int(actor_after.get("y", 0))],
                                "raw": str(decision.get("raw", "")),
                            }
                        )

                commands = parse_commands(str(decision.get("raw", "")))
                specials = [
                    c for c in commands
                    if c.opcode == "SPECIAL" and c.actor_uid is not None and int(c.actor_uid) == actor_uid
                ]
                targets_by_code: dict[str, set[int]] = defaultdict(set)
                for command in specials:
                    code = str(command.code)
                    carrier_special_codes[code] += 1
                    if command.target_uid is None:
                        continue
                    target_uid = int(command.target_uid)
                    target_before = _by_uid(before, target_uid)
                    target_after = _by_uid(after, target_uid)
                    if target_before is None and target_after is None:
                        continue
                    source_target_specials += 1
                    targets_by_code[code].add(target_uid)
                    before_effects = _effects(target_before)
                    after_effects = _effects(target_after)
                    added = sorted(after_effects - before_effects)
                    removed = sorted(before_effects - after_effects)
                    for effect in added:
                        code_target_added_effects[code][effect] += 1
                    for effect in removed:
                        code_target_removed_effects[code][effect] += 1
                    owner_relation = "unknown"
                    if actor_before and target_before:
                        owner_relation = (
                            "same_owner"
                            if int(actor_before.get("owner", -1)) == int(target_before.get("owner", -2))
                            else "other_owner"
                        )
                    code_owner_relations[code][owner_relation] += 1
                    if len(carrier_special_examples) < 80:
                        carrier_special_examples.append(
                            {
                                "battle_id": str(decision.get("battle_id", battle_dir.name)),
                                "decision_index": int(decision.get("decision_index", -1)),
                                "server_turn": int(decision.get("server_turn", -1)),
                                "action_type": action_type,
                                "actor_uid": actor_uid,
                                "actor_owner": int(actor_before.get("owner", -1)) if actor_before else None,
                                "actor_creature_id": int(actor_before.get("creature_id", -1)) if actor_before else None,
                                "actor_moved": moved,
                                "special_code": code,
                                "special_raw": str(command.raw),
                                "target_uid": target_uid,
                                "target_owner": int(target_before.get("owner", -1)) if target_before else None,
                                "target_creature_id": int(target_before.get("creature_id", -1)) if target_before else None,
                                "target_abilities": sorted(_abilities(target_before)),
                                "effects_before": sorted(before_effects),
                                "effects_after": sorted(after_effects),
                                "effects_added": added,
                                "effects_removed": removed,
                                "raw": str(decision.get("raw", "")),
                            }
                        )
                for code, targets in targets_by_code.items():
                    carrier_special_target_counts[f"{code}:{len(targets)}"] += 1
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_server_tooltip_special_wire_and_effect_deltas",
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
        "carrier_move_decisions": carrier_move_decisions,
        "carrier_special_codes": _counter(carrier_special_codes),
        "source_target_specials": source_target_specials,
        "carrier_special_target_counts": _counter(carrier_special_target_counts),
        "code_target_added_effects": {
            code: _counter(counter) for code, counter in sorted(code_target_added_effects.items())
        },
        "code_target_removed_effects": {
            code: _counter(counter) for code, counter in sorted(code_target_removed_effects.items())
        },
        "code_owner_relations": {
            code: _counter(counter) for code, counter in sorted(code_owner_relations.items())
        },
        "init_examples": init_examples,
        "carrier_special_examples": carrier_special_examples,
        "move_examples": move_examples,
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "A carrier SPECIAL code is not automatically Spider. Exact support requires a carrier-specific wire, "
            "an observed target immobilization consequence, multi-target semantics if present, and lifecycle evidence "
            "showing when the effect clears relative to carrier movement/death."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Spider web lifecycle evidence.")
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
