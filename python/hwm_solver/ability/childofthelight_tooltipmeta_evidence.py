from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from hwm_solver.ability.childofthelight_spellwire_evidence import ABILITY, _spellbook_entries
from hwm_solver.protocol.replay import parse_initial_entities, parse_tooltips


LIGHT_MARKERS = ("свет", "light")
SCHOOL_MARKERS = ("школ", "school")


def _counter(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in counter.most_common()}


def _norm(value: object) -> str:
    return " ".join(str(value or "").split())


def _walk(value: Any, path: tuple[str, ...] = ()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, path + (f"[{index}]",))
    else:
        yield path, value


def analyze_tooltip_metadata(corpus: Path) -> dict:
    """Inventory decoded bm_tooltips without assuming a Light-spell taxonomy.

    The goal is to determine whether the server payload independently exposes spell-level
    metadata that can classify a spell as Light.  We therefore report raw top-level sections,
    exact key overlap with the same battle's embedded spellbook names, and textual occurrences
    of school/Light markers.  The Child-of-the-Light ability tooltip itself is separated from
    non-Child text so it cannot be used as circular evidence for individual spell identities.
    """
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    if not root.is_dir():
        raise FileNotFoundError(root)
    battle_dirs = [p for p in root.iterdir() if p.is_dir()]
    battle_dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))

    parse_errors: list[str] = []
    carrier_battles = 0
    carrier_battles_with_tooltips = 0
    top_sections: Counter[str] = Counter()
    section_types: Counter[str] = Counter()
    mapping_key_counts: Counter[str] = Counter()
    mapping_spellbook_overlap_counts: Counter[str] = Counter()
    overlap_spell_names: dict[str, Counter[str]] = defaultdict(Counter)
    overlap_value_types: dict[str, Counter[str]] = defaultdict(Counter)
    top_level_name_markers: Counter[str] = Counter()
    child_light_text_hits = 0
    non_child_light_text_hits = 0
    school_text_hits = 0
    non_child_school_light_hits = 0
    light_text_paths: Counter[str] = Counter()
    school_text_paths: Counter[str] = Counter()
    non_child_text_examples: list[dict] = []
    overlap_examples: list[dict] = []
    top_level_examples: list[dict] = []

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

        if not any(
            ABILITY in {str(x).lower() for x in entity.abilities}
            for entity in entities.values()
        ):
            continue
        carrier_battles += 1
        if not tooltips:
            continue
        carrier_battles_with_tooltips += 1

        spell_names = {
            str(entry["name"]).lower()
            for entity in entities.values()
            for entry in _spellbook_entries(entity.magic_blob)
            if str(entry.get("name", ""))
        }

        for section, value in tooltips.items():
            section = str(section)
            top_sections[section] += 1
            section_types[f"{section}:{type(value).__name__}"] += 1
            lowered_section = section.lower()
            if any(marker in lowered_section for marker in ("spell", "magic", "school", "заклин", "маг", "школ")):
                top_level_name_markers[section] += 1

            if isinstance(value, dict):
                mapping_key_counts[section] += len(value)
                for raw_key, raw_value in value.items():
                    key = str(raw_key).lower()
                    if key not in spell_names:
                        continue
                    mapping_spellbook_overlap_counts[section] += 1
                    overlap_spell_names[section][key] += 1
                    overlap_value_types[section][type(raw_value).__name__] += 1
                    if len(overlap_examples) < 80:
                        overlap_examples.append(
                            {
                                "battle_id": battle_dir.name,
                                "section": section,
                                "key": str(raw_key),
                                "value": raw_value,
                            }
                        )

        if len(top_level_examples) < 20:
            top_level_examples.append(
                {
                    "battle_id": battle_dir.name,
                    "sections": sorted(str(k) for k in tooltips),
                }
            )

        for path, raw_value in _walk(tooltips):
            if not isinstance(raw_value, (str, int, float, bool)):
                continue
            text = _norm(raw_value)
            if not text:
                continue
            lower = text.lower()
            path_text = "/".join(path)
            has_light = any(marker in lower for marker in LIGHT_MARKERS)
            has_school = any(marker in lower for marker in SCHOOL_MARKERS)
            is_child_path = ABILITY in {part.lower() for part in path}
            if has_light:
                light_text_paths[path_text] += 1
                if is_child_path:
                    child_light_text_hits += 1
                else:
                    non_child_light_text_hits += 1
            if has_school:
                school_text_hits += 1
                school_text_paths[path_text] += 1
            if has_light and has_school and not is_child_path:
                non_child_school_light_hits += 1
            if (has_light or has_school) and not is_child_path and len(non_child_text_examples) < 80:
                non_child_text_examples.append(
                    {
                        "battle_id": battle_dir.name,
                        "path": list(path),
                        "text": text[:500],
                        "has_light_marker": has_light,
                        "has_school_marker": has_school,
                    }
                )

    return {
        "ability": ABILITY,
        "evidence_scope": "decoded_bm_tooltips_spell_school_metadata_inventory",
        "corpus_battle_dirs": len(battle_dirs),
        "carrier_battles": carrier_battles,
        "carrier_battles_with_tooltips": carrier_battles_with_tooltips,
        "top_sections": _counter(top_sections),
        "section_types": _counter(section_types),
        "mapping_key_counts": _counter(mapping_key_counts),
        "mapping_spellbook_overlap_counts": _counter(mapping_spellbook_overlap_counts),
        "overlap_spell_names": {
            section: _counter(counter) for section, counter in sorted(overlap_spell_names.items())
        },
        "overlap_value_types": {
            section: _counter(counter) for section, counter in sorted(overlap_value_types.items())
        },
        "top_level_name_markers": _counter(top_level_name_markers),
        "child_light_text_hits": child_light_text_hits,
        "non_child_light_text_hits": non_child_light_text_hits,
        "school_text_hits": school_text_hits,
        "non_child_school_light_hits": non_child_school_light_hits,
        "light_text_paths": _counter(light_text_paths),
        "school_text_paths": _counter(school_text_paths),
        "non_child_text_examples": non_child_text_examples,
        "overlap_examples": overlap_examples,
        "top_level_examples": top_level_examples,
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "Only raw decoded bm_tooltips structure/text and exact key overlap with the same battle's server "
            "spellbook are reported. Child-of-the-Light's own tooltip is separated from non-Child text. "
            "No spell is classified as Light from its name, effect, or common game knowledge."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Child-of-Light decoded tooltip spell metadata.")
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = analyze_tooltip_metadata(args.corpus)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 2 if report["parse_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
