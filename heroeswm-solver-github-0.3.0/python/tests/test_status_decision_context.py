from hwm_solver.protocol.replay import (
    RawEntity,
    _decision_semantic_unresolved_flags,
    parse_commands,
)


def hero(magic_blob: str) -> RawEntity:
    return RawEntity(
        uid=1, owner=1, creature_id=53, max_hp=1, top_hp=1,
        min_damage=0, max_damage=0, mana=20, max_mana=20,
        speed=0, atb=0, initiative=10, max_count=7, count=1,
        x=0, y=0, attack_range=0, shots=0, attack=0, defense=0,
        morale_raw=0, luck_raw=0, retaliation_raw=0, real_health=1,
        experience_level_code=0, abilities=["hero"], magic_blob=magic_blob,
    )


def target(uid: int = 2, owner: int = 1) -> RawEntity:
    e = hero("")
    e.uid = uid
    e.owner = owner
    e.abilities = []
    e.magic_blob = ""
    return e


def test_status_record_layout_and_single_exact_selection():
    cmds = parse_commands("Sfst001002040700040")
    assert len(cmds) == 1
    c = cmds[0]
    assert c.code == "fst"
    assert c.actor_uid == 1 and c.target_uid == 2
    assert c.value == 4
    assert c.duration == 7
    assert c.amount == 40

    entities = {1: hero("fast-4-1-40-0-0-light-"), 2: target()}
    assert _decision_semantic_unresolved_flags(cmds, entities, 1) == [False]


def test_mass_status_zero_cost_followups_require_first_selected_record():
    entities = {
        1: hero("fast-4-1-40-0-0-light-mfast-8-3-40-0-0-light-"),
        2: target(2),
        3: target(3),
    }
    cmds = parse_commands("Sfst001002080700040Sfst001003000700040")
    assert _decision_semantic_unresolved_flags(cmds, entities, 1) == [False, False]

    # A zero-cost result without a selected-spell record is a triggered effect, not proof
    # that the hero selected Fast.
    triggered = parse_commands("Sfst001003000700040")
    assert _decision_semantic_unresolved_flags(triggered, entities, 1) == [True]


def test_wrong_mana_cost_stays_semantically_unresolved():
    entities = {1: hero("fast-4-1-40-0-0-light-"), 2: target()}
    cmds = parse_commands("Sfst001002050700040")
    assert _decision_semantic_unresolved_flags(cmds, entities, 1) == [True]
