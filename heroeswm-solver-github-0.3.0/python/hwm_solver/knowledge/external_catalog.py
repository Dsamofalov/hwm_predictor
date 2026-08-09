from __future__ import annotations

"""Parsers for user-supplied/reference HeroesWM creature catalog HTML.

The battle wire protocol remains authoritative for the abilities of a concrete
entity in a concrete battle.  These reference pages only enrich stable creature
IDs / ability codes with human-readable metadata and static base stats.

No historical state parser is used here.
"""

from dataclasses import dataclass, asdict
from html import unescape
from pathlib import Path
import json
import re
from typing import Iterable


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _text(fragment: str) -> str:
    s = _TAG_RE.sub(" ", fragment)
    s = unescape(s).replace("\xa0", " ").replace("\ufeff", " ")
    return _WS_RE.sub(" ", s).strip()


def _decode_daily_help(path: Path) -> str:
    raw = path.read_bytes()
    # The supplied snapshot declares windows-1251 but is actually UTF-8+BOM.
    # Try UTF-8 first and fall back to cp1251 for older snapshots.
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            text = raw.decode(enc)
            if "creature.php?id=" in text or "ability.php?name=" in text:
                return text.lstrip("\ufeff")
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace").lstrip("\ufeff")


def _decode_hwm_daily(path: Path) -> str:
    raw = path.read_bytes()
    # The HWM Daily snapshot is a real cp1251 document.
    for enc in ("cp1251", "utf-8-sig", "utf-8"):
        try:
            text = raw.decode(enc)
            if "army_info.php?name=" in text:
                return text
        except UnicodeDecodeError:
            pass
    return raw.decode("cp1251", errors="replace")


def normalize_name(name: str) -> str:
    return _WS_RE.sub(" ", name.replace("\xa0", " ").strip()).casefold().replace("ё", "е")


def _number(text: str) -> float | None:
    text = text.strip().replace(",", ".")
    if not text or text in {"-", "–", "—"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _damage(text: str) -> tuple[float | None, float | None]:
    text = text.strip().replace(",", ".")
    m = re.fullmatch(r"\s*([0-9.]+)\s*[-–—]\s*([0-9.]+)\s*", text)
    if not m:
        v = _number(text)
        return (v, v)
    return float(m.group(1)), float(m.group(2))


@dataclass(frozen=True)
class ReferenceAbility:
    code: str
    name: str
    url: str


@dataclass(frozen=True)
class ReferenceCreature:
    id: int
    name: str
    level: str
    faction: str
    attack: float | None
    defense: float | None
    min_damage: float | None
    max_damage: float | None
    hp: float | None
    speed: float | None
    initiative: float | None
    shots: float | None
    mana: float | None
    range: float | None
    experience: float | None
    icon: str
    abilities: tuple[ReferenceAbility, ...]
    hwm_name: str | None = None


def parse_daily_help_creatures(path: Path) -> list[ReferenceCreature]:
    text = _decode_daily_help(path)
    # The source HTML is intentionally old/malformed XHTML where <td> tags are
    # often not closed.  Splitting on the next <td> is more deterministic than
    # relying on browser-style tag repair.
    row_html = re.findall(r"<tr\s+align=['\"]center['\"]>(.*?)</tr>", text, flags=re.I | re.S)
    out: list[ReferenceCreature] = []
    seen: set[int] = set()
    for row in row_html:
        cm = re.search(r"creature\.php\?id=(\d+)[^>]*>(.*?)</a>", row, flags=re.I | re.S)
        if not cm:
            continue
        cid = int(cm.group(1))
        if cid in seen:
            continue
        seen.add(cid)
        name = _text(cm.group(2))
        cells = re.split(r"<td(?:\s[^>]*)?>", row, flags=re.I)[1:]
        cols = [_text(cell) for cell in cells]
        # icon,name,level,faction,attack,defence,damage,hp,speed,initiative,
        # shots,mana,range,experience,abilities
        if len(cols) < 15:
            cols += [""] * (15 - len(cols))
        dmin, dmax = _damage(cols[6])
        icon_match = re.search(r"img/creatures/icons/([^'\">]+)", row, flags=re.I)
        abilities: list[ReferenceAbility] = []
        for am in re.finditer(r"ability\.php\?name=([^'\"&#]+)[^>]*>(.*?)</a>", row, flags=re.I | re.S):
            code = unescape(am.group(1)).strip()
            abilities.append(
                ReferenceAbility(
                    code=code,
                    name=_text(am.group(2)),
                    url=f"https://daily-help.ru/ability.php?name={code}",
                )
            )
        out.append(
            ReferenceCreature(
                id=cid,
                name=name,
                level=cols[2],
                faction=cols[3],
                attack=_number(cols[4]),
                defense=_number(cols[5]),
                min_damage=dmin,
                max_damage=dmax,
                hp=_number(cols[7]),
                speed=_number(cols[8]),
                initiative=_number(cols[9]),
                shots=_number(cols[10]),
                mana=_number(cols[11]),
                range=_number(cols[12]),
                experience=_number(cols[13]),
                icon=icon_match.group(1) if icon_match else "",
                abilities=tuple(abilities),
            )
        )
    return out


def parse_hwm_daily_slugs(path: Path) -> dict[str, str]:
    text = _decode_hwm_daily(path)
    out: dict[str, str] = {}
    pat = re.compile(
        r"<a[^>]+title\s*=\s*['\"]([^'\"]+)['\"][^>]+href\s*=\s*['\"]https?://www\.heroeswm\.ru/army_info\.php\?name=([^'\"&#]+)['\"]",
        flags=re.I | re.S,
    )
    # Attribute order differs in some snapshots; handle href-before-title too.
    pat2 = re.compile(
        r"<a[^>]+href\s*=\s*['\"]https?://www\.heroeswm\.ru/army_info\.php\?name=([^'\"&#]+)['\"][^>]+title\s*=\s*['\"]([^'\"]+)['\"]",
        flags=re.I | re.S,
    )
    for name, slug in pat.findall(text):
        out[normalize_name(unescape(name))] = unescape(slug)
    for slug, name in pat2.findall(text):
        out[normalize_name(unescape(name))] = unescape(slug)
    return out


def build_reference_catalog(creatures_html: Path, hwm_daily_html: Path | None = None) -> dict:
    creatures = parse_daily_help_creatures(creatures_html)
    slugs = parse_hwm_daily_slugs(hwm_daily_html) if hwm_daily_html else {}
    ability_map: dict[str, dict] = {}
    rows: list[dict] = []
    slug_matches = 0
    for c in creatures:
        row = asdict(c)
        slug = slugs.get(normalize_name(c.name))
        if slug:
            row["hwm_name"] = slug
            slug_matches += 1
        else:
            row["hwm_name"] = None
        rows.append(row)
        for a in c.abilities:
            rec = ability_map.setdefault(
                a.code,
                {"code": a.code, "name": a.name, "url": a.url, "creature_ids": []},
            )
            rec["creature_ids"].append(c.id)

    payload = {
        "schema_version": 1,
        "source": "user-supplied Daily Help creature table + optional HWM Daily GL snapshot",
        "authority": "reference metadata only; battle wire protocol remains authoritative per entity",
        "creatures": rows,
        "abilities": [ability_map[k] for k in sorted(ability_map)],
        "coverage": {
            "creatures": len(rows),
            "abilities": len(ability_map),
            "hwm_name_slug_matches": slug_matches,
            "hwm_daily_slugs": len(slugs),
        },
    }
    return payload


def compare_with_raw(reference: dict, raw_catalog: dict) -> dict:
    ref = {int(c["id"]): c for c in reference.get("creatures", [])}
    raw = {int(c["id"]): c for c in raw_catalog.get("creatures", []) if not c.get("is_hero")}
    shared = sorted(set(ref) & set(raw))
    exact = 0
    reference_subset = 0
    conflicts: list[dict] = []
    for cid in shared:
        rset = {a["code"] for a in ref[cid].get("abilities", [])}
        wset = set(raw[cid].get("ability_tags", []))
        if rset == wset:
            exact += 1
        if rset <= wset:
            reference_subset += 1
        else:
            conflicts.append(
                {
                    "creature_id": cid,
                    "name": ref[cid].get("name", str(cid)),
                    "reference_only": sorted(rset - wset),
                    "raw_only": sorted(wset - rset),
                }
            )
    return {
        "raw_nonhero_creatures": len(raw),
        "reference_creatures": len(ref),
        "shared_creature_ids": len(shared),
        "exact_ability_sets": exact,
        "reference_ability_set_is_subset_of_raw": reference_subset,
        "reference_subset_rate": reference_subset / len(shared) if shared else 0.0,
        "raw_only_creature_ids": len(set(raw) - set(ref)),
        "reference_only_creature_ids": len(set(ref) - set(raw)),
        "ability_conflicts": conflicts,
    }


def write_reference_catalog(payload: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = [
    "ReferenceAbility",
    "ReferenceCreature",
    "parse_daily_help_creatures",
    "parse_hwm_daily_slugs",
    "build_reference_catalog",
    "compare_with_raw",
    "write_reference_catalog",
]
