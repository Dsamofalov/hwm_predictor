from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, parse_initial_entities, parse_tooltips


ABILITY = "purge"
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


def _claims(description: str) -> dict:
    lower = description.lower()
    return {
        "percentages": [int(x) for x in re.findall(r"(\d+)\s*%", description)],
        "integers": [int(x) for x in re.findall(r"\b(\d+)\b", description)],
        "mentions_probability": any(x in lower for x in ("вероят", "шанс", "chance", "probab")),
        "mentions_positive": any(x in lower for x in ("позитив", "positive", "beneficial")),
        "mentions_remove": any(x in lower for x in ("снима", "remove", "dispel")),
        "mentions_attacked_target": any(x in lower for x in ("атакован", "attacked", "target")),
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
                    "abilities": sorted(abilities),
                }
            )
        if uids:
            carrier_uids[battle_dir.name] = uids
            if len(init_examples) < 25:
                init_examples.append(
                    {
                        "battle_id": battle_dir.name,
                        "carriers": rows,
                        "tooltip_name": name,
                        "tooltip_description": description,
                        "tooltip_claims": _claims(description) if description else {},
                    }
                )

    carrier_attacks = 0
    attack_action_types: Counter[str] = Counter()
    lethal_target_attacks = 0
    lethal_target_effect_cleanup: Counter[str] = Counter()
    attacks_target_with_effects = 0
    attacks_with_removed_effects = 0
    removed_effects: Counter[str] = Counter()
    removed_effect_turns_before: Counter[str] = Counter()
    same_target_special_codes: Counter[str] = Counter()
    code_removed_effects: dict[str, Counter[str]] = defaultdict(Counter)
    code_no_removal: Counter[str] = Counter()
    code_lethal_target: Counter[str] = Counter()
    removed_without_same_target_special = 0
    target_effect_count_before: Counter[int] = Counter()
    target_effect_count_removed: Counter[int] = Counter()
    positive_candidates: list[dict] = []
    negative_examples: list[dict] = []
    lethal_examples: list[dict] = []

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

                target_alive_after = bool(target_after and target_after.get("alive", False))
                effects_before = _effects(target_before)
                effects_after_raw = _effects(target_after)
                disappeared_raw = sorted(effects_before - effects_after_raw)
                removed = disappeared_raw if target_alive_after else []
                if effects_before:
                    attacks_target_with_effects += 1
                target_effect_count_before[len(effects_before)] += 1
                if target_alive_after:
                    target_effect_count_removed[len(removed)] += 1
                    if removed:
                        attacks_with_removed_effects += 1
                        for effect in removed:
                            removed_effects[effect] += 1
                            turns = dict(target_before.get("effect_turns") or {}).get(effect)
                            removed_effect_turns_before[f"{effect}:{turns}"] += 1
                else:
                    lethal_target_attacks += 1
                    for effect in disappeared_raw:
                        lethal_target_effect_cleanup[effect] += 1

                commands = parse_commands(str(decision.get("raw", "")))
                same_target_specials = [
                    c for c in commands
                    if c.opcode == "SPECIAL"
                    and c.actor_uid is not None and int(c.actor_uid) == actor_uid
                    and c.target_uid is not None and target_uid is not None
                    and int(c.target_uid) == target_uid
                ]
                codes = sorted({str(c.code) for c in same_target_specials})
                for code in codes:
                    same_target_special_codes[code] += 1
                    if not target_alive_after:
                        code_lethal_target[code] += 1
                    elif removed:
                        for effect in removed:
                            code_removed_effects[code][effect] += 1
                    else:
                        code_no_removal[code] += 1
                if target_alive_after and removed and not same_target_specials:
                    removed_without_same_target_special += 1

                row = {
                    "battle_id": str(decision.get("battle_id", battle_dir.name)),
                    "decision_index": int(decision.get("decision_index", -1)),
                    "server_turn": int(decision.get("server_turn", -1)),
                    "action_type": action_type,
                    "actor_uid": actor_uid,
                    "actor_creature_id": int(actor.get("creature_id", -1)),
                    "actor_abilities": sorted(_abilities(actor)),
                    "target_uid": target_uid,
                    "target_creature_id": int(target_before.get("creature_id", -1)),
                    "target_abilities": sorted(_abilities(target_before)),
                    "target_alive_after": target_alive_after,
                    "effects_before": sorted(effects_before),
                    "effects_after_raw": sorted(effects_after_raw),
                    "disappeared_effects_raw": disappeared_raw,
                    "purge_candidate_removed_effects": removed,
                    "effect_turns_before": dict(target_before.get("effect_turns") or {}),
                    "same_target_specials": [str(c.raw) for c in same_target_specials],
                    "raw": str(decision.get("raw", "")),
                }
                if target_alive_after and removed and len(positive_candidates) < 80:
                    positive_candidates.append(row)
                elif target_alive_after and not removed and effects_before and len(negative_examples) < 60:
                    negative_examples.append(row)
                elif not target_alive_after and effects_before and len(lethal_examples) < 40:
                    lethal_examples.append(row)
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_carrier_attack_target_effect_removal_nonlethal",
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
        "lethal_target_attacks": lethal_target_attacks,
        "lethal_target_effect_cleanup": _counter(lethal_target_effect_cleanup),
        "attacks_target_with_effects": attacks_target_with_effects,
        "attacks_with_removed_effects": attacks_with_removed_effects,
        "removed_effects": _counter(removed_effects),
        "removed_effect_turns_before": _counter(removed_effect_turns_before),
        "same_target_special_codes": _counter(same_target_special_codes),
        "code_removed_effects": {
            code: _counter(counter) for code, counter in sorted(code_removed_effects.items())
        },
        "code_no_removal": _counter(code_no_removal),
        "code_lethal_target": _counter(code_lethal_target),
        "removed_without_same_target_special": removed_without_same_target_special,
        "target_effect_count_before": _counter(target_effect_count_before),
        "target_effect_count_removed_nonlethal": _counter(target_effect_count_removed),
        "positive_candidates": positive_candidates,
        "negative_examples": negative_examples,
        "lethal_examples": lethal_examples,
        "init_examples": init_examples,
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "Lethal target cleanup is explicitly excluded from Purge candidates. An effect disappearing from a living "
            "target during a Purge-carrier attack is still not automatically Purge: damage can clear controls and other "
            "mechanics can remove statuses. No effect is labeled beneficial from its wire id. Exact proc labels require "
            "a carrier-specific raw discriminator plus a corpus/server mapping of which removed effects are positive and eligible."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Purge effect-removal evidence.")
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
