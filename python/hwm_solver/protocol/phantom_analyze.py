from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from hwm_solver.protocol.replay import parse_commands, parse_turn_records

SPHM_RE = re.compile(r"^Sphm(\d{3})(\d{3})(\d{2})(\d{3})(\d{4})$")
SPECIAL_RE = re.compile(r"^S([A-Za-z0-9_-]{3})([0-9.+-]*)$")
PHM_MOD_RE = re.compile(r"phm(\d{12})")


@dataclass
class PhantomRow:
    battle_id: str
    spawn_turn: int
    caster_uid: int
    clone_uid: int
    spell_id: int
    source_uid: int
    trailer: str
    clone_creature_id: int | None = None
    clone_count: int | None = None
    clone_x: int | None = None
    clone_y: int | None = None
    clone_total_hp: int | None = None
    clone_has_phm_modifier: bool = False
    source_creature_id: int | None = None
    ever_activated: bool = False
    first_activation_turn: int | None = None
    activation_count: int = 0
    damage_received_events: int = 0
    positive_damage_events: int = 0
    damage_received_total: int = 0
    first_positive_damage_turn: int | None = None
    ever_h: bool = False
    h_turn: int | None = None
    ever_u: bool = False
    u_turn: int | None = None
    actor_events_after_first_positive_damage: int = 0
    activation_after_first_positive_damage: bool = False
    damage_actor_events: int = 0
    referenced_specials: list[str] | None = None
    first_psc_turn: int | None = None
    psc_count: int = 0
    phm_modifier: str | None = None


def _entity_hp(e) -> int:
    if not e or e.count <= 0 or e.max_hp <= 0:
        return 0
    top = e.top_hp if e.top_hp > 0 else e.max_hp
    return max(0, (e.count - 1) * e.max_hp + top)


def _special_numeric_uids(raw: str) -> tuple[str, list[int]] | None:
    m = SPECIAL_RE.match(raw)
    if not m:
        return None
    code, payload = m.groups()
    digits = "".join(ch for ch in payload if ch.isdigit())
    # Do not claim grammar: expose every 3-digit aligned chunk only for correlation.
    vals = []
    for i in range(0, len(digits) - 2, 3):
        vals.append(int(digits[i:i+3]))
    return code, vals


def analyze(root: Path) -> dict:
    if (root / "battles").is_dir():
        root = root / "battles"

    rows: list[PhantomRow] = []
    parse_errors: list[str] = []
    spell_ids = Counter()
    trailers = Counter()
    ref_special_codes = Counter()
    psc_payloads = Counter()

    for battle_dir in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: int(p.name)):
        turns_path = battle_dir / "turns0.txt"
        if not turns_path.exists():
            continue
        battle_id = battle_dir.name
        turns = parse_turn_records(turns_path.read_text(encoding="utf-8", errors="replace"))
        parsed = [(turn, parse_commands(body)) for turn, body in turns]

        # Build a light entity catalogue from every spawned M in the turn stream.
        spawned = {}
        for _, cmds in parsed:
            for c in cmds:
                if c.opcode == "SPAWN_ENTITY" and c.spawned is not None:
                    spawned[c.spawned.uid] = c.spawned

        for ti, (turn, cmds) in enumerate(parsed):
            for c in cmds:
                if c.opcode != "SPECIAL" or c.code != "phm":
                    continue
                m = SPHM_RE.match(c.raw)
                if not m:
                    parse_errors.append(f"{battle_id}:{turn}:{c.raw}")
                    continue
                caster, clone, spell, source, trailer = m.groups()
                clone_uid, source_uid = int(clone), int(source)
                ce = spawned.get(clone_uid)
                se = spawned.get(source_uid)
                row = PhantomRow(
                    battle_id=battle_id,
                    spawn_turn=turn,
                    caster_uid=int(caster),
                    clone_uid=clone_uid,
                    spell_id=int(spell),
                    source_uid=source_uid,
                    trailer=trailer,
                    clone_creature_id=ce.creature_id if ce else None,
                    clone_count=ce.count if ce else None,
                    clone_x=ce.x if ce else None,
                    clone_y=ce.y if ce else None,
                    clone_total_hp=_entity_hp(ce) if ce else None,
                    clone_has_phm_modifier=bool(ce and PHM_MOD_RE.search(ce.raw_tail)),
                    source_creature_id=se.creature_id if se else None,
                    referenced_specials=[],
                )
                if ce:
                    mm = PHM_MOD_RE.search(ce.raw_tail)
                    row.phm_modifier = mm.group(1) if mm else None

                first_damage_seen = False
                for later_turn, later_cmds in parsed[ti:]:
                    for x in later_cmds:
                        # Skip the spawn special itself, but keep other records in same turn.
                        if later_turn == turn and x is c:
                            continue
                        if x.opcode == "ACTIVATE" and x.actor_uid == clone_uid:
                            row.ever_activated = True
                            row.activation_count += 1
                            if row.first_activation_turn is None:
                                row.first_activation_turn = later_turn
                            if first_damage_seen:
                                row.activation_after_first_positive_damage = True
                        if x.opcode == "DAMAGE":
                            if x.actor_uid == clone_uid:
                                row.damage_actor_events += 1
                                if first_damage_seen:
                                    row.actor_events_after_first_positive_damage += 1
                            if x.target_uid == clone_uid:
                                row.damage_received_events += 1
                                amount = int(x.amount or 0)
                                row.damage_received_total += max(0, amount)
                                if amount > 0:
                                    row.positive_damage_events += 1
                                    if row.first_positive_damage_turn is None:
                                        row.first_positive_damage_turn = later_turn
                                    first_damage_seen = True
                        if x.opcode == "HIDE_OR_DEATH" and x.actor_uid == clone_uid:
                            row.ever_h = True
                            row.h_turn = later_turn if row.h_turn is None else row.h_turn
                        if x.opcode == "U_RECORD" and x.actor_uid == clone_uid:
                            row.ever_u = True
                            row.u_turn = later_turn if row.u_turn is None else row.u_turn
                        if x.raw.startswith("S"):
                            sp = _special_numeric_uids(x.raw)
                            if sp:
                                code, uids = sp
                                if clone_uid in uids:
                                    row.referenced_specials.append(f"{later_turn}:{x.raw}")
                                    ref_special_codes[code] += 1
                                    if code == "psc":
                                        row.psc_count += 1
                                        if row.first_psc_turn is None:
                                            row.first_psc_turn = later_turn
                                        psc_payloads[x.raw] += 1
                spell_ids[row.spell_id] += 1
                trailers[row.trailer] += 1
                rows.append(row)

    def n(pred):
        return sum(1 for r in rows if pred(r))

    damaged = [r for r in rows if r.positive_damage_events]
    psc = [r for r in rows if r.psc_count]
    report = {
        "phantoms": len(rows),
        "battles": len({r.battle_id for r in rows}),
        "parse_errors": parse_errors,
        "spell_ids": dict(spell_ids),
        "trailers": dict(trailers),
        "clone_m_found": n(lambda r: r.clone_creature_id is not None),
        "clone_has_phm_modifier": n(lambda r: r.clone_has_phm_modifier),
        "source_creature_matches_clone": n(lambda r: r.clone_creature_id is not None and r.source_creature_id == r.clone_creature_id),
        "ever_activated": n(lambda r: r.ever_activated),
        "ever_h": n(lambda r: r.ever_h),
        "ever_u": n(lambda r: r.ever_u),
        "positive_damage_received": len(damaged),
        "damaged_then_h": sum(1 for r in damaged if r.ever_h and r.h_turn is not None and r.first_positive_damage_turn is not None and r.h_turn >= r.first_positive_damage_turn),
        "damaged_then_activated_again": sum(1 for r in damaged if r.activation_after_first_positive_damage),
        "damaged_then_dealt_damage": sum(1 for r in damaged if r.actor_events_after_first_positive_damage),
        "psc_referenced": len(psc),
        "psc_and_positive_damage": sum(1 for r in psc if r.positive_damage_events),
        "psc_then_h": sum(1 for r in psc if r.ever_h and r.first_psc_turn is not None and r.h_turn is not None and r.h_turn >= r.first_psc_turn),
        "special_codes_referencing_clone_aligned3": dict(ref_special_codes.most_common()),
        "rows": [asdict(r) for r in rows],
    }
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    report = analyze(args.corpus)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
