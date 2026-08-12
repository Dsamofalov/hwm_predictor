from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands


ABILITY = "torpor"
MECHANICAL_TAGS = frozenset({"mechanical", "warmachine", "statix"})
INELIGIBLE_TAGS = frozenset({"undead", "elemental"}) | MECHANICAL_TAGS


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("abilities") or [])}


def _effects(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x) for x in (entity.get("effects") or [])}


def _by_uid(state: list[dict], uid: int | None) -> dict | None:
    if uid is None:
        return None
    return next((e for e in state if int(e.get("uid", -1)) == int(uid)), None)


def _counter(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in counter.most_common()}


def _is_primary_torpor_signal(command, actor_uid: int, target_uid: int) -> bool:
    """Match raw Stor actor3,target3 only inside the Torpor evidence context.

    The generic replay scanner deliberately keeps unknown SPECIAL payloads conservative and
    therefore does not assign target_uid for `tor`.  The evidence audit can still verify the
    observed wire invariant without promoting it to production protocol semantics.
    """
    if command.opcode != "SPECIAL" or str(command.code) != "tor":
        return False
    if command.actor_uid is None or int(command.actor_uid) != actor_uid:
        return False
    if command.target_uid is not None:
        return int(command.target_uid) == target_uid
    raw = str(command.raw)
    if not raw.startswith("Stor"):
        return False
    numeric = raw[4:]
    return len(numeric) >= 6 and numeric[:6].isdigit() and int(numeric[3:6]) == target_uid


def analyze_corpus(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    if not root.is_dir():
        raise FileNotFoundError(root)
    battle_dirs = [p for p in root.iterdir() if p.is_dir()]
    battle_dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))

    parse_errors: list[str] = []
    carrier_melee_attacks = 0
    observed_proc_attacks = 0
    proc_signal_codes: Counter[str] = Counter()
    proc_target_ability_sets: Counter[str] = Counter()
    proc_target_ineligible_tags: Counter[str] = Counter()
    proc_effect_after: Counter[str] = Counter()
    proc_effect_turns_after: Counter[str] = Counter()
    proc_with_immediate_retaliation = 0
    proc_examples: list[dict] = []

    sleep_before_damage_rows = 0
    sleep_before_damage_effect_removed = 0
    sleep_before_damage_retaliation = 0
    wake_effect_before: Counter[str] = Counter()
    wake_effect_after: Counter[str] = Counter()
    wake_examples: list[dict] = []

    torpor_carrier_attacks_on_sleeping_target = 0
    torpor_carrier_sleeping_damage: list[dict] = []

    for battle_dir in battle_dirs:
        try:
            for decision in iter_battle_decisions(battle_dir):
                before = list(decision.get("state_before") or [])
                after = list(decision.get("state_after") or [])
                actor_uid = int(decision.get("actor_uid", -1))
                actor = _by_uid(before, actor_uid)
                action_type = str(decision.get("action_type", ""))
                target_raw = decision.get("target_uid")
                target_uid = int(target_raw) if target_raw is not None else None
                target_before = _by_uid(before, target_uid)
                target_after = _by_uid(after, target_uid)
                commands = parse_commands(str(decision.get("raw", "")))

                if actor and ABILITY in _abilities(actor) and action_type == "MELEE_ATTACK" and target_uid is not None:
                    carrier_melee_attacks += 1
                    tor_signals = [
                        command
                        for command in commands
                        if _is_primary_torpor_signal(command, actor_uid, target_uid)
                    ]
                    if tor_signals:
                        observed_proc_attacks += 1
                        proc_signal_codes["tor"] += len(tor_signals)
                        target_tags = _abilities(target_before)
                        proc_target_ability_sets[",".join(sorted(target_tags)) or "<none>"] += 1
                        for tag in sorted(target_tags & INELIGIBLE_TAGS):
                            proc_target_ineligible_tags[tag] += 1
                        after_effects = _effects(target_after)
                        proc_effect_after[str("proc_torpor" in after_effects)] += 1
                        turns = dict(target_after.get("effect_turns") or {}).get("proc_torpor") if target_after else None
                        proc_effect_turns_after[str(turns)] += 1
                        primary_index = next(
                            (
                                i for i, command in enumerate(commands)
                                if command.opcode == "DAMAGE"
                                and command.actor_uid is not None and int(command.actor_uid) == actor_uid
                                and command.target_uid is not None and int(command.target_uid) == target_uid
                            ),
                            -1,
                        )
                        retaliation = primary_index >= 0 and any(
                            command.opcode == "DAMAGE"
                            and command.actor_uid is not None and int(command.actor_uid) == target_uid
                            and command.target_uid is not None and int(command.target_uid) == actor_uid
                            for command in commands[primary_index + 1 :]
                        )
                        proc_with_immediate_retaliation += int(retaliation)
                        if len(proc_examples) < 60:
                            proc_examples.append({
                                "battle_id": str(decision.get("battle_id", battle_dir.name)),
                                "decision_index": int(decision.get("decision_index", -1)),
                                "server_turn": int(decision.get("server_turn", -1)),
                                "actor_uid": actor_uid,
                                "actor_creature_id": int(actor.get("creature_id", -1)),
                                "target_uid": target_uid,
                                "target_abilities": sorted(target_tags),
                                "tor_raw": [str(command.raw) for command in tor_signals],
                                "effect_after": "proc_torpor" in after_effects,
                                "effect_turns_after": turns,
                                "retaliation": retaliation,
                                "raw": str(decision.get("raw", "")),
                            })

                    if target_before and "proc_torpor" in _effects(target_before):
                        torpor_carrier_attacks_on_sleeping_target += 1
                        primary_damage = sum(
                            int(command.amount or 0)
                            for command in commands
                            if command.opcode == "DAMAGE"
                            and command.actor_uid is not None and int(command.actor_uid) == actor_uid
                            and command.target_uid is not None and int(command.target_uid) == target_uid
                        )
                        if len(torpor_carrier_sleeping_damage) < 60:
                            torpor_carrier_sleeping_damage.append({
                                "battle_id": str(decision.get("battle_id", battle_dir.name)),
                                "decision_index": int(decision.get("decision_index", -1)),
                                "server_turn": int(decision.get("server_turn", -1)),
                                "actor_uid": actor_uid,
                                "actor_creature_id": int(actor.get("creature_id", -1)),
                                "actor_count": int(actor.get("count", 0)),
                                "actor_attack": float(actor.get("attack", 0.0)),
                                "actor_min_damage": float(actor.get("min_damage", 0.0)),
                                "actor_max_damage": float(actor.get("max_damage", 0.0)),
                                "target_uid": target_uid,
                                "target_defense": float(target_before.get("defense", 0.0)),
                                "damage": primary_damage,
                                "raw": str(decision.get("raw", "")),
                            })

                # Wake-up population: target starts asleep and actually receives positive raw DAMAGE.
                for sleeping in before:
                    if "proc_torpor" not in _effects(sleeping) or not bool(sleeping.get("alive", False)):
                        continue
                    uid = int(sleeping.get("uid", -1))
                    incoming = [
                        command
                        for command in commands
                        if command.opcode == "DAMAGE"
                        and command.target_uid is not None and int(command.target_uid) == uid
                        and int(command.amount or 0) > 0
                    ]
                    if not incoming:
                        continue
                    sleeping_after = _by_uid(after, uid)
                    sleep_before_damage_rows += 1
                    before_turns = dict(sleeping.get("effect_turns") or {}).get("proc_torpor")
                    after_turns = dict(sleeping_after.get("effect_turns") or {}).get("proc_torpor") if sleeping_after else None
                    wake_effect_before[str(before_turns)] += 1
                    wake_effect_after[str(after_turns)] += 1
                    removed = sleeping_after is None or "proc_torpor" not in _effects(sleeping_after)
                    sleep_before_damage_effect_removed += int(removed)
                    attackers = {
                        int(command.actor_uid)
                        for command in incoming
                        if command.actor_uid is not None
                    }
                    retaliation = any(
                        command.opcode == "DAMAGE"
                        and command.actor_uid is not None and int(command.actor_uid) == uid
                        and command.target_uid is not None and int(command.target_uid) in attackers
                        for command in commands
                    )
                    sleep_before_damage_retaliation += int(retaliation)
                    if len(wake_examples) < 80:
                        wake_examples.append({
                            "battle_id": str(decision.get("battle_id", battle_dir.name)),
                            "decision_index": int(decision.get("decision_index", -1)),
                            "server_turn": int(decision.get("server_turn", -1)),
                            "active_actor_uid": actor_uid,
                            "sleeping_uid": uid,
                            "effect_turns_before": before_turns,
                            "effect_turns_after": after_turns,
                            "effect_removed": removed,
                            "incoming_damage": [str(command.raw) for command in incoming],
                            "retaliation_to_waking_attacker": retaliation,
                            "raw": str(decision.get("raw", "")),
                        })
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_tor_signal_effect_eligibility_wake_and_retaliation",
        "corpus_battle_dirs": len(battle_dirs),
        "carrier_melee_attacks": carrier_melee_attacks,
        "observed_proc_attacks": observed_proc_attacks,
        "proc_signal_codes": _counter(proc_signal_codes),
        "proc_target_ability_sets": dict(proc_target_ability_sets.most_common(40)),
        "proc_target_ineligible_tags": _counter(proc_target_ineligible_tags),
        "proc_effect_after": _counter(proc_effect_after),
        "proc_effect_turns_after": _counter(proc_effect_turns_after),
        "proc_with_immediate_retaliation": proc_with_immediate_retaliation,
        "proc_examples": proc_examples,
        "wake": {
            "sleep_before_positive_damage_rows": sleep_before_damage_rows,
            "effect_removed": sleep_before_damage_effect_removed,
            "retaliation_to_waking_attacker": sleep_before_damage_retaliation,
            "effect_turns_before": _counter(wake_effect_before),
            "effect_turns_after": _counter(wake_effect_after),
            "examples": wake_examples,
        },
        "sleeping_target_damage_from_torpor_carrier": {
            "attacks": torpor_carrier_attacks_on_sleeping_target,
            "examples": torpor_carrier_sleeping_damage,
            "status": "max_damage_rule_not_yet_proven",
        },
        "ineligible_context_tags": sorted(INELIGIBLE_TAGS),
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "Raw Stor/tor is used as the observed Torpor signal only for a torpor-tagged melee source and its primary "
            "target. The audit verifies 3-turn effect, eligibility, wake-on-positive-damage and retaliation semantics. "
            "The reference maximum-damage-against-sleeping-target rule remains a separate unresolved consequence and is "
            "not inferred from a few damage magnitudes. Proc probability remains the existing chronological model unless "
            "new holdout evidence justifies change."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Torpor lifecycle and wake evidence.")
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
