from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, parse_initial_entities, parse_tooltips


ABILITY = "childofthelight"


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
        "mentions_light": any(x in lower for x in ("свет", "light")),
        "mentions_spell": any(x in lower for x in ("заклин", "spell")),
        "mentions_damage_exclusion": any(x in lower for x in ("кроме наносящ", "except damage", "non-damage")),
        "mentions_resurrection_exclusion": any(x in lower for x in ("воскреш", "resurrect", "raise")),
        "mentions_expert": any(x in lower for x in ("искусн", "expert")),
        "mentions_also_applied": any(x in lower for x in ("и на это", "also", "also applied")),
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

    decisions_seen = 0
    carrier_targeted_specials = 0
    carrier_targeted_codes: Counter[str] = Counter()
    source_ability_sets: Counter[str] = Counter()
    code_copy_candidates: Counter[str] = Counter()
    code_solo_carrier_records: Counter[str] = Counter()
    copy_target_counts: Counter[str] = Counter()
    copy_value_equal: Counter[str] = Counter()
    copy_amount_equal: Counter[str] = Counter()
    carrier_added_effects: dict[str, Counter[str]] = defaultdict(Counter)
    copy_examples: list[dict] = []
    solo_examples: list[dict] = []

    for battle_dir in battle_dirs:
        carriers = carrier_uids.get(battle_dir.name)
        if not carriers:
            continue
        try:
            for decision in iter_battle_decisions(battle_dir):
                decisions_seen += 1
                before = list(decision.get("state_before") or [])
                after = list(decision.get("state_after") or [])
                by_uid = {int(e.get("uid", -1)): e for e in before}
                commands = parse_commands(str(decision.get("raw", "")))
                specials = [c for c in commands if c.opcode == "SPECIAL" and c.target_uid is not None]
                if not specials:
                    continue

                grouped: dict[tuple[int | None, str], list] = defaultdict(list)
                for command in specials:
                    source_uid = int(command.actor_uid) if command.actor_uid is not None else None
                    grouped[(source_uid, str(command.code))].append(command)

                for (source_uid, code), group in grouped.items():
                    carrier_records = [c for c in group if int(c.target_uid) in carriers]
                    if not carrier_records:
                        continue
                    source = by_uid.get(source_uid) if source_uid is not None else None
                    source_ability_sets[",".join(sorted(_abilities(source))) or "<none>"] += len(carrier_records)
                    carrier_targeted_specials += len(carrier_records)
                    carrier_targeted_codes[code] += len(carrier_records)
                    other_records = [c for c in group if int(c.target_uid) not in carriers]

                    for record in carrier_records:
                        carrier_uid = int(record.target_uid)
                        carrier_before = _by_uid(before, carrier_uid)
                        carrier_after = _by_uid(after, carrier_uid)
                        before_effects = _effects(carrier_before)
                        after_effects = _effects(carrier_after)
                        for effect in sorted(after_effects - before_effects):
                            carrier_added_effects[code][effect] += 1

                        if other_records:
                            code_copy_candidates[code] += 1
                            copy_target_counts[f"{code}:{1 + len(other_records)}"] += 1
                            same_value = all(c.value == record.value for c in other_records)
                            same_amount = all(c.amount == record.amount for c in other_records)
                            copy_value_equal[f"{code}:{same_value}"] += 1
                            copy_amount_equal[f"{code}:{same_amount}"] += 1
                            if len(copy_examples) < 80:
                                copy_examples.append(
                                    {
                                        "battle_id": str(decision.get("battle_id", battle_dir.name)),
                                        "decision_index": int(decision.get("decision_index", -1)),
                                        "server_turn": int(decision.get("server_turn", -1)),
                                        "action_type": str(decision.get("action_type", "")),
                                        "source_uid": source_uid,
                                        "source_owner": int(source.get("owner", -1)) if source else None,
                                        "source_abilities": sorted(_abilities(source)),
                                        "code": code,
                                        "carrier_uid": carrier_uid,
                                        "carrier_owner": int(carrier_before.get("owner", -1)) if carrier_before else None,
                                        "carrier_abilities": sorted(_abilities(carrier_before)),
                                        "carrier_special_raw": str(record.raw),
                                        "carrier_value": int(record.value) if record.value is not None else None,
                                        "carrier_amount": int(record.amount) if record.amount is not None else None,
                                        "carrier_effects_added": sorted(after_effects - before_effects),
                                        "other_targets": [
                                            {
                                                "uid": int(c.target_uid),
                                                "owner": int(by_uid[int(c.target_uid)].get("owner", -1)) if int(c.target_uid) in by_uid else None,
                                                "abilities": sorted(_abilities(by_uid.get(int(c.target_uid)))),
                                                "raw": str(c.raw),
                                                "value": int(c.value) if c.value is not None else None,
                                                "amount": int(c.amount) if c.amount is not None else None,
                                            }
                                            for c in other_records
                                        ],
                                        "same_value": same_value,
                                        "same_amount": same_amount,
                                        "raw": str(decision.get("raw", "")),
                                    }
                                )
                        else:
                            code_solo_carrier_records[code] += 1
                            if len(solo_examples) < 40:
                                solo_examples.append(
                                    {
                                        "battle_id": str(decision.get("battle_id", battle_dir.name)),
                                        "decision_index": int(decision.get("decision_index", -1)),
                                        "server_turn": int(decision.get("server_turn", -1)),
                                        "action_type": str(decision.get("action_type", "")),
                                        "source_uid": source_uid,
                                        "source_abilities": sorted(_abilities(source)),
                                        "code": code,
                                        "carrier_uid": carrier_uid,
                                        "carrier_special_raw": str(record.raw),
                                        "carrier_effects_added": sorted(after_effects - before_effects),
                                        "raw": str(decision.get("raw", "")),
                                    }
                                )
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_server_tooltip_and_same_caster_special_copy",
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
        "decisions_seen_in_carrier_battles": decisions_seen,
        "carrier_targeted_specials": carrier_targeted_specials,
        "carrier_targeted_codes": _counter(carrier_targeted_codes),
        "source_ability_sets": _counter(source_ability_sets),
        "code_copy_candidates": _counter(code_copy_candidates),
        "code_solo_carrier_records": _counter(code_solo_carrier_records),
        "copy_target_counts": _counter(copy_target_counts),
        "copy_value_equal": _counter(copy_value_equal),
        "copy_amount_equal": _counter(copy_amount_equal),
        "carrier_added_effects": {
            code: _counter(counter) for code, counter in sorted(carrier_added_effects.items())
        },
        "copy_examples": copy_examples,
        "solo_examples": solo_examples,
        "init_examples": init_examples,
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "Same-code SPECIAL records to a normal target and a Child-of-Light carrier are discovery candidates, "
            "not proof by themselves. Exact copy semantics require server-declared Light-school context or another "
            "unambiguous spell identity, exclusion of damage/resurrection, and matching observed consequence."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Child of Light spell-copy evidence.")
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
