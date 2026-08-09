from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Iterable

import numpy as np

from hwm_solver.protocol.replay import (
    _perspective_owner,
    _player_won,
    iter_compact_decisions,
    parse_initial_entities,
    parse_tooltips,
    parse_turns,
)

ACTION_TYPES = [
    "MOVE", "MELEE_ATTACK", "RANGED_ATTACK", "WAIT", "DEFEND",
    "HERO_ACTION", "CAST_OR_ABILITY", "ABILITY", "ATTACK",
]
ACTION_TO_ID = {name: i for i, name in enumerate(ACTION_TYPES)}
MAX_ENTITIES = 32
MAX_ACTIONS = 32
ENTITY_NUMERIC_DIM = 16
ACTION_DIM = 13


def _side_id(owner: int, perspective_owner: int | None) -> int:
    if perspective_owner is None:
        return 0
    return 1 if owner == perspective_owner else 2


def _entity_arrays(state: list[dict], actor_uid: int, perspective_owner: int | None):
    creature = np.zeros((MAX_ENTITIES,), dtype=np.int64)
    side = np.zeros((MAX_ENTITIES,), dtype=np.int64)
    numeric = np.zeros((MAX_ENTITIES, ENTITY_NUMERIC_DIM), dtype=np.float32)
    mask = np.zeros((MAX_ENTITIES,), dtype=np.bool_)
    uid_to_index: dict[int, int] = {}

    # Keep alive entities first, then stable UID order. Heroes are never silently discarded.
    ordered = sorted(state, key=lambda e: (not bool(e.get("alive", True)), int(e["uid"])))
    if len(ordered) > MAX_ENTITIES:
        heroes = [e for e in ordered if bool(e.get("is_hero"))]
        actor = [e for e in ordered if int(e["uid"]) == actor_uid]
        important_ids = {int(e["uid"]) for e in heroes + actor}
        rest = [e for e in ordered if int(e["uid"]) not in important_ids]
        ordered = (heroes + actor + rest)[:MAX_ENTITIES]
        seen = set()
        ordered = [e for e in ordered if not (int(e["uid"]) in seen or seen.add(int(e["uid"])))]

    for i, e in enumerate(ordered[:MAX_ENTITIES]):
        uid = int(e["uid"])
        uid_to_index[uid] = i
        creature[i] = max(0, min(4095, int(e.get("creature_id", 0))))
        side[i] = _side_id(int(e.get("owner", 0)), perspective_owner)
        max_hp = max(1.0, float(e.get("max_hp", 1)))
        max_mana = max(1.0, float(e.get("max_mana", 0) or 1))
        numeric[i] = np.array([
            min(1.5, math.log1p(max(0.0, float(e.get("count", 0)))) / 10.0),
            max(0.0, min(1.0, float(e.get("top_hp", 0)) / max_hp)),
            min(2.0, math.log1p(max_hp) / 8.0),
            min(2.0, math.log1p(max(0.0, float(e.get("min_damage", 0)))) / 8.0),
            min(2.0, math.log1p(max(0.0, float(e.get("max_damage", 0)))) / 8.0),
            float(e.get("speed", 0)) / 20.0,
            float(e.get("initiative", 0)) / 30.0,
            float(e.get("atb", 0)) / 100.0,
            float(e.get("x", 0)) / 20.0,
            float(e.get("y", 0)) / 20.0,
            min(2.0, float(e.get("shots", 0)) / 50.0),
            float(e.get("attack", 0)) / 200.0,
            float(e.get("defense", 0)) / 200.0,
            max(0.0, min(2.0, float(e.get("mana", 0)) / max_mana)),
            1.0 if bool(e.get("is_hero")) else 0.0,
            1.0 if uid == actor_uid else 0.0,
        ], dtype=np.float32)
        mask[i] = True

    return creature, side, numeric, mask, uid_to_index


def _action_vec(action_type: str, dx: int | None, dy: int | None, target: dict | None, actor: dict | None, code: str = "") -> np.ndarray:
    v = np.zeros((ACTION_DIM,), dtype=np.float32)
    idx = ACTION_TO_ID.get(action_type)
    if idx is not None:
        v[idx] = 1.0
    # For MOVE these are destination coordinates; for target actions they are target
    # coordinates. This lets the candidate scorer distinguish two enemies at different cells.
    px = dx if dx is not None else (int(target.get("x", 0)) if target is not None else None)
    py = dy if dy is not None else (int(target.get("y", 0)) if target is not None else None)
    meta = len(ACTION_TYPES)
    v[meta] = (float(px) / 20.0) if px is not None else -1.0
    v[meta + 1] = (float(py) / 20.0) if py is not None else -1.0
    if actor is not None and target is not None:
        v[meta + 2] = min(2.0, max(abs(float(target.get("x", 0)) - float(actor.get("x", 0))), abs(float(target.get("y", 0)) - float(actor.get("y", 0)))) / 10.0)
        total_hp = max(0.0, (float(target.get("count", 0))-1.0) * max(1.0, float(target.get("max_hp", 1))) + float(target.get("top_hp", 0)))
        v[meta + 3] = min(2.0, math.log1p(total_hp) / 12.0)
    else:
        v[meta + 2] = -1.0
        if code:
            h = int.from_bytes(hashlib.blake2b(code.encode("utf-8"), digest_size=2).digest(), "little")
            v[meta + 3] = h / 65535.0
        else:
            v[meta + 3] = 0.0
    return v


def _canonical_action(row: dict) -> tuple:
    return (
        row["action_type"], row.get("destination_x"), row.get("destination_y"),
        row.get("target_uid"), (row.get("special_codes") or [""])[0],
    )


def _candidate_actions(row: dict) -> tuple[np.ndarray, np.ndarray, int]:
    state = row["state_before"]
    actor_uid = int(row["actor_uid"])
    actor = next((e for e in state if int(e["uid"]) == actor_uid), None)
    if actor is None:
        raise ValueError("actor missing from state_before")

    candidates: list[tuple] = [_canonical_action(row)]
    seen = {candidates[0]}

    def add(c: tuple):
        if c not in seen and len(candidates) < MAX_ACTIONS:
            seen.add(c); candidates.append(c)

    add(("WAIT", None, None, None, ""))
    add(("DEFEND", None, None, None, ""))

    # Target alternatives. This is a proposal set for policy learning, not an authoritative
    # legal-action oracle. Runtime legality remains the simulator/client adapter's job.
    enemies = [e for e in state if bool(e.get("alive", True)) and int(e.get("owner", 0)) != int(actor.get("owner", 0))]
    enemies.sort(key=lambda e: (max(abs(int(e.get("x", 0))-int(actor.get("x", 0))), abs(int(e.get("y", 0))-int(actor.get("y", 0)))), int(e["uid"])))
    shooter = int(actor.get("shots", 0)) > 0 or "shooter" in set(actor.get("abilities", []))
    for e in enemies[:12]:
        dist = max(abs(int(e.get("x", 0))-int(actor.get("x", 0))), abs(int(e.get("y", 0))-int(actor.get("y", 0))))
        typ = "RANGED_ATTACK" if shooter and dist > 1 else ("MELEE_ATTACK" if dist <= max(1, int(float(actor.get("speed", 1)))) else "ATTACK")
        add((typ, None, None, int(e["uid"]), ""))

    # Conservative move proposals around the actor. They are negatives/proposals only; the
    # demonstrated action is always explicitly present even for exotic movement mechanics.
    occupied = {(int(e.get("x", -99)), int(e.get("y", -99))) for e in state if bool(e.get("alive", True))}
    ax, ay = int(actor.get("x", 0)), int(actor.get("y", 0))
    radius = max(1, min(8, int(round(float(actor.get("speed", 1))))))
    cells: list[tuple[int, int, int]] = []
    for x in range(max(0, ax-radius), min(21, ax+radius+1)):
        for y in range(max(0, ay-radius), min(21, ay+radius+1)):
            if (x, y) == (ax, ay) or (x, y) in occupied:
                continue
            dist = max(abs(x-ax), abs(y-ay))
            if dist <= radius:
                cells.append((dist, x, y))
    cells.sort()
    for _, x, y in cells:
        add(("MOVE", x, y, None, ""))
        if len(candidates) >= MAX_ACTIONS:
            break

    # Deterministically shuffle candidate positions so target=0 is not leaked.
    seed_material = f"{row['battle_id']}:{row['decision_index']}".encode()
    seed = int.from_bytes(hashlib.blake2b(seed_material, digest_size=8).digest(), "little")
    rng = np.random.default_rng(seed)
    order = np.arange(len(candidates))
    rng.shuffle(order)
    candidates = [candidates[i] for i in order]
    actual_idx = candidates.index(_canonical_action(row))

    feats = np.zeros((MAX_ACTIONS, ACTION_DIM), dtype=np.float32)
    mask = np.zeros((MAX_ACTIONS,), dtype=np.bool_)
    by_uid = {int(e["uid"]): e for e in state}
    for i, (typ, dx, dy, target_uid, code) in enumerate(candidates):
        target = by_uid.get(int(target_uid)) if target_uid is not None else None
        feats[i] = _action_vec(typ, dx, dy, target, actor, code)
        mask[i] = True
    return feats, mask, actual_idx


def _split_map(battle_dirs: list[Path]) -> dict[str, str]:
    # warid is monotonic enough for a chronological holdout and avoids same-battle leakage.
    ordered = sorted((d.name for d in battle_dirs), key=lambda x: int(x))
    n = len(ordered); a = int(n * 0.80); b = int(n * 0.90)
    out = {}
    for bid in ordered[:a]: out[bid] = "train"
    for bid in ordered[a:b]: out[bid] = "val"
    for bid in ordered[b:]: out[bid] = "test"
    return out


def _allocate_split_arrays(nrows: int) -> dict[str, np.ndarray]:
    return {
        "creature_id": np.zeros((nrows, MAX_ENTITIES), dtype=np.int64),
        "side": np.zeros((nrows, MAX_ENTITIES), dtype=np.int64),
        "numeric": np.zeros((nrows, MAX_ENTITIES, ENTITY_NUMERIC_DIM), dtype=np.float32),
        "entity_mask": np.zeros((nrows, MAX_ENTITIES), dtype=np.bool_),
        "action_features": np.zeros((nrows, MAX_ACTIONS, ACTION_DIM), dtype=np.float32),
        "action_mask": np.zeros((nrows, MAX_ACTIONS), dtype=np.bool_),
        "target": np.zeros((nrows,), dtype=np.int64),
        "win": np.zeros((nrows,), dtype=np.float32),
        "win_mask": np.zeros((nrows,), dtype=np.bool_),
        "decision_side": np.zeros((nrows,), dtype=np.int8),
        "battle_id": np.zeros((nrows,), dtype=np.int64),
        "decision_index": np.zeros((nrows,), dtype=np.int32),
        "semantic_unresolved_before": np.zeros((nrows,), dtype=np.int32),
        "semantic_unresolved_action": np.zeros((nrows,), dtype=np.int16),
        "state_semantically_exact_core": np.zeros((nrows,), dtype=np.bool_),
    }


def _load_battle_for_dataset(d: Path):
    init_payload = (d / "init.txt").read_text(encoding="utf-8", errors="replace")
    turns_payload = (d / "turns0.txt").read_text(encoding="utf-8", errors="replace")
    entities, warnings = parse_initial_entities(init_payload)
    turns = parse_turns(turns_payload)
    owner = _perspective_owner(entities)
    won = _player_won(init_payload, entities, owner)
    return init_payload, entities, turns, owner, won, warnings


def _row_is_accepted(row: dict, include_unknown_commands: bool) -> tuple[bool, str | None]:
    if row["action_type"] not in ACTION_TO_ID:
        if row["action_type"] == "FORCED_EVENT":
            return False, "forced_or_nonpolicy_event"
        if row["action_type"] == "PASS":
            return False, "noop_pass"
        return False, "unknown_action"
    if row["has_unknown_command"] and not include_unknown_commands:
        return False, "unknown_low_level_command"
    return True, None


def build_real_dataset(corpus_root: Path, out_dir: Path, *, include_unknown_commands: bool = False) -> dict:
    """Build corpus tensors in one semantic replay pass.

    Capacity is preallocated from the raw number of ``C<uid>`` activation records per
    split (plus a tiny safety margin).  This is a cheap lexical upper bound and avoids
    replaying every battle twice merely to discover the exact number of policy rows.
    Arrays are trimmed to the actual accepted count before ``np.savez``.
    """
    import re

    battles_dir = corpus_root / "battles" if (corpus_root / "battles").is_dir() else corpus_root
    battle_dirs = [d for d in battles_dir.iterdir() if d.is_dir() and (d / "init.txt").exists() and (d / "turns0.txt").exists()]
    battle_dirs.sort(key=lambda p: int(p.name))
    split_for = _split_map(battle_dirs)
    out_dir.mkdir(parents=True, exist_ok=True)

    # A policy decision is bounded by server ACTIVATE markers. Counting these does not
    # require tokenization/state reconstruction and is orders of magnitude cheaper than a
    # complete first replay pass. Add one row per battle for pre-first-C edge cases.
    capacities = {"train": 0, "val": 0, "test": 0}
    activate_re = re.compile(r"C\d{3}")
    for d in battle_dirs:
        raw = (d / "turns0.txt").read_text(encoding="utf-8", errors="replace")
        capacities[split_for[d.name]] += len(activate_re.findall(raw)) + 1

    arrays = {split: _allocate_split_arrays(capacity) for split, capacity in capacities.items()}
    cursor = {"train": 0, "val": 0, "test": 0}

    action_counts = Counter(); side_counts = Counter(); rejected = Counter(); outcome_counts = Counter()
    creature_ids = set(); ability_names = set(); special_codes = set(); tooltip_abilities = set(); max_entities = 0
    command_counts = Counter(); unknown_command_count = 0; parsed_battles = 0

    for d in battle_dirs:
        init_payload, entities, turns, owner, won, _warnings = _load_battle_for_dataset(d)
        outcome_counts[str(won)] += 1; parsed_battles += 1
        for e in entities.values():
            creature_ids.add(e.creature_id); ability_names.update(e.abilities)
        tt = parse_tooltips(init_payload); tooltip_abilities.update((tt.get("abil_names") or {}).keys())
        for turn in turns:
            for cmd in turn.commands:
                command_counts[cmd.opcode] += 1
                if cmd.opcode == "UNKNOWN": unknown_command_count += 1
                if cmd.opcode == "SPECIAL" and cmd.code: special_codes.add(cmd.code)

        split = split_for[d.name]; out = arrays[split]
        for row in iter_compact_decisions(d.name, entities, turns, owner, player_won=won):
            action_counts[row["action_type"]] += 1; side_counts[row["side"]] += 1
            max_entities = max(max_entities, len(row["state_before"]))
            accepted, reason = _row_is_accepted(row, include_unknown_commands)
            if not accepted:
                if reason: rejected[reason] += 1
                continue
            try:
                c, side, numeric, em, _uidmap = _entity_arrays(row["state_before"], int(row["actor_uid"]), owner)
                af, am, target = _candidate_actions(row)
            except Exception:
                rejected["feature_encoding_error"] += 1
                continue

            i = cursor[split]
            if i >= out["target"].shape[0]:
                # Should never happen if ACTIVATE is an upper bound. Keep this explicit so
                # protocol drift fails loudly instead of corrupting adjacent memory/rows.
                raise RuntimeError(f"dataset capacity exhausted for {split} at battle {d.name}: {i}/{out['target'].shape[0]}")
            out["creature_id"][i] = c; out["side"][i] = side; out["numeric"][i] = numeric; out["entity_mask"][i] = em
            out["action_features"][i] = af; out["action_mask"][i] = am; out["target"][i] = target
            out["win"][i] = 1.0 if won is True else 0.0; out["win_mask"][i] = won is not None
            out["decision_side"][i] = 1 if row["side"] == "PLAYER" else 2
            out["battle_id"][i] = int(d.name); out["decision_index"][i] = int(row["decision_index"])
            before = int(row.get("semantic_unresolved_records_before", 0)); after = int(row.get("semantic_unresolved_records_after", before))
            out["semantic_unresolved_before"][i] = before; out["semantic_unresolved_action"][i] = max(0, after - before)
            out["state_semantically_exact_core"][i] = bool(row.get("state_semantically_exact_core", False))
            cursor[split] += 1

    final_counts = {}
    for split, out in arrays.items():
        n = cursor[split]; final_counts[split] = n
        trimmed = {k: v[:n] for k, v in out.items()}
        np.savez(out_dir / f"{split}.npz", **trimmed)
        arrays[split] = trimmed

    catalog = {
        "creature_ids": sorted(creature_ids), "ability_tags": sorted(ability_names),
        "tooltip_ability_codes": sorted(tooltip_abilities), "special_codes": sorted(special_codes),
    }
    (out_dir / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "schema_version": 5, "source": "independently decoded raw init.txt + turns0.txt", "builder": "one-pass-bounded-preallocated",
        "battles": parsed_battles, "splits": final_counts, "capacity_by_split": capacities,
        "accepted_decisions": sum(final_counts.values()), "observed_decisions": int(sum(action_counts.values())),
        "rejected": dict(rejected), "action_counts_observed": dict(action_counts), "side_counts_observed": dict(side_counts), "outcomes": dict(outcome_counts),
        "commands": dict(command_counts), "unknown_command_count": unknown_command_count,
        "unknown_command_rate": unknown_command_count / max(1, sum(command_counts.values())),
        "creature_ids": len(creature_ids), "ability_tags": len(ability_names),
        "tooltip_ability_codes": len(tooltip_abilities), "special_codes": len(special_codes),
        "max_entities_observed": max_entities, "max_entities_encoded": MAX_ENTITIES,
        "candidate_actions": MAX_ACTIONS, "action_dim": ACTION_DIM,
        "split_policy": "chronological by numeric warid; 80/10/10; never split within battle",
        "safety": "Tokenizer-unknown rows are excluded by default; structurally known but semantically unresolved mechanics are retained with explicit uncertainty counters; forced/server-only events are excluded from policy targets; old historical state dumps are not labels or ground truth.",
    }
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report

