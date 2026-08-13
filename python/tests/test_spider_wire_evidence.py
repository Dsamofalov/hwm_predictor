from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.ability.spider_wire_evidence import analyze_corpus


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def test_spider_sent_wire_whole_corpus():
    report = analyze_corpus(CORPUS)
    warnings.warn(
        "SPIDER_WIRE_EVIDENCE "
        + json.dumps(report, ensure_ascii=False, sort_keys=True)
    )

    assert report["parse_errors"] == []
    assert report["corpus_battle_dirs"] == 866

    assert report["initial_spider_entities"] == 89
    assert report["initial_spider_with_entroots"] == 89
    assert report["initial_spider_without_entroots"] == 0
    assert report["initial_spider_ability_sets"] == {
        "alive,entroots,poisonattack,spider": 48,
        "alive,entroots,spider": 41,
    }

    assert report["ent_battles"] == 182
    assert report["ent_records"] == 806
    assert report["non_numeric_ent_records"] == 0
    assert report["payload_lengths"] == {"15": 806}
    assert report["trailers"] == {"000000000": 806}

    assert report["parser_actor_matches_first_uid"] == 806
    assert report["parser_actor_mismatches_first_uid"] == 0
    assert report["parser_target_uid_none"] == 806
    assert report["parser_target_uid_present"] == 0

    assert report["zero_source_records"] == 315
    assert report["nonzero_source_records"] == 491
    assert report["source_missing_records"] == 0
    assert report["source_ability_classes"] == {
        "entroots_without_spider": 405,
        "spider_and_entroots": 84,
        "neither": 2,
    }
    assert report["source_ability_sets"] == {
        "alive,big,enraged,entroots": 189,
        "alive,big,enraged,entroots,islow,rageoftheforest": 69,
        "alive,big,enraged,entroots,takeroots": 147,
        "alive,entroots,poisonattack,spider": 54,
        "alive,entroots,spider": 30,
        "alive,netshooter,nopenalty,rangepenalty,shooter": 2,
    }

    assert report["zero_target_records"] == 0
    assert report["nonzero_target_records"] == 806
    assert report["target_missing_before_and_after"] == 0
    assert report["target_present_before"] == 806
    assert report["target_present_after"] == 806
    assert report["owner_relations"] == {"other_owner": 491}

    assert (
        report["zero_source_records"]
        + report["source_missing_records"]
        + sum(report["source_ability_classes"].values())
        == report["ent_records"]
    )
