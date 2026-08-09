from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from hwm_solver.protocol.replay import parse_commands, parse_initial_entities, parse_turn_records

SPELL_RE = re.compile(
    r"([a-z_][a-z0-9_]*)-"
    r"(-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)-"
    r"(-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)-([a-z_]+)-"
)

# These are candidate wire/name associations, NOT assumed truth.  The report below proves
# or rejects each one using only the new raw corpus + the authoritative spellbook embedded
# in the same M-record. Old parsed state dumps are never read.
CANDIDATES = {
    "fst": ("fast", "FRIENDLY"),
    "slw": ("slow", "ENEMY"),
    "bls": ("bless", "FRIENDLY"),
    "crs": ("curse", "ENEMY"),
    "stn": ("stoneskin", "FRIENDLY"),
    "dfm": ("deflect_missile", "FRIENDLY"),
    "rgm": ("righteous_might", "FRIENDLY"),
    "cnf": ("confusion", "ENEMY"),
}

@dataclass(frozen=True)
class Spell:
    name: str
    mana_cost: int
    level: int
    effect: float
    secondary: float
    persistent: int
    school: str


def parse_spellbook(blob: str) -> dict[str, Spell]:
    # Text after ^ is the modifier blob, not the selectable spellbook.
    text = blob.split("^", 1)[0]
    out: dict[str, Spell] = {}
    for m in SPELL_RE.finditer(text):
        name = m.group(1)
        try:
            out.setdefault(name, Spell(
                name=name,
                mana_cost=int(float(m.group(2))),
                level=int(float(m.group(3))),
                effect=float(m.group(4)),
                secondary=float(m.group(5)),
                persistent=int(float(m.group(6))),
                school=m.group(7),
            ))
        except ValueError:
            continue
    return out


def _special_numeric(raw: str) -> str:
    return raw[4:] if raw.startswith("S") and len(raw) >= 4 else ""


def analyze(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    battle_dirs = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: int(p.name))
    stats = {
        code: {
            "spell": spell,
            "expected_target_side": side,
            "actions": 0,
            "clean_actions": 0,
            "records": 0,
            "clean_records": 0,
            "actor_has_spell": 0,
            "clean_actor_has_spell": 0,
            "target_known": 0,
            "target_side_matches": 0,
            "clean_target_known": 0,
            "clean_target_side_matches": 0,
            "payload15": 0,
            "clean_payload15": 0,
            "magnitude_matches_spellbook": 0,
            "clean_magnitude_matches_spellbook": 0,
            "duration_matches_power_x100": 0,
            "clean_duration_matches_power_x100": 0,
            "first_flag_counts": Counter(),
            "duration_raw_counts": Counter(),
            "magnitude_counts": Counter(),
            "clean_examples": [],
            "single_clean_actions": 0,
            "single_clean_actor_has_spell": 0,
            "single_clean_payload15": 0,
            "single_clean_magnitude_matches_spellbook": 0,
            "single_clean_duration_matches_power_x100": 0,
            "single_clean_target_known": 0,
            "single_clean_target_side_matches": 0,
        }
        for code, (spell, side) in CANDIDATES.items()
    }

    hero_actions = 0
    for battle_dir in battle_dirs:
        init = (battle_dir / "init.txt").read_text(encoding="utf-8", errors="replace")
        turns = (battle_dir / "turns0.txt").read_text(encoding="utf-8", errors="replace")
        entities, _ = parse_initial_entities(init)
        # Spawn records may introduce later targets. Owner/hero metadata in the M record is enough
        # for this analysis; no historical state parser is consulted.
        by_uid = dict(entities)
        books = {uid: parse_spellbook(e.magic_blob) for uid, e in by_uid.items() if e.is_hero}

        active: int | None = None
        pending = []
        for _turn_no, raw_turn in parse_turn_records(turns):
            for cmd in parse_commands(raw_turn):
                if cmd.opcode == "SPAWN_ENTITY" and cmd.spawned is not None:
                    by_uid[cmd.spawned.uid] = cmd.spawned
                    if cmd.spawned.is_hero:
                        books[cmd.spawned.uid] = parse_spellbook(cmd.spawned.magic_blob)

                if cmd.opcode != "ACTIVATE":
                    pending.append(cmd)
                    continue

                if active is not None and active in by_uid and by_uid[active].is_hero and pending:
                    hero_actions += 1
                    specials = [c for c in pending if c.opcode == "SPECIAL"]
                    codes_in_action = {c.code for c in specials}
                    for code, (spell_name, expected_side) in CANDIDATES.items():
                        recs = [c for c in specials if c.code == code]
                        if not recs:
                            continue
                        st = stats[code]
                        st["actions"] += 1
                        st["records"] += len(recs)
                        book = books.get(active, {})
                        spell = book.get(spell_name)
                        if spell is not None:
                            st["actor_has_spell"] += 1

                        # A clean cast has no other S-family in the action. It may still contain
                        # m/i/l bookkeeping records, which are normal for spell actions.
                        clean = codes_in_action == {code}
                        single_clean = clean and len(recs) == 1
                        if clean:
                            st["clean_actions"] += 1
                            st["clean_records"] += len(recs)
                            if spell is not None:
                                st["clean_actor_has_spell"] += 1
                        if single_clean:
                            st["single_clean_actions"] += 1
                            if spell is not None:
                                st["single_clean_actor_has_spell"] += 1

                        actor_owner = by_uid[active].owner
                        actor_power = by_uid[active].max_count
                        for r in recs:
                            target = by_uid.get(int(r.target_uid)) if r.target_uid is not None else None
                            # Generic SPECIAL scanner exposes only actor UID. Parse stable 15-digit
                            # status layout here strictly for the evidence report.
                            numeric = _special_numeric(r.raw)
                            if len(numeric) == 15 and numeric.isdigit():
                                st["payload15"] += 1
                                # status layout observed in all candidate families:
                                # caster3,target3,flag2,duration4,magnitude3
                                target_uid = int(numeric[3:6])
                                flag = int(numeric[6:8])
                                duration_raw = int(numeric[8:12])
                                magnitude = int(numeric[12:15])
                                target = by_uid.get(target_uid)
                                st["first_flag_counts"][str(flag)] += 1
                                st["duration_raw_counts"][str(duration_raw)] += 1
                                st["magnitude_counts"][str(magnitude)] += 1
                                if spell is not None and abs(magnitude - spell.effect) < 1e-9:
                                    st["magnitude_matches_spellbook"] += 1
                                if duration_raw == actor_power * 100:
                                    st["duration_matches_power_x100"] += 1
                                if clean:
                                    st["clean_payload15"] += 1
                                    if spell is not None and abs(magnitude - spell.effect) < 1e-9:
                                        st["clean_magnitude_matches_spellbook"] += 1
                                    if duration_raw == actor_power * 100:
                                        st["clean_duration_matches_power_x100"] += 1
                                    if single_clean:
                                        st["single_clean_payload15"] += 1
                                        if spell is not None and abs(magnitude - spell.effect) < 1e-9:
                                            st["single_clean_magnitude_matches_spellbook"] += 1
                                        if duration_raw == actor_power * 100:
                                            st["single_clean_duration_matches_power_x100"] += 1
                                    if len(st["clean_examples"]) < 8:
                                        st["clean_examples"].append({
                                            "battle_id": battle_dir.name,
                                            "actor_uid": active,
                                            "actor_power_field": actor_power,
                                            "raw": r.raw,
                                            "target_uid": target_uid,
                                            "target_owner": target.owner if target else None,
                                            "spell_effect": spell.effect if spell else None,
                                        })

                            if target is not None:
                                st["target_known"] += 1
                                match = (target.owner == actor_owner) if expected_side == "FRIENDLY" else (target.owner != actor_owner)
                                st["target_side_matches"] += int(match)
                                if clean:
                                    st["clean_target_known"] += 1
                                    st["clean_target_side_matches"] += int(match)
                                if single_clean:
                                    st["single_clean_target_known"] += 1
                                    st["single_clean_target_side_matches"] += int(match)

                active = cmd.actor_uid
                pending = []

    report = {"battles": len(battle_dirs), "hero_actions": hero_actions, "candidates": {}}
    for code, st in stats.items():
        # JSON-friendly counters and evidence-gated status.
        clean_payload = int(st["clean_payload15"])
        clean_known = int(st["clean_target_known"])
        clean_actions = int(st["clean_actions"])
        single_n = int(st["single_clean_payload15"])
        single_known = int(st["single_clean_target_known"])
        single_actions = int(st["single_clean_actions"])
        supported_single = bool(
            single_actions >= 10
            and st["single_clean_actor_has_spell"] == single_actions
            and single_n == single_actions
            and st["single_clean_magnitude_matches_spellbook"] == single_n
            and st["single_clean_duration_matches_power_x100"] == single_n
            and single_known == single_n
            and st["single_clean_target_side_matches"] == single_known
        )
        supported = bool(
            clean_actions >= 10
            and st["clean_actor_has_spell"] == clean_actions
            and clean_payload == st["clean_records"]
            and clean_payload > 0
            and st["clean_magnitude_matches_spellbook"] == clean_payload
            and st["clean_duration_matches_power_x100"] == clean_payload
            and clean_known == clean_payload
            and st["clean_target_side_matches"] == clean_known
        )
        item = dict(st)
        for key in ("first_flag_counts", "duration_raw_counts", "magnitude_counts"):
            item[key] = dict(st[key].most_common())
        item["independently_supported_clean_subset"] = supported
        item["independently_supported_single_target"] = supported_single
        report["candidates"][code] = item
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    report = analyze(args.corpus)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        code: {
            "spell": row["spell"],
            "actions": row["actions"],
            "clean_actions": row["clean_actions"],
            "clean_records": row["clean_records"],
            "supported_all_clean": row["independently_supported_clean_subset"],
            "supported_single": row["independently_supported_single_target"],
            "single_actions": row["single_clean_actions"],
            "single_magnitude": f"{row['single_clean_magnitude_matches_spellbook']}/{row['single_clean_payload15']}",
            "single_duration": f"{row['single_clean_duration_matches_power_x100']}/{row['single_clean_payload15']}",
            "single_side": f"{row['single_clean_target_side_matches']}/{row['single_clean_target_known']}",
            "clean_magnitude": f"{row['clean_magnitude_matches_spellbook']}/{row['clean_payload15']}",
            "clean_duration": f"{row['clean_duration_matches_power_x100']}/{row['clean_payload15']}",
            "clean_side": f"{row['clean_target_side_matches']}/{row['clean_target_known']}",
        }
        for code, row in report["candidates"].items()
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
