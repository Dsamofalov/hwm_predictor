from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, parse_initial_entities, parse_tooltips


ABILITY = "shieldguard"
ATTACK_TYPES = frozenset({"MELEE_ATTACK", "RANGED_ATTACK"})


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
        "mentions_physical": any(x in lower for x in ("физичес", "physical")),
        "mentions_adjacent": any(x in lower for x in ("сосед", "adjacent")),
        "mentions_friendly": any(x in lower for x in ("дружеств", "friendly", "ally")),
        "mentions_equal_parts": any(x in lower for x in ("равные част", "equal part")),
        "mentions_half_guard_share": any(x in lower for x in ("половин", "half")),
    }


def _counter(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in counter.most_common()}


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
            rows.append({"uid": uid, "owner": int(entity.owner), "creature_id": int(entity.creature_id), "count": int(entity.count), "x": int(entity.x), "y": int(entity.y), "abilities": sorted(abilities)})
        if uids:
            carrier_uids[battle_dir.name] = uids
            if len(init_examples) < 25:
                init_examples.append({"battle_id": battle_dir.name, "carriers": rows, "tooltip_name": name, "tooltip_description": description, "tooltip_claims": _claims(description) if description else {}})

    physical_attacks_in_carrier_battles = 0
    guard_opportunity_attacks = 0
    opportunity_action_types: Counter[str] = Counter()
    candidate_guard_counts: Counter[int] = Counter()
    observed_guard_counts: Counter[int] = Counter()
    exact_guard_set_attacks = 0
    missing_guard_hits = 0
    extra_guard_hits = 0
    extra_guard_geometry: Counter[str] = Counter()
    target_damage_missing = 0
    guard_to_target_damage_ratio: Counter[str] = Counter()
    guard_damage_rounding_delta: Counter[str] = Counter()
    guard_source_ability_sets: Counter[str] = Counter()
    special_codes: Counter[str] = Counter()
    examples: list[dict] = []

    for battle_dir in battle_dirs:
        carriers = carrier_uids.get(battle_dir.name)
        if not carriers:
            continue
        try:
            for decision in iter_battle_decisions(battle_dir):
                action_type = str(decision.get("action_type", ""))
                if action_type not in ATTACK_TYPES:
                    continue
                before = list(decision.get("state_before") or [])
                actor_uid = int(decision.get("actor_uid", -1))
                actor = _by_uid(before, actor_uid)
                target_raw = decision.get("target_uid")
                target_uid = int(target_raw) if target_raw is not None else None
                target = _by_uid(before, target_uid)
                if not actor or not target:
                    continue
                physical_attacks_in_carrier_battles += 1
                target_owner = int(target.get("owner", -1))
                if target_owner == int(actor.get("owner", -2)):
                    continue
                all_live_guards = [
                    entity for entity in before
                    if int(entity.get("uid", -1)) in carriers
                    and int(entity.get("uid", -1)) != target_uid
                    and bool(entity.get("alive", False))
                    and int(entity.get("owner", -1)) == target_owner
                ]
                all_guard_uids = {int(entity.get("uid", -1)) for entity in all_live_guards}
                candidates = [entity for entity in all_live_guards if not bool(entity.get("is_hidden", False)) and _adjacent(entity, target)]
                if not candidates:
                    continue
                guard_opportunity_attacks += 1
                opportunity_action_types[action_type] += 1
                candidate_uids = {int(entity.get("uid", -1)) for entity in candidates}
                candidate_guard_counts[len(candidate_uids)] += 1

                commands = parse_commands(str(decision.get("raw", "")))
                for command in commands:
                    if command.opcode == "SPECIAL":
                        special_codes[str(command.code)] += 1
                actor_damage = [command for command in commands if command.opcode == "DAMAGE" and command.actor_uid is not None and int(command.actor_uid) == actor_uid and command.target_uid is not None]
                target_amounts = [int(command.amount or 0) for command in actor_damage if int(command.target_uid) == target_uid]
                target_damage = target_amounts[0] if target_amounts else None
                if target_damage is None:
                    target_damage_missing += 1
                observed_guard_records = [command for command in actor_damage if int(command.target_uid) in all_guard_uids]
                observed_uids = {int(command.target_uid) for command in observed_guard_records}
                observed_guard_counts[len(observed_uids)] += 1
                missing = candidate_uids - observed_uids
                extra = observed_uids - candidate_uids
                missing_guard_hits += len(missing)
                extra_guard_hits += len(extra)
                if observed_uids == candidate_uids:
                    exact_guard_set_attacks += 1

                guard_rows = []
                for command in observed_guard_records:
                    uid = int(command.target_uid)
                    guard = _by_uid(before, uid)
                    amount = int(command.amount or 0)
                    guard_source_ability_sets[",".join(sorted(_abilities(guard))) or "<none>"] += 1
                    if uid in extra and guard:
                        extra_guard_geometry[f"hidden={bool(guard.get('is_hidden', False))}|adjacent={_adjacent(guard, target)}"] += 1
                    if target_damage and target_damage > 0:
                        guard_to_target_damage_ratio[f"{amount / target_damage:.3f}"] += 1
                        guard_damage_rounding_delta[str(2 * amount - target_damage)] += 1
                    guard_rows.append({"uid": uid, "creature_id": int(guard.get("creature_id", -1)) if guard else None, "abilities": sorted(_abilities(guard)), "candidate": uid in candidate_uids, "damage": amount, "ratio_to_target": amount / target_damage if target_damage else None, "twice_guard_minus_target": 2 * amount - target_damage if target_damage is not None else None, "raw": str(command.raw)})

                if len(examples) < 100:
                    examples.append({"battle_id": str(decision.get("battle_id", battle_dir.name)), "decision_index": int(decision.get("decision_index", -1)), "server_turn": int(decision.get("server_turn", -1)), "action_type": action_type, "actor_uid": actor_uid, "actor_creature_id": int(actor.get("creature_id", -1)), "actor_abilities": sorted(_abilities(actor)), "target_uid": target_uid, "target_creature_id": int(target.get("creature_id", -1)), "target_damage": target_damage, "candidate_guard_uids": sorted(candidate_uids), "observed_guard_uids": sorted(observed_uids), "missing_guard_uids": sorted(missing), "extra_guard_uids": sorted(extra), "guard_damage": guard_rows, "raw": str(decision.get("raw", ""))})
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_adjacent_friendly_guard_damage_sharing",
        "corpus_battle_dirs": len(battle_dirs),
        "carrier_battles": len(carrier_uids),
        "carrier_entities": carrier_entities,
        "carrier_creatures": _counter(carrier_creatures),
        "carrier_ability_sets": _counter(carrier_ability_sets),
        "tooltip_battles": tooltip_battles,
        "tooltip_names": _counter(tooltip_names),
        "tooltip_descriptions": _counter(tooltip_descriptions),
        "tooltip_claim_shapes": [{"count": int(count), "claims": json.loads(raw)} for raw, count in tooltip_claim_shapes.most_common()],
        "physical_attacks_in_carrier_battles": physical_attacks_in_carrier_battles,
        "guard_opportunity_attacks": guard_opportunity_attacks,
        "opportunity_action_types": _counter(opportunity_action_types),
        "candidate_guard_counts": _counter(candidate_guard_counts),
        "observed_guard_counts": _counter(observed_guard_counts),
        "exact_guard_set_attacks": exact_guard_set_attacks,
        "missing_guard_hits": missing_guard_hits,
        "extra_guard_hits": extra_guard_hits,
        "extra_guard_geometry": _counter(extra_guard_geometry),
        "target_damage_missing": target_damage_missing,
        "guard_to_target_damage_ratio": _counter(guard_to_target_damage_ratio),
        "twice_guard_damage_minus_target_damage": _counter(guard_damage_rounding_delta),
        "guard_ability_sets": _counter(guard_source_ability_sets),
        "special_codes": _counter(special_codes),
        "examples": examples,
        "init_examples": init_examples,
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "Eligible adjacent guards and observed attacker-source DAMAGE to all live same-owner Shield Guard carriers are "
            "collected independently, so missing/extra sources are auditable. Exact sharing requires exact guard-set agreement "
            "and a consistent half-share rounding rule after excluding concurrent collateral/reflect mechanics. The server "
            "tooltip, not historical reference text, remains the final rule source."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Shield Guard damage-sharing evidence.")
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
