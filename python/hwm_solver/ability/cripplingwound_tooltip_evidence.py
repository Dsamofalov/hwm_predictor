from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from pathlib import Path

from hwm_solver.protocol.replay import parse_tooltips


ABILITY = "cripplingwound"


def _normalize(text: object) -> str:
    value = html.unescape(str(text or ""))
    return " ".join(value.split())


def _extract_claims(description: str) -> dict:
    """Extract only explicit numeric claims from the server-provided tooltip text.

    This deliberately does not infer a proc probability: the tooltip says there is a
    chance, but supplies no numeric probability. The exact consequence is recognized
    only when the normalized server wording contains all three numeric modifiers.
    """
    lower = description.lower()
    percentages = [int(x) for x in re.findall(r"(\d+)\s*%", description)]
    integers = [int(x) for x in re.findall(r"\b(\d+)\b", description)]
    speed_50 = 50 in percentages and any(token in lower for token in ("скорост", "speed"))
    initiative_30 = 30 in percentages and any(token in lower for token in ("инициатив", "initiative"))
    duration_2 = 2 in integers and any(token in lower for token in ("ход", "turn"))
    chance_without_numeric_probability = any(token in lower for token in ("шанс", "chance"))
    return {
        "percentages": percentages,
        "integers": integers,
        "explicit_speed_reduction_percent": 50 if speed_50 else None,
        "explicit_initiative_reduction_percent": 30 if initiative_30 else None,
        "explicit_duration_turns": 2 if duration_2 else None,
        "mentions_chance": chance_without_numeric_probability,
        "numeric_proc_probability_percent": None,
        "exact_consequence_recognized": bool(speed_50 and initiative_30 and duration_2),
    }


def analyze_corpus(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    if not root.is_dir():
        raise FileNotFoundError(root)

    battle_dirs = [p for p in root.iterdir() if p.is_dir()]
    battle_dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))

    names: Counter[str] = Counter()
    descriptions: Counter[str] = Counter()
    claim_shapes: Counter[str] = Counter()
    battles_with_tooltips = 0
    battles_with_ability_tooltip = 0
    parse_failures: list[str] = []
    examples: list[dict] = []

    for battle_dir in battle_dirs:
        init_path = battle_dir / "init.txt"
        if not init_path.exists():
            continue
        try:
            tooltips = parse_tooltips(init_path.read_text(encoding="utf-8", errors="replace"))
        except Exception as exc:
            parse_failures.append(f"{battle_dir.name}:{type(exc).__name__}:{exc}")
            continue
        if not tooltips:
            continue
        battles_with_tooltips += 1
        name = _normalize((tooltips.get("abil_names") or {}).get(ABILITY))
        description = _normalize((tooltips.get("abil_desc") or {}).get(ABILITY))
        if not name and not description:
            continue
        battles_with_ability_tooltip += 1
        if name:
            names[name] += 1
        if description:
            descriptions[description] += 1
            claims = _extract_claims(description)
            claim_shapes[json.dumps(claims, ensure_ascii=False, sort_keys=True)] += 1
            if len(examples) < 12:
                examples.append(
                    {
                        "battle_id": battle_dir.name,
                        "name": name,
                        "description": description,
                        "claims": claims,
                    }
                )

    parsed_claims = []
    for raw, count in claim_shapes.most_common():
        parsed_claims.append({"count": int(count), "claims": json.loads(raw)})

    exact_descriptions = sum(
        count
        for raw, count in claim_shapes.items()
        if json.loads(raw).get("exact_consequence_recognized")
    )
    chance_descriptions = sum(
        count
        for raw, count in claim_shapes.items()
        if json.loads(raw).get("mentions_chance")
    )

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_init_server_bm_tooltips",
        "corpus_battle_dirs": len(battle_dirs),
        "battles_with_tooltips": battles_with_tooltips,
        "battles_with_ability_tooltip": battles_with_ability_tooltip,
        "parse_failures": parse_failures,
        "names": dict(names.most_common()),
        "descriptions": dict(descriptions.most_common()),
        "claim_shapes": parsed_claims,
        "exact_consequence_descriptions": exact_descriptions,
        "chance_without_numeric_probability_descriptions": chance_descriptions,
        "derived_exact_consequence": {
            "speed_multiplier": 0.5 if exact_descriptions else None,
            "initiative_multiplier": 0.7 if exact_descriptions else None,
            "duration_turns": 2 if exact_descriptions else None,
        },
        "probability": {
            "numeric_probability_from_tooltip": None,
            "status": "unknown" if chance_descriptions else "not_observed",
        },
        "examples": examples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Crippling Wound server tooltip evidence.")
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = analyze_corpus(args.corpus)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 2 if report["parse_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
