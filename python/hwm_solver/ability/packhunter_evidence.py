from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, parse_initial_entities, parse_tooltips


ABILITY = "packhunter"


def _normalize(value: object) -> str:
    return " ".join(html.unescape(str(value or "")).split())


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("abilities") or [])}


def _by_uid(state: list[dict], uid: int | None) -> dict | None:
    if uid is None:
        return None
    return next((e for e in state if int(e.get("uid", -1)) == int(uid)), None)


def _cells(entity: dict) -> set[tuple[int, int]]:
    x, y = int(entity.get("x", 0)), int(entity.get("y", 0))
    side = 2 if "big" in _abilities(entity) else 1
    return {(x + dx, y + dy) for dx in range(side) for dy in range(side)}


def _adjacent(a: dict, b: dict) -> bool:
    return any(
        max(abs(ax - bx), abs(ay - by)) <= 1
        for ax, ay in _cells(a)
        for bx, by in _cells(b)
    )


def _claims(description: str) -> dict:
    lower = description.lower()
    return {
        "percentages": [int(x) for x in re.findall(r"(\d+)\s*%", description)],
        "integers": [int(x) for x in re.findall(r"\b(\d+)\b", description)],
        "mentions_melee": any(x in lower for x in ("ближн", "melee")),
        "mentions_same_creature": any(x in lower for x in ("таких же", "same creature", "same creatures")),
        "mentions_adjacent": any(x in lower for x in ("рядом", "сосед", "adjacent", "near")),
        "mentions_all": any(x in lower for x in ("все другие", "all other")),
        "mentions_simultaneous": any(x in lower for x in ("одновременно", "simultaneous")),
    }


def _counter(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in counter.most_common()}


def _same_creature_allies(state: list[dict], actor: dict) -> list[dict]:
    owner = int(actor.get("owner", -1))
    creature = int(actor.get("creature_id", -1))
    actor_uid = int(actor.get("uid", -1))
    return [
        entity
        for entity in state
        if int(entity.get("uid", -1)) != actor_uid
        and bool(entity.get("alive", False))
        and not bool(entity.get("is_hidden", False))
        and int(entity.get("owner", -2)) == owner
        and int(entity.get("creature_id", -2)) == creature
    ]


def _candidate_helpers(state: list[dict], actor: dict, target: dict) -> list[dict]:
    return [
        entity
        for entity in _same_creature_allies(state, actor)
        if ABILITY in _abilities(entity) and _adjacent(entity, target)
    ]


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
    tooltip_battles = 0
    tooltip_names: Counter[str] = Counter()
    tooltip_descriptions: Counter[str] = Counter()
    tooltip_claim_shapes: Counter[str] = Counter()
    init_examples: list[dict] = []

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

        name = _normalize((tooltips.get("abil_names") or {}).get(ABILITY))
        description = _normalize((tooltips.get("abil_desc") or {}).get(ABILITY))
        if name or description:
            tooltip_battles += 1
            if name:
                tooltip_names[name] += 1
            if description:
                tooltip_descriptions[description] += 1
                tooltip_claim_shapes[json.dumps(_claims(description), ensure_ascii=False, sort_keys=True)] += 1

        uids: set[int] = set()
        rows: list[dict] = []
        for entity in entities.values():
            abilities = {str(x).lower() for x in entity.abilities}
            if ABILITY not in abilities:
                continue
            uid = int(entity.uid)
            uids.add(uid)
            carrier_entities += 1
            carrier_creatures[int(entity.creature_id)] += 1
            carrier_ability_sets[",".join(sorted(abilities)) or "<none>"] += 1
            rows.append(
                {
                    "uid": uid,
                    "owner": int(entity.owner),
                    "creature_id": int(entity.creature_id),
                    "count": int(entity.count),
                    "x": int(entity.x),
                    "y": int(entity.y),
                    "abilities": sorted(abilities),
                }
            )
        if uids:
            carrier_uids[battle_dir.name] = uids
            if len(init_examples) < 25:
                init_examples.append(
                    {
                        "battle_id": battle_dir.name,
                        "carriers": rows,
                        "tooltip_name": name,
                        "tooltip_description": description,
                        "tooltip_claims": _claims(description) if description else {},
                    }
                )

    carrier_melee_attacks = 0
    helper_opportunity_attacks = 0
    opportunity_helper_counts: Counter[int] = Counter()
    observed_helper_counts: Counter[int] = Counter()
    exact_helper_set_attacks = 0
    missing_helper_hits = 0
    extra_same_creature_hits = 0
    helper_damage_hits = 0
    helper_damage_before_primary: Counter[str] = Counter()
    helper_damage_before_retaliation: Counter[str] = Counter()
    helper_source_ability_sets: Counter[str] = Counter()
    extra_source_geometry: Counter[str] = Counter()
    special_codes: Counter[str] = Counter()
    opportunity_examples: list[dict] = []
    no_opportunity_examples: list[dict] = []

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
                carrier_melee_attacks += 1
                helpers = _candidate_helpers(before, actor, target)
                helper_uids = {int(e.get("uid", -1)) for e in helpers}
                same_creature_allies = _same_creature_allies(before, actor)
                same_creature_uids = {int(e.get("uid", -1)) for e in same_creature_allies}
                commands = parse_commands(str(decision.get("raw", "")))
                for c in commands:
                    if c.opcode == "SPECIAL":
                        special_codes[str(c.code)] += 1

                primary_indices = [
                    i for i, c in enumerate(commands)
                    if c.opcode == "DAMAGE" and c.actor_uid == actor_uid and c.target_uid == target_uid
                ]
                retaliation_indices = [
                    i for i, c in enumerate(commands)
                    if c.opcode == "DAMAGE" and c.actor_uid == target_uid and c.target_uid == actor_uid
                ]
                same_creature_records = [
                    (i, c)
                    for i, c in enumerate(commands)
                    if c.opcode == "DAMAGE"
                    and c.actor_uid is not None and int(c.actor_uid) in same_creature_uids
                    and c.target_uid == target_uid
                ]
                observed_helper_uids = {int(c.actor_uid) for _, c in same_creature_records}

                if helpers:
                    helper_opportunity_attacks += 1
                    opportunity_helper_counts[len(helper_uids)] += 1
                    observed_helper_counts[len(observed_helper_uids)] += 1
                    missing = helper_uids - observed_helper_uids
                    extra = observed_helper_uids - helper_uids
                    missing_helper_hits += len(missing)
                    extra_same_creature_hits += len(extra)
                    helper_damage_hits += len(same_creature_records)
                    if observed_helper_uids == helper_uids:
                        exact_helper_set_attacks += 1
                    first_primary = min(primary_indices) if primary_indices else None
                    first_retaliation = min(retaliation_indices) if retaliation_indices else None
                    for index, command in same_creature_records:
                        helper = _by_uid(before, int(command.actor_uid))
                        helper_source_ability_sets[",".join(sorted(_abilities(helper))) or "<none>"] += 1
                        helper_damage_before_primary[str(first_primary is not None and index < first_primary)] += 1
                        helper_damage_before_retaliation[str(first_retaliation is None or index < first_retaliation)] += 1
                        if helper and int(command.actor_uid) in extra:
                            extra_source_geometry[
                                f"ability={ABILITY in _abilities(helper)}|adjacent={_adjacent(helper, target)}"
                            ] += 1
                    if len(opportunity_examples) < 80:
                        opportunity_examples.append(
                            {
                                "battle_id": str(decision.get("battle_id", battle_dir.name)),
                                "decision_index": int(decision.get("decision_index", -1)),
                                "server_turn": int(decision.get("server_turn", -1)),
                                "actor_uid": actor_uid,
                                "actor_creature_id": int(actor.get("creature_id", -1)),
                                "actor_abilities": sorted(_abilities(actor)),
                                "target_uid": target_uid,
                                "target_creature_id": int(target.get("creature_id", -1)),
                                "candidate_helper_uids": sorted(helper_uids),
                                "observed_same_creature_helper_uids": sorted(observed_helper_uids),
                                "missing_helper_uids": sorted(missing),
                                "extra_helper_uids": sorted(extra),
                                "helper_damage": [
                                    {
                                        "index": index,
                                        "source_uid": int(c.actor_uid),
                                        "amount": int(c.amount or 0),
                                        "raw": str(c.raw),
                                    }
                                    for index, c in same_creature_records
                                ],
                                "primary_damage_indices": primary_indices,
                                "retaliation_indices": retaliation_indices,
                                "raw": str(decision.get("raw", "")),
                            }
                        )
                elif len(no_opportunity_examples) < 50:
                    no_opportunity_examples.append(
                        {
                            "battle_id": str(decision.get("battle_id", battle_dir.name)),
                            "decision_index": int(decision.get("decision_index", -1)),
                            "server_turn": int(decision.get("server_turn", -1)),
                            "actor_uid": actor_uid,
                            "actor_creature_id": int(actor.get("creature_id", -1)),
                            "target_uid": target_uid,
                            "raw": str(decision.get("raw", "")),
                        }
                    )
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_melee_same_creature_adjacent_assist",
        "corpus_battle_dirs": len(battle_dirs),
        "carrier_battles": len(carrier_uids),
        "carrier_entities": carrier_entities,
        "carrier_creatures": _counter(carrier_creatures),
        "carrier_ability_sets": _counter(carrier_ability_sets),
        "tooltip_battles": tooltip_battles,
        "tooltip_names": _counter(tooltip_names),
        "tooltip_descriptions": _counter(tooltip_descriptions),
        "tooltip_claim_shapes": [
            {"count": int(count), "claims": json.loads(raw)}
            for raw, count in tooltip_claim_shapes.most_common()
        ],
        "carrier_melee_attacks": carrier_melee_attacks,
        "helper_opportunity_attacks": helper_opportunity_attacks,
        "opportunity_helper_counts": _counter(opportunity_helper_counts),
        "observed_helper_counts": _counter(observed_helper_counts),
        "exact_helper_set_attacks": exact_helper_set_attacks,
        "missing_helper_hits": missing_helper_hits,
        "extra_same_creature_hits": extra_same_creature_hits,
        "extra_source_geometry": _counter(extra_source_geometry),
        "helper_damage_hits": helper_damage_hits,
        "helper_damage_before_primary": _counter(helper_damage_before_primary),
        "helper_damage_before_retaliation": _counter(helper_damage_before_retaliation),
        "helper_source_ability_sets": _counter(helper_source_ability_sets),
        "special_codes": _counter(special_codes),
        "opportunity_examples": opportunity_examples,
        "no_opportunity_examples": no_opportunity_examples,
        "init_examples": init_examples,
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "The adjacent same-owner same-creature carrier set is a geometry candidate, not a guaranteed Pack Hunter "
            "truth label. Observed secondary sources are collected independently from all same-owner/same-creature "
            "stacks before comparison, so extra sources are auditable. Exact support requires corpus agreement that "
            "every eligible helper contributes exactly one same-target attack with no unexplained sources, plus "
            "independently proven damage/retaliation ordering."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Pack Hunter assist evidence.")
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
