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
    assert report["initial_spider_entities"] > 0
    assert report["initial_spider_with_entroots"] == report["initial_spider_entities"]
    assert report["initial_spider_without_entroots"] == 0

    assert report["ent_records"] > 0
    assert report["non_numeric_ent_records"] == 0
    assert report["payload_lengths"] == {"15": report["ent_records"]}
    assert report["parser_actor_matches_first_uid"] == report["ent_records"]
    assert report["parser_actor_mismatches_first_uid"] == 0
    assert report["parser_target_uid_none"] == report["ent_records"]
    assert report["parser_target_uid_present"] == 0

    classified = sum(report["source_ability_classes"].values())
    assert (
        report["zero_source_records"]
        + report["source_missing_records"]
        + classified
        == report["ent_records"]
    )
