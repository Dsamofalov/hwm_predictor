from __future__ import annotations

import copy
import json
import warnings
from pathlib import Path

from hwm_solver.ability.gribbomb_selfdestruct_evidence import analyze_corpus
from hwm_solver.protocol.replay import (
    _apply_command,
    _validated_gribbomb_bomb,
    parse_commands,
    parse_replay,
)


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def _battle_dir(battle_id: str) -> Path:
    root = CORPUS / "battles" if (CORPUS / "battles").is_dir() else CORPUS
    return root / battle_id


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

    # The carrier self-destruction is now an exact observed replay transition. The three
    # target DAMAGE records above remain authoritative observed deltas; no predictive Earth
    # damage formula is synthesized from the single activation.
    assert report["replay_actor_alive_after"] == 0
    assert example["actor_alive_after_generic_replay"] is False

    warnings.warn(
        "GRIBBOMB_BOM_EVIDENCE "
        + json.dumps(report, ensure_ascii=False, sort_keys=True)
    )


def test_gribbomb_bom_replay_kills_only_validated_carrier():
    replay = parse_replay(_battle_dir("1632859583"))
    decision = next(
        d for d in replay.decisions
        if d.actor_uid == 5 and "bom" in d.special_codes
    )
    bomb = next(c for c in parse_commands(decision.raw) if c.opcode == "SPECIAL" and c.code == "bom")

    assert _validated_gribbomb_bomb(bomb, decision.state_before.entities)
    actor_after = decision.state_after.entities[5]
    assert actor_after.alive is False
    assert actor_after.count == 0
    assert actor_after.top_hp == 0

    wrong_source = copy.deepcopy(decision.state_before.entities)
    wrong_source[5].abilities = [a for a in wrong_source[5].abilities if a != "gribbomb"]
    assert not _validated_gribbomb_bomb(bomb, wrong_source)
    _apply_command(wrong_source, bomb)
    assert wrong_source[5].alive is True

    malformed = next(c for c in parse_commands("Sbom005000000000001") if c.opcode == "SPECIAL")
    malformed_state = copy.deepcopy(decision.state_before.entities)
    assert not _validated_gribbomb_bomb(malformed, malformed_state)
    _apply_command(malformed_state, malformed)
    assert malformed_state[5].alive is True


def test_gribbomb_non_bom_deaths_are_not_selfdestruct_candidates():
    report = analyze_corpus(CORPUS)
    assert report["parse_errors"] == []
    # Generic replay now contains four Gribbomb-carrier deaths: the one exact Sbom
    # self-destruction plus three ordinary attack/retaliation deaths with explicit external
    # damage. Removing the one validated bomb leaves exactly the same three negative controls.
    assert report["active_actor_deaths"] == 4
    assert report["active_actor_deaths_no_external_damage"] == 1
    assert report["active_actor_deaths_with_outgoing_damage"] == 4
    assert report["active_actor_deaths"] - report["validated_bom_activations"] == 3
    assert report["externally_explained_deaths"] == 3
    assert len(report["external_death_examples"]) == 3
    assert all(row["external_damage"] for row in report["external_death_examples"])
