from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.ability.cripplingwound_evidence import analyze_corpus, analyze_decisions


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def _entity(uid: int, owner: int, abilities: list[str], *, effects=None, effect_turns=None) -> dict:
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
        "effects": list(effects or []),
        "effect_turns": dict(effect_turns or {}),
    }


def _decision(*, actor_abilities: list[str], raw: str, target_abilities=None) -> dict:
    before = [
        _entity(1, 0, actor_abilities),
        _entity(2, 1, list(target_abilities or [])),
    ]
    after = [
        _entity(1, 0, actor_abilities),
        _entity(2, 1, list(target_abilities or []), effects=["proc_cripple"], effect_turns={"proc_cripple": 2}),
    ]
    return {
        "battle_id": "100",
        "decision_index": 3,
        "server_turn": 7,
        "actor_uid": 1,
        "target_uid": 2,
        "action_type": "MELEE_ATTACK",
        "raw": raw,
        "state_before": before,
        "state_after": after,
    }


def test_primary_wnd_requires_server_declared_carrier_for_isolated_sample():
    raw = "d0010020000000010Swnd001002123456789"
    report = analyze_decisions([_decision(actor_abilities=["cripplingwound"], raw=raw)])
    assert report["wire"]["records_total"] == 1
    assert report["wire"]["source_carrier_records"] == 1
    assert report["wire"]["primary_actor_target_records"] == 1
    assert report["carrier_attacks"]["total"] == 1
    assert report["carrier_attacks"]["proc"] == 1
    assert report["observed_consequence"]["canonical_proc_effect_after"]["true"] == 1

    control = analyze_decisions([_decision(actor_abilities=[], raw=raw)])
    assert control["wire"]["records_total"] == 1
    assert control["wire"]["source_carrier_records"] == 0
    assert control["wire"]["noncarrier_source_records"] == 1
    assert control["carrier_attacks"]["total"] == 0


def test_counter_wnd_is_not_mislabeled_as_primary_proc():
    raw = "d0010020000000010d0020010000000005Swnd002001987654321"
    decision = _decision(actor_abilities=[], target_abilities=["cripplingwound"], raw=raw)
    report = analyze_decisions([decision])
    assert report["wire"]["source_carrier_records"] == 1
    assert report["wire"]["counter_source_records"] == 1
    assert report["wire"]["primary_actor_target_records"] == 0
    assert report["carrier_attacks"]["total"] == 0


def test_cripplingwound_whole_corpus_evidence():
    report = analyze_corpus(CORPUS)
    assert report["parse_errors"] == []
    assert report["analysis_errors"] == []
    assert report["corpus_battles_seen"] >= 800

    wire = report["wire"]
    assert wire["records_total"] > 0
    assert wire["source_carrier_records"] == wire["records_total"]
    assert wire["noncarrier_source_records"] == 0
    assert wire["other_relation_records"] == 0
    assert (
        wire["primary_actor_target_records"] + wire["counter_source_records"]
        == wire["source_carrier_records"]
    )
    assert wire["after_same_pair_damage"] == wire["source_carrier_records"]
    assert wire["trailer_telemetry"] == {"000000000": wire["records_total"]}

    carrier = report["carrier_attacks"]
    assert carrier["total"] > carrier["proc"] > 0
    assert carrier["no_proc"] > 0

    consequence = report["observed_consequence"]
    assert consequence["canonical_proc_effect_after"] == {
        "true": carrier["proc"],
        "false": 0,
    }
    assert consequence["canonical_effect_turns_after"] == {"2": carrier["proc"]}

    holdout = report["temporal_holdout"]
    assert holdout["train_rows"] > 0
    assert holdout["holdout_rows"] > 0
    warnings.warn(
        "CRIPPLINGWOUND_EVIDENCE "
        + json.dumps(
            {
                "wire": wire,
                "carrier_attacks": carrier,
                "observed_consequence": consequence,
                "temporal_holdout": holdout,
                "noncarrier_wire_examples": report["noncarrier_wire_examples"],
                "other_relation_examples": report["other_relation_examples"],
                "proc_examples": report["proc_examples"],
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
