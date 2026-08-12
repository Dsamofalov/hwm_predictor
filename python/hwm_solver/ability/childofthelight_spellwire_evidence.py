from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from hwm_solver.protocol.replay import (
    SPECIAL_DIRECT_DAMAGE_CODES,
    STATUS_WIRE_TO_BASE,
    iter_battle_decisions,
    parse_commands,
    parse_initial_entities,
)


ABILITY = "childofthelight"
LIGHT_SCHOOL = "light"


def _counter(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in counter.most_common()}


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("abilities") or [])}


def _by_uid(state: list[dict], uid: int | None) -> dict | None:
    if uid is None:
        return None
    return next((e for e in state if int(e.get("uid", -1)) == int(uid)), None)


def _effects(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x) for x in (entity.get("effects") or [])}


def _spellbook_entries(magic_blob: str) -> list[dict]:
    """Parse the raw seven-token server spellbook grammar, including declared school."""
    text = str(magic_blob or "").split("^", 1)[0]
    tok = text.split("-")
    out: list[dict] = []
    for i in range(0, len(tok) - 6, 7):
        name = tok[i]
        if not name:
            continue
        try:
            cost = int(float(tok[i + 1]))
            effect = float(tok[i + 3])
        except ValueError:
            continue
        out.append(
            {
                "name": name,
                "cost": cost,
                "level": tok[i + 2],
                "effect": effect,
                "param4": tok[i + 4],
                "param5": tok[i + 5],
                "school": tok[i + 6].lower(),
            }
        )
    return out


def _matching_light_status_entries(entries: list[dict], code: str, cost: int) -> list[dict]:
    base = STATUS_WIRE_TO_BASE.get(code)
    if not base or cost <= 0:
        return []
    names = {base, "m" + base}
    return [
        entry
        for entry in entries
        if entry["school"] == LIGHT_SCHOOL
        and str(entry["name"]) in names
        and cost <= int(entry["cost"])
    ]


def analyze_spellwire_corpus(corpus: Path) -> dict:
    """Separate Child-of-Light copy candidates from ordinary mass/status controls.

    This auditor intentionally stops before runtime semantics.  A candidate is considered
    single-target Light evidence only when the raw server spellbook of the actual source
    declares a Light spell whose canonical name matches the observed status wire, the
    raw status record carries a positive effective mana cost compatible with that entry,
    and the same decision/source/code also contains a non-carrier target.  Mass spellbook
    entries are retained as controls rather than counted as copy evidence.
    """
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    if not root.is_dir():
        raise FileNotFoundError(root)
    battle_dirs = [p for p in root.iterdir() if p.is_dir()]
    battle_dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))

    parse_errors: list[str] = []
    carrier_uids: dict[str, set[int]] = {}
    spellbooks: dict[tuple[str, int], list[dict]] = {}
    light_spellbook_actors = 0
    light_spell_names: Counter[str] = Counter()

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

        carriers = {
            int(entity.uid)
            for entity in entities.values()
            if ABILITY in {str(x).lower() for x in entity.abilities}
        }
        if not carriers:
            continue
        carrier_uids[battle_dir.name] = carriers

        for entity in entities.values():
            entries = _spellbook_entries(entity.magic_blob)
            spellbooks[(battle_dir.name, int(entity.uid))] = entries
            light_entries = [e for e in entries if e["school"] == LIGHT_SCHOOL]
            if light_entries:
                light_spellbook_actors += 1
                for entry in light_entries:
                    light_spell_names[str(entry["name"])] += 1

    status_groups_with_carrier = 0
    status_groups_positive_cost = 0
    status_groups_without_positive_cost = 0
    status_groups_without_source_spellbook = 0
    light_status_groups = 0
    light_single_groups = 0
    light_mass_groups = 0
    light_ambiguous_groups = 0
    light_single_copy_groups = 0
    light_single_direct_carrier_groups = 0
    light_mass_control_groups = 0
    light_single_copy_carrier_records = 0
    direct_damage_carrier_records = 0
    raise_dead_carrier_records = 0

    status_codes: Counter[str] = Counter()
    positive_costs: Counter[str] = Counter()
    light_match_codes: Counter[str] = Counter()
    single_copy_codes: Counter[str] = Counter()
    single_direct_codes: Counter[str] = Counter()
    mass_control_codes: Counter[str] = Counter()
    ambiguous_codes: Counter[str] = Counter()
    single_copy_source_ability_sets: Counter[str] = Counter()
    single_copy_carrier_ability_sets: Counter[str] = Counter()
    single_copy_effects: dict[str, Counter[str]] = defaultdict(Counter)
    single_copy_amounts: dict[str, Counter[int]] = defaultdict(Counter)
    single_copy_durations: dict[str, Counter[int]] = defaultdict(Counter)
    single_copy_other_target_counts: Counter[str] = Counter()
    direct_damage_codes: Counter[str] = Counter()

    single_copy_examples: list[dict] = []
    mass_control_examples: list[dict] = []
    ambiguous_examples: list[dict] = []

    for battle_dir in battle_dirs:
        carriers = carrier_uids.get(battle_dir.name)
        if not carriers:
            continue
        try:
            for decision in iter_battle_decisions(battle_dir):
                before = list(decision.get("state_before") or [])
                after = list(decision.get("state_after") or [])
                commands = parse_commands(str(decision.get("raw", "")))
                specials = [c for c in commands if c.opcode == "SPECIAL" and c.target_uid is not None]
                if not specials:
                    continue

                for command in specials:
                    if int(command.target_uid) not in carriers:
                        continue
                    if str(command.code) in SPECIAL_DIRECT_DAMAGE_CODES:
                        direct_damage_carrier_records += 1
                        direct_damage_codes[str(command.code)] += 1
                    elif str(command.code) == "rsd":
                        raise_dead_carrier_records += 1

                grouped: dict[tuple[int | None, str], list] = defaultdict(list)
                for command in specials:
                    grouped[(int(command.actor_uid) if command.actor_uid is not None else None, str(command.code))].append(command)

                for (source_uid, code), group in grouped.items():
                    if code not in STATUS_WIRE_TO_BASE:
                        continue
                    carrier_records = [c for c in group if int(c.target_uid) in carriers]
                    if not carrier_records:
                        continue
                    status_groups_with_carrier += 1
                    status_codes[code] += 1
                    other_records = [c for c in group if int(c.target_uid) not in carriers]

                    costs = sorted({int(c.value) for c in group if c.value is not None and c.value > 0})
                    if not costs:
                        status_groups_without_positive_cost += 1
                        continue
                    status_groups_positive_cost += 1
                    for cost in costs:
                        positive_costs[f"{code}:{cost}"] += 1

                    entries = spellbooks.get((battle_dir.name, source_uid)) if source_uid is not None else None
                    if entries is None:
                        status_groups_without_source_spellbook += 1
                        continue

                    matches: list[dict] = []
                    for cost in costs:
                        matches.extend(_matching_light_status_entries(entries, code, cost))
                    if not matches:
                        continue
                    light_status_groups += 1
                    light_match_codes[code] += 1
                    names = {str(e["name"]) for e in matches}
                    base = STATUS_WIRE_TO_BASE[code]
                    has_single = base in names
                    has_mass = "m" + base in names

                    source = _by_uid(before, source_uid)
                    base_row = {
                        "battle_id": str(decision.get("battle_id", battle_dir.name)),
                        "decision_index": int(decision.get("decision_index", -1)),
                        "server_turn": int(decision.get("server_turn", -1)),
                        "action_type": str(decision.get("action_type", "")),
                        "source_uid": source_uid,
                        "source_abilities": sorted(_abilities(source)),
                        "code": code,
                        "costs": costs,
                        "matching_light_entries": matches,
                        "carrier_uids": [int(c.target_uid) for c in carrier_records],
                        "other_target_uids": [int(c.target_uid) for c in other_records],
                        "raw": str(decision.get("raw", "")),
                    }

                    if has_single and has_mass:
                        light_ambiguous_groups += 1
                        ambiguous_codes[code] += 1
                        if len(ambiguous_examples) < 30:
                            ambiguous_examples.append(base_row)
                        continue
                    if has_mass:
                        light_mass_groups += 1
                        light_mass_control_groups += 1
                        mass_control_codes[code] += 1
                        if len(mass_control_examples) < 30:
                            mass_control_examples.append(base_row)
                        continue
                    if not has_single:
                        continue

                    light_single_groups += 1
                    if not other_records:
                        light_single_direct_carrier_groups += 1
                        single_direct_codes[code] += 1
                        continue

                    light_single_copy_groups += 1
                    single_copy_codes[code] += 1
                    single_copy_other_target_counts[f"{code}:{len(other_records)}"] += 1
                    single_copy_source_ability_sets[
                        ",".join(sorted(_abilities(source))) or "<none>"
                    ] += 1

                    for record in carrier_records:
                        light_single_copy_carrier_records += 1
                        carrier_uid = int(record.target_uid)
                        carrier_before = _by_uid(before, carrier_uid)
                        carrier_after = _by_uid(after, carrier_uid)
                        single_copy_carrier_ability_sets[
                            ",".join(sorted(_abilities(carrier_before))) or "<none>"
                        ] += 1
                        for effect in sorted(_effects(carrier_after) - _effects(carrier_before)):
                            single_copy_effects[code][effect] += 1
                        if record.amount is not None:
                            single_copy_amounts[code][int(record.amount)] += 1
                        if record.duration is not None:
                            single_copy_durations[code][int(record.duration)] += 1

                    if len(single_copy_examples) < 60:
                        row = dict(base_row)
                        row["carrier_records"] = [
                            {
                                "uid": int(c.target_uid),
                                "raw": str(c.raw),
                                "value": int(c.value) if c.value is not None else None,
                                "amount": int(c.amount) if c.amount is not None else None,
                                "duration": int(c.duration) if c.duration is not None else None,
                            }
                            for c in carrier_records
                        ]
                        row["other_records"] = [
                            {
                                "uid": int(c.target_uid),
                                "raw": str(c.raw),
                                "value": int(c.value) if c.value is not None else None,
                                "amount": int(c.amount) if c.amount is not None else None,
                                "duration": int(c.duration) if c.duration is not None else None,
                            }
                            for c in other_records
                        ]
                        single_copy_examples.append(row)
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "server_declared_light_spellbook_status_wire_discriminator",
        "corpus_battle_dirs": len(battle_dirs),
        "carrier_battles": len(carrier_uids),
        "light_spellbook_actors_in_carrier_battles": light_spellbook_actors,
        "light_spell_names": _counter(light_spell_names),
        "status_groups_with_carrier": status_groups_with_carrier,
        "status_groups_positive_cost": status_groups_positive_cost,
        "status_groups_without_positive_cost": status_groups_without_positive_cost,
        "status_groups_without_source_spellbook": status_groups_without_source_spellbook,
        "status_codes": _counter(status_codes),
        "positive_costs": _counter(positive_costs),
        "light_status_groups": light_status_groups,
        "light_match_codes": _counter(light_match_codes),
        "light_single_groups": light_single_groups,
        "light_mass_groups": light_mass_groups,
        "light_ambiguous_groups": light_ambiguous_groups,
        "light_single_copy_groups": light_single_copy_groups,
        "light_single_direct_carrier_groups": light_single_direct_carrier_groups,
        "light_mass_control_groups": light_mass_control_groups,
        "light_single_copy_carrier_records": light_single_copy_carrier_records,
        "single_copy_codes": _counter(single_copy_codes),
        "single_direct_codes": _counter(single_direct_codes),
        "mass_control_codes": _counter(mass_control_codes),
        "ambiguous_codes": _counter(ambiguous_codes),
        "single_copy_source_ability_sets": _counter(single_copy_source_ability_sets),
        "single_copy_carrier_ability_sets": _counter(single_copy_carrier_ability_sets),
        "single_copy_effects": {
            code: _counter(counter) for code, counter in sorted(single_copy_effects.items())
        },
        "single_copy_amounts": {
            code: _counter(counter) for code, counter in sorted(single_copy_amounts.items())
        },
        "single_copy_durations": {
            code: _counter(counter) for code, counter in sorted(single_copy_durations.items())
        },
        "single_copy_other_target_counts": _counter(single_copy_other_target_counts),
        "direct_damage_carrier_records": direct_damage_carrier_records,
        "direct_damage_codes": _counter(direct_damage_codes),
        "raise_dead_carrier_records": raise_dead_carrier_records,
        "single_copy_examples": single_copy_examples,
        "mass_control_examples": mass_control_examples,
        "ambiguous_examples": ambiguous_examples,
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "A single-target Light status group is evidence only when the actual source's raw server spellbook, "
            "wire status code and positive effective cost jointly identify a non-mass Light spell and the same "
            "decision also carries a non-carrier target. Mass Light spells are explicit controls, while direct "
            "damage and resurrection are excluded by the Child-of-Light server tooltip. No runtime copy rule is "
            "created by this auditor."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Child of Light spellbook/wire discrimination.")
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = analyze_spellwire_corpus(args.corpus)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 2 if report["parse_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
