from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

WORKFLOW = Path('.github/workflows/apply_mightyslam_patch.yml')
SCRIPT = Path('.github/scripts/apply_mightyslam_patch.py')


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'{path}: expected one anchor, found {n}: {old[:100]!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')


def replace_n(path: str, old: str, new: str, expected: int) -> None:
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    n = text.count(old)
    if n != expected:
        raise SystemExit(f'{path}: expected {expected} anchors, found {n}: {old[:100]!r}')
    p.write_text(text.replace(old, new), encoding='utf-8')


def run(*args: str, env=None, capture: bool = False) -> str:
    cp = subprocess.run(args, check=True, env=env, text=True, capture_output=capture)
    return cp.stdout if capture else ''


# ---------------------------------------------------------------------------
# Python replay: exact Sm​sl grammar, semantic gate, cooldown marker, ABILITY.
# ---------------------------------------------------------------------------
py = 'python/hwm_solver/protocol/replay.py'
replace_once(
    py,
    '''def _validated_mana_feed(command: "LowLevelCommand", entities: dict[int, RawEntity]) -> bool:\n''',
    '''def _validated_mighty_slam(command: "LowLevelCommand", entities: dict[int, RawEntity]) -> bool:\n    """Validate the corpus-proven Mighty Slam activation marker.\n\n    All 32 observed records are `Smsl` + actor3 + twelve zeroes, occur on a living\n    carrier of `mightyslam`, and are followed by ordinary DAMAGE / optional\n    FORCED_POSITION records that remain the authoritative observed transition.\n    """\n    if command.opcode != "SPECIAL" or command.code != "msl" or command.actor_uid is None:\n        return False\n    actor = entities.get(int(command.actor_uid))\n    return bool(\n        actor and actor.alive and "mightyslam" in set(actor.abilities)\n        and command.raw == f"Smsl{int(command.actor_uid):03d}000000000000"\n    )\n\n\ndef _validated_mana_feed(command: "LowLevelCommand", entities: dict[int, RawEntity]) -> bool:\n'''
)

replace_once(
    py,
    '''            elif code == "mfd" and len(numeric) == 15 and numeric.isdigit() and numeric[8:] == "0000000":\n''',
    '''            elif code == "msl" and len(numeric) == 15 and numeric.isdigit() and numeric[3:] == "000000000000":\n                # Mighty Slam activation marker: actor3 + zero trailer. Damage targets\n                # and knockback are carried by the following d/b records.\n                out.append(LowLevelCommand(\n                    "SPECIAL", raw, actor_uid=int(numeric[:3]), duration=0, code=code,\n                ))\n            elif code == "mfd" and len(numeric) == 15 and numeric.isdigit() and numeric[8:] == "0000000":\n'''
)

replace_once(
    py,
    '''        elif c.opcode == "SPECIAL" and c.code == "mfd":\n            unresolved = not _validated_mana_feed(c, entities)\n''',
    '''        elif c.opcode == "SPECIAL" and c.code == "msl":\n            unresolved = not _validated_mighty_slam(c, entities)\n        elif c.opcode == "SPECIAL" and c.code == "mfd":\n            unresolved = not _validated_mana_feed(c, entities)\n'''
)

# State mutation anchor is intentionally found by the already verified Mana Feed branch.
replace_once(
    py,
    '''    elif c.opcode == "SPECIAL" and c.code == "mfd" and _validated_mana_feed(c, entities):\n''',
    '''    elif c.opcode == "SPECIAL" and c.code == "msl" and _validated_mighty_slam(c, entities):\n        actor = entities[int(c.actor_uid)]\n        actor.effects["msl"] = "observed:Smsl cooldown"\n        actor.effect_turns["msl"] = 3\n    elif c.opcode == "SPECIAL" and c.code == "mfd" and _validated_mana_feed(c, entities):\n'''
)

replace_once(
    py,
    '''    for key in ("proc_stone", "proc_cripple"):\n''',
    '''    for key in ("proc_stone", "proc_cripple", "msl"):\n'''
)

# There are two compact/full decision classifiers with the same local structure.
replace_n(
    py,
    '''    mana_feed = next((c for c in specials if c.code == "mfd" and c.actor_uid == actor_uid and c.target_uid is not None), None)\n''',
    '''    mana_feed = next((c for c in specials if c.code == "mfd" and c.actor_uid == actor_uid and c.target_uid is not None), None)\n    mighty_slam = next((c for c in specials if c.code == "msl" and c.actor_uid == actor_uid), None)\n''',
    2,
)
replace_n(
    py,
    '''    elif mana_feed:\n        typ = "ABILITY"\n''',
    '''    elif mana_feed:\n        typ = "ABILITY"\n    elif mighty_slam:\n        typ = "ABILITY"\n''',
    2,
)

# ---------------------------------------------------------------------------
# Python replay regression.
# ---------------------------------------------------------------------------
pytest = 'python/tests/test_replay_parser.py'
replace_once(
    pytest,
    '''def test_tooltips_decode():\n''',
    r'''def test_mighty_slam_exact_wire_cooldown_and_action_type():
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


def test_tooltips_decode():'''
)

# ---------------------------------------------------------------------------
# C++ observed protocol: exact Sm​sl marker and 3-activation cooldown effect.
# ---------------------------------------------------------------------------
proto = 'cpp/src/protocol.cpp'
replace_once(
    proto,
    '''                else if(code=="mfd" && j==i+19 && digits(text.substr(i+4,15)) && text.substr(i+12,7)=="0000000"){\n''',
    '''                else if(code=="msl" && j==i+19 && digits(text.substr(i+4,15)) && text.substr(i+7,12)=="000000000000"){\n                    const uint64_t slam_uid=loose_int(text.substr(i+4,3));\n                    auto* slam_actor=s.entity(slam_uid);\n                    const bool exact=slam_actor&&slam_actor->alive&&has_ability(*slam_actor,"mightyslam");\n                    if(exact){known(n);upsert_status_effect(*slam_actor,"msl",3,1.0f,text.substr(i,n));emit(events,seq,"MIGHTY_SLAM",slam_uid,0,text.substr(i,n));}\n                    else{semantic(n);emit(events,seq,"SPECIAL",slam_uid,0,text.substr(i,n));}\n                }\n                else if(code=="mfd" && j==i+19 && digits(text.substr(i+4,15)) && text.substr(i+12,7)=="0000000"){\n'''
)
replace_once(
    proto,
    '''                    const uint32_t stone=status_effect_id("proc_stone"),cripple=status_effect_id("proc_cripple");\n                    for(auto&fx:prev->effects) if((fx.id==stone||fx.id==cripple)&&fx.duration>0)--fx.duration;\n                    prev->effects.erase(std::remove_if(prev->effects.begin(),prev->effects.end(),[&](const Effect&fx){\n                        return (fx.id==stone||fx.id==cripple)&&fx.duration<=0;\n                    }),prev->effects.end());\n''',
    '''                    const uint32_t stone=status_effect_id("proc_stone"),cripple=status_effect_id("proc_cripple"),slam=status_effect_id("msl");\n                    for(auto&fx:prev->effects) if((fx.id==stone||fx.id==cripple||fx.id==slam)&&fx.duration>0)--fx.duration;\n                    prev->effects.erase(std::remove_if(prev->effects.begin(),prev->effects.end(),[&](const Effect&fx){\n                        return (fx.id==stone||fx.id==cripple||fx.id==slam)&&fx.duration<=0;\n                    }),prev->effects.end());\n'''
)

# ---------------------------------------------------------------------------
# C++ legal action + exact core transition.
# ---------------------------------------------------------------------------
sim = 'cpp/src/simulator.cpp'
replace_once(
    sim,
    '''    const uint32_t carrier_wire_id=stable_tag_id("car");\n    const uint32_t mana_feed_wire_id=stable_tag_id("mfd");\n''',
    '''    const uint32_t carrier_wire_id=stable_tag_id("car");\n    const uint32_t mana_feed_wire_id=stable_tag_id("mfd");\n    const uint32_t mighty_slam_wire_id=stable_tag_id("msl");\n'''
)

# Add an Ability action alongside every legal generic melee anchor.
replace_once(
    sim,
    '''            Action hit;hit.action_id=id++;hit.actor_uid=actor->uid;hit.type=ActionType::MeleeAttack;hit.target_uid=e.uid;hit.source="generic";if(anchor!=actor->anchor)hit.destination=anchor;a.push_back(std::move(hit));\n''',
    '''            Action hit;hit.action_id=id++;hit.actor_uid=actor->uid;hit.type=ActionType::MeleeAttack;hit.target_uid=e.uid;hit.source="generic";if(anchor!=actor->anchor)hit.destination=anchor;a.push_back(std::move(hit));\n            if(!actor->rune_speed_active&&has_tag(*actor,"mightyslam")&&!has_live_effect(*actor,"msl")){\n                Action slam;slam.action_id=id++;slam.actor_uid=actor->uid;slam.type=ActionType::Ability;slam.target_uid=e.uid;\n                slam.ability_id=mighty_slam_wire_id;slam.source="exact:Smsl+reference+corpus";if(anchor!=actor->anchor)slam.destination=anchor;a.push_back(std::move(slam));\n            }\n'''
)

# Apply-side IDs and movement bookkeeping.
replace_once(
    sim,
    '''    const uint32_t carrier_wire_id=stable_tag_id("car");\n    const uint32_t mana_feed_wire_id=stable_tag_id("mfd");\n    const bool rune_activation=a.type==ActionType::Ability&&a.ability_id&&*a.ability_id==rune_speed_id;\n''',
    '''    const uint32_t carrier_wire_id=stable_tag_id("car");\n    const uint32_t mana_feed_wire_id=stable_tag_id("mfd");\n    const uint32_t mighty_slam_wire_id=stable_tag_id("msl");\n    const bool rune_activation=a.type==ActionType::Ability&&a.ability_id&&*a.ability_id==rune_speed_id;\n'''
)
replace_once(
    sim,
    '''    const bool carrier_action=a.type==ActionType::Ability&&a.ability_id&&*a.ability_id==carrier_wire_id;\n    const bool mana_feed_action=a.type==ActionType::Ability&&a.ability_id&&*a.ability_id==mana_feed_wire_id;\n''',
    '''    const bool carrier_action=a.type==ActionType::Ability&&a.ability_id&&*a.ability_id==carrier_wire_id;\n    const bool mana_feed_action=a.type==ActionType::Ability&&a.ability_id&&*a.ability_id==mana_feed_wire_id;\n    const bool mighty_slam_action=a.type==ActionType::Ability&&a.ability_id&&*a.ability_id==mighty_slam_wire_id;\n'''
)
replace_once(
    sim,
    '''    const bool self_moves=(a.type==ActionType::Move&&a.destination&&*a.destination!=actor->anchor)||(a.type==ActionType::MeleeAttack&&a.destination&&*a.destination!=actor->anchor);\n''',
    '''    const bool self_moves=(a.type==ActionType::Move&&a.destination&&*a.destination!=actor->anchor)||(a.type==ActionType::MeleeAttack&&a.destination&&*a.destination!=actor->anchor)||(mighty_slam_action&&a.destination&&*a.destination!=actor->anchor);\n'''
)

# Insert Slam before Mana Feed. Target list is frozen before any knockback.
replace_once(
    sim,
    '''    } else if(mana_feed_action){\n''',
    '''    } else if(mighty_slam_action){\n        if(!a.target_uid||!has_tag(*actor,"mightyslam")||has_live_effect(*actor,"msl")){tr.valid=false;tr.warning="mighty_slam_unavailable";return tr;}\n        const Cell origin=actor->anchor;if(a.destination)actor->anchor=*a.destination;\n        const int moved_cells=a.destination?dist(origin,*a.destination):0;\n        auto*primary=tr.state.entity(*a.target_uid);\n        if(!primary||!primary->alive||primary->is_hero||primary->is_hidden||primary->side==actor->side||primary->side==Side::Unknown||\n           !footprints_adjacent(*actor,actor->anchor,*primary,primary->anchor)){tr.valid=false;tr.warning="mighty_slam_target_invalid";return tr;}\n        std::vector<uint64_t> slam_targets{primary->uid};\n        for(uint64_t uid:collateral_candidates(tr.state,*actor,*primary,CollateralZone::TargetAdjacent)){\n            const auto*secondary=tr.state.entity(uid);\n            if(!secondary||!secondary->alive||secondary->side==actor->side||secondary->side==Side::Unknown)continue;\n            slam_targets.push_back(uid);\n        }\n        std::sort(slam_targets.begin()+1,slam_targets.end());\n        slam_targets.erase(std::unique(slam_targets.begin(),slam_targets.end()),slam_targets.end());\n        std::vector<uint64_t> knockback_candidates;\n        for(size_t idx=0;idx<slam_targets.size();++idx){\n            auto*target=tr.state.entity(slam_targets[idx]);if(!target||!target->alive)continue;\n            const double hit_roll=std::clamp(roll+0.04*(double(idx)-double(slam_targets.size()-1)/2.0),0.0,1.0);\n            const int dmg=std::max(1,(int)std::llround(roll_damage(tr.state,*actor,*target,hit_roll,false,false,moved_cells)*damage_.multiplier(actor->creature_id,ActionType::MeleeAttack)*ability_transfer_multiplier(damage_,ability_damage_,*actor,*target,ActionType::MeleeAttack)));\n            const int hp_before=total_hp(*target);const bool phantom=target->is_phantom;deal_damage(*target,dmg);\n            const int actual=std::max(0,hp_before-total_hp(*target));const int drain=(phantom&&actual>0)?std::min(dmg,hp_before):actual;\n            if(drain>0&&has_tag(*actor,"lifedrain"))restore_hp(*actor,drain/2);\n            if(actual>0&&target->alive&&has_tag(*actor,"weakeningstrike")){target->attack=std::max(0.0f,target->attack-4.0f);if(!has_tag(*target,"armoured")&&!has_tag(*target,"organicarmor"))target->defense=std::max(0.0f,target->defense-4.0f);}\n            if(actual>0&&actor->alive&&target->alive&&has_tag(*target,"fireshield")){const int reflected=std::max(0,(int)std::llround(actual*0.20*fire_damage_multiplier(*actor)));if(reflected>0)deal_damage(*actor,reflected);}\n            if(actual>0&&actor->alive&&target->alive&&has_tag(*target,"magmashield")){const int reflected=std::max(0,(int)std::llround(actual*0.40*fire_damage_multiplier(*actor)));if(reflected>0)deal_damage(*actor,reflected);}\n            if(actual>0&&actor->alive&&target->alive&&has_tag(*target,"painmirror"))deal_damage(*actor,std::max(0,(int)std::llround(actual*0.10)));\n            if(target->alive&&!target->is_big)knockback_candidates.push_back(target->uid);\n        }\n        // Corpus: every observed forced-position target is small. Push one cell away\n        // from the Slam actor only when the resulting footprint is legal; otherwise the\n        // server simply emits no forced-position record.\n        for(uint64_t uid:knockback_candidates){\n            auto*target=tr.state.entity(uid);if(!target||!target->alive||target->is_big)continue;\n            const double acx=actor->anchor.x+(actor->footprint_w-1)*0.5,acy=actor->anchor.y+(actor->footprint_h-1)*0.5;\n            const double tcx=target->anchor.x+(target->footprint_w-1)*0.5,tcy=target->anchor.y+(target->footprint_h-1)*0.5;\n            const int sx=signum(tcx-acx),sy=signum(tcy-acy);if(!sx&&!sy)continue;\n            const Cell pushed{target->anchor.x+sx,target->anchor.y+sy};if(can_place(tr.state,*target,pushed))target->anchor=pushed;\n        }\n        // Set 3 before the generic end-of-action tick. It becomes 2 immediately,\n        // blocks the next two own activations, and is available on the third — exactly\n        // the minimum repeat gap measured in the corpus.\n        set_proc_effect(*actor,"msl",3,1.0f,"exact:mightyslam cooldown");tr.warning="exact_mighty_slam";\n    } else if(mana_feed_action){\n'''
)

# ---------------------------------------------------------------------------
# C++ regression: splash enemies only, small knockback, no retaliation, cooldown.
# ---------------------------------------------------------------------------
cpptest = 'cpp/tests/test_main.cpp'
anchor = 'static bool test_mana_feed_exact_action_and_protocol() {'
test_fn = r'''static bool test_mighty_slam_exact_action_splash_knockback_cooldown() {
    GenericSimulator sim;
    BattleState s=fixture(); auto* actor=s.entity(1); auto* primary=s.entity(2); CHECK(actor&&primary);
    actor->owner=1;actor->side=Side::Player;actor->anchor={1,1};actor->count=8;actor->max_count=8;
    actor->max_hp_per_unit=100;actor->top_unit_hp=100;actor->attack=25;actor->min_damage=actor->max_damage=10;
    actor->ability_ids.push_back(stable_ability_id("mightyslam"));
    primary->owner=2;primary->side=Side::Pve;primary->anchor={2,1};primary->count=20;primary->max_count=20;
    primary->max_hp_per_unit=50;primary->top_unit_hp=50;primary->retaliation_available=true;primary->min_damage=primary->max_damage=100;
    Entity secondary=*primary;secondary.uid=3;secondary.anchor={2,2};secondary.count=20;secondary.max_count=20;secondary.top_unit_hp=50;
    Entity friendly=secondary;friendly.uid=4;friendly.owner=1;friendly.side=Side::Player;friendly.anchor={3,2};
    Entity far=secondary;far.uid=5;far.anchor={8,8};
    Entity big=secondary;big.uid=6;big.anchor={3,1};big.is_big=true;big.footprint_w=2;big.footprint_h=1;
    s.entities.push_back(secondary);s.entities.push_back(friendly);s.entities.push_back(far);s.entities.push_back(big);

    auto acts=sim.legal_actions(s);
    auto slam=std::find_if(acts.begin(),acts.end(),[](const Action&a){return a.type==ActionType::Ability&&a.target_uid&&*a.target_uid==2&&a.ability_id&&*a.ability_id==stable_ability_id("msl")&&!a.destination;});
    CHECK(slam!=acts.end());
    const int actor_hp=entity_total_hp(*actor), p_hp=entity_total_hp(*primary), sec_hp=entity_total_hp(*s.entity(3));
    const int friend_hp=entity_total_hp(*s.entity(4)), far_hp=entity_total_hp(*s.entity(5)), big_hp=entity_total_hp(*s.entity(6));
    const Cell p0=primary->anchor, sec0=s.entity(3)->anchor, big0=s.entity(6)->anchor;
    auto tr=sim.apply(s,*slam,0.5); CHECK(tr.valid); CHECK(tr.warning=="exact_mighty_slam");
    CHECK(entity_total_hp(*tr.state.entity(2))<p_hp); CHECK(entity_total_hp(*tr.state.entity(3))<sec_hp);
    CHECK(entity_total_hp(*tr.state.entity(4))==friend_hp); CHECK(entity_total_hp(*tr.state.entity(5))==far_hp);
    CHECK(entity_total_hp(*tr.state.entity(6))<big_hp); // adjacent enemy big stack is splashed
    CHECK(entity_total_hp(*tr.state.entity(1))==actor_hp); // no ordinary retaliation
    CHECK(tr.state.entity(2)->anchor!=p0); CHECK(tr.state.entity(3)->anchor!=sec0);
    CHECK(tr.state.entity(6)->anchor==big0); // big creature never knocked back
    CHECK(effect_magnitude(*tr.state.entity(1),"msl")>0.0f);

    BattleState cd=tr.state;cd.active_entity_uid=1;cd.side_to_act=Side::Player;
    auto blocked1=sim.legal_actions(cd);CHECK(std::none_of(blocked1.begin(),blocked1.end(),[](const Action&a){return a.ability_id&&*a.ability_id==stable_ability_id("msl");}));
    auto w1=std::find_if(blocked1.begin(),blocked1.end(),[](const Action&a){return a.type==ActionType::Wait;});CHECK(w1!=blocked1.end());
    auto t1=sim.apply(cd,*w1,0.5);CHECK(t1.valid);t1.state.active_entity_uid=1;t1.state.side_to_act=Side::Player;
    auto blocked2=sim.legal_actions(t1.state);CHECK(std::none_of(blocked2.begin(),blocked2.end(),[](const Action&a){return a.ability_id&&*a.ability_id==stable_ability_id("msl");}));
    auto w2=std::find_if(blocked2.begin(),blocked2.end(),[](const Action&a){return a.type==ActionType::Wait;});CHECK(w2!=blocked2.end());
    auto t2=sim.apply(t1.state,*w2,0.5);CHECK(t2.valid);t2.state.active_entity_uid=1;t2.state.side_to_act=Side::Player;
    auto ready=sim.legal_actions(t2.state);CHECK(std::any_of(ready.begin(),ready.end(),[](const Action&a){return a.ability_id&&*a.ability_id==stable_ability_id("msl");}));

    // Observed protocol marker becomes semantic-safe and stores the same cooldown.
    BattleState p=s;p.stream_contiguous=false;p.protocol_ready=false;p.recommendation_safe=false;p.active_entity_uid=1;
    ProtocolDecoder decoder;
    auto decoded=decoder.decode_update(p,"t=000turns=>1:C001000000Smsl001000000000000d0010020000000010i0010100C002000000");
    CHECK(std::any_of(decoded.events.begin(),decoded.events.end(),[](const BattleEvent&e){return e.type=="MIGHTY_SLAM"&&e.actor_uid==1;}));
    CHECK(effect_magnitude(*decoded.state.entity(1),"msl")>0.0f);CHECK(decoded.state.semantic_unresolved_records==0);
    return true;
}


'''
replace_once(cpptest, anchor, test_fn + anchor)
replace_once(
    cpptest,
    '    if (!test_mana_feed_exact_action_and_protocol()) return EXIT_FAILURE;',
    '    if (!test_mighty_slam_exact_action_splash_knockback_cooldown()) return EXIT_FAILURE;\n    if (!test_mana_feed_exact_action_and_protocol()) return EXIT_FAILURE;'
)

# ---------------------------------------------------------------------------
# Registry promotion.
# ---------------------------------------------------------------------------
reg = 'python/hwm_solver/knowledge/build_ability_registry.py'
replace_once(
    reg,
    '    "takeroots", "fireattack", "battlethirst", "tasteofblood", "bloodfrenzy", "organicarmor", "shieldother", "concentration", "lizardbite", "lifedrain", "regeneration", "manafeed",\n',
    '    "takeroots", "fireattack", "battlethirst", "tasteofblood", "bloodfrenzy", "organicarmor", "shieldother", "concentration", "lizardbite", "lifedrain", "regeneration", "manafeed", "mightyslam",\n'
)
run('python','python/hwm_solver/knowledge/build_ability_registry.py','data/catalog/generated_v4.json','--out','data/catalog/ability_registry.json','--ability-damage','models/ability_damage_model.csv','--collateral','models/collateral_model.csv','--proc','models/proc_model.csv','--kill-trigger','models/kill_trigger_model.csv')
registry=json.loads(Path('data/catalog/ability_registry.json').read_text(encoding='utf-8'))
counts=registry['support_counts']
if counts.get('exact_search')!=85 or counts.get('learned_damage')!=177 or counts.get('unresolved')!=78:
    raise SystemExit(f'unexpected registry counts after Mighty Slam: {counts}')

# ---------------------------------------------------------------------------
# Corpus verification using patched replay parser.
# ---------------------------------------------------------------------------
env=os.environ.copy();env['PYTHONPATH']='python'
run('python','scripts/ability_probe.py','hwm_battles','mightyslam','--rows','1000','--out','data/reports/mightyslam_probe.json',env=env)
probe=json.loads(Path('data/reports/mightyslam_probe.json').read_text(encoding='utf-8'))
msl_rows=[r for r in probe['rows'] if 'msl' in set(r.get('special_codes') or [])]
if len(msl_rows)!=32:
    raise SystemExit(f'expected 32 Sm​sl rows, got {len(msl_rows)}')
if any(r['action_type']!='ABILITY' for r in msl_rows):
    raise SystemExit('not all Sm​sl rows classified as ABILITY')
if any(r['actor_before'] is None or 'mightyslam' not in set(r['actor_before'].get('abilities') or []) for r in msl_rows):
    raise SystemExit('Mighty Slam actor ability invariant failed')

# Current ability-risk report should reflect the promoted support class.
run('python','-m','hwm_solver.evaluation.ability_risk_report','hwm_battles','--registry','data/catalog/ability_registry.json','--out','data/reports/ability-risk-current.json',env=env)
risk=json.loads(Path('data/reports/ability-risk-current.json').read_text(encoding='utf-8'))

# ---------------------------------------------------------------------------
# Documentation status synchronization.
# ---------------------------------------------------------------------------
for path in ['SPEC.md','HeroesWM_Solver_TZ_Status_0.3.0.md']:
    p=Path(path);text=p.read_text(encoding='utf-8')
    text=text.replace('Life Drain, Regeneration и Mana Feed переведены в exact-search.','Life Drain, Regeneration, Mana Feed и Mighty Slam переведены в exact-search.',1)
    text=text.replace('registry: **84 exact-search**','registry: **85 exact-search**',1)
    text=text.replace('; **78 unresolved**. `Life Drain`', '; **78 unresolved**. `Mighty Slam` теперь имеет отдельный exact `ABILITY` path: выбранная цель + соседние вражеские стеки, knockback только small при валидной клетке, без retaliation, cooldown по минимальному наблюдаемому gap=3; `Life Drain`',1)
    text=text.replace('`Life Drain`, `Regeneration` и `Mana Feed` закрыты 10.08.2026','`Life Drain`, `Regeneration`, `Mana Feed` и `Mighty Slam` закрыты 10.08.2026',1)
    # Synchronize stale module/phase checkpoint snapshots without touching historical raw metrics.
    text=text.replace('Ability Registry: 81 exact-search, 11 exact-targeting', 'Ability Registry: 85 exact-search, 11 exact-targeting')
    text=text.replace('81 ability имеют exact-search support', '85 ability имеют exact-search support')
    text=text.replace('81 exact-search abilities плюс', '85 exact-search abilities плюс')
    p.write_text(text,encoding='utf-8')

for path in ['IMPLEMENTATION_REPORT.md','HeroesWM_Solver_Implementation_Report_0.3.0.md']:
    p=Path(path);text=p.read_text(encoding='utf-8')
    text=text.replace('| Ability Registry exact-search | 84 |','| Ability Registry exact-search | 85 |',1)
    text=text.replace('  "exact_search": 84,','  "exact_search": 85,',1)
    text=text.replace('  "learned_damage": 178,','  "learned_damage": 177,',1)
    text=text.replace('Mana Drain; Mana Feed; Life Drain; Regeneration; Blood Frenzy;', 'Mana Drain; Mana Feed; Life Drain; Regeneration; Mighty Slam; Blood Frenzy;',1)
    text=text.replace('Life Drain, Regeneration and Mana Feed are `exact_search`;', 'Life Drain, Regeneration, Mana Feed and Mighty Slam are `exact_search`;',1)
    text=text.replace('Life Drain, Regeneration and Mana Feed transitions.', 'Life Drain, Regeneration, Mana Feed and Mighty Slam transitions.',1)
    p.write_text(text,encoding='utf-8')

# TEST_REPORT registry counts; Python test count is updated after collection below.
tr=Path('TEST_REPORT.md');text=tr.read_text(encoding='utf-8')
text=re.sub(r'exact_search:\s+84', 'exact_search:           85', text, count=1)
text=text.replace('after exact Life Drain, Regeneration and Mana Feed transitions', 'after exact Life Drain, Regeneration, Mana Feed and Mighty Slam transitions',1)
tr.write_text(text,encoding='utf-8')

# ---------------------------------------------------------------------------
# Verification before functional commit.
# ---------------------------------------------------------------------------
WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True)
run('cmake','--preset','debug')
run('cmake','--build','build/debug','--parallel','2')
run('ctest','--test-dir','build/debug','--output-on-failure')
run('python','-m','pytest','-q',env=env)
collect=run('python','-m','pytest','--collect-only','-q',env=env,capture=True)
m=re.search(r'(\d+) tests? collected',collect)
if not m:
    # pytest -q may end in e.g. "42 tests collected in ..."
    raise SystemExit('could not determine pytest collection count')
pytests=int(m.group(1))
text=tr.read_text(encoding='utf-8')
text=re.sub(r'Python pytest:\s+\d+/\d+ PASS',f'Python pytest:              {pytests}/{pytests} PASS',text,count=1)
tr.write_text(text,encoding='utf-8')
run('git','diff','--check','--','cpp/src/protocol.cpp','cpp/src/simulator.cpp','cpp/tests/test_main.cpp','python/hwm_solver/protocol/replay.py','python/tests/test_replay_parser.py','python/hwm_solver/knowledge/build_ability_registry.py')

run('git','config','user.name','github-actions[bot]')
run('git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
run('git','add','-A')
run('git','commit','-m','feat: model exact Mighty Slam action')
functional_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()

# Changelog bookkeeping commit with the real functional SHA.
p=Path('changelog.md');text=p.read_text(encoding='utf-8').rstrip()+'\n\n'
staging=os.environ.get('GITHUB_SHA','unknown')
text += f'''### Exact Mighty Slam action\n\n- Commit: `{staging}`\n  - Staged a self-removing verified patch after 32/32 `Smsl` observations, multi-target/knockback evidence and same-actor cooldown-gap analysis.\n- Commit: `{functional_sha}`\n  - Promoted `mightyslam` to an explicit legal `ABILITY` sharing normal melee reach/move anchors.\n  - Added selected-target + target-adjacent **enemy-only** splash using the simulator's authoritative footprint geometry.\n  - Added one-cell knockback away from the actor only for surviving small targets and only when `can_place()` accepts the destination; observed corpus has 14/14 forced targets small.\n  - Suppressed ordinary retaliation for the Slam branch and retained core physical damage/resistance plus Life Drain, Weakening Strike and reflect interactions.\n  - Added a 3-activation cooldown marker; minimum observed same-actor repeat gap is 3.\n  - Decoded `Smsl<actor>000000000000` as semantic-safe in Python and C++; server DAMAGE/FORCED_POSITION remain authoritative for observed replay.\n  - Re-ran the 866-battle probe: **32/32 `Smsl` decisions classify as `ABILITY`**.\n  - Promoted registry to **85 exact-search / 177 learned-damage / 78 unresolved** and refreshed `ability-risk-current.json` (mean {risk['risk_mean']:.4f}, p90 {risk['risk_p90']:.4f}).\n  - Synchronized top-level and stale M04/M12/Phase7 ability counts in the active specification/reports.\n  - C++ Debug build/CTest and full Python pytest (**{pytests}/{pytests}**) passed before commit.\n'''
p.write_text(text,encoding='utf-8')
run('git','add','changelog.md')
run('git','commit','-m','docs: log exact Mighty Slam implementation')
run('git','push','origin','HEAD:main')
