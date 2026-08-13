from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, parse_initial_entities


ENT_ANY = re.compile(r"^Sent([0-9]+)$")


def _counter(counter: Counter) -> dict[str, int]:
    return {str(key): int(value) for key, value in counter.most_common()}


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(value).lower() for value in (entity.get("abilities") or [])}


def _by_uid(state: list[dict], uid: int) -> dict | None:
    return next((entity for entity in state if int(entity.get("uid", -1)) == int(uid)), None)


def _source_class(abilities: set[str]) -> str:
    has_spider = "spider" in abilities
    has_entroots = "entroots" in abilities
    if has_spider and has_entroots:
        return "spider_and_entroots"
    if has_entroots:
        return "entroots_without_spider"
    if has_spider:
        return "spider_without_entroots"
    return "neither"


def analyze_corpus(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    if not root.is_dir():
        raise FileNotFoundError(root)
    battle_dirs = sorted(
        (path for path in root.iterdir() if path.is_dir()),
        key=lambda path: (0, int(path.name)) if path.name.isdigit() else (1, path.name),
    )

    parse_errors: list[str] = []
    initial_spider_entities = 0
    initial_spider_with_entroots = 0
    initial_spider_without_entroots = 0
    initial_spider_ability_sets: Counter[str] = Counter()

    for battle_dir in battle_dirs:
        init_path = battle_dir / "init.txt"
        if not init_path.exists():
            continue
        try:
            entities, warnings = parse_initial_entities(
                init_path.read_text(encoding="utf-8", errors="replace")
            )
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:init:{type(exc).__name__}:{exc}")
            continue
        if warnings:
            parse_errors.extend(f"{battle_dir.name}:init_warning:{warning}" for warning in warnings)
        for entity in entities.values():
            abilities = {str(value).lower() for value in entity.abilities}
            if "spider" not in abilities:
                continue
            initial_spider_entities += 1
            initial_spider_ability_sets[",".join(sorted(abilities)) or "<none>"] += 1
            if "entroots" in abilities:
                initial_spider_with_entroots += 1
            else:
                initial_spider_without_entroots += 1

    ent_records = 0
    ent_battles: set[str] = set()
    non_numeric_ent_records = 0
    payload_lengths: Counter[str] = Counter()
    trailers: Counter[str] = Counter()
    parser_actor_matches_first_uid = 0
    parser_actor_mismatches_first_uid = 0
    parser_target_uid_none = 0
    parser_target_uid_present = 0
    zero_source_records = 0
    nonzero_source_records = 0
    source_missing_records = 0
    source_ability_sets: Counter[str] = Counter()
    source_ability_classes: Counter[str] = Counter()
    zero_target_records = 0
    nonzero_target_records = 0
    target_missing_before_and_after = 0
    target_present_before = 0
    target_present_after = 0
    owner_relations: Counter[str] = Counter()
    examples: list[dict] = []

    for battle_dir in battle_dirs:
        try:
            for decision in iter_battle_decisions(battle_dir):
                before = list(decision.get("state_before") or [])
                after = list(decision.get("state_after") or [])
                for command in parse_commands(str(decision.get("raw", ""))):
                    if command.opcode != "SPECIAL" or command.code != "ent":
                        continue
                    ent_records += 1
                    ent_battles.add(battle_dir.name)
                    if command.target_uid is None:
                        parser_target_uid_none += 1
                    else:
                        parser_target_uid_present += 1

                    match = ENT_ANY.fullmatch(str(command.raw))
                    if not match:
                        non_numeric_ent_records += 1
                        if len(examples) < 40:
                            examples.append(
                                {
                                    "battle_id": battle_dir.name,
                                    "decision_index": int(decision.get("decision_index", -1)),
                                    "raw": str(command.raw),
                                    "kind": "non_numeric",
                                }
                            )
                        continue

                    payload = match.group(1)
                    payload_lengths[str(len(payload))] += 1
                    first_uid = int(payload[:3]) if len(payload) >= 3 else None
                    if first_uid is not None and command.actor_uid is not None and int(command.actor_uid) == first_uid:
                        parser_actor_matches_first_uid += 1
                    else:
                        parser_actor_mismatches_first_uid += 1

                    source_uid = int(payload[:3]) if len(payload) >= 3 else None
                    target_uid = int(payload[3:6]) if len(payload) >= 6 else None
                    trailer = payload[6:] if len(payload) >= 6 else ""
                    trailers[trailer] += 1

                    source = None
                    source_class = "unavailable"
                    source_abilities: list[str] = []
                    if source_uid == 0:
                        zero_source_records += 1
                    elif source_uid is not None:
                        nonzero_source_records += 1
                        source = _by_uid(before, source_uid) or _by_uid(after, source_uid)
                        if source is None:
                            source_missing_records += 1
                        else:
                            abilities = _abilities(source)
                            source_abilities = sorted(abilities)
                            source_ability_sets[",".join(source_abilities) or "<none>"] += 1
                            source_class = _source_class(abilities)
                            source_ability_classes[source_class] += 1

                    target_before = None
                    target_after = None
                    if target_uid == 0:
                        zero_target_records += 1
                    elif target_uid is not None:
                        nonzero_target_records += 1
                        target_before = _by_uid(before, target_uid)
                        target_after = _by_uid(after, target_uid)
                        if target_before is not None:
                            target_present_before += 1
                        if target_after is not None:
                            target_present_after += 1
                        if target_before is None and target_after is None:
                            target_missing_before_and_after += 1

                    target_for_owner = target_before or target_after
                    if source is not None and target_for_owner is not None:
                        owner_relations[
                            "same_owner"
                            if int(source.get("owner", -1)) == int(target_for_owner.get("owner", -2))
                            else "other_owner"
                        ] += 1

                    if len(examples) < 40:
                        examples.append(
                            {
                                "battle_id": battle_dir.name,
                                "decision_index": int(decision.get("decision_index", -1)),
                                "server_turn": int(decision.get("server_turn", -1)),
                                "decision_actor_uid": int(decision.get("actor_uid", -1)),
                                "action_type": str(decision.get("action_type", "")),
                                "raw": str(command.raw),
                                "payload_length": len(payload),
                                "source_uid": source_uid,
                                "target_uid": target_uid,
                                "trailer": trailer,
                                "source_class": source_class,
                                "source_abilities": source_abilities,
                                "target_present_before": target_before is not None,
                                "target_present_after": target_after is not None,
                            }
                        )
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    return {
        "evidence_scope": "corpus_wide_raw_Sent_wire_and_source_ability_controls",
        "corpus_battle_dirs": len(battle_dirs),
        "initial_spider_entities": initial_spider_entities,
        "initial_spider_with_entroots": initial_spider_with_entroots,
        "initial_spider_without_entroots": initial_spider_without_entroots,
        "initial_spider_ability_sets": _counter(initial_spider_ability_sets),
        "ent_battles": len(ent_battles),
        "ent_records": ent_records,
        "non_numeric_ent_records": non_numeric_ent_records,
        "payload_lengths": _counter(payload_lengths),
        "trailers": _counter(trailers),
        "parser_actor_matches_first_uid": parser_actor_matches_first_uid,
        "parser_actor_mismatches_first_uid": parser_actor_mismatches_first_uid,
        "parser_target_uid_none": parser_target_uid_none,
        "parser_target_uid_present": parser_target_uid_present,
        "zero_source_records": zero_source_records,
        "nonzero_source_records": nonzero_source_records,
        "source_missing_records": source_missing_records,
        "source_ability_sets": _counter(source_ability_sets),
        "source_ability_classes": _counter(source_ability_classes),
        "zero_target_records": zero_target_records,
        "nonzero_target_records": nonzero_target_records,
        "target_missing_before_and_after": target_missing_before_and_after,
        "target_present_before": target_present_before,
        "target_present_after": target_present_after,
        "owner_relations": _counter(owner_relations),
        "examples": examples,
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "Sent is raw code 'ent', not a Spider label. Every observed Spider carrier must be checked for "
            "co-present entroots, and source controls outside Spider are required before assigning Sent to Spider. "
            "Decoding source3/target3/trailer9 structurally does not itself create a runtime mechanic."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit raw Sent wire structure and Spider/Entroots attribution controls.")
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
