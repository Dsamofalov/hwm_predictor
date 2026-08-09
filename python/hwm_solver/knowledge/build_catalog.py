from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from hwm_solver.protocol.replay import parse_commands, parse_initial_entities, parse_tooltips, parse_turn_records
from hwm_solver.knowledge.external_catalog import build_reference_catalog, compare_with_raw


def fnv1a32(text: str) -> int:
    h = 2166136261
    for b in text.encode("utf-8"):
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h or 1


def _mode(counter: Counter[str]) -> str:
    return counter.most_common(1)[0][0] if counter else ""


def build_catalog(corpus: Path, out: Path, reference_creatures_html: Path | None = None, hwm_daily_html: Path | None = None) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    battles = sorted((d for d in root.iterdir() if d.is_dir() and d.name.isdigit()), key=lambda d: int(d.name))

    creatures: dict[int, dict] = {}
    ability_names: dict[str, Counter[str]] = defaultdict(Counter)
    ability_desc: dict[str, Counter[str]] = defaultdict(Counter)
    perk_hints: dict[str, Counter[str]] = defaultdict(Counter)
    special_codes: Counter[str] = Counter()
    ability_tag_frequency: Counter[str] = Counter()

    for battle in battles:
        init = (battle / "init.txt").read_text(encoding="utf-8", errors="replace")
        entities, _ = parse_initial_entities(init)
        for e in entities.values():
            c = creatures.setdefault(
                e.creature_id,
                {
                    "id": e.creature_id,
                    "samples": 0,
                    "names": Counter(),
                    "sprites": Counter(),
                    "ability_tags": Counter(),
                    "max_hp": [], "min_damage": [], "max_damage": [], "speed": [],
                    "initiative": [], "attack": [], "defense": [], "shots": [],
                    "is_hero_samples": 0,
                },
            )
            c["samples"] += 1
            if e.name: c["names"][e.name] += 1
            if e.sprite: c["sprites"][e.sprite] += 1
            c["is_hero_samples"] += int(e.is_hero)
            for tag in e.abilities:
                c["ability_tags"][tag] += 1
                ability_tag_frequency[tag] += 1
            for key, value in (
                ("max_hp", e.max_hp), ("min_damage", e.min_damage), ("max_damage", e.max_damage),
                ("speed", e.speed), ("initiative", e.initiative), ("attack", e.attack),
                ("defense", e.defense), ("shots", e.shots),
            ):
                c[key].append(float(value))

        tt = parse_tooltips(init)
        for code, text in (tt.get("abil_names") or {}).items():
            ability_names[str(code)][html.unescape(str(text)).strip()] += 1
        for code, text in (tt.get("abil_desc") or {}).items():
            ability_desc[str(code)][html.unescape(str(text)).strip()] += 1
        for code, text in (tt.get("perk_hints") or {}).items():
            perk_hints[str(code)][html.unescape(str(text)).strip()] += 1

        turns = (battle / "turns0.txt").read_text(encoding="utf-8", errors="replace")
        for _, raw in parse_turn_records(turns):
            for cmd in parse_commands(raw):
                if cmd.opcode == "SPECIAL" and cmd.code:
                    special_codes[cmd.code] += 1

    creature_rows = []
    for cid, c in sorted(creatures.items()):
        tags = sorted(c["ability_tags"], key=lambda x: (-c["ability_tags"][x], x))
        row = {
            "id": cid,
            "name": _mode(c["names"]) or str(cid),
            "sprite": _mode(c["sprites"]),
            "samples": c["samples"],
            "is_hero": c["is_hero_samples"] > c["samples"] / 2,
            "ability_tags": tags,
            "ability_ids": [fnv1a32(t) for t in tags],
            "observed": {},
        }
        for key in ("max_hp", "min_damage", "max_damage", "speed", "initiative", "attack", "defense", "shots"):
            vals = c[key]
            row["observed"][key] = {"min": min(vals), "max": max(vals)} if vals else {"min": 0, "max": 0}
        creature_rows.append(row)

    all_ability_codes = sorted(set(ability_names) | set(ability_desc) | set(ability_tag_frequency))
    abilities = []
    for code in all_ability_codes:
        abilities.append(
            {
                "id": fnv1a32(code),
                "code": code,
                "name": _mode(ability_names[code]) or code,
                "description": _mode(ability_desc[code]),
                "observed_entity_tags": ability_tag_frequency[code],
            }
        )

    payload = {
        "schema_version": 3,
        "version": "raw-corpus-866+reference-v3",
        "source": "independently decoded init.txt/turns0.txt from supplied 866-battle corpus; old state parser not used",
        "authority": "raw battle entity tags are authoritative per battle; external HTML is descriptive/reference metadata only",
        "battles": len(battles),
        "creatures": creature_rows,
        "abilities": abilities,
        "perks": [
            {"code": code, "hint": _mode(hints)} for code, hints in sorted(perk_hints.items(), key=lambda x: int(x[0]) if x[0].isdigit() else x[0])
        ],
        "special_codes": [{"code": code, "samples": n} for code, n in special_codes.most_common()],
        "coverage": {
            "creature_ids": len(creature_rows),
            "ability_codes": len(abilities),
            "perk_codes": len(perk_hints),
            "special_codes": len(special_codes),
            "ability_tags_with_server_description": sum(1 for a in abilities if a["description"]),
        },
    }
    if reference_creatures_html is not None:
        reference = build_reference_catalog(reference_creatures_html, hwm_daily_html)
        comparison = compare_with_raw(reference, payload)
        payload["reference_catalog"] = {
            "source": reference.get("source"),
            "authority": reference.get("authority"),
            "coverage": reference.get("coverage", {}),
            "comparison": comparison,
        }
        ref_creatures = {int(c["id"]): c for c in reference.get("creatures", [])}
        ref_abilities = {a["code"]: a for a in reference.get("abilities", [])}
        for c in payload["creatures"]:
            r = ref_creatures.get(int(c["id"]))
            if r:
                c["reference"] = {k: v for k, v in r.items() if k != "abilities"}
                c["reference"]["abilities"] = r.get("abilities", [])
        existing_codes = {a["code"] for a in payload["abilities"]}
        for a in payload["abilities"]:
            r = ref_abilities.get(a["code"])
            if r:
                a["reference_name"] = r.get("name", "")
                a["reference_url"] = r.get("url", "")
                a["reference_creature_count"] = len(r.get("creature_ids", []))
        # Keep reference-only ability definitions for UI/mechanic registry discovery,
        # but never inject them into an observed entity's runtime tags.
        for code, r in sorted(ref_abilities.items()):
            if code in existing_codes:
                continue
            payload["abilities"].append({
                "id": fnv1a32(code), "code": code, "name": r.get("name", code),
                "description": "", "observed_entity_tags": 0,
                "reference_name": r.get("name", ""), "reference_url": r.get("url", ""),
                "reference_creature_count": len(r.get("creature_ids", [])),
                "reference_only": True,
            })

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Compact runtime/UI lookup. Tab-separated so localized names can contain commas safely.
    tsv = out.with_suffix(".tsv")
    with tsv.open("w", encoding="utf-8", newline="") as f:
        f.write("creature_id\tname\tsprite\tis_hero\tability_codes\n")
        for c in creature_rows:
            name = c["name"].replace("\t", " ").replace("\n", " ")
            sprite = c["sprite"].replace("\t", " ").replace("\n", " ")
            f.write(f"{c['id']}\t{name}\t{sprite}\t{int(c['is_hero'])}\t{'|'.join(c['ability_tags'])}\n")
    return payload["coverage"]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("corpus", type=Path)
    p.add_argument("--out", type=Path, default=Path("data/catalog/generated.json"))
    p.add_argument("--reference-creatures-html", type=Path)
    p.add_argument("--hwm-daily-html", type=Path)
    a = p.parse_args()
    print(json.dumps(build_catalog(a.corpus, a.out, a.reference_creatures_html, a.hwm_daily_html), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
