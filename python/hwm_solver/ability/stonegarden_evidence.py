from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, parse_initial_entities, parse_tooltips


ABILITY = "stonegarden"
PROC_ABILITY = "stoning"
STONE_EFFECTS = frozenset({"proc_stone", "sta", "stone"})


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("abilities") or [])}


def _effects(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("effects") or [])}


def _by_uid(state: list[dict], uid: int | None) -> dict | None:
    if uid is None:
        return None
    return next((e for e in state if int(e.get("uid", -1)) == int(uid)), None)


def _counter(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in counter.most_common()}


def _is_stone(entity: dict) -> bool:
    return bool(_effects(entity) & STONE_EFFECTS)


def _brier(labels: list[int], predictions: list[float]) -> float | None:
    if not labels or len(labels) != len(predictions):
        return None
    return sum((float(y) - float(p)) ** 2 for y, p in zip(labels, predictions)) / len(labels)


def _chronological_split(rows: list[dict], frac: float = 0.8) -> tuple[list[dict], list[dict]]:
    battles = sorted({str(row["battle_id"]) for row in rows}, key=lambda x: (0, int(x)) if x.isdigit() else (1, x))
    if len(battles) < 2:
        return rows, []
    cut = min(len(battles) - 1, max(1, int(len(battles) * frac)))
    train_ids = set(battles[:cut])
    return [row for row in rows if row["battle_id"] in train_ids], [row for row in rows if row["battle_id"] not in train_ids]


def _reference_probability(stone_value: int) -> float:
    return min(1.0, 0.10 + 0.05 * max(0, int(stone_value)))


def analyze_corpus(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    if not root.is_dir():
        raise FileNotFoundError(root)
    battle_dirs = [p for p in root.iterdir() if p.is_dir()]
    battle_dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))

    parse_errors: list[str] = []
    carrier_uids: dict[str, set[int]] = {}
    carrier_entities = 0
    carrier_creatures: Counter[int] = Counter()
    carrier_ability_sets: Counter[str] = Counter()
    carrier_without_stoning = 0
    tooltip_battles = 0
    tooltip_names: Counter[str] = Counter()
    tooltip_descriptions: Counter[str] = Counter()

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

        name = str((tooltips.get("abil_names") or {}).get(ABILITY) or "").strip()
        description = str((tooltips.get("abil_desc") or {}).get(ABILITY) or "").strip()
        if name or description:
            tooltip_battles += 1
            if name:
                tooltip_names[name] += 1
            if description:
                tooltip_descriptions[description] += 1

        uids: set[int] = set()
        for entity in entities.values():
            abilities = {str(x).lower() for x in entity.abilities}
            if ABILITY not in abilities:
                continue
            uid = int(entity.uid)
            uids.add(uid)
            carrier_entities += 1
            carrier_creatures[int(entity.creature_id)] += 1
            carrier_ability_sets[",".join(sorted(abilities)) or "<none>"] += 1
            carrier_without_stoning += int(PROC_ABILITY not in abilities)
        if uids:
            carrier_uids[battle_dir.name] = uids

    rows: list[dict] = []
    stone_stack_hist: Counter[int] = Counter()
    stone_creature_hist: Counter[int] = Counter()
    proc_by_stone_stacks: dict[int, list[int]] = {}
    proc_by_stone_creatures: dict[int, list[int]] = {}
    signal_shape: Counter[str] = Counter()
    target_already_stone = 0
    proc_target_already_stone = 0
    examples: list[dict] = []

    for battle_dir in battle_dirs:
        carriers = carrier_uids.get(battle_dir.name)
        if not carriers:
            continue
        try:
            for decision in iter_battle_decisions(battle_dir):
                actor_uid = int(decision.get("actor_uid", -1))
                if actor_uid not in carriers or str(decision.get("action_type", "")) != "MELEE_ATTACK":
                    continue
                before = list(decision.get("state_before") or [])
                actor = _by_uid(before, actor_uid)
                target_raw = decision.get("target_uid")
                target_uid = int(target_raw) if target_raw is not None else None
                target = _by_uid(before, target_uid)
                if not actor or not target:
                    continue
                commands = parse_commands(str(decision.get("raw", "")))
                sta_records = [
                    command
                    for command in commands
                    if command.opcode == "SPECIAL"
                    and str(command.code) == "sta"
                    and command.actor_uid is not None and int(command.actor_uid) == actor_uid
                    and command.target_uid is not None and target_uid is not None
                    and int(command.target_uid) == target_uid
                ]
                proc = int(bool(sta_records))
                stone_entities = [
                    entity for entity in before
                    if bool(entity.get("alive", False)) and not bool(entity.get("is_hidden", False)) and _is_stone(entity)
                ]
                stone_stacks = len(stone_entities)
                stone_creatures = sum(max(0, int(entity.get("count", 0))) for entity in stone_entities)
                target_stone = _is_stone(target)
                target_already_stone += int(target_stone)
                proc_target_already_stone += int(proc and target_stone)
                stone_stack_hist[stone_stacks] += 1
                stone_creature_hist[stone_creatures] += 1
                proc_by_stone_stacks.setdefault(stone_stacks, []).append(proc)
                proc_by_stone_creatures.setdefault(stone_creatures, []).append(proc)
                if sta_records:
                    for command in sta_records:
                        signal_shape[str(command.raw)] += 1
                row = {
                    "battle_id": str(decision.get("battle_id", battle_dir.name)),
                    "decision_index": int(decision.get("decision_index", -1)),
                    "server_turn": int(decision.get("server_turn", -1)),
                    "actor_uid": actor_uid,
                    "actor_creature_id": int(actor.get("creature_id", -1)),
                    "actor_count": int(actor.get("count", 0)),
                    "actor_abilities": sorted(_abilities(actor)),
                    "target_uid": target_uid,
                    "target_creature_id": int(target.get("creature_id", -1)),
                    "target_abilities": sorted(_abilities(target)),
                    "target_already_stone": target_stone,
                    "stone_stacks_before": stone_stacks,
                    "stone_creatures_before": stone_creatures,
                    "stone_entities": [
                        {"uid": int(entity.get("uid", -1)), "owner": int(entity.get("owner", -1)), "count": int(entity.get("count", 0)), "creature_id": int(entity.get("creature_id", -1)), "effects": sorted(_effects(entity))}
                        for entity in stone_entities
                    ],
                    "proc": proc,
                    "sta_raw": [str(command.raw) for command in sta_records],
                    "raw": str(decision.get("raw", "")),
                }
                rows.append(row)
                if len(examples) < 100:
                    examples.append(row)
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    train, holdout = _chronological_split(rows)
    train_rate = sum(int(row["proc"]) for row in train) / len(train) if train else 0.0
    holdout_labels = [int(row["proc"]) for row in holdout]
    baseline_predictions = [train_rate for _ in holdout]
    stack_predictions = [_reference_probability(int(row["stone_stacks_before"])) for row in holdout]
    creature_predictions = [_reference_probability(int(row["stone_creatures_before"])) for row in holdout]
    baseline_brier = _brier(holdout_labels, baseline_predictions)
    stack_brier = _brier(holdout_labels, stack_predictions)
    creature_brier = _brier(holdout_labels, creature_predictions)

    def grouped(mapping: dict[int, list[int]]) -> dict[str, dict]:
        return {
            str(key): {"attacks": len(values), "procs": sum(values), "proc_rate": sum(values) / len(values)}
            for key, values in sorted(mapping.items())
        }

    return {
        "ability": ABILITY,
        "proc_ability": PROC_ABILITY,
        "evidence_scope": "raw_stoning_signal_vs_pre_hit_battlefield_stone_population",
        "corpus_battle_dirs": len(battle_dirs),
        "carrier_battles": len(carrier_uids),
        "carrier_entities": carrier_entities,
        "carrier_creatures": _counter(carrier_creatures),
        "carrier_ability_sets": _counter(carrier_ability_sets),
        "carrier_without_stoning": carrier_without_stoning,
        "tooltip_battles": tooltip_battles,
        "tooltip_names": _counter(tooltip_names),
        "tooltip_descriptions": _counter(tooltip_descriptions),
        "carrier_melee_attacks": len(rows),
        "observed_procs": sum(int(row["proc"]) for row in rows),
        "stone_effect_aliases": sorted(STONE_EFFECTS),
        "stone_stack_histogram": _counter(stone_stack_hist),
        "stone_creature_histogram": _counter(stone_creature_hist),
        "proc_by_stone_stacks": grouped(proc_by_stone_stacks),
        "proc_by_stone_creatures": grouped(proc_by_stone_creatures),
        "target_already_stone_attacks": target_already_stone,
        "proc_target_already_stone": proc_target_already_stone,
        "sta_signal_raw_shapes": dict(signal_shape.most_common(40)),
        "temporal_holdout": {
            "train_battles": len({row["battle_id"] for row in train}),
            "train_rows": len(train),
            "train_proc_rate": train_rate,
            "holdout_battles": len({row["battle_id"] for row in holdout}),
            "holdout_rows": len(holdout),
            "holdout_proc_rate": sum(holdout_labels) / len(holdout_labels) if holdout_labels else None,
            "train_frequency": {"brier": baseline_brier},
            "reference_stack_count": {
                "formula": "min(1, 0.10 + 0.05 * pre_hit_stone_stack_count)",
                "brier": stack_brier,
                "brier_improvement_vs_baseline": (baseline_brier - stack_brier) if baseline_brier is not None and stack_brier is not None else None,
            },
            "reference_creature_count": {
                "formula": "min(1, 0.10 + 0.05 * sum(pre_hit_stone_stack_counts))",
                "brier": creature_brier,
                "brier_improvement_vs_baseline": (baseline_brier - creature_brier) if baseline_brier is not None and creature_brier is not None else None,
            },
        },
        "examples": examples,
        "parse_errors": parse_errors,
        "integration_implication": (
            "Current C++ ProcModel probability_for receives only attacker/target and cannot represent battlefield stone "
            "population. If a stone-population rule survives chronological holdout, integration requires a narrow "
            "battlefield-state feature path (derivable from existing entity effects/counts), not a new canonical state field."
        ),
        "interpretation_guard": (
            "The 10% + 5% reference formulas are falsification candidates only. No Stone Garden probability change is "
            "allowed unless a battlefield-stone interpretation beats train-frequency on chronological battle holdout and "
            "the raw Ssta carrier/target signal remains collision-free."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Stone Garden battlefield-state proc evidence.")
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = analyze_corpus(args.corpus)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 2 if report["parse_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
