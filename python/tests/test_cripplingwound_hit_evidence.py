from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.ability.cripplingwound_hit_evidence import analyze_corpus, analyze_decisions


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def _entity(uid: int, owner: int, abilities: list[str]) -> dict:
    return {
        "uid": uid,
        "owner": owner,
        "creature_id": 1000 + uid,
        "max_hp": 20,
        "top_hp": 20,
        "max_count": 10,
        "count": 10,
        "x": uid,
        "y": 5,
        "abilities": abilities,
        "alive": True,
        "effects": [],
        "effect_turns": {},
    }


def _decision(raw: str, *, actor_abilities=None, target_abilities=None) -> dict:
    return {
        "battle_id": "100",
        "decision_index": 1,
        "server_turn": 5,
        "actor_uid": 1,
        "target_uid": 2,
        "action_type": "MELEE_ATTACK",
        "raw": raw,
        "state_before": [
            _entity(1, 0, list(actor_abilities or [])),
            _entity(2, 1, list(target_abilities or [])),
        ],
        "state_after": [],
    }


def test_multi_hit_primary_is_counted_per_damage_hit():
    raw = (
        "d0010020000000010Swnd001002000000000"
        "d0010020000000011"
        "d0010020000000012Swnd001002000000000"
    )
    report = analyze_decisions([_decision(raw, actor_abilities=["cripplingwound"])])
    primary = report["primary_attack_hits"]
    assert primary["hits"] == 3
    assert primary["proc_hits"] == 2
    assert primary["no_proc_hits"] == 1
    assert primary["hit_ordinals"] == {"1": 1, "2": 1, "3": 1}
    assert primary["proc_hit_ordinals"] == {"1": 1, "3": 1}
    assert report["proc_marker_invariants"]["multi_marker_hits"] == 0


def test_counter_hit_is_separate_probability_population():
    raw = "d0010020000000010d0020010000000005Swnd002001000000000"
    report = analyze_decisions(
        [_decision(raw, actor_abilities=[], target_abilities=["cripplingwound"])]
    )
    assert report["primary_attack_hits"]["hits"] == 0
    assert report["counter_hits"]["hits"] == 1
    assert report["counter_hits"]["proc_hits"] == 1


def test_cripplingwound_hit_level_whole_corpus():
    report = analyze_corpus(CORPUS)
    assert report["parse_errors"] == []
    assert report["analysis_errors"] == []
    assert report["corpus_battles_seen"] >= 800

    all_hits = report["all_carrier_damage_hits"]
    primary = report["primary_attack_hits"]
    counter = report["counter_hits"]
    other = report["other_damage_hits"]
    assert primary["hits"] > primary["proc_hits"] > 0
    assert counter["hits"] > counter["proc_hits"] > 0
    assert all_hits["hits"] == primary["hits"] + counter["hits"] + other["hits"]
    assert all_hits["proc_hits"] == primary["proc_hits"] + counter["proc_hits"] + other["proc_hits"]
    assert other["proc_hits"] == 0

    invariants = report["proc_marker_invariants"]
    assert invariants["proc_hits"] == all_hits["proc_hits"]
    assert invariants["exactly_one_marker_per_proc_hit"] == all_hits["proc_hits"]
    assert invariants["multi_marker_hits"] == 0

    assert report["primary_temporal_holdout"]["train_rows"] > 0
    assert report["primary_temporal_holdout"]["holdout_rows"] > 0
    warnings.warn(
        "CRIPPLINGWOUND_HIT_EVIDENCE "
        + json.dumps(report, ensure_ascii=False, sort_keys=True)
    )
