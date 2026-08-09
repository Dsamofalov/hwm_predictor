from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

from hwm_solver.protocol.replay import parse_initial_entities, parse_turns

SPELLS = {
    "mfs": "magicfist",
    "ltn": "lighting",
    "ice": "icebolt",
    "mar": "magicarrow",
    "swm": "swarm",
}


def stable_id(text: str) -> int:
    h = 2166136261
    for b in text.encode("utf-8"):
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def _percent_tag(abilities: set[str], prefix: str) -> float:
    for pct in (95, 90, 80, 75, 60, 50, 40, 30, 25, 20, 15, 10):
        if f"{prefix}{pct}" in abilities:
            return pct / 100.0
    return 0.0


def _intrinsic_multiplier(spell: str, target) -> float:
    abilities = set(target.abilities)
    m = 1.0 - _percent_tag(abilities, "magicproof")
    if spell == "magicfist" and "organicarmor" in abilities:
        m *= 0.20
    if spell == "lighting":
        m *= 1.0 - _percent_tag(abilities, "airproof")
        if "vulnerabilitytoair" in abilities:
            m *= 1.25
    elif spell == "icebolt":
        m *= 1.0 - _percent_tag(abilities, "waterproof")
    return max(0.0, m)


def _rows(battle_dir: Path):
    entities, _ = parse_initial_entities((battle_dir / "init.txt").read_text(errors="replace"))
    for turn in parse_turns((battle_dir / "turns0.txt").read_text(errors="replace")):
        for cmd in turn.commands:
            if cmd.opcode != "SPECIAL" or cmd.code not in SPELLS or cmd.amount is None:
                continue
            actor = entities.get(cmd.actor_uid)
            target = entities.get(cmd.target_uid)
            if not actor or not target:
                continue
            spell_name = SPELLS[cmd.code]
            tok = actor.magic_blob.split("^", 1)[0].split("-")
            declared_costs = []
            for i in range(0, len(tok) - 6, 7):
                if tok[i] != spell_name:
                    continue
                try:
                    declared_costs.append(int(float(tok[i + 1])))
                except ValueError:
                    pass
            effective_cost = int(cmd.value or 0)
            if not declared_costs or effective_cost <= 0 or not any(effective_cost <= c for c in declared_costs):
                continue
            intrinsic = _intrinsic_multiplier(spell_name, target)
            if intrinsic <= 0:
                continue
            yield spell_name, actor.creature_id, target.creature_id, abs(int(cmd.amount)), intrinsic


def build(corpus: Path, out: Path, train_fraction: float = 0.8) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    battles = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: int(p.name))
    cut = int(len(battles) * train_fraction)
    train = [r for d in battles[:cut] for r in _rows(d)]
    test = [r for d in battles[cut:] for r in _rows(d)]
    if not train:
        raise RuntimeError("no validated caster direct-spell samples found")

    groups: dict[tuple[str, str, int, int], list[int]] = defaultdict(list)
    # Hierarchy is exact actor+target -> actor -> target -> spell.
    for spell, actor_cid, target_cid, damage, intrinsic in train:
        normalized = damage / intrinsic
        groups[("SAT", spell, actor_cid, target_cid)].append(normalized)
        groups[("SA", spell, actor_cid, 0)].append(normalized)
        groups[("ST", spell, 0, target_cid)].append(normalized)
        groups[("S", spell, 0, 0)].append(normalized)

    model = {k: float(statistics.median(v)) for k, v in groups.items()}

    def predict(row) -> float:
        spell, actor_cid, target_cid, _, intrinsic = row
        for key in (
            ("SAT", spell, actor_cid, target_cid),
            ("SA", spell, actor_cid, 0),
            ("ST", spell, 0, target_cid),
            ("S", spell, 0, 0),
        ):
            if key in model:
                return model[key] * intrinsic
        return 1.0 * intrinsic

    abs_err = []
    rel_err = []
    for row in test:
        pred = predict(row)
        truth = row[3]
        abs_err.append(abs(pred - truth))
        rel_err.append(abs(pred - truth) / max(1, truth))

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scope", "spell_id", "spell_name", "actor_creature_id", "target_creature_id", "samples", "median_damage"])
        for (scope, spell, actor_cid, target_cid), values in sorted(groups.items()):
            w.writerow([scope, stable_id(spell), spell, actor_cid, target_cid, len(values), f"{statistics.median(values):.6f}"])

    report = {
        "schema": "hwm-caster-spell-damage-v3-normalized",
        "source": "server spellbook-validated raw S-records normalized by exact target resistances; historical parser/state dumps not used",
        "train_battles": cut,
        "heldout_battles": len(battles) - cut,
        "train_samples": len(train),
        "heldout_samples": len(test),
        "spells": sorted({r[0] for r in train}),
        "rows": len(groups),
        "heldout_mae": (sum(abs_err) / len(abs_err)) if abs_err else None,
        "heldout_median_relative_error": statistics.median(rel_err) if rel_err else None,
        "heldout_mean_relative_error": (sum(rel_err) / len(rel_err)) if rel_err else None,
        "out": str(out),
    }
    out.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("corpus", type=Path)
    p.add_argument("--out", type=Path, default=Path("models/hero_spell_damage.csv"))
    p.add_argument("--train-fraction", type=float, default=0.8)
    a = p.parse_args()
    print(json.dumps(build(a.corpus, a.out, a.train_fraction), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
