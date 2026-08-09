from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from hwm_solver.protocol.replay import (
    STATUS_WIRE_TO_BASE, _spellbook_status_matches, iter_battle_decisions,
    parse_commands, parse_initial_entities,
)


DIRECT_WIRE_TO_NAME = {
    "mfs": "magicfist", "ltn": "lighting", "ice": "icebolt",
    "mar": "magicarrow", "swm": "swarm",
}
FRIENDLY_STATUS = {"fst", "bls", "stn", "dfm", "rgm"}


def _runtime_status_targetable(target: dict, actor: dict, wire: str) -> bool:
    if not target.get("alive") or target.get("is_hero"):
        return False
    abilities = set(target.get("abilities", []))
    if "hidden" in abilities or "warmachine" in abilities or "statix" in abilities:
        return False
    friendly = int(target.get("owner", 0)) == int(actor.get("owner", -1))
    if (wire in FRIENDLY_STATUS) != friendly:
        return False
    if wire == "cnf" and abilities.intersection({"undead", "elemental", "mechanical"}):
        return False
    return True


def _selected_status(commands, hero_entity):
    for c in commands:
        if c.opcode != "SPECIAL" or c.code not in STATUS_WIRE_TO_BASE or not c.value or c.value <= 0:
            continue
        matches = _spellbook_status_matches(hero_entity, c.code, int(c.value))
        if len(matches) == 1:
            name, magnitude, mass = matches[0]
            return {"wire": c.code, "name": name, "mass": mass, "target_uid": c.target_uid,
                    "observed_cost": int(c.value), "magnitude": magnitude}
    return None



def analyze(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    battle_dirs = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: int(p.name))
    split_at = int(len(battle_dirs) * 0.8)
    train_ids = {p.name for p in battle_dirs[:split_at]}

    hero_decisions = 0
    by_type: Counter[str] = Counter()
    psc_multiplicity: Counter[int] = Counter()
    psc_modes: Counter[int] = Counter()
    basic_rows: list[dict] = []
    choice_family: Counter[str] = Counter()
    choice_supported: Counter[str] = Counter()
    choice_split_total: Counter[str] = Counter()
    choice_split_supported: Counter[str] = Counter()
    status_selected: Counter[str] = Counter()
    status_supported: Counter[str] = Counter()

    for battle_dir in battle_dirs:
        init_payload = (battle_dir / "init.txt").read_text(encoding="utf-8", errors="replace")
        initial_entities, _ = parse_initial_entities(init_payload)
        split = "train" if battle_dir.name in train_ids else "heldout"
        for decision in iter_battle_decisions(battle_dir):
            by_uid = {int(e["uid"]): e for e in decision["state_before"]}
            actor = by_uid.get(int(decision["actor_uid"]))
            if not actor or not actor.get("is_hero"):
                continue
            hero_decisions += 1
            by_type[decision["action_type"]] += 1
            commands = parse_commands(decision["raw"])
            initial_hero = initial_entities.get(int(decision["actor_uid"]))
            supported = False
            family = "unsupported"

            if any(c.opcode == "WAIT" for c in commands):
                family = "wait"; supported = True
            elif any(c.opcode == "DEFEND" for c in commands):
                family = "defend"; supported = True
            else:
                psc_all = [c for c in commands if c.opcode == "SPECIAL" and c.code == "psc"]
                if len(psc_all) == 1 and psc_all[0].value == 62:
                    family = "hero_basic"; supported = True
                else:
                    status = _selected_status(commands, initial_hero) if initial_hero else None
                    if status:
                        family = "status_mass" if status["mass"] else "status_single"
                        status_selected[status["name"]] += 1
                        if status["mass"]:
                            supported = any(_runtime_status_targetable(t, actor, status["wire"])
                                            for t in decision["state_before"])
                        else:
                            target = by_uid.get(int(status["target_uid"])) if status["target_uid"] is not None else None
                            supported = bool(target and _runtime_status_targetable(target, actor, status["wire"]))
                        if supported:
                            status_supported[status["name"]] += 1
                    else:
                        direct = [c for c in commands if c.opcode == "SPECIAL" and c.code in DIRECT_WIRE_TO_NAME]
                        if len(direct) == 1 and initial_hero:
                            spell_name = DIRECT_WIRE_TO_NAME[direct[0].code]
                            # Runtime has a direct spell iff it is present in the server spellbook.
                            names = {x for x in initial_hero.magic_blob.split("-")[::7]}
                            target = by_uid.get(int(direct[0].target_uid)) if direct[0].target_uid is not None else None
                            family = "direct_damage"
                            supported = spell_name in names and bool(target and target.get("alive") and not target.get("is_hero"))
                            if direct[0].code == "swm" and target:
                                abilities = set(target.get("abilities", []))
                                supported = supported and not abilities.intersection({"undead", "elemental", "mechanical", "warmachine"})

            choice_family[family] += 1
            choice_split_total[split] += 1
            if supported:
                choice_supported[family] += 1
                choice_split_supported[split] += 1

            psc = [c for c in commands if c.opcode == "SPECIAL" and c.code == "psc"]
            if psc:
                psc_multiplicity[len(psc)] += 1
            for command in psc:
                if command.value is not None:
                    psc_modes[int(command.value)] += 1
            if len(psc) != 1 or psc[0].value != 62:
                continue
            command = psc[0]
            target = by_uid.get(int(command.target_uid)) if command.target_uid is not None else None
            expected = 16 + 4 * int(actor.get("max_count", 0))
            basic_rows.append({
                "battle_id": battle_dir.name,
                "split": "train" if battle_dir.name in train_ids else "heldout",
                "side": decision["side"],
                "actor_uid": int(actor["uid"]),
                "actor_creature_id": int(actor["creature_id"]),
                "actor_max_count": int(actor.get("max_count", 0)),
                "target_uid": int(command.target_uid) if command.target_uid is not None else None,
                "target_creature_id": int(target["creature_id"]) if target else None,
                "target_is_enemy": bool(target and int(target["owner"]) != int(actor["owner"])),
                "target_is_hero": bool(target and target.get("is_hero")),
                "target_is_phantom": bool(target and target.get("is_phantom")),
                "target_is_statix": bool(target and "statix" in set(target.get("abilities", []))),
                "target_is_warmachine": bool(target and "warmachine" in set(target.get("abilities", []))),
                "observed_damage": int(command.amount or 0),
                "formula_damage": expected,
                "formula_exact": int(command.amount or 0) == expected,
            })

    split_counts = Counter(row["split"] for row in basic_rows)
    exact_counts = Counter(row["split"] for row in basic_rows if row["formula_exact"])
    return {
        "battles": len(battle_dirs),
        "hero_decisions": hero_decisions,
        "hero_action_type_counts": dict(by_type),
        "psc_decision_multiplicity": {str(k): v for k, v in sorted(psc_multiplicity.items())},
        "psc_mode_counts": {str(k): v for k, v in sorted(psc_modes.items())},
        "basic_attack_mode": 62,
        "basic_attack_samples": len(basic_rows),
        "basic_attack_train_samples": split_counts["train"],
        "basic_attack_heldout_samples": split_counts["heldout"],
        "basic_attack_formula": "damage = 16 + 4 * actor.max_count",
        "basic_attack_formula_exact": sum(row["formula_exact"] for row in basic_rows),
        "basic_attack_formula_exact_train": exact_counts["train"],
        "basic_attack_formula_exact_heldout": exact_counts["heldout"],
        "basic_attack_enemy_targets": sum(row["target_is_enemy"] for row in basic_rows),
        "basic_attack_target_hero": sum(row["target_is_hero"] for row in basic_rows),
        "basic_attack_target_phantom": sum(row["target_is_phantom"] for row in basic_rows),
        "basic_attack_target_statix": sum(row["target_is_statix"] for row in basic_rows),
        "basic_attack_target_warmachine": sum(row["target_is_warmachine"] for row in basic_rows),
        "basic_attack_actor_creature_ids": dict(Counter(str(row["actor_creature_id"]) for row in basic_rows)),
        "historical_choice_family_counts": dict(choice_family),
        "historical_choice_supported_counts": dict(choice_supported),
        "historical_choice_coverage": (sum(choice_supported.values()) / hero_decisions) if hero_decisions else 0.0,
        "historical_choice_train_coverage": (choice_split_supported["train"] / choice_split_total["train"]) if choice_split_total["train"] else 0.0,
        "historical_choice_heldout_coverage": (choice_split_supported["heldout"] / choice_split_total["heldout"]) if choice_split_total["heldout"] else 0.0,
        "status_selected_spell_counts": dict(status_selected),
        "status_supported_spell_counts": dict(status_supported),
        "basic_attack_supported": bool(
            basic_rows
            and all(row["formula_exact"] for row in basic_rows)
            and all(row["target_is_enemy"] for row in basic_rows)
            and not any(row["target_is_hero"] or row["target_statix"] or row["target_is_warmachine"] for row in [])
        ),
        "basic_attack_rows": basic_rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    report = analyze(args.corpus)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "basic_attack_rows"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
