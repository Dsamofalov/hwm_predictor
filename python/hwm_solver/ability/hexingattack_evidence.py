from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, parse_initial_entities, parse_tooltips


ABILITY = "hexingattack"
ATTACK_TYPES = {"MELEE_ATTACK", "RANGED_ATTACK"}


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
    names = {
        "curse": any(x in lower for x in ("проклят", "curse")),
        "slow": any(x in lower for x in ("замедлен", "slow")),
        "weakness": any(x in lower for x in ("слабост", "weakness")),
        "disrupting_ray": any(x in lower for x in ("разрушающ", "disrupting ray")),
    }
    return {
        "percentages": [int(x) for x in re.findall(r"(\d+)\s*%", description)],
        "integers": [int(x) for x in re.findall(r"\b(\d+)\b", description)],
        "mentions_probability": any(x in lower for x in ("вероят", "шанс", "chance", "probab")),
        "mentions_attack": any(x in lower for x in ("атак", "attack")),
        "mentions_expert": any(x in lower for x in ("искусн", "expert")),
        "named_effects": names,
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

    carrier_attacks = 0
    attack_action_types: Counter[str] = Counter()
    attack_creatures: Counter[int] = Counter()
    attacks_with_same_target_special = 0
    same_target_special_records = 0
    same_target_codes: Counter[str] = Counter()
    code_added_effects: dict[str, Counter[str]] = defaultdict(Counter)
    code_value_shapes: dict[str, Counter[str]] = defaultdict(Counter)
    code_amount_shapes: dict[str, Counter[str]] = defaultdict(Counter)
    other_special_codes: Counter[str] = Counter()
    wire_windows: Counter[str] = Counter()
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
                carrier_attacks += 1
                attack_action_types[action_type] += 1
                before = list(decision.get("state_before") or [])
                after = list(decision.get("state_after") or [])
                actor = _by_uid(before, actor_uid)
                if actor:
                    attack_creatures[int(actor.get("creature_id", -1))] += 1
                target_raw = decision.get("target_uid")
                target_uid = int(target_raw) if target_raw is not None else None
                target_before = _by_uid(before, target_uid) if target_uid is not None else None
                target_after = _by_uid(after, target_uid) if target_uid is not None else None
                commands = parse_commands(str(decision.get("raw", "")))
                specials = [c for c in commands if c.opcode == "SPECIAL"]
                same_target = [
                    c for c in specials
                    if c.actor_uid is not None
                    and int(c.actor_uid) == actor_uid
                    and c.target_uid is not None
                    and target_uid is not None
                    and int(c.target_uid) == target_uid
                ]
                for c in specials:
                    if c not in same_target:
                        other_special_codes[str(c.code)] += 1

                before_effects = _effects(target_before)
                after_effects = _effects(target_after)
                added = sorted(after_effects - before_effects)

                if same_target:
                    attacks_with_same_target_special += 1
                    same_target_special_records += len(same_target)
                    indices = {id(c): i for i, c in enumerate(commands)}
                    for c in same_target:
                        code = str(c.code)
                        same_target_codes[code] += 1
                        code_value_shapes[code][str(c.value)] += 1
                        code_amount_shapes[code][str(c.amount)] += 1
                        for effect in added:
                            code_added_effects[code][effect] += 1
                        index = indices[id(c)]
                        start = max(0, index - 2)
                        end = min(len(commands), index + 3)
                        window = "->".join(
                            x.opcode if x.opcode != "SPECIAL" else f"SPECIAL:{x.code}"
                            for x in commands[start:end]
                        )
                        wire_windows[f"{code}:{window}"] += 1
                    if len(positive_examples) < 80:
                        positive_examples.append(
                            {
                                "battle_id": str(decision.get("battle_id", battle_dir.name)),
                                "decision_index": int(decision.get("decision_index", -1)),
                                "server_turn": int(decision.get("server_turn", -1)),
                                "action_type": action_type,
                                "actor_uid": actor_uid,
                                "actor_creature_id": int(actor.get("creature_id", -1)) if actor else None,
                                "actor_abilities": sorted(_abilities(actor)),
                                "target_uid": target_uid,
                                "target_creature_id": int(target_before.get("creature_id", -1)) if target_before else None,
                                "target_abilities": sorted(_abilities(target_before)),
                                "target_effects_added": added,
                                "specials": [
                                    {
                                        "code": str(c.code),
                                        "raw": str(c.raw),
                                        "value": int(c.value) if c.value is not None else None,
                                        "amount": int(c.amount) if c.amount is not None else None,
                                    }
                                    for c in same_target
                                ],
                                "raw": str(decision.get("raw", "")),
                            }
                        )
                elif len(negative_examples) < 60:
                    negative_examples.append(
                        {
                            "battle_id": str(decision.get("battle_id", battle_dir.name)),
                            "decision_index": int(decision.get("decision_index", -1)),
                            "server_turn": int(decision.get("server_turn", -1)),
                            "action_type": action_type,
                            "actor_uid": actor_uid,
                            "actor_creature_id": int(actor.get("creature_id", -1)) if actor else None,
                            "actor_abilities": sorted(_abilities(actor)),
                            "target_uid": target_uid,
                            "target_abilities": sorted(_abilities(target_before)),
                            "target_effects_added": added,
                            "raw": str(decision.get("raw", "")),
                        }
                    )
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_carrier_attack_same_target_status_wire",
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
        "attack_creatures": _counter(attack_creatures),
        "attacks_with_same_target_special": attacks_with_same_target_special,
        "same_target_special_records": same_target_special_records,
        "same_target_codes": _counter(same_target_codes),
        "code_added_effects": {
            code: _counter(counter) for code, counter in sorted(code_added_effects.items())
        },
        "code_value_shapes": {
            code: _counter(counter) for code, counter in sorted(code_value_shapes.items())
        },
        "code_amount_shapes": {
            code: _counter(counter) for code, counter in sorted(code_amount_shapes.items())
        },
        "other_special_codes": _counter(other_special_codes),
        "wire_windows": _counter(wire_windows),
        "positive_examples": positive_examples,
        "negative_examples": negative_examples,
        "init_examples": init_examples,
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "A same-target SPECIAL emitted by a Hexing Attack carrier is not automatically the Hexing proc because "
            "co-carried abilities can emit their own status records. Exact proc labels require a code/consequence set "
            "whose collisions are audited outside Hexing Attack before probability modeling."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Hexing Attack status-wire evidence.")
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
