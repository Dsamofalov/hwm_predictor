from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from hwm_solver.ability.auraoffirevul_applicability_evidence import (
    ABILITY,
    FIRE_SCHOOL,
    _abilities,
    _by_uid,
    _spellbook_entries,
)
from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, parse_initial_entities


def _counter(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in counter.most_common()}


def _decision_mana(state: list[dict], actor_uid: int) -> int | None:
    actor = _by_uid(state, actor_uid)
    if actor is None:
        return None
    return int(actor.get("mana", 0))


def _special_numeric_shape(raw: str) -> dict:
    numeric = raw[4:] if len(raw) >= 4 else ""
    out = {
        "numeric": numeric,
        "numeric_len": len(numeric),
        "all_digits": numeric.isdigit(),
        "field_actor": None,
        "field_target": None,
        "field_param3": None,
        "field_amount6": None,
    }
    if len(numeric) == 15 and numeric.isdigit():
        out.update(
            {
                "field_actor": int(numeric[:3]),
                "field_target": int(numeric[3:6]),
                "field_param3": int(numeric[6:9]),
                "field_amount6": int(numeric[9:15]),
            }
        )
    return out


def analyze_corpus(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    if not root.is_dir():
        raise FileNotFoundError(root)

    battle_dirs = [p for p in root.iterdir() if p.is_dir()]
    battle_dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))

    parse_errors: list[str] = []
    aura_battles: set[str] = set()
    fire_spellbook_battles: set[str] = set()
    all_spellbooks: dict[tuple[str, int], list[dict]] = {}
    fire_spellbooks: dict[tuple[str, int], list[dict]] = {}

    for battle_dir in battle_dirs:
        init_path = battle_dir / "init.txt"
        turns_path = battle_dir / "turns0.txt"
        if not init_path.exists() or not turns_path.exists():
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
        if any(ABILITY in {str(x).lower() for x in e.abilities} for e in entities.values()):
            aura_battles.add(battle_dir.name)
        for entity in entities.values():
            entries = _spellbook_entries(entity.magic_blob)
            fire_entries = [e for e in entries if e["school"] == FIRE_SCHOOL]
            if not fire_entries:
                continue
            key = (battle_dir.name, int(entity.uid))
            all_spellbooks[key] = entries
            fire_spellbooks[key] = fire_entries
            fire_spellbook_battles.add(battle_dir.name)

    special_codes: Counter[str] = Counter()
    code_fire_spell_names: dict[str, Counter[str]] = defaultdict(Counter)
    code_all_spell_names: dict[str, Counter[str]] = defaultdict(Counter)
    code_mana_spent: dict[str, Counter[int]] = defaultdict(Counter)
    code_damage_hit_counts: dict[str, Counter[int]] = defaultdict(Counter)
    mana_spend_decisions = 0
    mana_spend_special_codes: Counter[str] = Counter()
    mana_spend_fire_candidates: Counter[str] = Counter()
    focus_examples: dict[str, list[dict]] = defaultdict(list)
    mana_examples: list[dict] = []

    for battle_dir in battle_dirs:
        if battle_dir.name not in fire_spellbook_battles:
            continue
        try:
            for decision in iter_battle_decisions(battle_dir):
                battle_id = str(decision.get("battle_id", battle_dir.name))
                actor_uid = int(decision.get("actor_uid", -1))
                key = (battle_id, actor_uid)
                fire_entries = fire_spellbooks.get(key)
                if not fire_entries:
                    continue
                all_entries = all_spellbooks[key]
                before = list(decision.get("state_before") or [])
                after = list(decision.get("state_after") or [])
                before_mana = _decision_mana(before, actor_uid)
                after_mana = _decision_mana(after, actor_uid)
                mana_spent = None
                if before_mana is not None and after_mana is not None:
                    mana_spent = before_mana - after_mana

                commands = parse_commands(str(decision.get("raw", "")))
                specials = [
                    c for c in commands
                    if c.opcode == "SPECIAL" and c.actor_uid == actor_uid
                ]
                damages = [
                    c for c in commands
                    if c.opcode == "DAMAGE" and c.actor_uid == actor_uid and c.target_uid is not None
                ]

                if mana_spent is not None and mana_spent > 0:
                    mana_spend_decisions += 1
                    for c in specials:
                        mana_spend_special_codes[str(c.code)] += 1
                    for entry in fire_entries:
                        if mana_spent <= int(entry["cost"]):
                            mana_spend_fire_candidates[str(entry["name"])] += 1
                    if len(mana_examples) < 80:
                        mana_examples.append(
                            {
                                "battle_id": battle_id,
                                "decision_index": int(decision.get("decision_index", -1)),
                                "server_turn": int(decision.get("server_turn", -1)),
                                "action_type": str(decision.get("action_type", "")),
                                "actor_uid": actor_uid,
                                "actor_abilities": sorted(_abilities(_by_uid(before, actor_uid))),
                                "before_mana": before_mana,
                                "after_mana": after_mana,
                                "mana_spent": mana_spent,
                                "special_codes": [str(c.code) for c in specials],
                                "damage": [
                                    {
                                        "target_uid": int(c.target_uid),
                                        "amount": int(c.amount or 0),
                                    }
                                    for c in damages
                                ],
                                "fire_spellbook": fire_entries,
                                "all_spellbook": all_entries,
                                "raw": str(decision.get("raw", "")),
                            }
                        )

                for command in specials:
                    code = str(command.code)
                    special_codes[code] += 1
                    for entry in fire_entries:
                        code_fire_spell_names[code][str(entry["name"])] += 1
                    for entry in all_entries:
                        code_all_spell_names[code][str(entry["name"])] += 1
                    if mana_spent is not None:
                        code_mana_spent[code][int(mana_spent)] += 1
                    code_damage_hit_counts[code][len(damages)] += 1

                    if code == "fbl":
                        shape = _special_numeric_shape(str(command.raw))
                        target = _by_uid(before, shape["field_target"])
                        focus_examples[code].append(
                            {
                                "battle_id": battle_id,
                                "decision_index": int(decision.get("decision_index", -1)),
                                "server_turn": int(decision.get("server_turn", -1)),
                                "action_type": str(decision.get("action_type", "")),
                                "actor_uid": actor_uid,
                                "actor_abilities": sorted(_abilities(_by_uid(before, actor_uid))),
                                "before_mana": before_mana,
                                "after_mana": after_mana,
                                "mana_spent": mana_spent,
                                "special_raw": str(command.raw),
                                "special_shape": shape,
                                "target_guess_exists": target is not None,
                                "target_guess_owner": int(target.get("owner", -1)) if target else None,
                                "damage": [
                                    {
                                        "target_uid": int(c.target_uid),
                                        "amount": int(c.amount or 0),
                                    }
                                    for c in damages
                                ],
                                "fire_spellbook": fire_entries,
                                "all_spellbook": all_entries,
                                "raw": str(decision.get("raw", "")),
                            }
                        )
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    fbl_examples = list(focus_examples.get("fbl", []))
    fbl_fire_names: Counter[str] = Counter()
    fbl_spellbook_unique = 0
    fbl_mana_compatible = 0
    fbl_damage_decisions = 0
    for row in fbl_examples:
        fire_names = {str(e["name"]) for e in row["fire_spellbook"]}
        for name in fire_names:
            fbl_fire_names[name] += 1
        if fire_names == {"fireball"}:
            fbl_spellbook_unique += 1
        spent = row.get("mana_spent")
        if spent is not None and spent > 0 and any(
            str(e["name"]) == "fireball" and spent <= int(e["cost"])
            for e in row["fire_spellbook"]
        ):
            fbl_mana_compatible += 1
        if row["damage"]:
            fbl_damage_decisions += 1

    return {
        "ability": ABILITY,
        "evidence_scope": "whole_corpus_raw_fire_spellbook_to_special_wire",
        "corpus_battle_dirs": len(battle_dirs),
        "aura_battles": len(aura_battles),
        "fire_spellbook_battles": len(fire_spellbook_battles),
        "fire_spellbook_actors": len(fire_spellbooks),
        "special_codes": _counter(special_codes),
        "code_fire_spell_names": {
            code: _counter(counter) for code, counter in sorted(code_fire_spell_names.items())
        },
        "code_all_spell_names": {
            code: _counter(counter) for code, counter in sorted(code_all_spell_names.items())
        },
        "code_mana_spent": {
            code: _counter(counter) for code, counter in sorted(code_mana_spent.items())
        },
        "code_damage_hit_counts": {
            code: _counter(counter) for code, counter in sorted(code_damage_hit_counts.items())
        },
        "mana_spend_decisions": mana_spend_decisions,
        "mana_spend_special_codes": _counter(mana_spend_special_codes),
        "mana_spend_fire_candidates": _counter(mana_spend_fire_candidates),
        "fbl": {
            "records": int(special_codes.get("fbl", 0)),
            "examples_captured": len(fbl_examples),
            "fire_spell_names": _counter(fbl_fire_names),
            "unique_fireball_spellbook_examples": fbl_spellbook_unique,
            "mana_compatible_fireball_examples": fbl_mana_compatible,
            "damage_decisions": fbl_damage_decisions,
            "examples": fbl_examples,
        },
        "mana_examples": mana_examples,
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "A wire-code/name mapping is exact only when raw SPECIAL shape, server spellbook, "
            "mana transition, target relation and damage consequence jointly exclude alternative spells. "
            "The code abbreviation alone is not evidence."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Aura of Fire Vulnerability Fire-spell wire evidence.")
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
