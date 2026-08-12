from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, parse_initial_entities, parse_tooltips


ABILITY = "venom"
ATTACK_TYPES = frozenset({"MELEE_ATTACK", "RANGED_ATTACK"})


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


def _by_uid(state: list[dict], uid: int | None) -> dict | None:
    if uid is None:
        return None
    return next((e for e in state if int(e.get("uid", -1)) == int(uid)), None)


def _total_hp(entity: dict | None) -> int:
    if not entity or not bool(entity.get("alive", False)):
        return 0
    count = int(entity.get("count", 0))
    max_hp = max(1, int(entity.get("max_hp", 1)))
    top_hp = int(entity.get("top_hp", 0)) or max_hp
    return max(0, (count - 1) * max_hp + top_hp) if count > 0 else 0


def _claims(description: str) -> dict:
    lower = description.lower()
    return {
        "percentages": [int(x) for x in re.findall(r"(\d+)\s*%", description)],
        "integers": [int(x) for x in re.findall(r"\b(\d+)\b", description)],
        "mentions_attack": any(x in lower for x in ("атак", "attack")),
        "mentions_poison": any(x in lower for x in ("яд", "отрав", "poison", "venom")),
        "mentions_three_turns": bool(re.search(r"\b3\b", description)) and any(x in lower for x in ("ход", "turn")),
        "mentions_five_per_creature": bool(re.search(r"\b5\b", description)) and any(x in lower for x in ("существ", "creature")),
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
            rows.append({
                "uid": uid,
                "owner": int(entity.owner),
                "creature_id": int(entity.creature_id),
                "count": int(entity.count),
                "abilities": sorted(abilities),
            })
        if uids:
            carrier_uids[battle_dir.name] = uids
            if len(init_examples) < 25:
                init_examples.append({
                    "battle_id": battle_dir.name,
                    "carriers": rows,
                    "tooltip_name": name,
                    "tooltip_description": description,
                    "tooltip_claims": _claims(description) if description else {},
                })

    carrier_attacks = 0
    attack_action_types: Counter[str] = Counter()
    same_target_special_codes: Counter[str] = Counter()
    attacks_with_added_effect = 0
    added_effects: Counter[str] = Counter()
    added_effect_turns: Counter[str] = Counter()
    added_effect_values: Counter[str] = Counter()
    candidate_effect_ids: set[str] = set()
    positive_examples: list[dict] = []
    negative_examples: list[dict] = []

    for battle_dir in battle_dirs:
        carriers = carrier_uids.get(battle_dir.name)
        if not carriers:
            continue
        try:
            for decision in iter_battle_decisions(battle_dir):
                actor_uid = int(decision.get("actor_uid", -1))
                action_type = str(decision.get("action_type", ""))
                if actor_uid not in carriers or action_type not in ATTACK_TYPES:
                    continue
                before = list(decision.get("state_before") or [])
                after = list(decision.get("state_after") or [])
                actor = _by_uid(before, actor_uid)
                target_raw = decision.get("target_uid")
                target_uid = int(target_raw) if target_raw is not None else None
                target_before = _by_uid(before, target_uid)
                target_after = _by_uid(after, target_uid)
                if not actor or not target_before:
                    continue
                carrier_attacks += 1
                attack_action_types[action_type] += 1
                commands = parse_commands(str(decision.get("raw", "")))
                same_target_specials = [
                    command
                    for command in commands
                    if command.opcode == "SPECIAL"
                    and command.actor_uid is not None and int(command.actor_uid) == actor_uid
                    and command.target_uid is not None and target_uid is not None
                    and int(command.target_uid) == target_uid
                ]
                for command in same_target_specials:
                    same_target_special_codes[str(command.code)] += 1

                before_effects = _effects(target_before)
                after_effects = _effects(target_after)
                added = sorted(after_effects - before_effects)
                if added:
                    attacks_with_added_effect += 1
                    for effect in added:
                        candidate_effect_ids.add(effect)
                        added_effects[effect] += 1
                        turns = dict(target_after.get("effect_turns") or {}).get(effect) if target_after else None
                        value = dict(target_after.get("effect_values") or {}).get(effect) if target_after else None
                        added_effect_turns[f"{effect}:{turns}"] += 1
                        added_effect_values[f"{effect}:{value}"] += 1
                row = {
                    "battle_id": str(decision.get("battle_id", battle_dir.name)),
                    "decision_index": int(decision.get("decision_index", -1)),
                    "server_turn": int(decision.get("server_turn", -1)),
                    "action_type": action_type,
                    "actor_uid": actor_uid,
                    "actor_creature_id": int(actor.get("creature_id", -1)),
                    "actor_count": int(actor.get("count", 0)),
                    "actor_abilities": sorted(_abilities(actor)),
                    "target_uid": target_uid,
                    "target_creature_id": int(target_before.get("creature_id", -1)),
                    "target_abilities": sorted(_abilities(target_before)),
                    "effects_added": added,
                    "effect_turns_after": dict(target_after.get("effect_turns") or {}) if target_after else {},
                    "effect_values_after": dict(target_after.get("effect_values") or {}) if target_after else {},
                    "same_target_specials": [str(c.raw) for c in same_target_specials],
                    "raw": str(decision.get("raw", "")),
                }
                if added and len(positive_examples) < 80:
                    positive_examples.append(row)
                elif not added and len(negative_examples) < 60:
                    negative_examples.append(row)
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:attack:{type(exc).__name__}:{exc}")

    lifecycle_rows = 0
    lifecycle_actor_turns = 0
    lifecycle_hp_loss: Counter[str] = Counter()
    lifecycle_turn_delta: Counter[str] = Counter()
    lifecycle_direct_damage_sum: Counter[str] = Counter()
    lifecycle_examples: list[dict] = []

    if candidate_effect_ids:
        for battle_dir in battle_dirs:
            if battle_dir.name not in carrier_uids:
                continue
            try:
                for decision in iter_battle_decisions(battle_dir):
                    before = list(decision.get("state_before") or [])
                    after = list(decision.get("state_after") or [])
                    actor_uid = int(decision.get("actor_uid", -1))
                    commands = parse_commands(str(decision.get("raw", "")))
                    for entity_before in before:
                        live_candidates = sorted(_effects(entity_before) & candidate_effect_ids)
                        if not live_candidates or not bool(entity_before.get("alive", False)):
                            continue
                        uid = int(entity_before.get("uid", -1))
                        entity_after = _by_uid(after, uid)
                        if entity_after is None:
                            continue
                        lifecycle_rows += 1
                        if uid == actor_uid:
                            lifecycle_actor_turns += 1
                        hp_before = _total_hp(entity_before)
                        hp_after = _total_hp(entity_after)
                        hp_loss = max(0, hp_before - hp_after)
                        direct_damage = sum(
                            int(command.amount or 0)
                            for command in commands
                            if command.opcode == "DAMAGE"
                            and command.target_uid is not None and int(command.target_uid) == uid
                        )
                        for effect in live_candidates:
                            turns_before = dict(entity_before.get("effect_turns") or {}).get(effect)
                            turns_after = dict(entity_after.get("effect_turns") or {}).get(effect)
                            lifecycle_hp_loss[f"{effect}:{hp_loss}"] += 1
                            lifecycle_direct_damage_sum[f"{effect}:{direct_damage}"] += 1
                            lifecycle_turn_delta[f"{effect}:{turns_before}->{turns_after}"] += 1
                        if len(lifecycle_examples) < 100:
                            lifecycle_examples.append({
                                "battle_id": str(decision.get("battle_id", battle_dir.name)),
                                "decision_index": int(decision.get("decision_index", -1)),
                                "server_turn": int(decision.get("server_turn", -1)),
                                "active_actor_uid": actor_uid,
                                "affected_uid": uid,
                                "affected_is_active_actor": uid == actor_uid,
                                "candidate_effects": live_candidates,
                                "effect_turns_before": dict(entity_before.get("effect_turns") or {}),
                                "effect_turns_after": dict(entity_after.get("effect_turns") or {}),
                                "hp_before": hp_before,
                                "hp_after": hp_after,
                                "hp_loss": hp_loss,
                                "direct_damage_sum": direct_damage,
                                "raw": str(decision.get("raw", "")),
                            })
            except Exception as exc:
                parse_errors.append(f"{battle_dir.name}:lifecycle:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_attack_proc_candidate_and_effect_lifecycle",
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
        "carrier_attacks": carrier_attacks,
        "attack_action_types": _counter(attack_action_types),
        "same_target_special_codes": _counter(same_target_special_codes),
        "attacks_with_added_effect": attacks_with_added_effect,
        "candidate_effect_ids": sorted(candidate_effect_ids),
        "added_effects": _counter(added_effects),
        "added_effect_turns": _counter(added_effect_turns),
        "added_effect_values": _counter(added_effect_values),
        "positive_examples": positive_examples,
        "negative_examples": negative_examples,
        "lifecycle": {
            "rows": lifecycle_rows,
            "affected_actor_turn_rows": lifecycle_actor_turns,
            "hp_loss": _counter(lifecycle_hp_loss),
            "direct_damage_sum": _counter(lifecycle_direct_damage_sum),
            "turn_delta": _counter(lifecycle_turn_delta),
            "examples": lifecycle_examples,
        },
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "Effects added by a Venom carrier attack are discovery candidates, not automatically poison because co-carried "
            "abilities may add effects. Lifecycle HP loss is reported alongside raw direct DAMAGE so poison ticks can be "
            "separated from ordinary hits. Exact 3-turn and 5-per-carrier-creature semantics require a unique effect/wire "
            "mapping and corpus-perfect lifecycle; no trigger probability is assumed."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Venom proc and DoT lifecycle evidence.")
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
