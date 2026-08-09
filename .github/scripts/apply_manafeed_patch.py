from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

WORKFLOW=Path('.github/workflows/apply_manafeed_patch.yml')
SCRIPT=Path('.github/scripts/apply_manafeed_patch.py')


def replace_once(path:str,old:str,new:str)->None:
    p=Path(path); text=p.read_text(encoding='utf-8'); n=text.count(old)
    if n!=1: raise SystemExit(f'{path}: expected one anchor, found {n}')
    p.write_text(text.replace(old,new,1),encoding='utf-8')


def replace_n(path:str,old:str,new:str,n:int)->None:
    p=Path(path); text=p.read_text(encoding='utf-8'); got=text.count(old)
    if got!=n: raise SystemExit(f'{path}: expected {n} anchors, found {got}')
    p.write_text(text.replace(old,new),encoding='utf-8')


def run(*args:str,env=None)->None:
    subprocess.run(args,check=True,env=env)

# ---------------------------------------------------------------------------
# Python raw replay parser: exact Smfd layout and state mutation.
# ---------------------------------------------------------------------------
py='python/hwm_solver/protocol/replay.py'
replace_once(py,
'''def _validated_weakeningstrike(command: "LowLevelCommand", entities: dict[int, RawEntity]) -> bool:
    """Validate W<actor><target> as Weakening Strike.''',
'''def _validated_mana_feed(command: "LowLevelCommand", entities: dict[int, RawEntity]) -> bool:
    """Validate the corpus-proven Smfd Mana Feed record.

    All 42 observed records use actor3,own_hero3,amount2,0000000. The amount equals
    min(current stack count, current creature mana), matching the reference mechanic.
    """
    if command.opcode != "SPECIAL" or command.code != "mfd":
        return False
    if command.actor_uid is None or command.target_uid is None or command.amount is None:
        return False
    actor=entities.get(int(command.actor_uid)); hero=entities.get(int(command.target_uid))
    amount=int(command.amount)
    return bool(
        actor and hero and actor.alive and "manafeed" in set(actor.abilities)
        and hero.is_hero and actor.owner == hero.owner and amount > 0
        and int(command.duration or 0) == 0
        and amount == min(max(0,int(actor.count)),max(0,int(actor.mana)))
    )


def _validated_weakeningstrike(command: "LowLevelCommand", entities: dict[int, RawEntity]) -> bool:
    """Validate W<actor><target> as Weakening Strike.''')

replace_once(py,
'''            elif code == "rgl" and len(numeric) == 15 and numeric.isdigit() and numeric[:3] == "000":
                # Mana Drain's heal result uses 000,source_uid3,heal9. Other mechanics can''',
'''            elif code == "mfd" and len(numeric) == 15 and numeric.isdigit() and numeric[8:] == "0000000":
                # Mana Feed: actor3,own_hero3,amount2,0000000. Exactness is gated
                # against actor ability/owner/count/mana before the state mutation.
                out.append(LowLevelCommand(
                    "SPECIAL", raw, actor_uid=int(numeric[:3]), target_uid=int(numeric[3:6]),
                    amount=int(numeric[6:8]), duration=0, code=code,
                ))
            elif code == "rgl" and len(numeric) == 15 and numeric.isdigit() and numeric[:3] == "000":
                # Mana Drain's heal result uses 000,source_uid3,heal9. Other mechanics can''')

replace_once(py,
'''        elif c.opcode == "SPECIAL" and c.code == "rgl":
            drain_actor = entities.get(int(c.actor_uid)) if c.actor_uid is not None else None''',
'''        elif c.opcode == "SPECIAL" and c.code == "mfd":
            unresolved = not _validated_mana_feed(c, entities)
        elif c.opcode == "SPECIAL" and c.code == "rgl":
            drain_actor = entities.get(int(c.actor_uid)) if c.actor_uid is not None else None''')

replace_once(py,
'''    elif c.opcode == "SPECIAL" and c.code == "rgl" and c.actor_uid in entities and c.amount is not None:
        actor=entities[c.actor_uid]''',
'''    elif c.opcode == "SPECIAL" and c.code == "mfd" and _validated_mana_feed(c, entities):
        actor=entities[int(c.actor_uid)]; hero=entities[int(c.target_uid)]; amount=int(c.amount or 0)
        actor.mana=max(0,actor.mana-amount); hero.mana+=amount
    elif c.opcode == "SPECIAL" and c.code == "rgl" and c.actor_uid in entities and c.amount is not None:
        actor=entities[c.actor_uid]''')

# Both full and compact action classifiers should preserve the hero target and use ABILITY.
replace_n(py,
'''    specials = [c for c in cmds if c.opcode == "SPECIAL"]
    rune_speed_activations = [c for c in cmds if c.opcode == "RUNE_SPEED_ACTIVATE"]''',
'''    specials = [c for c in cmds if c.opcode == "SPECIAL"]
    mana_feed = next((c for c in specials if c.code == "mfd" and c.actor_uid == actor_uid and c.target_uid is not None), None)
    rune_speed_activations = [c for c in cmds if c.opcode == "RUNE_SPEED_ACTIVATE"]''',2)
replace_n(py,
'''    target_uid = dealt[0].target_uid if dealt else (teleports[0].target_uid if teleports else (carriers[0].target_uid if carriers else (phantom.target_uid if phantom else None)))''',
'''    target_uid = dealt[0].target_uid if dealt else (teleports[0].target_uid if teleports else (carriers[0].target_uid if carriers else (mana_feed.target_uid if mana_feed else (phantom.target_uid if phantom else None))))''',2)
replace_n(py,
'''    elif carriers:
        typ = "ABILITY"''',
'''    elif mana_feed:
        typ = "ABILITY"
    elif carriers:
        typ = "ABILITY"''',2)

# ---------------------------------------------------------------------------
# Python regression: parser + exact semantic gate + state transition.
# ---------------------------------------------------------------------------
pytest='python/tests/test_replay_parser.py'
replace_once(pytest,
'''    _perspective_owner, _apply_command,
)''',
'''    _perspective_owner, _apply_command, _decision_semantic_unresolved_flags,
)''')
replace_once(pytest,
'''def test_tooltips_decode():''',
r'''def test_mana_feed_exact_wire_and_transition():
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


def test_tooltips_decode():''')

# ---------------------------------------------------------------------------
# C++ live protocol decoder exact Smfd transition.
# ---------------------------------------------------------------------------
cppproto='cpp/src/protocol.cpp'
replace_once(cppproto,
'''                else if(code=="rgl" && j==i+19 && digits(text.substr(i+4,15)) && text.substr(i+4,3)=="000"){
                    // Mana Drain heal record.''',
'''                else if(code=="mfd" && j==i+19 && digits(text.substr(i+4,15)) && text.substr(i+12,7)=="0000000"){
                    // Mana Feed corpus invariant (42/42 observed): actor3,own_hero3,
                    // amount2,0000000. The amount is min(current count,current mana).
                    const uint64_t target_uid=loose_int(text.substr(i+7,3));
                    const int amount=loose_int(text.substr(i+10,2));
                    auto* actor=s.entity(uid); auto* hero=s.entity(target_uid);
                    const int expected=actor?std::min(std::max(0,actor->count),std::max(0,actor->mana)):0;
                    const bool exact=actor&&hero&&actor->alive&&has_ability(*actor,"manafeed")&&hero->is_hero&&
                        actor->owner==hero->owner&&amount>0&&amount==expected;
                    if(exact){known(n);actor->mana-=amount;hero->mana+=amount;emit(events,seq,"MANA_FEED",uid,target_uid,text.substr(i,n));}
                    else{semantic(n);emit(events,seq,"SPECIAL",uid,target_uid,text.substr(i,n));}
                }
                else if(code=="rgl" && j==i+19 && digits(text.substr(i+4,15)) && text.substr(i+4,3)=="000"){
                    // Mana Drain heal record.''')

# ---------------------------------------------------------------------------
# C++ legal action + simulator transition.
# ---------------------------------------------------------------------------
sim='cpp/src/simulator.cpp'
replace_once(sim,
'''    const uint32_t carrier_wire_id=stable_tag_id("car");
    if(!actor->rune_speed_active&&has_tag(*actor,"carrier")){''',
'''    const uint32_t carrier_wire_id=stable_tag_id("car");
    const uint32_t mana_feed_wire_id=stable_tag_id("mfd");
    if(!actor->rune_speed_active&&has_tag(*actor,"manafeed")&&actor->mana>0&&actor->count>0){
        for(const auto&hero:s.entities){
            if(!hero.alive||!hero.is_hero||hero.owner!=actor->owner)continue;
            Action feed;feed.action_id=id++;feed.actor_uid=actor->uid;feed.type=ActionType::Ability;
            feed.target_uid=hero.uid;feed.ability_id=mana_feed_wire_id;feed.source="exact:Smfd+reference";
            a.push_back(std::move(feed));
        }
    }
    if(!actor->rune_speed_active&&has_tag(*actor,"carrier")){''')
replace_once(sim,
'''    const uint32_t carrier_wire_id=stable_tag_id("car");
    const bool rune_activation=a.type==ActionType::Ability&&a.ability_id&&*a.ability_id==rune_speed_id;
    const bool carrier_action=a.type==ActionType::Ability&&a.ability_id&&*a.ability_id==carrier_wire_id;''',
'''    const uint32_t carrier_wire_id=stable_tag_id("car");
    const uint32_t mana_feed_wire_id=stable_tag_id("mfd");
    const bool rune_activation=a.type==ActionType::Ability&&a.ability_id&&*a.ability_id==rune_speed_id;
    const bool carrier_action=a.type==ActionType::Ability&&a.ability_id&&*a.ability_id==carrier_wire_id;
    const bool mana_feed_action=a.type==ActionType::Ability&&a.ability_id&&*a.ability_id==mana_feed_wire_id;''')
replace_once(sim,
'''    } else if(carrier_action){
        if(!a.target_uid||!a.destination){tr.valid=false;tr.warning="carrier_target_or_destination_missing";return tr;}''',
'''    } else if(mana_feed_action){
        if(!a.target_uid){tr.valid=false;tr.warning="mana_feed_target_missing";return tr;}
        auto* hero=tr.state.entity(*a.target_uid);
        const int amount=std::min(std::max(0,actor->count),std::max(0,actor->mana));
        if(!hero||!hero->alive||!hero->is_hero||hero->owner!=actor->owner||!has_tag(*actor,"manafeed")||amount<=0){
            tr.valid=false;tr.warning="mana_feed_action_invalid";return tr;
        }
        actor->mana-=amount;hero->mana+=amount;tr.warning="exact_mana_feed";
    } else if(carrier_action){
        if(!a.target_uid||!a.destination){tr.valid=false;tr.warning="carrier_target_or_destination_missing";return tr;}''')

# ---------------------------------------------------------------------------
# C++ regression: legal target, min(count,mana), protocol state mutation.
# ---------------------------------------------------------------------------
cpptest='cpp/tests/test_main.cpp'
anchor='static bool test_mana_drain_and_reference_damage_perks() {'
test_fn=r'''static bool test_mana_feed_exact_action_and_protocol() {
    GenericSimulator sim;
    BattleState s=fixture(); auto* actor=s.entity(1); CHECK(actor);
    actor->owner=1; actor->count=5; actor->max_count=20; actor->mana=15;
    actor->ability_ids.push_back(stable_ability_id("manafeed"));
    Entity hero; hero.uid=3; hero.owner=1; hero.side=Side::Player; hero.is_hero=true; hero.alive=true; hero.mana=10;
    Entity enemy_hero=hero; enemy_hero.uid=4; enemy_hero.owner=2; enemy_hero.side=Side::Pve; enemy_hero.mana=7;
    s.entities.push_back(hero); s.entities.push_back(enemy_hero);

    auto acts=sim.legal_actions(s);
    auto feed=std::find_if(acts.begin(),acts.end(),[](const Action&a){
        return a.type==ActionType::Ability&&a.target_uid&&*a.target_uid==3&&a.ability_id&&*a.ability_id==stable_ability_id("mfd");
    });
    CHECK(feed!=acts.end());
    CHECK(std::none_of(acts.begin(),acts.end(),[](const Action&a){return a.type==ActionType::Ability&&a.target_uid&&*a.target_uid==4&&a.ability_id&&*a.ability_id==stable_ability_id("mfd");}));
    auto tr=sim.apply(s,*feed,0.5); CHECK(tr.valid); CHECK(tr.warning=="exact_mana_feed");
    CHECK(tr.state.entity(1)->mana==10); CHECK(tr.state.entity(3)->mana==15); CHECK(tr.state.entity(4)->mana==7);

    BattleState limited=s; limited.entity(1)->count=20; limited.entity(1)->mana=3;
    auto limited_acts=sim.legal_actions(limited);
    auto limited_feed=std::find_if(limited_acts.begin(),limited_acts.end(),[](const Action&a){return a.type==ActionType::Ability&&a.target_uid&&*a.target_uid==3&&a.ability_id&&*a.ability_id==stable_ability_id("mfd");});
    CHECK(limited_feed!=limited_acts.end());
    auto limited_tr=sim.apply(limited,*limited_feed,0.5); CHECK(limited_tr.valid);
    CHECK(limited_tr.state.entity(1)->mana==0); CHECK(limited_tr.state.entity(3)->mana==13);
    BattleState empty=limited; empty.entity(1)->mana=0;
    CHECK(std::none_of(sim.legal_actions(empty).begin(),sim.legal_actions(empty).end(),[](const Action&a){return a.type==ActionType::Ability&&a.ability_id&&*a.ability_id==stable_ability_id("mfd");}));

    // Live protocol decoder must apply the same exact transition and clear semantic risk.
    BattleState p=s; p.halfturn=0; p.stream_contiguous=false; p.protocol_ready=false; p.recommendation_safe=false;
    p.entity(1)->mana=15; p.entity(1)->count=5; p.entity(3)->mana=10; p.active_entity_uid=0;
    ProtocolDecoder decoder;
    auto decoded=decoder.decode_update(p,"t=000turns=>1:C001000000Smfd001003050000000i0010100C002000000");
    CHECK(decoded.state.entity(1)->mana==10); CHECK(decoded.state.entity(3)->mana==15);
    CHECK(std::any_of(decoded.events.begin(),decoded.events.end(),[](const BattleEvent&e){return e.type=="MANA_FEED"&&e.actor_uid==1&&e.target_uid==3;}));
    CHECK(decoded.state.semantic_unresolved_records==0); CHECK(decoded.state.recommendation_safe);
    return true;
}


'''
replace_once(cpptest,anchor,test_fn+anchor)
replace_once(cpptest,
'''    if (!test_mana_drain_and_reference_damage_perks()) return EXIT_FAILURE;''',
'''    if (!test_mana_feed_exact_action_and_protocol()) return EXIT_FAILURE;
    if (!test_mana_drain_and_reference_damage_perks()) return EXIT_FAILURE;''')

# ---------------------------------------------------------------------------
# Ability registry.
# ---------------------------------------------------------------------------
reg='python/hwm_solver/knowledge/build_ability_registry.py'
replace_once(reg,
'''    "takeroots", "fireattack", "battlethirst", "tasteofblood", "bloodfrenzy", "organicarmor", "shieldother", "concentration", "lizardbite", "lifedrain", "regeneration",
''',
'''    "takeroots", "fireattack", "battlethirst", "tasteofblood", "bloodfrenzy", "organicarmor", "shieldother", "concentration", "lizardbite", "lifedrain", "regeneration", "manafeed",
''')
run('python','python/hwm_solver/knowledge/build_ability_registry.py','data/catalog/generated_v4.json','--out','data/catalog/ability_registry.json','--ability-damage','models/ability_damage_model.csv','--collateral','models/collateral_model.csv','--proc','models/proc_model.csv','--kill-trigger','models/kill_trigger_model.csv')
registry=json.loads(Path('data/catalog/ability_registry.json').read_text(encoding='utf-8'))
counts=registry['support_counts']
if counts.get('exact_search')!=84 or counts.get('learned_damage')!=178 or counts.get('unresolved')!=78:
    raise SystemExit(f'unexpected registry counts after Mana Feed promotion: {counts}')

# ---------------------------------------------------------------------------
# Re-run corpus evidence with the patched canonical replay parser.
# ---------------------------------------------------------------------------
env=os.environ.copy(); env['PYTHONPATH']='python'
run('python','scripts/ability_probe.py','hwm_battles','manafeed','--rows','1000','--out','data/reports/manafeed_probe.json',env=env)
report=json.loads(Path('data/reports/manafeed_probe.json').read_text(encoding='utf-8'))
if report['special_codes'].get('mfd')!=42 or report['errors']:
    raise SystemExit(f'Mana Feed corpus probe invariant failed: mfd={report["special_codes"].get("mfd")}, errors={report["errors"][:3]}')
mfd=[r for r in report['rows'] if 'mfd' in r.get('special_codes',[])]
if len(mfd)!=42:
    raise SystemExit(f'expected 42 detailed Smfd rows, found {len(mfd)}')
pat=re.compile(r'Smfd(\d{3})(\d{3})(\d{2})0000000')
for r in mfd:
    m=pat.search(r['raw'])
    if not m: raise SystemExit(f'bad Smfd raw: {r["raw"]}')
    actor_uid,target_uid,amount=map(int,m.groups())
    expected=min(int(r['actor_count']),int(r['actor_mana_before']))
    checks=(r['action_type']=='ABILITY',r['target_uid']==target_uid,r['actor_uid']==actor_uid,amount==expected,
            r['actor_mana_after']==r['actor_mana_before']-amount,
            r['friendly_hero_mana_after']==r['friendly_hero_mana_before']+amount)
    if not all(checks): raise SystemExit(f'Smfd transition mismatch: {r}')

# ---------------------------------------------------------------------------
# Active spec/status docs.
# ---------------------------------------------------------------------------
for path in ['SPEC.md','HeroesWM_Solver_TZ_Status_0.3.0.md']:
    replace_once(path,
        '**Последнее обновление реализации:** 10.08.2026 — Life Drain и Regeneration переведены в exact-search.  \n',
        '**Последнее обновление реализации:** 10.08.2026 — Life Drain, Regeneration и Mana Feed переведены в exact-search.  \n')
    replace_once(path,
        '- Ability catalog: **421** ability code; registry: **83 exact-search**, 11 exact-targeting, 18 partial-exact, 8 modeled-proc, 5 modeled-collateral, 2 modeled-kill-trigger, dynamic spellbook; **78 unresolved**. `Life Drain` моделируется точным transition-правилом лечения/воскрешения от 50% фактически нанесённого физического урона; `Regeneration` — точным start-of-turn лечением `random(3,5) * min(current_count, 10)` HP только текущего верхнего существа, без увеличения `count`.',
        '- Ability catalog: **421** ability code; registry: **84 exact-search**, 11 exact-targeting, 18 partial-exact, 8 modeled-proc, 5 modeled-collateral, 2 modeled-kill-trigger, dynamic spellbook; **78 unresolved**. `Life Drain` моделируется точным transition-правилом лечения/воскрешения от 50% фактически нанесённого физического урона; `Regeneration` — точным start-of-turn лечением `random(3,5) * min(current_count, 10)` HP только текущего верхнего существа, без увеличения `count`; `Mana Feed` — exact `Smfd` action на собственного героя с передачей `min(current_count, current_mana)` маны.')
    replace_once(path,
        '1. Закрытие high-impact unresolved creature abilities; `Life Drain` и `Regeneration` закрыты 10.08.2026, текущая точка исследования — remaining assist/counter/stateful abilities.',
        '1. Закрытие high-impact unresolved creature abilities; `Life Drain`, `Regeneration` и `Mana Feed` закрыты 10.08.2026, текущая точка исследования — remaining assist/counter/summon/control abilities.')

for path in ['IMPLEMENTATION_REPORT.md','HeroesWM_Solver_Implementation_Report_0.3.0.md']:
    replace_once(path,'| Ability Registry exact-search | 83 |','| Ability Registry exact-search | 84 |')
    replace_once(path,'  "exact_search": 83,','  "exact_search": 84,')
    replace_once(path,'  "learned_damage": 179,','  "learned_damage": 178,')
    replace_once(path,
        'Mana Drain; Life Drain; Regeneration; Blood Frenzy;',
        'Mana Drain; Mana Feed; Life Drain; Regeneration; Blood Frenzy;')
    replace_once(path,
        '**Current research frontier:** remaining assist/counter/summon/control abilities. Life Drain and Regeneration were promoted to `exact_search` on 10.08.2026; Regeneration is modeled only on an actual rollout turn transition and cannot resurrect creatures.',
        '**Current research frontier:** remaining assist/counter/summon/control abilities. Life Drain, Regeneration and Mana Feed are `exact_search`; Mana Feed is additionally validated on all 42 observed `Smfd` actions in the 866-battle corpus.')
    replace_once(path,
        '1. Continue high-impact unresolved abilities after the completed Life Drain and Regeneration transitions.',
        '1. Continue high-impact unresolved abilities after the completed Life Drain, Regeneration and Mana Feed transitions.')

tr=Path('TEST_REPORT.md'); text=tr.read_text(encoding='utf-8')
if text.count('Python pytest:              39/39 PASS')!=1 or text.count('exact_search:           83')!=1:
    raise SystemExit('TEST_REPORT anchor mismatch')
text=text.replace('Python pytest:              39/39 PASS','Python pytest:              40/40 PASS',1)
text=text.replace('exact_search:           83','exact_search:           84',1)
text=text.replace(
    'Registry counts regenerated 10.08.2026 after exact Life Drain and Regeneration transitions; held-out risk numbers below remain the 09.08.2026 checkpoint snapshot and are not relabeled.',
    'Registry counts regenerated 10.08.2026 after exact Life Drain, Regeneration and Mana Feed transitions; all 42 observed `Smfd` actions pass the exact corpus transition invariant. Held-out risk numbers below remain the 09.08.2026 checkpoint snapshot and are not relabeled.',1)
tr.write_text(text,encoding='utf-8')

# ---------------------------------------------------------------------------
# Targeted verification before functional commit.
# ---------------------------------------------------------------------------
WORKFLOW.unlink(missing_ok=True); SCRIPT.unlink(missing_ok=True)
run('cmake','--preset','debug')
run('cmake','--build','build/debug','--parallel','2')
run('ctest','--test-dir','build/debug','--output-on-failure')
run('python','-m','pytest','-q',env=env)
run('git','diff','--check','--','cpp/src/protocol.cpp','cpp/src/simulator.cpp','cpp/tests/test_main.cpp','python/hwm_solver/protocol/replay.py','python/tests/test_replay_parser.py','python/hwm_solver/knowledge/build_ability_registry.py','scripts/ability_probe.py')

run('git','config','user.name','github-actions[bot]')
run('git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
run('git','add','-A')
run('git','commit','-m','feat: model exact Mana Feed action')
functional_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()

p=Path('changelog.md'); text=p.read_text(encoding='utf-8').rstrip()+'\n\n'
staging=os.environ.get('GITHUB_SHA','unknown')
text += f'''### Exact Mana Feed action\n\n- Commit: `{staging}`\n  - Staged a self-removing verified patch after the corpus probe isolated 42 `Smfd` observations.\n- Commit: `{functional_sha}`\n  - Decoded `Smfd` as actor3 + own-hero3 + amount2 + zero trailer and marked it exact only when actor ability, ownership and `amount=min(count,mana)` invariants hold.\n  - Added Python and C++ canonical mana transitions: creature mana decreases and own hero mana increases by the same amount.\n  - Added exact C++ legal `Ability` generation and simulator execution targeting only the actor's own hero.\n  - Reclassified observed Mana Feed decisions as target-bound `ABILITY` actions instead of generic targetless `CAST_OR_ABILITY`.\n  - Re-ran the full 866-battle Mana Feed probe: **42/42 `Smfd` records** satisfy the exact action/target/mana-delta invariant.\n  - Added Python and C++ regressions, promoted `manafeed` to exact-search and regenerated the registry to 84 exact-search / 178 learned-damage / 78 unresolved.\n  - Updated active Markdown specification, implementation reports, test report and `data/reports/manafeed_probe.json`.\n  - Targeted C++ build/CTest and Python pytest passed before commit.\n'''
p.write_text(text,encoding='utf-8')
run('git','add','changelog.md')
run('git','commit','-m','docs: log exact Mana Feed implementation')
run('git','push','origin','HEAD:main')
