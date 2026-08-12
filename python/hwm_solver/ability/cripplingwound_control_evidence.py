from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands


ABILITY = "cripplingwound"
WND = re.compile(r"Swnd(\d{3})(\d{3})(\d{9})")
HYP = re.compile(r"Shyp(\d{3})(\d{3})")


def _by_uid(state: list[dict], uid: int) -> dict | None:
    return next((e for e in state if int(e.get("uid", -1)) == int(uid)), None)


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("abilities") or [])}


def analyze_decisions(decisions: Iterable[dict]) -> dict:
    history: dict[str, list[dict]] = defaultdict(list)
    same_owner_records: list[dict] = []
    carrier_wnd_records = 0
    parse_errors: list[str] = []

    for decision in decisions:
        battle_id = str(decision.get("battle_id", ""))
        raw = str(decision.get("raw", ""))
        before = list(decision.get("state_before") or [])
        try:
            # Parse once as a structural sanity check. The raw regex below intentionally
            # preserves Shyp even though replay.py does not currently model its target UID.
            parse_commands(raw)
            for match in WND.finditer(raw):
                source_uid = int(match.group(1))
                target_uid = int(match.group(2))
                source = _by_uid(before, source_uid)
                target = _by_uid(before, target_uid)
                if source is None or target is None or ABILITY not in _abilities(source):
                    continue
                carrier_wnd_records += 1
                source_owner = int(source.get("owner", -1))
                target_owner = int(target.get("owner", -1))
                if source_owner != target_owner:
                    continue

                preceding_hyp: list[dict] = []
                for prior in reversed(history[battle_id]):
                    matches = [
                        {
                            "controller_uid": int(m.group(1)),
                            "controlled_uid": int(m.group(2)),
                            "raw_marker": m.group(0),
                            "decision_index": prior["decision_index"],
                            "server_turn": prior["server_turn"],
                            "raw": prior["raw"],
                        }
                        for m in HYP.finditer(prior["raw"])
                        if int(m.group(2)) == source_uid
                    ]
                    if matches:
                        preceding_hyp.extend(matches)
                        break

                same_owner_records.append(
                    {
                        "battle_id": battle_id,
                        "decision_index": int(decision.get("decision_index", -1)),
                        "server_turn": int(decision.get("server_turn", -1)),
                        "source_uid": source_uid,
                        "target_uid": target_uid,
                        "source_owner": source_owner,
                        "target_owner": target_owner,
                        "source_creature_id": int(source.get("creature_id", 0)),
                        "target_creature_id": int(target.get("creature_id", 0)),
                        "source_abilities": sorted(_abilities(source)),
                        "raw_wnd": match.group(0),
                        "raw_decision": raw,
                        "preceding_shyp_targeting_source": preceding_hyp,
                    }
                )
        except Exception as exc:
            parse_errors.append(
                f"{battle_id}:{decision.get('decision_index')}:"
                f"{type(exc).__name__}:{exc}"
            )
        history[battle_id].append(
            {
                "decision_index": int(decision.get("decision_index", -1)),
                "server_turn": int(decision.get("server_turn", -1)),
                "raw": raw,
            }
        )

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_same_owner_proc_control_context",
        "carrier_wnd_records": carrier_wnd_records,
        "same_owner_carrier_wnd_records": len(same_owner_records),
        "same_owner_with_prior_shyp_targeting_source": sum(
            bool(row["preceding_shyp_targeting_source"]) for row in same_owner_records
        ),
        "same_owner_without_prior_shyp_targeting_source": sum(
            not bool(row["preceding_shyp_targeting_source"]) for row in same_owner_records
        ),
        "parse_errors": parse_errors,
        "examples": same_owner_records,
        "integration_implication": (
            "static entity owner is insufficient for Swnd semantic validation under "
            "temporary control; preserve the observed proc and resolve control-side context"
        ),
    }


def analyze_corpus(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    if not root.is_dir():
        raise FileNotFoundError(root)
    battle_dirs = [p for p in root.iterdir() if p.is_dir()]
    battle_dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))
    replay_errors: list[str] = []

    def stream():
        for battle_dir in battle_dirs:
            if not (battle_dir / "init.txt").exists() or not (battle_dir / "turns0.txt").exists():
                continue
            try:
                yield from iter_battle_decisions(battle_dir)
            except Exception as exc:
                replay_errors.append(f"{battle_dir.name}:{type(exc).__name__}:{exc}")

    report = analyze_decisions(stream())
    report["corpus_battle_dirs"] = len(battle_dirs)
    report["replay_errors"] = replay_errors
    report["corpus"] = str(corpus)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit same-owner Crippling Wound control context.")
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = analyze_corpus(args.corpus)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 2 if report["parse_errors"] or report["replay_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
