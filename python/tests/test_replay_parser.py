from hwm_solver.protocol.replay import (
    parse_entity_record, parse_turn_records, parse_commands, build_decisions, parse_tooltips,
    _perspective_owner, _apply_command, _decision_semantic_unresolved_flags,
)


def test_entity_fixed_fields():
    raw = (
        "M002:000002000172000022000022000003000005000000000000000005000100000010"
        "000728000728000011000005000000000000000008000006000000000000000001000022000223"
        "bearani|[1.4-15.04ca24]|Медведи#Bears|alive|big|enraged|pawstrike|~^"
    )
    e = parse_entity_record(raw)
    assert e.uid == 2
    assert e.owner == 2
    assert e.creature_id == 172
    assert e.max_hp == 22 and e.top_hp == 22
    assert e.max_count == 728 and e.count == 728
    assert (e.x, e.y) == (11, 5)
    assert e.attack == 8 and e.defense == 6
    assert e.name == "Медведи#Bears"
    assert "pawstrike" in e.abilities


def test_turn_and_core_commands():
    payload = (
        "t=000turns=>1:C013-011.5;>2:"
        "m0130905d0130050000002847Senr002100000000001i0130000m0130203i0130100C010-001.1;"
    )
    turns = parse_turn_records(payload)
    assert [x[0] for x in turns] == [1, 2]
    cmds = parse_commands(turns[1][1])
    assert [c.opcode for c in cmds] == ["MOVE", "DAMAGE", "SPECIAL", "STATE", "MOVE", "STATE", "ACTIVATE"]
    assert cmds[1].target_uid == 5 and cmds[1].amount == 2847
    assert cmds[2].code == "enr"


def test_damage_math():
    raw = (
        "M002:000002000172000022000022000003000005000000000000000005000100000010"
        "000010000010000011000005000000000000000008000006000000000000000001000022000223"
        "bearani|[1.4]|Bears|alive|~^"
    )
    e = parse_entity_record(raw)
    assert e.total_hp == 220
    e.apply_damage(23)
    assert e.count == 9 and e.top_hp == 21
    e.apply_damage(9999)
    assert e.count == 0 and not e.alive




def test_phantom_modifier_and_positive_damage_dissipation():
    raw = (
        "M017:0000010000720000140000140000050000080000000000000000060000460013.400004200004200"
        "0001000009000006000013000052000029000005000001000001000014000003"
        "hunterelfani|[1.4-34.29b25c]|Grandmaster bowmen|alive|shooter|doubleshoot|wardingarrows|"
        "~^sum100000000001phm100000000001"
    )
    e = parse_entity_record(raw)
    assert e.is_phantom
    before = e.total_hp
    assert before > 1
    e.apply_damage(1)
    assert e.count == 0 and e.top_hp == 0 and not e.alive



def test_psc_damage_layout_and_phantom_dissipation():
    from hwm_solver.protocol.replay import RawEntity, _apply_command
    e = RawEntity(uid=17, owner=1, creature_id=72, max_hp=14, top_hp=14,
        min_damage=5, max_damage=8, mana=0, max_mana=0, speed=6, atb=0, initiative=13.4,
        max_count=52, count=52, x=1, y=2, attack_range=6, shots=9, attack=52, defense=29,
        morale_raw=0, luck_raw=0, retaliation_raw=0, real_health=0, experience_level_code=0,
        is_phantom=True)
    c = parse_commands("Spsc002017000016062")[0]
    assert c.opcode == "SPECIAL" and c.code == "psc"
    assert c.actor_uid == 2 and c.target_uid == 17 and c.amount == 16
    assert c.value == 62
    entities = {17: e}
    _apply_command(entities, c)
    assert not e.alive and e.count == 0

def test_mana_feed_exact_wire_and_transition():
    from hwm_solver.protocol.replay import RawEntity

    def entity(uid: int, owner: int, mana: int, count: int, abilities: list[str]) -> RawEntity:
        return RawEntity(uid=uid, owner=owner, creature_id=120, max_hp=20, top_hp=20,
            min_damage=1, max_damage=1, mana=mana, max_mana=max(mana, 15), speed=5, atb=0,
            initiative=10, max_count=max(1,count), count=count, x=1, y=1, attack_range=6,
            shots=5, attack=5, defense=5, morale_raw=0, luck_raw=0, retaliation_raw=0,
            real_health=0, experience_level_code=0, abilities=abilities)

    actor=entity(15,1,15,5,["manafeed"])
    hero=entity(1,1,10,1,["hero"])
    enemy_hero=entity(2,2,7,1,["hero"])
    entities={15:actor,1:hero,2:enemy_hero}
    cmd=parse_commands("Smfd015001050000000")[0]
    assert cmd.opcode == "SPECIAL" and cmd.code == "mfd"
    assert (cmd.actor_uid,cmd.target_uid,cmd.amount,cmd.duration) == (15,1,5,0)
    assert _decision_semantic_unresolved_flags([cmd],entities,15) == [False]
    _apply_command(entities,cmd)
    assert actor.mana == 10 and hero.mana == 15 and enemy_hero.mana == 7

    # Transfer is limited by remaining creature mana when count is larger.
    actor.mana=3; actor.count=20; hero.mana=15
    cmd=parse_commands("Smfd015001030000000")[0]
    assert _decision_semantic_unresolved_flags([cmd],entities,15) == [False]
    _apply_command(entities,cmd)
    assert actor.mana == 0 and hero.mana == 18

    # Wrong owner/amount must remain semantic-risk and must not mutate state.
    bad=parse_commands("Smfd015002010000000")[0]
    assert _decision_semantic_unresolved_flags([bad],entities,15) == [True]


def test_mighty_slam_exact_wire_cooldown_and_action_type():
    from hwm_solver.protocol.replay import RawEntity, _apply_command, _decision_semantic_unresolved_flags

    actor = RawEntity(
        uid=6, owner=1, creature_id=652, max_hp=100, top_hp=100,
        min_damage=10, max_damage=20, mana=0, max_mana=0, speed=4, atb=90,
        initiative=12, max_count=6, count=6, x=2, y=4, attack_range=1, shots=0,
        attack=20, defense=20, morale_raw=0, luck_raw=0, retaliation_raw=0,
        real_health=0, experience_level_code=0, abilities=["mightyslam", "big"],
    )
    target = RawEntity(
        uid=8, owner=2, creature_id=71, max_hp=26, top_hp=26,
        min_damage=1, max_damage=2, mana=0, max_mana=0, speed=4, atb=96,
        initiative=9.6, max_count=320, count=320, x=4, y=7, attack_range=1, shots=0,
        attack=10, defense=10, morale_raw=0, luck_raw=0, retaliation_raw=0,
        real_health=0, experience_level_code=0, abilities=[],
    )
    entities = {6: actor, 8: target}
    cmd = parse_commands("Smsl006000000000000")[0]
    assert cmd.opcode == "SPECIAL" and cmd.code == "msl" and cmd.actor_uid == 6
    assert _decision_semantic_unresolved_flags([cmd], entities, 6) == [False]
    _apply_command(entities, cmd)
    assert actor.effects["msl"].startswith("observed:")
    assert actor.effect_turns["msl"] == 3

    # Wrong actor ability is preserved as semantic risk.
    actor.abilities = ["big"]
    assert _decision_semantic_unresolved_flags([cmd], entities, 6) == [True]


def test_tooltips_decode():
    import base64, json
    data = base64.b64encode(json.dumps({"abil_names":{"shooter":"Shooter"}}).encode()).decode().replace("=", "<")
    got = parse_tooltips("x;bm_tooltips=" + data)
    assert got["abil_names"]["shooter"] == "Shooter"


def test_opaque_structural_records_are_not_tokenizer_unknowns():
    payload = (
        "&001o013p016k003A003004B0081209b0180919r0171008"
        "s023070100015bld0000slw737.81crs439.05"
    )
    cmds = parse_commands(payload)
    assert not any(c.opcode == "UNKNOWN" for c in cmds)
    assert [c.opcode for c in cmds] == [
        "OPAQUE_SHORT", "OPAQUE_SHORT", "OPAQUE_SHORT", "OPAQUE_SHORT",
        "OPAQUE_A", "FORCED_POSITION", "FORCED_POSITION", "FORCED_POSITION",
        "SPAWN_POSITION", "OPAQUE_EFFECT", "OPAQUE_EFFECT", "OPAQUE_EFFECT",
    ]


def test_perspective_owner_prefers_owner_one_not_m001():
    enemy = parse_entity_record(
        "M001:000002000172000022000022000003000005000000000000000005000100000010"
        "000010000010000011000005000000000000000008000006000000000000000001000022000223"
        "enemyhero|[1.4]|Enemy|hero|~^"
    )
    player = parse_entity_record(
        "M007:000001000172000022000022000003000005000000000000000005000100000010"
        "000010000010000011000005000000000000000008000006000000000000000001000022000223"
        "playerhero|[1.4]|Player|hero|~^"
    )
    assert _perspective_owner({1: enemy, 7: player}) == 1


def test_hide_record_removes_entity():
    e = parse_entity_record(
        "M007:000001000172000022000022000003000005000000000000000005000100000010"
        "000010000010000011000005000000000000000008000006000000000000000001000022000223"
        "bearani|[1.4]|Bear|alive|~^"
    )
    cmd = parse_commands("h007")[0]
    entities = {7: e}
    _apply_command(entities, cmd)
    assert entities[7].count == 0
    assert entities[7].top_hp == 0
    assert not entities[7].alive


def _entity_for_action(uid: int, *, owner: int = 1, creature_id: int = 745, abilities: str = "alive"):
    # Use a known-good fixed-width entity then override only semantics needed by action tests.
    e = parse_entity_record(
        f"M{uid:03d}:000001000172000022000022000003000005000000000000000005000100000010"
        "000010000010000011000005000000000000000008000006000000000000000001000022000223"
        f"unit|[1.4]|Unit|{abilities}|~^"
    )
    e.owner = owner
    e.creature_id = creature_id
    return e


def test_invisibility_and_siphon_records_are_high_level_ability_not_unknown():
    from hwm_solver.protocol.replay import BattleSnapshot, _action_from_commands
    inv = _entity_for_action(15, abilities="alive|caster|invisibility")
    snap = BattleSnapshot("x", 0, 1, 15, 1, {15: inv})
    typ, *_ = _action_from_commands(15, parse_commands("Y015000001i0150100"), snap)
    assert typ == "ABILITY"

    siphon = _entity_for_action(6, creature_id=281, abilities="alive|demonic|siphonmana")
    snap = BattleSnapshot("x", 0, 1, 6, 1, {6: siphon})
    typ, *_ = _action_from_commands(6, parse_commands("z006001010x006002005x006003005i0060100"), snap)
    assert typ == "ABILITY"


def test_bad_morale_is_forced_nonpolicy_event():
    from hwm_solver.protocol.replay import BattleSnapshot, _action_from_commands
    e = _entity_for_action(11, abilities="alive|big|flyer")
    snap = BattleSnapshot("x", 0, 1, 11, 1, {11: e})
    typ, *_ = _action_from_commands(11, parse_commands("l011badmorale^i0110050"), snap)
    assert typ == "FORCED_EVENT"


def test_hero_state_only_noop_is_retained_as_inferred_defend():
    from hwm_solver.protocol.replay import BattleSnapshot, _action_from_commands
    hero = _entity_for_action(4, creature_id=648, abilities="shooter|hero")
    snap = BattleSnapshot("x", 0, 1, 4, 1, {4: hero})
    typ, *_ = _action_from_commands(4, parse_commands("i0040100"), snap)
    assert typ == "DEFEND"


def test_special_direct_damage_layout_and_state_mutation():
    from hwm_solver.protocol.replay import RawEntity, parse_commands, _apply_command
    e = RawEntity(uid=19, owner=2, creature_id=1, max_hp=10, top_hp=10,
        min_damage=1, max_damage=1, mana=0, max_mana=0, speed=1, atb=0, initiative=1,
        max_count=10, count=10, x=5, y=5, attack_range=0, shots=0, attack=1, defense=1,
        morale_raw=0, luck_raw=0, retaliation_raw=0, real_health=0, experience_level_code=0)
    entities={19:e}
    cmds=parse_commands("Smfs002019005000030")
    assert len(cmds)==1
    c=cmds[0]
    assert c.opcode=="SPECIAL" and c.code=="mfs" and c.actor_uid==2
    assert c.target_uid==19 and c.amount==30
    _apply_command(entities,c)
    assert entities[19].total_hp==70


def test_raise_dead_exact_layout_and_observed_heal():
    from hwm_solver.protocol.replay import RawEntity, parse_commands, _apply_command, _validated_raise_dead
    actor = RawEntity(uid=1, owner=1, creature_id=58, max_hp=22, top_hp=9999,
        min_damage=1, max_damage=1, mana=20, max_mana=20, speed=0, atb=0, initiative=1,
        max_count=1, count=1, x=0, y=2, attack_range=0, shots=0, attack=1, defense=1,
        morale_raw=0, luck_raw=0, retaliation_raw=0, real_health=0, experience_level_code=0,
        abilities=['hero'], magic_blob='raisedead-9-2-136-17-0-neutral-^')
    target = RawEntity(uid=18, owner=1, creature_id=1, max_hp=50, top_hp=0,
        min_damage=1, max_damage=1, mana=0, max_mana=0, speed=1, atb=0, initiative=1,
        max_count=10, count=0, x=2, y=2, attack_range=0, shots=0, attack=1, defense=1,
        morale_raw=0, luck_raw=0, retaliation_raw=0, real_health=0, experience_level_code=0,
        abilities=['undead'], alive=False)
    c = parse_commands('Srsd001018-19000136')[0]
    assert c.opcode == 'SPECIAL' and c.code == 'rsd'
    assert c.actor_uid == 1 and c.target_uid == 18 and c.value == 9 and c.amount == 136
    entities = {1: actor, 18: target}
    assert _validated_raise_dead(c, entities)
    _apply_command(entities, c)
    assert actor.mana == 11
    assert target.alive and target.total_hp == 136
    assert target.count == 3 and target.top_hp == 36


def test_raise_dead_caps_at_original_stack_capacity_and_rejects_non_undead():
    from hwm_solver.protocol.replay import RawEntity, parse_commands, _apply_command, _validated_raise_dead
    actor = RawEntity(uid=1, owner=2, creature_id=268, max_hp=100, top_hp=100,
        min_damage=1, max_damage=1, mana=20, max_mana=20, speed=0, atb=0, initiative=1,
        max_count=1, count=1, x=0, y=2, attack_range=0, shots=0, attack=1, defense=1,
        morale_raw=0, luck_raw=0, retaliation_raw=0, real_health=0, experience_level_code=0,
        abilities=['undead','caster'], magic_blob='raisedead-9-0-180-23-0-neutral-^')
    target = RawEntity(uid=6, owner=2, creature_id=269, max_hp=70, top_hp=60,
        min_damage=1, max_damage=1, mana=0, max_mana=0, speed=1, atb=0, initiative=1,
        max_count=2, count=2, x=2, y=2, attack_range=0, shots=0, attack=1, defense=1,
        morale_raw=0, luck_raw=0, retaliation_raw=0, real_health=0, experience_level_code=0,
        abilities=['undead'])
    c = parse_commands('Srsd001006-19000203')[0]
    entities={1:actor,6:target}
    assert _validated_raise_dead(c, entities)
    _apply_command(entities,c)
    assert target.total_hp == 140  # capped at 2 * 70
    target.abilities=[]; target.count=1; target.top_hp=1; target.alive=True
    assert not _validated_raise_dead(c, entities)


def test_ranged_ammo_decrements_two_for_doubleshoot_decision():
    from hwm_solver.protocol.replay import _apply_decision_commands
    actor = _entity_for_action(1, abilities="alive|shooter|doubleshoot")
    actor.shots = 5
    target = _entity_for_action(2, owner=2)
    target.x, target.y = 10, 10
    entities = {1: actor, 2: target}
    cmds = parse_commands("m0010101d0010020000000001i0010100")
    _apply_decision_commands(entities, 1, "RANGED_ATTACK", cmds)
    assert actor.shots == 3


def test_phantom_forces_exact_layout_source_link_and_mana():
    from hwm_solver.protocol.replay import (
        RawEntity, _apply_command, _decision_semantic_unresolved_flags,
        _validated_phantom_forces, _validated_phantom_forces_decision,
    )
    caster = RawEntity(uid=1, owner=1, creature_id=53, max_hp=22, top_hp=9999,
        min_damage=1, max_damage=1, mana=30, max_mana=30, speed=0, atb=0, initiative=1,
        max_count=1, count=1, x=0, y=2, attack_range=0, shots=0, attack=1, defense=1,
        morale_raw=0, luck_raw=0, retaliation_raw=0, real_health=0, experience_level_code=0,
        abilities=['hero'], magic_blob='phantom_forces-18-3-5-0-1-neutral-^')
    source = RawEntity(uid=13, owner=1, creature_id=72, max_hp=14, top_hp=3,
        min_damage=5, max_damage=8, mana=0, max_mana=0, speed=5, atb=100, initiative=13.2,
        max_count=55, count=35, x=1, y=10, attack_range=6, shots=14, attack=62, defense=43,
        morale_raw=0, luck_raw=0, retaliation_raw=0, real_health=0, experience_level_code=0,
        abilities=['alive','shooter','doubleshoot'])
    clone = RawEntity(uid=17, owner=1, creature_id=72, max_hp=14, top_hp=14,
        min_damage=5, max_damage=8, mana=0, max_mana=0, speed=5, atb=43, initiative=13.2,
        max_count=35, count=35, x=2, y=10, attack_range=6, shots=14, attack=62, defense=43,
        morale_raw=0, luck_raw=0, retaliation_raw=0, real_health=0, experience_level_code=0,
        abilities=['alive','shooter','doubleshoot'], is_phantom=True)
    c = parse_commands('Sphm001017180130000')[0]
    assert c.actor_uid == 1 and c.target_uid == 13 and c.amount == 17
    assert c.value == 18 and c.duration == 0
    entities = {1: caster, 13: source, 17: clone}
    assert _validated_phantom_forces(c, entities)
    _apply_command(entities, c)
    assert caster.mana == 12

    p = parse_commands('P017286')[0]
    spawn = parse_commands(
        'M017:0000010000720000140000140000050000080000000000000000050000430013.2'
        '000035000035000002000010000006000014000062000043000000000001000001000014000003'
        'unit|[1.4]|Unit|alive|shooter|doubleshoot|~^phm100000000001'
    )[0]
    pending = [p, spawn, c]
    before = {1: caster, 13: source}
    assert _validated_phantom_forces_decision(c, pending, before)
    assert _decision_semantic_unresolved_flags(pending, before, 1) == [False, False, False]


def test_rune_speed_exact_activation_clear_and_action_label():
    from hwm_solver.protocol.replay import (
        BattleSnapshot, _action_from_commands, _apply_command,
        _decision_semantic_unresolved_flags,
    )
    # The run modifier is authoritative raw state; no creature-id/name lookup is used.
    e = parse_entity_record(
        "M011:000001000172000022000022000003000005000000000000000005000100000010"
        "000010000010000001000001000000000000000008000006000000000000000001000022000223"
        "unit|[1.4]|Unit|alive|~^run100000000001"
    )
    assert e.run_modifier == "100000000001"
    assert e.rune_speed_available and not e.rune_speed_consumed and not e.rune_speed_active

    activate = parse_commands("m0110101Srn2011001100200000")
    assert [c.opcode for c in activate] == ["MOVE", "RUNE_SPEED_ACTIVATE"]
    snap = BattleSnapshot("x", 0, 1, 11, 1, {11: e})
    typ, *_rest, codes = _action_from_commands(11, activate, snap)
    assert typ == "ABILITY" and "rn2" in codes
    assert _decision_semantic_unresolved_flags(activate, {11: e}, 11) == [False, False]
    for c in activate:
        _apply_command({11: e}, c)
    assert e.rune_speed_active and e.rune_speed_consumed

    clear = parse_commands("Srn2011000000000000")[0]
    assert clear.opcode == "RUNE_SPEED_CLEAR"
    assert _decision_semantic_unresolved_flags([clear], {11: e}, 11) == [False]
    _apply_command({11: e}, clear)
    assert not e.rune_speed_active and e.rune_speed_consumed


def test_endurance_u_record_exact_speed_increment():
    from hwm_solver.protocol.replay import RawEntity, LowLevelCommand, _decision_semantic_unresolved_flags, _apply_command

    e = RawEntity(
        uid=18, owner=2, creature_id=920, max_hp=100, top_hp=100,
        min_damage=1, max_damage=2, mana=0, max_mana=0, speed=4.0, atb=0,
        initiative=10, max_count=1, count=1, x=10, y=1, attack_range=0, shots=0,
        attack=10, defense=10, morale_raw=0, luck_raw=0, retaliation_raw=0,
        real_health=100, experience_level_code=0, abilities=["alive", "big", "endurance"],
    )
    entities = {18: e}
    cmd = LowLevelCommand("U_RECORD", "u018", actor_uid=18)
    assert _decision_semantic_unresolved_flags([cmd], entities, 1) == [False]
    _apply_command(entities, cmd)
    assert entities[18].speed == 5.0
    for _ in range(10):
        _apply_command(entities, cmd)
    assert entities[18].speed == 8.0

    other = RawEntity(
        uid=3, owner=2, creature_id=930, max_hp=100, top_hp=100,
        min_damage=1, max_damage=2, mana=0, max_mana=0, speed=4.0, atb=0,
        initiative=10, max_count=1, count=1, x=10, y=1, attack_range=0, shots=0,
        attack=10, defense=10, morale_raw=0, luck_raw=0, retaliation_raw=0,
        real_health=100, experience_level_code=0, abilities=["alive", "shooter"],
    )
    assert _decision_semantic_unresolved_flags([LowLevelCommand("U_RECORD", "u003", actor_uid=3)], {3: other}, 1) == [True]


def test_observed_stoning_and_crippling_are_exact_and_activation_scoped():
    from hwm_solver.protocol.replay import (
        _apply_decision_commands, _decision_semantic_unresolved_flags,
        _tick_observed_activation_effects,
    )
    stone = _entity_for_action(1, abilities="alive|stoning")
    cripple = _entity_for_action(3, abilities="alive|cripplingwound")
    target = _entity_for_action(2, owner=2, abilities="alive")
    entities = {1: stone, 2: target, 3: cripple}

    sta = parse_commands("Ssta001002000000098")
    assert sta[0].target_uid == 2 and sta[0].code == "sta"
    assert _decision_semantic_unresolved_flags(sta, entities, 1) == [False]
    _apply_decision_commands(entities, 1, "MELEE_ATTACK", sta)
    assert "proc_stone" in target.effects and target.effect_turns["proc_stone"] == 1
    _tick_observed_activation_effects(target)
    assert "proc_stone" not in target.effects

    wnd = parse_commands("Swnd003002000000000")
    assert wnd[0].target_uid == 2 and wnd[0].code == "wnd"
    assert _decision_semantic_unresolved_flags(wnd, entities, 3) == [False]
    _apply_decision_commands(entities, 3, "MELEE_ATTACK", wnd)
    assert "proc_cripple" in target.effects and target.effect_turns["proc_cripple"] == 2
    _tick_observed_activation_effects(target)
    assert target.effect_turns["proc_cripple"] == 1
    _tick_observed_activation_effects(target)
    assert "proc_cripple" not in target.effects

def test_mana_drain_wire_pair_is_exact_state_mutation():
    from hwm_solver.protocol.replay import RawEntity, parse_commands, _apply_decision_commands, _decision_semantic_unresolved_flags
    actor=RawEntity(uid=14,owner=1,creature_id=68,max_hp=19,top_hp=3,min_damage=1,max_damage=2,mana=0,max_mana=0,speed=5,atb=0,initiative=10,max_count=84,count=72,x=1,y=1,attack_range=0,shots=0,attack=10,defense=10,morale_raw=0,luck_raw=0,retaliation_raw=0,real_health=0,experience_level_code=0,abilities=['undead','flyer','incorporeal','manadrain'])
    target=RawEntity(uid=5,owner=2,creature_id=855,max_hp=20,top_hp=20,min_damage=1,max_damage=2,mana=10,max_mana=10,speed=5,atb=0,initiative=10,max_count=10,count=10,x=2,y=1,attack_range=0,shots=0,attack=10,defense=10,morale_raw=0,luck_raw=0,retaliation_raw=0,real_health=0,experience_level_code=0,abilities=['alive','caster'])
    entities={14:actor,5:target}
    cmds=parse_commands('Srgl000014000000095z014005005')
    flags=_decision_semantic_unresolved_flags(cmds,entities,14)
    assert flags == [False, False]
    before=actor.total_hp
    _apply_decision_commands(entities,14,'MELEE_ATTACK',cmds)
    assert actor.total_hp == before + 95
    assert target.mana == 5

def test_entrenchment_observed_stationary_then_move_lifecycle():
    from hwm_solver.protocol.replay import RawEntity, parse_commands, _apply_decision_commands
    e=RawEntity(uid=1,owner=1,creature_id=1,max_hp=20,top_hp=20,min_damage=1,max_damage=2,mana=0,max_mana=0,speed=5,atb=0,initiative=10,max_count=10,count=10,x=1,y=1,attack_range=0,shots=0,attack=10,defense=10,morale_raw=0,luck_raw=0,retaliation_raw=0,real_health=0,experience_level_code=0,abilities=['alive','entrenchment'])
    entities={1:e}
    _apply_decision_commands(entities,1,'DEFEND',parse_commands('m0010101Sdef001100000000030i0010100'))
    assert entities[1].effect_values.get('proc_entrenchment') == 0.5
    _apply_decision_commands(entities,1,'MOVE',parse_commands('m0010201i0010100'))
    assert 'proc_entrenchment' not in entities[1].effects


def test_battle_thirst_and_taste_of_blood_wire_counters_are_exact():
    from hwm_solver.protocol.replay import (
        _apply_decision_commands,
        _decision_semantic_unresolved_flags,
        parse_commands,
    )
    thirst = _entity_for_action(1, abilities="alive|battlethirst")
    taste = _entity_for_action(2, owner=2, abilities="alive|tasteofblood")
    thirst.attack = 10
    taste.min_damage = 2
    taste.max_damage = 4
    entities = {1: thirst, 2: taste}

    cmds = parse_commands("Sbtt001004000000000Stob002007000000000")
    assert _decision_semantic_unresolved_flags(cmds, entities, 1) == [False, False]
    _apply_decision_commands(entities, 1, "DEFEND", cmds)
    assert thirst.effect_values["btt"] == 4.0
    assert taste.effect_values["tob"] == 5.0
