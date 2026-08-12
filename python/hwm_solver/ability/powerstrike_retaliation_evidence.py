from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from hwm_solver.ability.powerstrike_evidence import ABILITY, _abilities, _by_uid
from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands


def _retaliation_rows(decision: dict) -> list[dict]:
    """Extract retaliation hits made by a Power Strike carrier inside another actor's decision.

    A retaliation opportunity is corpus-observed rather than inferred from initiative rules:
    the active actor first DAMAGES the primary target and that target later DAMAGES the
    active actor in the same raw decision.  Proc recognition is then source-conditioned on
    the retaliating stack's server-declared `powerstrike` tag and requires the same raw
    consequence ordering used by the primary-attack evidence: retaliation DAMAGE ->
    forced-position of the struck active actor -> I<active><retaliator>.
    """
    if str(decision.get("action_type")) != "MELEE_ATTACK":
        return []
    before = list(decision.get("state_before") or [])
    active_uid = int(decision.get("actor_uid", -1))
    primary_target_raw = decision.get("target_uid")
    if primary_target_raw is None:
        return []
    target_uid = int(primary_target_raw)
    active = _by_uid(before, active_uid)
    target = _by_uid(before, target_uid)
    if active is None or target is None or ABILITY not in _abilities(target):
        return []

    commands = parse_commands(str(decision.get("raw", "")))
    primary_idx = next(
        (
            i
            for i, c in enumerate(commands)
            if c.opcode == "DAMAGE" and c.actor_uid == active_uid and c.target_uid == target_uid
        ),
        None,
    )
    if primary_idx is None:
        return []

    out: list[dict] = []
    for retaliation_idx, retaliation in enumerate(commands):
        if retaliation_idx <= primary_idx:
            continue
        if retaliation.opcode != "DAMAGE" or retaliation.actor_uid != target_uid or retaliation.target_uid != active_uid:
            continue

        next_damage_idx = next(
            (i for i, c in enumerate(commands) if i > retaliation_idx and c.opcode == "DAMAGE"),
            len(commands),
        )
        forced_pair = next(
            (
                (i, c)
                for i, c in enumerate(commands)
                if retaliation_idx < i < next_damage_idx
                and c.opcode == "FORCED_POSITION"
                and c.actor_uid == active_uid
            ),
            None,
        )
        i_pair = None
        if forced_pair is not None:
            i_pair = next(
                (
                    (i, c)
                    for i, c in enumerate(commands)
                    if forced_pair[0] < i < next_damage_idx
                    and c.opcode == "I_RECORD"
                    and c.actor_uid == active_uid
                    and c.target_uid == target_uid
                ),
                None,
            )
        proc = forced_pair is not None and i_pair is not None
        zero_state_after_i = False
        if i_pair is not None:
            zero_state_after_i = any(
                c.opcode == "STATE" and c.actor_uid == active_uid and c.code == "0000"
                for c in commands[i_pair[0] + 1 : next_damage_idx]
            )

        out.append(
            {
                "battle_id": str(decision.get("battle_id", "")),
                "decision_index": int(decision.get("decision_index", -1)),
                "server_turn": int(decision.get("server_turn", -1)),
                "active_uid": active_uid,
                "retaliator_uid": target_uid,
                "active_creature_id": int(active.get("creature_id", 0)),
                "retaliator_creature_id": int(target.get("creature_id", 0)),
                "active_owner": int(active.get("owner", -1)),
                "retaliator_owner": int(target.get("owner", -1)),
                "retaliator_abilities": sorted(_abilities(target)),
                "retaliation_damage": int(retaliation.amount or 0),
                "proc": proc,
                "forced_xy": (
                    [int(forced_pair[1].x), int(forced_pair[1].y)]
                    if forced_pair is not None and forced_pair[1].x is not None and forced_pair[1].y is not None
                    else None
                ),
                "raw_i": i_pair[1].raw if i_pair is not None else None,
                "zero_state_after_i": zero_state_after_i,
                "retaliation_index": retaliation_idx,
                "raw": str(decision.get("raw", "")),
            }
        )
    return out


def _primary_proc_suppression(decision: dict) -> dict | None:
    if str(decision.get("action_type")) != "MELEE_ATTACK":
        return None
    before = list(decision.get("state_before") or [])
    actor_uid = int(decision.get("actor_uid", -1))
    target_raw = decision.get("target_uid")
    if target_raw is None:
        return None
    target_uid = int(target_raw)
    actor = _by_uid(before, actor_uid)
    if actor is None or ABILITY not in _abilities(actor):
        return None

    commands = parse_commands(str(decision.get("raw", "")))
    primary_idx = next(
        (
            i for i, c in enumerate(commands)
            if c.opcode == "DAMAGE" and c.actor_uid == actor_uid and c.target_uid == target_uid
        ),
        None,
    )
    if primary_idx is None:
        return None
    forced_pair = next(
        (
            (i, c) for i, c in enumerate(commands)
            if i > primary_idx and c.opcode == "FORCED_POSITION" and c.actor_uid == target_uid
        ),
        None,
    )
    i_pair = None
    if forced_pair is not None:
        i_pair = next(
            (
                (i, c) for i, c in enumerate(commands)
                if i > forced_pair[0]
                and c.opcode == "I_RECORD"
                and c.actor_uid == target_uid
                and c.target_uid == actor_uid
            ),
            None,
        )
    if i_pair is None:
        return None

    retaliation_after_proc = any(
        c.opcode == "DAMAGE"
        and c.actor_uid == target_uid
        and c.target_uid == actor_uid
        for c in commands[i_pair[0] + 1 :]
    )
    return {
        "battle_id": str(decision.get("battle_id", "")),
        "decision_index": int(decision.get("decision_index", -1)),
        "server_turn": int(decision.get("server_turn", -1)),
        "actor_uid": actor_uid,
        "target_uid": target_uid,
        "retaliation_after_proc": retaliation_after_proc,
        "raw": str(decision.get("raw", "")),
    }


def analyze_decisions(decisions: Iterable[dict]) -> dict:
    retaliation_rows: list[dict] = []
    primary_proc_rows: list[dict] = []
    errors: list[str] = []
    battles: set[str] = set()

    for decision in decisions:
        battles.add(str(decision.get("battle_id", "")))
        try:
            retaliation_rows.extend(_retaliation_rows(decision))
            primary = _primary_proc_suppression(decision)
            if primary is not None:
                primary_proc_rows.append(primary)
        except Exception as exc:
            errors.append(
                f"{decision.get('battle_id')}:{decision.get('decision_index')}:"
                f"{type(exc).__name__}:{exc}"
            )

    retaliation_proc = [r for r in retaliation_rows if r["proc"]]
    return {
        "ability": ABILITY,
        "runtime_status": "learned_damage",
        "evidence_scope": "read_only_retaliation_audit",
        "corpus_battles_seen": len(battles),
        "analysis_errors": errors,
        "carrier_retaliation_hits": len(retaliation_rows),
        "carrier_retaliation_battles": len({r["battle_id"] for r in retaliation_rows}),
        "carrier_retaliation_proc_hits": len(retaliation_proc),
        "carrier_retaliation_proc_battles": len({r["battle_id"] for r in retaliation_proc}),
        "carrier_retaliation_proc_zero_state_after_i": sum(bool(r["zero_state_after_i"]) for r in retaliation_proc),
        "primary_proc_hits": len(primary_proc_rows),
        "primary_proc_with_retaliation_after_i": sum(bool(r["retaliation_after_proc"]) for r in primary_proc_rows),
        "retaliation_proc_examples": retaliation_proc[:20],
        "retaliation_no_proc_examples": [r for r in retaliation_rows if not r["proc"]][:10],
        "primary_proc_examples": primary_proc_rows[:10],
    }


def analyze_corpus(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    parse_errors: list[str] = []

    def stream():
        if not root.is_dir():
            raise FileNotFoundError(root)
        dirs = [p for p in root.iterdir() if p.is_dir()]
        dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))
        for battle_dir in dirs:
            if not (battle_dir / "init.txt").exists() or not (battle_dir / "turns0.txt").exists():
                continue
            try:
                yield from iter_battle_decisions(battle_dir)
            except Exception as exc:
                parse_errors.append(f"{battle_dir.name}:{type(exc).__name__}:{exc}")

    report = analyze_decisions(stream())
    report["corpus"] = str(corpus)
    report["parse_errors"] = parse_errors
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only Power Strike retaliation audit.")
    ap.add_argument("corpus", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    report = analyze_corpus(args.corpus)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 2 if report["parse_errors"] or report["analysis_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
