from __future__ import annotations

import argparse
import copy
import json
from collections import Counter, defaultdict
from pathlib import Path

from hwm_solver.protocol.replay import (
    _apply_command,
    _perspective_owner,
    _player_won,
    command_semantically_unresolved,
    parse_commands,
    parse_initial_entities,
    parse_turns,
)


def _terminal_core_consistent(entities: dict, player_owner: int | None, player_won: bool | None) -> bool | None:
    if player_owner is None or player_won is None:
        return None
    def alive_nonhero(e):
        return e.alive and e.count > 0 and not e.is_hero
    if player_won:
        return not any(alive_nonhero(e) and e.owner != player_owner and e.owner > 0 for e in entities.values())
    return not any(alive_nonhero(e) and e.owner == player_owner for e in entities.values())


def analyze(corpus: Path, out: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    dirs = sorted((d for d in root.iterdir() if d.is_dir()), key=lambda p: int(p.name))

    code_battles: dict[str, set[str]] = defaultdict(set)
    code_occ = Counter()
    code_bad = Counter()
    opcode_battles: dict[str, set[str]] = defaultdict(set)
    opcode_occ = Counter()
    opcode_bad = Counter()
    battle_rows = []

    consistent_total = 0
    inconsistent_total = 0
    known_total = 0

    for d in dirs:
        init = (d / "init.txt").read_text(encoding="utf-8", errors="replace")
        turns_text = (d / "turns0.txt").read_text(encoding="utf-8", errors="replace")
        entities, _ = parse_initial_entities(init)
        owner = _perspective_owner(entities)
        won = _player_won(init, entities, owner)
        working = copy.deepcopy(entities)
        special_codes = Counter()
        unresolved_ops = Counter()
        total_records = 0

        for turn in parse_turns(turns_text):
            for cmd in turn.commands:
                total_records += 1
                if cmd.opcode == "SPECIAL" and cmd.code:
                    special_codes[cmd.code] += 1
                if command_semantically_unresolved(cmd, working):
                    unresolved_ops[cmd.opcode] += 1
                _apply_command(working, cmd)

        consistent = _terminal_core_consistent(working, owner, won)
        if consistent is not None:
            known_total += 1
            if consistent:
                consistent_total += 1
            else:
                inconsistent_total += 1

        for code, n in special_codes.items():
            code_battles[code].add(d.name)
            code_occ[code] += n
            if consistent is False:
                code_bad[code] += 1
        for op, n in unresolved_ops.items():
            opcode_battles[op].add(d.name)
            opcode_occ[op] += n
            if consistent is False:
                opcode_bad[op] += 1

        battle_rows.append({
            "battle_id": d.name,
            "player_won": won,
            "terminal_core_consistent": consistent,
            "special_codes": sorted(special_codes),
            "unresolved_opcodes": dict(unresolved_ops),
            "semantic_unresolved_records": sum(unresolved_ops.values()),
            "protocol_records": total_records,
        })

    baseline_bad = inconsistent_total / max(1, known_total)

    def summarize(keys, battles_map, occ, bad):
        rows = []
        for key in sorted(keys):
            n_battles = len(battles_map[key])
            bad_battles = bad[key]
            bad_rate = bad_battles / max(1, n_battles)
            # Descriptive association only; not a causal mechanic label.
            rows.append({
                "key": key,
                "battle_count": n_battles,
                "occurrences": occ[key],
                "terminal_core_inconsistent_battles": bad_battles,
                "terminal_core_inconsistency_rate": bad_rate,
                "lift_vs_corpus": bad_rate - baseline_bad,
                "priority_score": n_battles ** 0.5 * max(0.0, bad_rate - baseline_bad),
            })
        rows.sort(key=lambda r: (r["priority_score"], r["battle_count"]), reverse=True)
        return rows

    result = {
        "source": "new raw init.txt + turns0.txt only; old historical parser/state dumps are not used as truth",
        "battles": len(dirs),
        "outcome_known": known_total,
        "terminal_core_consistent": consistent_total,
        "terminal_core_inconsistent": inconsistent_total,
        "terminal_core_inconsistency_rate": baseline_bad,
        "interpretation": (
            "Failure means the independently decoded core mutations do not eliminate the known losing side. "
            "It is a proxy for missing state mechanics, not proof that any associated special code caused the drift."
        ),
        "special_code_risk": summarize(code_battles.keys(), code_battles, code_occ, code_bad),
        "unresolved_opcode_risk": summarize(opcode_battles.keys(), opcode_battles, opcode_occ, opcode_bad),
        "battles_detail": battle_rows,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("corpus", type=Path)
    p.add_argument("--out", type=Path, default=Path("data/mechanic_risk_report.json"))
    a = p.parse_args()
    r = analyze(a.corpus, a.out)
    summary = {k: r[k] for k in (
        "battles", "outcome_known", "terminal_core_consistent",
        "terminal_core_inconsistent", "terminal_core_inconsistency_rate"
    )}
    summary["top_special_risk"] = r["special_code_risk"][:20]
    summary["top_opcode_risk"] = r["unresolved_opcode_risk"][:20]
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
