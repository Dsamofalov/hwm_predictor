from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from pathlib import Path

from hwm_solver.protocol.replay import parse_initial_entities, parse_tooltips


ABILITY = "auraoffirevul"


def _normalize(value: object) -> str:
    return " ".join(html.unescape(str(value or "")).split())


def _claims(description: str) -> dict:
    lower = description.lower()
    percentages = [int(x) for x in re.findall(r"(\d+)\s*%", description)]
    integers = [int(x) for x in re.findall(r"\b(\d+)\b", description)]
    return {
        "percentages": percentages,
        "integers": integers,
        "mentions_fire": any(token in lower for token in ("огн", "fire")),
        "mentions_damage": any(token in lower for token in ("урон", "damage")),
        "mentions_adjacent": any(token in lower for token in ("сосед", "рядом", "adjacent", "nearby")),
        "mentions_enemy": any(token in lower for token in ("враг", "противник", "enemy")),
        "mentions_ally": any(token in lower for token in ("союз", "ally")),
        "mentions_aura": any(token in lower for token in ("аур", "aura")),
    }


def analyze_corpus(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    if not root.is_dir():
        raise FileNotFoundError(root)

    battle_dirs = [p for p in root.iterdir() if p.is_dir()]
    battle_dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))

    parse_errors: list[str] = []
    carrier_entities = 0
    carrier_battles: set[str] = set()
    carrier_creatures: Counter[int] = Counter()
    carrier_ability_sets: Counter[str] = Counter()
    carrier_owners: Counter[int] = Counter()
    carrier_positions: Counter[str] = Counter()
    tooltip_battles = 0
    names: Counter[str] = Counter()
    descriptions: Counter[str] = Counter()
    claim_shapes: Counter[str] = Counter()
    examples: list[dict] = []

    for battle_dir in battle_dirs:
        init_path = battle_dir / "init.txt"
        if not init_path.exists():
            continue
        try:
            payload = init_path.read_text(encoding="utf-8", errors="replace")
            entities, warnings = parse_initial_entities(payload)
            tooltips = parse_tooltips(payload)
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:{type(exc).__name__}:{exc}")
            continue

        battle_carriers = []
        for entity in entities.values():
            abilities = {str(x).lower() for x in entity.abilities}
            if ABILITY not in abilities:
                continue
            carrier_entities += 1
            carrier_battles.add(battle_dir.name)
            carrier_creatures[int(entity.creature_id)] += 1
            carrier_owners[int(entity.owner)] += 1
            carrier_positions[f"{int(entity.x)},{int(entity.y)}"] += 1
            ability_set = ",".join(sorted(abilities)) or "<none>"
            carrier_ability_sets[ability_set] += 1
            battle_carriers.append(
                {
                    "uid": int(entity.uid),
                    "owner": int(entity.owner),
                    "creature_id": int(entity.creature_id),
                    "count": int(entity.count),
                    "x": int(entity.x),
                    "y": int(entity.y),
                    "abilities": sorted(abilities),
                }
            )

        name = _normalize((tooltips.get("abil_names") or {}).get(ABILITY))
        description = _normalize((tooltips.get("abil_desc") or {}).get(ABILITY))
        if name or description:
            tooltip_battles += 1
            if name:
                names[name] += 1
            if description:
                descriptions[description] += 1
                claim_shapes[json.dumps(_claims(description), ensure_ascii=False, sort_keys=True)] += 1

        if battle_carriers and len(examples) < 20:
            examples.append(
                {
                    "battle_id": battle_dir.name,
                    "carriers": battle_carriers,
                    "tooltip_name": name,
                    "tooltip_description": description,
                    "tooltip_claims": _claims(description) if description else {},
                    "parse_warnings": list(warnings),
                }
            )

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_init_server_tags_and_tooltips",
        "corpus_battle_dirs": len(battle_dirs),
        "parse_errors": parse_errors,
        "carrier_entities": carrier_entities,
        "carrier_battles": len(carrier_battles),
        "carrier_creatures": {str(k): int(v) for k, v in carrier_creatures.most_common()},
        "carrier_owners": {str(k): int(v) for k, v in carrier_owners.most_common()},
        "carrier_positions": dict(carrier_positions.most_common(30)),
        "carrier_ability_sets": dict(carrier_ability_sets.most_common()),
        "tooltip_battles": tooltip_battles,
        "tooltip_names": dict(names.most_common()),
        "tooltip_descriptions": dict(descriptions.most_common()),
        "tooltip_claim_shapes": [
            {"count": int(count), "claims": json.loads(raw)}
            for raw, count in claim_shapes.most_common()
        ],
        "examples": examples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Aura of Fire Vulnerability raw-init evidence.")
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
