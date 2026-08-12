from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, parse_initial_entities, parse_tooltips


ABILITY = "ragingblood"


def _normalize(value: object) -> str:
    return " ".join(html.unescape(str(value or "")).split())


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("abilities") or [])}


def _effects(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x) for x in (entity.get("effects") or [])}


def _by_uid(state: list[dict], uid: int) -> dict | None:
    return next((e for e in state if int(e.get("uid", -1)) == int(uid)), None)


def _claims(description: str) -> dict:
    lower = description.lower()
    return {
        "percentages": [int(x) for x in re.findall(r"(\d+)\s*%", description)],
        "integers": [int(x) for x in re.findall(r"\b(\d+)\b", description)],
        "mentions_hero": any(x in lower for x in ("геро", "hero")),
        "mentions_faction": any(x in lower for x in ("фракц", "faction")),
        "mentions_rage": any(x in lower for x in ("ярост", "rage")),
        "mentions_stats": any(x in lower for x in ("характерист", "stat")),
        "mentions_aggressive": any(x in lower for x in ("агрессив", "aggress")),
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
    hero_same_owner_counts: Counter[str] = Counter()
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

        heroes_by_owner: Counter[int] = Counter()
        for entity in entities.values():
            if "hero" in {str(x).lower() for x in entity.abilities}:
                heroes_by_owner[int(entity.owner)] += 1

        uids: set[int] = set()
        rows = []
        for entity in entities.values():
            abilities = {str(x).lower() for x in entity.abilities}
            if ABILITY not in abilities:
                continue
            uid = int(entity.uid)
            uids.add(uid)
            carrier_entities += 1
            carrier_creatures[int(entity.creature_id)] += 1
            carrier_ability_sets[",".join(sorted(abilities)) or "<none>"] += 1
            same_owner_heroes = heroes_by_owner[int(entity.owner)]
            hero_same_owner_counts[str(same_owner_heroes)] += 1
            rows.append(
                {
                    "uid": uid,
                    "owner": int(entity.owner),
                    "creature_id": int(entity.creature_id),
                    "count": int(entity.count),
                    "abilities": sorted(abilities),
                    "same_owner_heroes": int(same_owner_heroes),
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
                        "tooltip_claims": _claims(description) if description else {},
                    }
                )

    carrier_decisions = 0
    action_types: Counter[str] = Counter()
    source_special_codes: Counter[str] = Counter()
    added_effects: Counter[str] = Counter()
    removed_effects: Counter[str] = Counter()
    effect_value_shapes: Counter[str] = Counter()
    stat_delta_shapes: Counter[str] = Counter()
    action_stat_deltas: dict[str, Counter[str]] = defaultdict(Counter)
    transition_examples: list[dict] = []

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
                action_types[action_type] += 1
                before = list(decision.get("state_before") or [])
                after = list(decision.get("state_after") or [])
                actor_before = _by_uid(before, actor_uid)
                actor_after = _by_uid(after, actor_uid)
                if not actor_before or not actor_after:
                    continue
                commands = parse_commands(str(decision.get("raw", "")))
                for command in commands:
                    if command.opcode == "SPECIAL" and command.actor_uid is not None and int(command.actor_uid) == actor_uid:
                        source_special_codes[str(command.code)] += 1

                before_effects = _effects(actor_before)
                after_effects = _effects(actor_after)
                added = sorted(after_effects - before_effects)
                removed = sorted(before_effects - after_effects)
                for effect in added:
                    added_effects[effect] += 1
                for effect in removed:
                    removed_effects[effect] += 1
                values = dict(actor_after.get("effect_values") or {})
                for effect in added:
                    effect_value_shapes[f"{effect}:{values.get(effect)}"] += 1

                stat_deltas = {}
                for key in ("attack", "defense", "speed", "initiative", "atb"):
                    b = float(actor_before.get(key, 0.0))
                    a = float(actor_after.get(key, 0.0))
                    delta = a - b
                    if abs(delta) > 1e-9:
                        stat_deltas[key] = delta
                shape = ",".join(f"{k}={v:+g}" for k, v in sorted(stat_deltas.items())) or "<none>"
                stat_delta_shapes[shape] += 1
                action_stat_deltas[action_type][shape] += 1

                if (added or removed or stat_deltas) and len(transition_examples) < 80:
                    transition_examples.append(
                        {
                            "battle_id": str(decision.get("battle_id", battle_dir.name)),
                            "decision_index": int(decision.get("decision_index", -1)),
                            "server_turn": int(decision.get("server_turn", -1)),
                            "action_type": action_type,
                            "actor_uid": actor_uid,
                            "actor_creature_id": int(actor_before.get("creature_id", -1)),
                            "actor_abilities": sorted(_abilities(actor_before)),
                            "effects_added": added,
                            "effects_removed": removed,
                            "effect_values_after": values,
                            "stat_deltas": stat_deltas,
                            "raw": str(decision.get("raw", "")),
                        }
                    )
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_server_tooltip_and_carrier_stat_effect_transitions",
        "corpus_battle_dirs": len(battle_dirs),
        "carrier_battles": len(carrier_uids),
        "carrier_entities": carrier_entities,
        "carrier_creatures": _counter(carrier_creatures),
        "carrier_ability_sets": _counter(carrier_ability_sets),
        "same_owner_hero_counts": _counter(hero_same_owner_counts),
        "tooltip_battles": tooltip_battles,
        "tooltip_names": _counter(tooltip_names),
        "tooltip_descriptions": _counter(tooltip_descriptions),
        "tooltip_claim_shapes": [
            {"count": int(count), "claims": json.loads(raw)}
            for raw, count in tooltip_claim_shapes.most_common()
        ],
        "carrier_decisions": carrier_decisions,
        "action_types": _counter(action_types),
        "source_special_codes": _counter(source_special_codes),
        "effects_added": _counter(added_effects),
        "effects_removed": _counter(removed_effects),
        "effect_value_shapes": _counter(effect_value_shapes),
        "stat_delta_shapes": _counter(stat_delta_shapes),
        "action_stat_deltas": {
            action: _counter(counter) for action, counter in sorted(action_stat_deltas.items())
        },
        "init_examples": init_examples,
        "transition_examples": transition_examples,
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "Raging Blood is not assumed equivalent to generic Enraged/Rage mechanics. Exact support requires a "
            "carrier-specific server condition (including any hero/faction prerequisite), raw transition discriminator, "
            "and independently proven stat magnitudes/lifecycle. Same-owner hero presence is only context, not faction truth."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Raging Blood transition evidence.")
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
