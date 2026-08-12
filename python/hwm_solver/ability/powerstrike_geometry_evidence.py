from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from hwm_solver.ability.powerstrike_discriminator import _extended_row
from hwm_solver.ability.powerstrike_evidence import ABILITY, _attack_row
from hwm_solver.protocol.replay import iter_battle_decisions


def _anomaly_row(decision: dict) -> dict | None:
    base = _attack_row(decision)
    if base is None or ABILITY not in set(base["actor_abilities"]) or not base["proc"]:
        return None
    row = _extended_row(decision, base)
    geometry = row["geometry"]
    if geometry["kind"] != "same_coordinate" and geometry["distance"] in {None, 1} and not geometry["destination_preoccupied"]:
        return None

    before = list(decision.get("state_before") or [])
    after = list(decision.get("state_after") or [])
    target_before = next((e for e in before if int(e.get("uid", -1)) == int(row["target_uid"])), None)
    target_after = next((e for e in after if int(e.get("uid", -1)) == int(row["target_uid"])), None)
    actor_before = next((e for e in before if int(e.get("uid", -1)) == int(row["actor_uid"])), None)

    return {
        "battle_id": row["battle_id"],
        "decision_index": row["decision_index"],
        "server_turn": row["server_turn"],
        "actor_uid": row["actor_uid"],
        "target_uid": row["target_uid"],
        "actor_creature_id": row["actor_creature_id"],
        "target_creature_id": row["target_creature_id"],
        "actor_abilities": row["actor_abilities"],
        "target_abilities": row["target_abilities"],
        "actor_owner": row["actor_owner"],
        "target_owner": row["target_owner"],
        "actor_before": actor_before,
        "target_before": target_before,
        "target_after": target_after,
        "primary_damage": row["primary_damage"],
        "target_total_hp": row["target_total_hp"],
        "target_total_hp_after_primary": row["target_total_hp_after_primary"],
        "target_total_hp_after_decision": row["target_total_hp_after_decision"],
        "geometry": geometry,
        "wire": row["wire"],
        "raw_i_records": row["raw_i_records"],
        "raw": row["raw"],
    }


def analyze_decisions(decisions: Iterable[dict]) -> dict:
    anomalies: list[dict] = []
    errors: list[str] = []
    proc_count = 0
    for decision in decisions:
        try:
            base = _attack_row(decision)
            if base is not None and ABILITY in set(base["actor_abilities"]) and base["proc"]:
                proc_count += 1
            row = _anomaly_row(decision)
            if row is not None:
                anomalies.append(row)
        except Exception as exc:
            errors.append(
                f"{decision.get('battle_id')}:{decision.get('decision_index')}:"
                f"{type(exc).__name__}:{exc}"
            )

    same = [r for r in anomalies if r["geometry"]["kind"] == "same_coordinate"]
    non_unit = [r for r in anomalies if r["geometry"]["distance"] not in {None, 0, 1}]
    occupied = [r for r in anomalies if r["geometry"]["destination_preoccupied"] is True]
    killed_by_primary = [r for r in anomalies if int(r["target_total_hp_after_primary"]) == 0]
    return {
        "ability": ABILITY,
        "runtime_status": "learned_damage",
        "proc_rows": proc_count,
        "anomaly_rows": len(anomalies),
        "same_coordinate": same,
        "non_unit_distance": non_unit,
        "preoccupied_destination": occupied,
        "killed_by_primary_anomalies": killed_by_primary,
        "analysis_errors": errors,
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
    ap = argparse.ArgumentParser(description="Read-only Power Strike forced-position anomaly probe.")
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
