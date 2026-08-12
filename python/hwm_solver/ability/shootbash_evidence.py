from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, parse_initial_entities, parse_tooltips


ABILITY = "shootbash"
MECHANICAL_TAGS = frozenset({"mechanical", "warmachine", "statix"})


def _normalize(value: object) -> str:
    return " ".join(html.unescape(str(value or "")).split())


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("abilities") or [])}


def _is_mechanical(entity: dict | None) -> bool:
    return bool(_abilities(entity) & MECHANICAL_TAGS)


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
        "mentions_chance": any(x in lower for x in ("шанс", "chance")),
        "mentions_ranged": any(x in lower for x in ("дистанц", "стрел", "ranged", "shoot")),
        "mentions_stun": any(x in lower for x in ("оглуш", "stun")),
        "mentions_retaliation": any(x in lower for x in ("ответн", "retaliat")),
        "mentions_initiative": any(x in lower for x in ("инициатив", "initiative")),
        "mentions_mechanical_exclusion": any(x in lower for x in ("механичес", "mechanical")),
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

    ranged_attacks = 0
    nonranged_attacks = 0
    target_mechanical_attacks = 0
    same_target_special_attacks = 0
    same_target_codes: Counter[str] = Counter()
    code_target_added_effects: dict[str, Counter[str]] = defaultdict(Counter)
    code_target_atb_delta: dict[str, Counter[str]] = defaultdict(Counter)
    code_target_mechanical: dict[str, Counter[str]] = defaultdict(Counter)
    actor_cocarriers: Counter[str] = Counter()
    retaliation_damage_after_primary = 0
    positive_examples: list[dict] = []
    negative_examples: list[dict] = []

    for battle_dir in battle_dirs:
        carriers = carrier_uids.get(battle_dir.name)
        if not carriers:
            continue
        try:
            for decision in iter_battle_decisions(battle_dir):
                actor_uid = int(decision.get("actor_uid", -1))
                if actor_uid not in carriers:
                    continue
                action_type = str(decision.get("action_type", ""))
                if action_type == "RANGED_ATTACK":
                    ranged_attacks += 1
                elif action_type in {"MELEE_ATTACK", "RANGED_ATTACK"}:
                    nonranged_attacks += 1
                else:
                    continue
                before = list(decision.get("state_before") or [])
                after = list(decision.get("state_after") or [])
                actor = _by_uid(before, actor_uid)
                target_raw = decision.get("target_uid")
                target_uid = int(target_raw) if target_raw is not None else None
                target_before = _by_uid(before, target_uid)
                target_after = _by_uid(after, target_uid)
                if actor:
                    interesting = sorted(_abilities(actor) & {"shootbash", "wardingarrows", "shieldbash", "stoning", "torpor"})
                    actor_cocarriers[",".join(interesting) or "<none>"] += 1
                target_is_mechanical = _is_mechanical(target_before)
                if target_is_mechanical:
                    target_mechanical_attacks += 1

                commands = parse_commands(str(decision.get("raw", "")))
                same_target = [
                    c for c in commands
                    if c.opcode == "SPECIAL"
                    and c.actor_uid is not None and int(c.actor_uid) == actor_uid
                    and c.target_uid is not None and target_uid is not None and int(c.target_uid) == target_uid
                ]
                primary_damage_indices = [
                    i for i, c in enumerate(commands)
                    if c.opcode == "DAMAGE" and c.actor_uid is not None and int(c.actor_uid) == actor_uid
                    and c.target_uid is not None and target_uid is not None and int(c.target_uid) == target_uid
                ]
                if primary_damage_indices and target_uid is not None:
                    first = primary_damage_indices[0]
                    if any(
                        c.opcode == "DAMAGE"
                        and c.actor_uid is not None and int(c.actor_uid) == target_uid
                        and c.target_uid is not None and int(c.target_uid) == actor_uid
                        for c in commands[first + 1 :]
                    ):
                        retaliation_damage_after_primary += 1

                before_effects = _effects(target_before)
                after_effects = _effects(target_after)
                added = sorted(after_effects - before_effects)
                atb_delta = None
                if target_before and target_after:
                    atb_delta = float(target_after.get("atb", 0.0)) - float(target_before.get("atb", 0.0))

                if action_type == "RANGED_ATTACK" and same_target:
                    same_target_special_attacks += 1
                    for c in same_target:
                        code = str(c.code)
                        same_target_codes[code] += 1
                        for effect in added:
                            code_target_added_effects[code][effect] += 1
                        code_target_atb_delta[code][f"{atb_delta:+.6g}" if atb_delta is not None else "None"] += 1
                        code_target_mechanical[code][str(target_is_mechanical)] += 1
                    if len(positive_examples) < 80:
                        positive_examples.append(
                            {
                                "battle_id": str(decision.get("battle_id", battle_dir.name)),
                                "decision_index": int(decision.get("decision_index", -1)),
                                "server_turn": int(decision.get("server_turn", -1)),
                                "actor_uid": actor_uid,
                                "actor_creature_id": int(actor.get("creature_id", -1)) if actor else None,
                                "actor_abilities": sorted(_abilities(actor)),
                                "target_uid": target_uid,
                                "target_creature_id": int(target_before.get("creature_id", -1)) if target_before else None,
                                "target_abilities": sorted(_abilities(target_before)),
                                "target_is_mechanical_context": target_is_mechanical,
                                "target_effects_added": added,
                                "target_atb_delta": atb_delta,
                                "same_target_specials": [str(c.raw) for c in same_target],
                                "raw": str(decision.get("raw", "")),
                            }
                        )
                elif action_type == "RANGED_ATTACK" and len(negative_examples) < 60:
                    negative_examples.append(
                        {
                            "battle_id": str(decision.get("battle_id", battle_dir.name)),
                            "decision_index": int(decision.get("decision_index", -1)),
                            "server_turn": int(decision.get("server_turn", -1)),
                            "actor_uid": actor_uid,
                            "actor_creature_id": int(actor.get("creature_id", -1)) if actor else None,
                            "actor_abilities": sorted(_abilities(actor)),
                            "target_uid": target_uid,
                            "target_abilities": sorted(_abilities(target_before)),
                            "target_is_mechanical_context": target_is_mechanical,
                            "target_atb_delta": atb_delta,
                            "raw": str(decision.get("raw", "")),
                        }
                    )
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_ranged_attack_same_target_stun_wire",
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
        "mechanical_context_tags": sorted(MECHANICAL_TAGS),
        "ranged_attacks": ranged_attacks,
        "nonranged_attack_rows": nonranged_attacks,
        "target_mechanical_attacks": target_mechanical_attacks,
        "same_target_special_attacks": same_target_special_attacks,
        "same_target_codes": _counter(same_target_codes),
        "code_target_added_effects": {
            code: _counter(counter) for code, counter in sorted(code_target_added_effects.items())
        },
        "code_target_atb_delta": {
            code: _counter(counter) for code, counter in sorted(code_target_atb_delta.items())
        },
        "code_target_mechanical": {
            code: _counter(counter) for code, counter in sorted(code_target_mechanical.items())
        },
        "actor_relevant_cocarriers": _counter(actor_cocarriers),
        "retaliation_damage_after_primary": retaliation_damage_after_primary,
        "positive_examples": positive_examples,
        "negative_examples": negative_examples,
        "init_examples": init_examples,
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "A same-target SPECIAL after a Shoot Bash ranged attack is not automatically the proc. Codes must be "
            "collision-audited against Warding Arrows, Shield Bash and other control abilities before hit-level proc "
            "labels or probability models are built. The mechanical/warmachine/statix grouping is diagnostic context "
            "only; mechanical exclusion and retaliation suppression still require separate raw/server proof."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Shoot Bash ranged stun evidence.")
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
