from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.ability.childofthelight_evidence import analyze_corpus
from hwm_solver.ability.childofthelight_school_evidence import analyze_school_tokens
from hwm_solver.ability.childofthelight_spellwire_evidence import analyze_spellwire_corpus
from hwm_solver.ability.childofthelight_tooltipmeta_evidence import analyze_tooltip_metadata


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


EXPECTED_TOOLTIP = (
    "Любое брошенное заклинание школы магии Света, кроме наносящих урон и воскрешения, "
    "накладывается и на это существо, причем на искусном уровне."
)


def test_childofthelight_whole_corpus_evidence():
    report = analyze_corpus(CORPUS)
    assert report["parse_errors"] == []
    assert report["corpus_battle_dirs"] == 866
    assert report["carrier_battles"] == 108
    assert report["carrier_entities"] == 137
    assert report["carrier_creatures"] == {"588": 102, "928": 35}
    assert report["carrier_ability_sets"] == {
        "alive,big,blinding_attack,childofthelight": 102,
        "alive,childofthelight,confusionstrike,fireproof25,flyer": 35,
    }
    assert report["tooltip_battles"] == 121
    assert report["tooltip_names"] == {"Дитя Света.": 121}
    assert report["tooltip_descriptions"] == {EXPECTED_TOOLTIP: 121}
    assert report["tooltip_claim_shapes"] == [
        {
            "count": 121,
            "claims": {
                "integers": [],
                "mentions_also_applied": True,
                "mentions_damage_exclusion": True,
                "mentions_expert": True,
                "mentions_light": True,
                "mentions_resurrection_exclusion": True,
                "mentions_spell": True,
                "percentages": [],
            },
        }
    ]
    assert report["decisions_seen_in_carrier_battles"] == 5634
    assert report["carrier_targeted_specials"] == 223
    assert report["carrier_targeted_codes"] == {
        "fst": 88,
        "stn": 47,
        "rgm": 25,
        "ray": 17,
        "slw": 13,
        "crs": 10,
        "psc": 10,
        "sff": 7,
        "ltn": 2,
        "sta": 2,
        "cnf": 1,
        "mfs": 1,
    }
    assert report["code_copy_candidates"] == {
        "fst": 88,
        "stn": 47,
        "rgm": 25,
        "ray": 17,
        "psc": 9,
        "crs": 5,
        "slw": 3,
        "cnf": 1,
    }
    assert report["code_solo_carrier_records"] == {
        "slw": 10,
        "sff": 7,
        "crs": 5,
        "ltn": 2,
        "sta": 2,
        "mfs": 1,
        "psc": 1,
    }

    school = analyze_school_tokens(CORPUS)
    assert school["parse_errors"] == []
    assert school["corpus_battle_dirs"] == 866
    assert school["carrier_battles"] == 108
    assert school["spellbook_actors"] == 651
    assert school["spellbook_entries"] == 2031
    assert school["schools"] == {
        "neutral": 1405,
        "air": 275,
        "earth": 144,
        "cold": 141,
        "other": 31,
        "fire": 18,
        "nt": 17,
    }
    assert sum(school["schools"].values()) == school["spellbook_entries"]

    wire = analyze_spellwire_corpus(CORPUS)
    assert wire["parse_errors"] == []
    assert wire["corpus_battle_dirs"] == 866
    assert wire["carrier_battles"] == 108
    # The first hosted probe disproved the guessed literal token "light". Keep this
    # explicit until independent server metadata identifies a game-school discriminator.
    assert wire["light_spellbook_actors_in_carrier_battles"] == 0
    assert wire["light_spell_names"] == {}
    assert wire["status_groups_with_carrier"] == 175
    assert wire["status_groups_positive_cost"] == 163
    assert wire["status_groups_without_positive_cost"] == 12
    assert wire["status_groups_without_source_spellbook"] == 0
    assert wire["status_codes"] == {
        "fst": 70,
        "stn": 47,
        "ray": 17,
        "slw": 13,
        "crs": 10,
        "rgm": 10,
        "sff": 7,
        "cnf": 1,
    }
    assert wire["light_status_groups"] == 0
    assert wire["light_single_groups"] == 0
    assert wire["light_mass_groups"] == 0
    assert wire["light_ambiguous_groups"] == 0
    assert wire["light_single_copy_groups"] == 0
    assert wire["light_mass_control_groups"] == 0
    assert wire["direct_damage_carrier_records"] == 3
    assert wire["direct_damage_codes"] == {"ltn": 2, "mfs": 1}
    assert wire["raise_dead_carrier_records"] == 0

    tooltipmeta = analyze_tooltip_metadata(CORPUS)
    assert tooltipmeta["parse_errors"] == []
    assert tooltipmeta["corpus_battle_dirs"] == 866
    assert tooltipmeta["carrier_battles"] == 108
    assert tooltipmeta["carrier_battles_with_tooltips"] == 108
    assert tooltipmeta["top_sections"] == {
        "abil_desc": 108,
        "abil_names": 108,
        "perk_hints": 108,
    }
    assert tooltipmeta["section_types"] == {
        "abil_desc:dict": 108,
        "abil_names:dict": 108,
        "perk_hints:dict": 108,
    }
    assert tooltipmeta["mapping_key_counts"] == {
        "abil_desc": 2711,
        "abil_names": 2711,
        "perk_hints": 1279,
    }
    # bm_tooltips has no spell-level namespace in carrier battles: none of its keys
    # overlaps the same battle's server spellbook names, so it cannot independently
    # classify neutral/nt status entries as Light or Dark.
    assert tooltipmeta["mapping_spellbook_overlap_counts"] == {}
    assert tooltipmeta["overlap_spell_names"] == {}
    assert tooltipmeta["overlap_value_types"] == {}
    assert tooltipmeta["overlap_examples"] == []
    assert tooltipmeta["top_level_name_markers"] == {}
    # There is other ability/perk prose mentioning Light, but no non-Child metadata
    # that jointly names Light and identifies a spell school. Preserve that distinction.
    assert tooltipmeta["child_light_text_hits"] == 216
    assert tooltipmeta["non_child_light_text_hits"] == 92
    assert tooltipmeta["school_text_hits"] == 112
    assert tooltipmeta["non_child_school_light_hits"] == 0

    warnings.warn(
        "CHILDOFTHELIGHT_SCHOOL_EVIDENCE "
        + json.dumps(school, ensure_ascii=False, sort_keys=True)
    )
    warnings.warn(
        "CHILDOFTHELIGHT_SPELLWIRE_EVIDENCE "
        + json.dumps(wire, ensure_ascii=False, sort_keys=True)
    )
    warnings.warn(
        "CHILDOFTHELIGHT_TOOLTIPMETA_EVIDENCE "
        + json.dumps(tooltipmeta, ensure_ascii=False, sort_keys=True)
    )
