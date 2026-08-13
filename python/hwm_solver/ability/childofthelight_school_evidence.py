from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from hwm_solver.ability.childofthelight_spellwire_evidence import ABILITY, _spellbook_entries
from hwm_solver.protocol.replay import parse_initial_entities


def _counter(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in counter.most_common()}


def analyze_school_tokens(corpus: Path) -> dict:
    """Inventory raw spellbook school tokens in battles containing Child of the Light.

    No token is translated to a game-school name here.  This is intentionally a protocol
    corpus inventory so later semantic aliases can be backed by observed server data.
    """
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    if not root.is_dir():
        raise FileNotFoundError(root)
    battle_dirs = [p for p in root.iterdir() if p.is_dir()]
    battle_dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))

    carrier_battles = 0
    spellbook_actors = 0
    spellbook_entries = 0
    schools: Counter[str] = Counter()
    school_spell_names: dict[str, Counter[str]] = defaultdict(Counter)
    school_actor_ability_sets: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[str, list[dict]] = defaultdict(list)
    parse_errors: list[str] = []

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
        if not any(
            ABILITY in {str(x).lower() for x in entity.abilities}
            for entity in entities.values()
        ):
            continue
        carrier_battles += 1

        for entity in entities.values():
            entries = _spellbook_entries(entity.magic_blob)
            if not entries:
                continue
            spellbook_actors += 1
            ability_set = ",".join(sorted(str(x).lower() for x in entity.abilities)) or "<none>"
            for entry in entries:
                spellbook_entries += 1
                school = str(entry["school"])
                name = str(entry["name"])
                schools[school] += 1
                school_spell_names[school][name] += 1
                school_actor_ability_sets[school][ability_set] += 1
                if len(examples[school]) < 20:
                    examples[school].append(
                        {
                            "battle_id": battle_dir.name,
                            "actor_uid": int(entity.uid),
                            "actor_abilities": sorted(str(x).lower() for x in entity.abilities),
                            "entry": entry,
                        }
                    )

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_server_spellbook_school_token_inventory",
        "corpus_battle_dirs": len(battle_dirs),
        "carrier_battles": carrier_battles,
        "spellbook_actors": spellbook_actors,
        "spellbook_entries": spellbook_entries,
        "schools": _counter(schools),
        "school_spell_names": {
            school: _counter(counter) for school, counter in sorted(school_spell_names.items())
        },
        "school_actor_ability_sets": {
            school: _counter(counter) for school, counter in sorted(school_actor_ability_sets.items())
        },
        "examples": {school: rows for school, rows in sorted(examples.items())},
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "School strings are reported exactly as supplied by the server spellbook. "
            "This auditor does not translate a raw token to Light, Dark, Fire, Air, Water or Earth."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit raw Child-of-Light spellbook school tokens.")
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = analyze_school_tokens(args.corpus)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 2 if report["parse_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
