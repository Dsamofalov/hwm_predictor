from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.ability.gribbomb_selfdestruct_evidence import analyze_corpus


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def test_gribbomb_bom_activation_whole_corpus():
    report = analyze_corpus(CORPUS)
    assert report["parse_errors"] == []
    assert report["corpus_battle_dirs"] >= 800
    assert report["carrier_battles"] == 7

    # Primary discriminator: one carrier-only Sbom activation in the supplied corpus.
    assert report["bom_activations"] == 1
    assert report["validated_bom_activations"] == 1
    assert report["selfdestruct_candidates"] == 1
    assert report["malformed_bom_markers"] == []
    assert report["special_codes"] == {"bom": 1}

    # The activation damages exactly every living stack around the carrier and no others.
    assert report["candidate_damage_hits"] == 3
    assert report["candidate_adjacent_living_targets"] == 3
    assert report["exact_adjacent_target_set_candidates"] == 1
    assert report["missing_adjacent_targets"] == 0
    assert report["extra_nonadjacent_targets"] == 0

    example = report["candidate_examples"][0]
    assert example["battle_id"] == "1632859583"
    assert example["actor_uid"] == 5
    assert example["actor_total_hp_before"] == 36101
    assert example["adjacent_living_uids_before"] == [6, 11, 13]
    assert example["damaged_uids"] == [6, 11, 13]
    assert sorted((row["target_uid"], row["amount"]) for row in example["damage"]) == [
        (6, 36101),
        (11, 26354),
        (13, 26354),
    ]

    # Explicitly preserve the current runtime boundary: generic replay still leaves the
    # carrier alive because the self-destruction has no ordinary DAMAGE-to-self record.
    # A later replay-core package must flip this gate instead of silently overclaiming exactness.
    assert report["replay_actor_alive_after"] == 1
    assert example["actor_alive_after_generic_replay"] is True

    warnings.warn(
        "GRIBBOMB_BOM_EVIDENCE "
        + json.dumps(report, ensure_ascii=False, sort_keys=True)
    )


def test_gribbomb_non_bom_deaths_are_not_selfdestruct_candidates():
    report = analyze_corpus(CORPUS)
    assert report["parse_errors"] == []
    # The three active-carrier deaths visible to the current generic replay are ordinary
    # attack/retaliation deaths with explicit external damage, not Gribbomb activations.
    assert report["active_actor_deaths"] == 3
    assert report["active_actor_deaths_no_external_damage"] == 0
    assert report["active_actor_deaths_with_outgoing_damage"] == 3
    assert report["externally_explained_deaths"] == 3
    assert len(report["external_death_examples"]) == 3
    assert all(row["external_damage"] for row in report["external_death_examples"])
