from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

from hwm_solver.protocol.replay import iter_battle_decisions

SPHM_RE = re.compile(r"Sphm(\d{3})(\d{3})(\d{2})(\d{3})(\d{4})")


def _size(e: dict) -> int:
    return 2 if "big" in set(e.get("abilities", [])) else 1


def _cells(e: dict, x: int | None = None, y: int | None = None) -> set[tuple[int, int]]:
    x = int(e["x"]) if x is None else x
    y = int(e["y"]) if y is None else y
    w = _size(e)
    return {(x + dx, y + dy) for dx in range(w) for dy in range(w)}


def _adjacent(a: set[tuple[int, int]], b: set[tuple[int, int]]) -> bool:
    return any(max(abs(ax - bx), abs(ay - by)) == 1 for ax, ay in a for bx, by in b)


def _candidate_offsets(before: dict[int, dict], source: dict) -> list[tuple[int, int]]:
    src_cells = _cells(source)
    occupied: set[tuple[int, int]] = set()
    for uid, e in before.items():
        if uid == int(source["uid"]) or not e.get("alive") or e.get("is_hero"):
            continue
        # Keep this aligned with the current runtime occupancy contract.
        if "hidden" in set(e.get("abilities", [])):
            continue
        occupied |= _cells(e)

    result = []
    for y in range(1, 21):
        for x in range(1, 13):
            cc = _cells(source, x, y)
            if max(px for px, _ in cc) > 12 or max(py for _, py in cc) > 20:
                continue
            if cc & src_cells or cc & occupied:
                continue
            if _adjacent(cc, src_cells):
                result.append((x - int(source["x"]), y - int(source["y"])))
    return result


def collect(corpus: Path) -> tuple[list[Path], list[dict]]:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    battles = sorted((d for d in root.iterdir() if d.is_dir()), key=lambda p: int(p.name))
    rows: list[dict] = []
    for battle in battles:
        for decision in iter_battle_decisions(battle):
            m = SPHM_RE.search(decision["raw"])
            if not m:
                continue
            caster_uid, clone_uid, effective_cost, source_uid, trailer = map(int, m.groups())
            before = {int(e["uid"]): e for e in decision["state_before"]}
            after = {int(e["uid"]): e for e in decision["state_after"]}
            caster, source, clone = before.get(caster_uid), before.get(source_uid), after.get(clone_uid)
            if not caster or not source or not clone:
                continue
            rows.append({
                "battle_id": int(battle.name),
                "caster_uid": caster_uid, "source_uid": source_uid, "clone_uid": clone_uid,
                "effective_cost": effective_cost, "trailer": trailer,
                "side": "P" if int(source["owner"]) == 1 else "E",
                "footprint": _size(source),
                "dx": int(clone["x"]) - int(source["x"]),
                "dy": int(clone["y"]) - int(source["y"]),
                "clone_atb": float(clone["atb"]),
                "source_count": int(source["count"]), "clone_count": int(clone["count"]),
                "source_creature_id": int(source["creature_id"]), "clone_creature_id": int(clone["creature_id"]),
                "source_owner": int(source["owner"]), "clone_owner": int(clone["owner"]),
                "source_is_phantom": bool(source.get("is_phantom")), "clone_is_phantom": bool(clone.get("is_phantom")),
                "source_alive": bool(source.get("alive")), "source_is_hero": bool(source.get("is_hero")),
                "semantic_exact_before": bool(decision["state_semantically_exact_core"]),
                "candidates": _candidate_offsets(before, source),
            })
    return battles, rows


def train(corpus: Path, out: Path, train_fraction: float = 0.8) -> dict:
    battles, rows = collect(corpus)
    cut = int(len(battles) * train_fraction)
    train_ids = {int(d.name) for d in battles[:cut]}
    train_rows = [r for r in rows if r["battle_id"] in train_ids]
    held = [r for r in rows if r["battle_id"] not in train_ids]

    weights: dict[tuple[str, int], Counter] = defaultdict(Counter)
    atbs: dict[tuple[str, int], list[float]] = defaultdict(list)
    for r in train_rows:
        key = (r["side"], r["footprint"])
        weights[key][(r["dx"], r["dy"])] += 1
        atbs[key].append(r["clone_atb"])
    overall_atb = mean(r["clone_atb"] for r in train_rows)

    def ranked(r: dict) -> list[tuple[int, int]]:
        key = (r["side"], r["footprint"])
        w = weights.get(key, Counter())
        return sorted(r["candidates"], key=lambda o: (-w[o], abs(o[0]) + abs(o[1]), o[0], o[1]))

    def eval_rows(xs: list[dict]) -> dict:
        top1 = top3 = present = 0
        atb_abs = []
        for r in xs:
            chosen = (r["dx"], r["dy"])
            order = ranked(r)
            if chosen in order:
                present += 1
                rank = order.index(chosen)
                top1 += rank == 0
                top3 += rank < 3
            pred_atb = mean(atbs[(r["side"], r["footprint"])]) if atbs.get((r["side"], r["footprint"])) else overall_atb
            atb_abs.append(abs(pred_atb - r["clone_atb"]))
        n = max(1, len(xs))
        return {
            "rows": len(xs), "observed_placement_in_legal_candidates": present,
            "placement_top1": top1 / n, "placement_top3": top3 / n,
            "clone_atb_mae": mean(atb_abs) if atb_abs else None,
            "clone_atb_median_abs_error": median(atb_abs) if atb_abs else None,
        }

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["kind", "side", "footprint", "dx", "dy", "value"])
        for key in sorted(weights):
            side, footprint = key
            for (dx, dy), count in weights[key].most_common():
                w.writerow(["placement", side, footprint, dx, dy, count])
            w.writerow(["atb", side, footprint, 0, 0, f"{mean(atbs[key]):.12g}"])
        w.writerow(["atb", "*", 0, 0, 0, f"{overall_atb:.12g}"])

    exact_rows = [r for r in rows if r["semantic_exact_before"]]
    report = {
        "source": "new raw init.txt + turns0.txt only; historical parser/state dumps not used",
        "mechanic": "Phantom Forces / Sphm",
        "observations": len(rows), "battles_with_spell": len({r['battle_id'] for r in rows}),
        "train_battles": cut, "heldout_battles": len(battles) - cut,
        "train_rows": len(train_rows), "heldout_rows": len(held),
        "wire_invariants": {
            "trailer_zero": sum(r["trailer"] == 0 for r in rows),
            "source_alive": sum(r["source_alive"] for r in rows),
            "source_nonhero": sum(not r["source_is_hero"] for r in rows),
            "source_nonphantom": sum(not r["source_is_phantom"] for r in rows),
            "clone_phantom": sum(r["clone_is_phantom"] for r in rows),
            "same_owner": sum(r["source_owner"] == r["clone_owner"] for r in rows),
            "same_creature_id": sum(r["source_creature_id"] == r["clone_creature_id"] for r in rows),
            "clone_count_equals_source_all": sum(r["clone_count"] == r["source_count"] for r in rows),
            "semantic_exact_before_rows": len(exact_rows),
            "clone_count_equals_source_exact_before": sum(r["clone_count"] == r["source_count"] for r in exact_rows),
        },
        "train": eval_rows(train_rows), "heldout": eval_rows(held),
        "placement_model": "train-only empirical offset weights conditioned on Player/PvE side and 1x1/2x2 footprint; sampled only among currently legal adjacent anchors",
        "atb_model": "train-only group mean conditioned on side+footprint",
        "note": "Placement is modeled as chance; it is not exposed as a user-selectable destination. Clone stats/count are copied from source only in structurally/semantically safe speculative states.",
        "out": str(out),
    }
    out.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("corpus", type=Path)
    p.add_argument("--out", type=Path, default=Path("models/phantom_forces_model.csv"))
    p.add_argument("--train-fraction", type=float, default=0.8)
    a = p.parse_args()
    print(json.dumps(train(a.corpus, a.out, a.train_fraction), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
