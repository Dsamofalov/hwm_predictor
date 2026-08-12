from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.ability.cripplingwound_control_evidence import analyze_corpus, analyze_decisions


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def _entity(uid: int, owner: int, abilities: list[str]) -> dict:
    return {
        "uid": uid,
        "owner": owner,
        "creature_id": 1000 + uid,
        "abilities": abilities,
        "alive": True,
    }


def test_same_owner_wnd_reports_prior_shyp_targeting_source():
    decisions = [
        {
            "battle_id": "1",
            "decision_index": 1,
            "server_turn": 1,
            "raw": "Shyp009014180006520",
            "state_before": [_entity(9, 2, []), _entity(14, 1, ["cripplingwound"])],
        },
        {
            "battle_id": "1",
            "decision_index": 2,
            "server_turn": 2,
            "raw": "d0140110000000024Swnd014011000000000",
            "state_before": [
                _entity(14, 1, ["cripplingwound"]),
                _entity(11, 1, []),
            ],
        },
    ]
    report = analyze_decisions(decisions)
    assert report["carrier_wnd_records"] == 1
    assert report["same_owner_carrier_wnd_records"] == 1
    assert report["same_owner_with_prior_shyp_targeting_source"] == 1
    assert report["same_owner_without_prior_shyp_targeting_source"] == 0


def test_cripplingwound_same_owner_control_context_whole_corpus():
    report = analyze_corpus(CORPUS)
    assert report["parse_errors"] == []
    assert report["replay_errors"] == []
    assert report["corpus_battle_dirs"] >= 800
    assert report["carrier_wnd_records"] > 0
    assert report["same_owner_carrier_wnd_records"] > 0
    assert (
        report["same_owner_with_prior_shyp_targeting_source"]
        == report["same_owner_carrier_wnd_records"]
    )
    assert report["same_owner_without_prior_shyp_targeting_source"] == 0
    warnings.warn(
        "CRIPPLINGWOUND_CONTROL_EVIDENCE "
        + json.dumps(report, ensure_ascii=False, sort_keys=True)
    )
