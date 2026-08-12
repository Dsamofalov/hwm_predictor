from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, parse_initial_entities, parse_tooltips


ABILITY = "taunt"
ATTACK_TYPES = {"MELEE_ATTACK", "RANGED_ATTACK"}


def _normalize(value: object) -> str:
    return " ".join(html.unescape(str(value or "")).split())


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("abilities") or [])}


def _by_uid(state: list[dict], uid: int) -> dict | None:
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
        "mentions_chance": any(x in lower for x in ("шанс", "chance")),
        "mentions_attack": any(x in lower for x in ("атак", "attack")),
        "mentions_friendly": any(x in lower for x in ("дружеств", "союз", "friendly", "ally")),
        "mentions_adjacent": any(x in lower for x in ("сосед", "рядом", "adjacent", "nearby")),
        "mentions_redirect": any(x in lower for x in ("отвлеч", "перенаправ", "redirect", "distract")),
    }


def _counter(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in counter.most_common()}


def _special_row(command, by_uid: dict[int, dict]) -> dict:
    source = by_uid.get(int(command.actor_uid)) if command.actor_uid is not None else None
    target = by_uid.get(int(command.target_uid)) if command.target_uid is not None else None
    return {
        "raw": str(command.raw),
        "code": str(command.code),
        "actor_uid": int(command.actor_uid) if command.actor_uid is not None else None,
        "actor_abilities": sorted(_abilities(source)),
        "target_uid": int(command.target_uid) if command.target_uid is not None else None,
        "target_abilities": sorted(_abilities(target)),
        "value": int(command.value) if command.value is not None else None,
        "amount": int(command.amount) if command.amount is not None else None,
    }


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
    carrier_owners: Counter[int] = Counter()
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

        rows = []
        uids: set[int] = set()
        for entity in entities.values():
            abilities = {str(x).lower() for x in entity.abilities}
            if ABILITY not in abilities:
                continue
            uid = int(entity.uid)
            uids.add(uid)
            carrier_entities += 1
            carrier_creatures[int(entity.creature_id)] += 1
            carrier_owners[int(entity.owner)] += 1
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
            if len(init_examples) < 20:
                init_examples.append(
                    {
                        "battle_id": battle_dir.name,
                        "carriers": rows,
                        "tooltip_name": name,
                        "tooltip_description": description,
                        "tooltip_claims": _claims(description) if description else {},
                    }
                )

    attacks_seen = 0
    attacks_targeting_carrier = 0
    attacks_targeting_carrier_with_adjacent_ally = 0
    attacks_targeting_adjacent_ally = 0
    carrier_ally_opportunities = 0
    target_action_types: Counter[str] = Counter()
    carrier_involved_special_codes: Counter[str] = Counter()
    opportunity_special_codes: Counter[str] = Counter()
    special_code_contexts: dict[str, Counter[str]] = defaultdict(Counter)
    target_geometry: Counter[str] = Counter()
    direct_examples: list[dict] = []
    ally_examples: list[dict] = []

    for battle_dir in battle_dirs:
        carriers = carrier_uids.get(battle_dir.name)
        if not carriers:
            continue
        try:
            for decision in iter_battle_decisions(battle_dir):
                action_type = str(decision.get("action_type", ""))
                if action_type not in ATTACK_TYPES:
                    continue
                attacks_seen += 1
                before = list(decision.get("state_before") or [])
                by_uid = {int(e.get("uid", -1)): e for e in before}
                actor_uid = int(decision.get("actor_uid", -1))
                actor = by_uid.get(actor_uid)
                target_uid_raw = decision.get("target_uid")
                target_uid = int(target_uid_raw) if target_uid_raw is not None else None
                target = by_uid.get(target_uid) if target_uid is not None else None
                if not actor or not target:
                    continue
                commands = parse_commands(str(decision.get("raw", "")))
                specials = [c for c in commands if c.opcode == "SPECIAL"]

                relevant_carriers = [
                    by_uid[uid]
                    for uid in carriers
                    if uid in by_uid
                    and bool(by_uid[uid].get("alive", False))
                    and int(by_uid[uid].get("owner", -1)) != int(actor.get("owner", -2))
                ]
                if not relevant_carriers:
                    continue

                direct_carrier = target_uid in carriers
                carrier_adjacent_allies: dict[int, list[int]] = {}
                for carrier in relevant_carriers:
                    carrier_uid = int(carrier.get("uid", -1))
                    allies = [
                        int(e.get("uid", -1))
                        for e in before
                        if int(e.get("uid", -1)) != carrier_uid
                        and bool(e.get("alive", False))
                        and not bool(e.get("is_hidden", False))
                        and int(e.get("owner", -1)) == int(carrier.get("owner", -2))
                        and _adjacent(carrier, e)
                    ]
                    if allies:
                        carrier_adjacent_allies[carrier_uid] = allies

                if carrier_adjacent_allies:
                    carrier_ally_opportunities += 1

                context = None
                if direct_carrier:
                    attacks_targeting_carrier += 1
                    target_action_types[action_type] += 1
                    if target_uid in carrier_adjacent_allies:
                        attacks_targeting_carrier_with_adjacent_ally += 1
                        context = "carrier_target_with_adjacent_ally"
                        target_geometry[str(len(carrier_adjacent_allies[target_uid]))] += 1
                else:
                    adjacent_carriers = [
                        carrier_uid
                        for carrier_uid, allies in carrier_adjacent_allies.items()
                        if target_uid in allies
                    ]
                    if adjacent_carriers:
                        attacks_targeting_adjacent_ally += 1
                        context = "adjacent_ally_target"

                if context is None:
                    continue

                for special in specials:
                    source_uid = int(special.actor_uid) if special.actor_uid is not None else None
                    special_target_uid = int(special.target_uid) if special.target_uid is not None else None
                    involved = source_uid in carriers or special_target_uid in carriers
                    if involved:
                        carrier_involved_special_codes[str(special.code)] += 1
                    opportunity_special_codes[str(special.code)] += 1
                    special_code_contexts[str(special.code)][context] += 1

                row = {
                    "battle_id": str(decision.get("battle_id", battle_dir.name)),
                    "decision_index": int(decision.get("decision_index", -1)),
                    "server_turn": int(decision.get("server_turn", -1)),
                    "action_type": action_type,
                    "actor_uid": actor_uid,
                    "actor_owner": int(actor.get("owner", -1)),
                    "actor_abilities": sorted(_abilities(actor)),
                    "target_uid": target_uid,
                    "target_owner": int(target.get("owner", -1)),
                    "target_abilities": sorted(_abilities(target)),
                    "carrier_adjacent_allies": {str(k): v for k, v in carrier_adjacent_allies.items()},
                    "specials": [_special_row(c, by_uid) for c in specials],
                    "raw": str(decision.get("raw", "")),
                }
                if context == "carrier_target_with_adjacent_ally" and len(direct_examples) < 50:
                    direct_examples.append(row)
                elif context == "adjacent_ally_target" and len(ally_examples) < 50:
                    ally_examples.append(row)
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_targeting_context_and_server_tooltip",
        "corpus_battle_dirs": len(battle_dirs),
        "carrier_battles": len(carrier_uids),
        "carrier_entities": carrier_entities,
        "carrier_creatures": _counter(carrier_creatures),
        "carrier_ability_sets": _counter(carrier_ability_sets),
        "carrier_owners": _counter(carrier_owners),
        "tooltip_battles": tooltip_battles,
        "tooltip_names": _counter(tooltip_names),
        "tooltip_descriptions": _counter(tooltip_descriptions),
        "tooltip_claim_shapes": [
            {"count": int(count), "claims": json.loads(raw)}
            for raw, count in tooltip_claim_shapes.most_common()
        ],
        "attacks_seen_in_carrier_battles": attacks_seen,
        "carrier_ally_opportunities": carrier_ally_opportunities,
        "attacks_targeting_carrier": attacks_targeting_carrier,
        "attacks_targeting_carrier_with_adjacent_ally": attacks_targeting_carrier_with_adjacent_ally,
        "attacks_targeting_adjacent_ally": attacks_targeting_adjacent_ally,
        "target_action_types": _counter(target_action_types),
        "carrier_involved_special_codes": _counter(carrier_involved_special_codes),
        "opportunity_special_codes": _counter(opportunity_special_codes),
        "special_code_contexts": {
            code: _counter(counter) for code, counter in sorted(special_code_contexts.items())
        },
        "adjacent_ally_count_when_carrier_targeted": _counter(target_geometry),
        "direct_carrier_examples": direct_examples,
        "adjacent_ally_examples": ally_examples,
        "init_examples": init_examples,
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "An enemy attack ending on a Taunt carrier is not a proc label. The original intended target is not "
            "assumed from final DAMAGE. A Taunt proc requires a carrier-specific raw discriminator that distinguishes "
            "redirected attacks from ordinary direct attacks; adjacent-ally attacks are kept as separate controls."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Taunt targeting evidence.")
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
