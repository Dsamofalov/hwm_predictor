from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

WORKFLOW = Path('.github/workflows/apply_regeneration_patch.yml')
SCRIPT = Path('.github/scripts/apply_regeneration_patch.py')


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected one patch anchor, found {count}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')


def run(*args: str) -> None:
    subprocess.run(args, check=True)


# ---- Runtime transition ----------------------------------------------------
sim = 'cpp/src/simulator.cpp'
replace_once(
    sim,
    '''static void restore_hp(Entity& target,int heal){
    if(heal<=0||target.max_count<=0||target.max_hp_per_unit<=0)return;
    const int mh=std::max(1,target.max_hp_per_unit);
    const int64_t cap=static_cast<int64_t>(target.max_count)*mh;
    const int64_t hp=std::min(cap,static_cast<int64_t>(total_hp(target))+heal);
    if(hp<=0)return;
    target.count=static_cast<int>((hp+mh-1)/mh);target.top_unit_hp=static_cast<int>(hp-static_cast<int64_t>(target.count-1)*mh);target.alive=true;
}

Transition GenericSimulator::apply''',
    '''static void restore_hp(Entity& target,int heal){
    if(heal<=0||target.max_count<=0||target.max_hp_per_unit<=0)return;
    const int mh=std::max(1,target.max_hp_per_unit);
    const int64_t cap=static_cast<int64_t>(target.max_count)*mh;
    const int64_t hp=std::min(cap,static_cast<int64_t>(total_hp(target))+heal);
    if(hp<=0)return;
    target.count=static_cast<int>((hp+mh-1)/mh);target.top_unit_hp=static_cast<int>(hp-static_cast<int64_t>(target.count-1)*mh);target.alive=true;
}
static void heal_top_unit_only(Entity& target,int heal){
    // HeroesWM Regeneration restores only the currently living top creature.
    // It must never increase stack count (unlike Raise Dead / Life Drain).
    if(heal<=0||!target.alive||target.count<=0||target.max_hp_per_unit<=0)return;
    const int mh=std::max(1,target.max_hp_per_unit);
    const int current=target.top_unit_hp>0?std::min(mh,target.top_unit_hp):mh;
    target.top_unit_hp=std::min(mh,current+heal);
}
static int regeneration_heal(double roll){
    // Exact HeroesWM range: a uniformly sampled integer 30..50 HP at turn start.
    const double r=std::clamp(roll,0.0,1.0);
    return 30+std::min(20,static_cast<int>(std::floor(r*21.0)));
}

Transition GenericSimulator::apply'''
)

replace_once(
    sim,
    '''    tr.state.active_entity_uid=next;if(auto*n=tr.state.entity(next)){tr.state.side_to_act=n->side;if(!rune_activation){n->retaliation_available=true;n->defending=false;
        const auto shield_id=status_effect_id("proc_shieldbash");
        n->effects.erase(std::remove_if(n->effects.begin(),n->effects.end(),[&](const Effect&fx){return fx.id==shield_id;}),n->effects.end());
    }}else tr.state.side_to_act=Side::Unknown;
    bool p=false,e=false;for(auto&x:tr.state.entities)if(x.alive&&!x.is_hero){if(x.side==Side::Player)p=true;if(x.side==Side::Pve)e=true;}tr.terminal=!p||!e;if(tr.terminal)tr.state.phase=Phase::Finished;return tr;''',
    '''    tr.state.active_entity_uid=next;
    auto* next_entity=tr.state.entity(next);
    if(next_entity){
        tr.state.side_to_act=next_entity->side;
        if(!rune_activation){
            next_entity->retaliation_available=true;next_entity->defending=false;
            const auto shield_id=status_effect_id("proc_shieldbash");
            next_entity->effects.erase(std::remove_if(next_entity->effects.begin(),next_entity->effects.end(),[&](const Effect&fx){return fx.id==shield_id;}),next_entity->effects.end());
        }
    }else tr.state.side_to_act=Side::Unknown;
    bool p=false,e=false;for(auto&x:tr.state.entities)if(x.alive&&!x.is_hero){if(x.side==Side::Player)p=true;if(x.side==Side::Pve)e=true;}
    tr.terminal=!p||!e;
    // Regeneration is a start-of-turn mechanic. The root state already contains any
    // server-applied heal, so only apply it when this rollout actually advances to a
    // new actor. Srn2 is a preparatory immediate reactivation, not a new turn.
    if(!tr.terminal&&!rune_activation&&next_entity&&has_tag(*next_entity,"regeneration"))
        heal_top_unit_only(*next_entity,regeneration_heal(roll));
    if(tr.terminal)tr.state.phase=Phase::Finished;return tr;'''
)

# ---- Regression ------------------------------------------------------------
tests = 'cpp/tests/test_main.cpp'
anchor = 'static bool test_life_drain_exact_heal_resurrection_and_retaliation() {'
test_fn = r'''static bool test_regeneration_exact_turn_start_no_resurrection() {
    GenericSimulator sim;

    auto make_state=[](int top_hp){
        BattleState s=fixture();
        auto* actor=s.entity(1); auto* regen=s.entity(2); CHECK(actor&&regen);
        s.decision_seq=10;
        actor->last_acted_seq=9; actor->initiative=1; actor->atb=0;
        regen->max_count=10; regen->count=3; regen->max_hp_per_unit=125;
        regen->top_unit_hp=top_hp; regen->initiative=100; regen->atb=10000;
        regen->last_acted_seq=0; add_tag(*regen,"regeneration");
        return s;
    };

    auto apply_wait=[&](BattleState s,double roll){
        auto acts=sim.legal_actions(s);
        auto it=std::find_if(acts.begin(),acts.end(),[](const Action&a){return a.type==ActionType::Wait;});
        CHECK(it!=acts.end());
        auto tr=sim.apply(s,*it,roll); CHECK(tr.valid); CHECK(!tr.terminal);
        CHECK(tr.state.active_entity_uid==2); CHECK(tr.state.entity(2));
        return tr;
    };

    auto low=apply_wait(make_state(20),0.0);
    CHECK(low.state.entity(2)->top_unit_hp==50);  // +30
    CHECK(low.state.entity(2)->count==3);

    auto mid=apply_wait(make_state(20),0.5);
    CHECK(mid.state.entity(2)->top_unit_hp==60);  // +40
    CHECK(mid.state.entity(2)->count==3);

    auto high=apply_wait(make_state(20),1.0);
    CHECK(high.state.entity(2)->top_unit_hp==70); // +50
    CHECK(high.state.entity(2)->count==3);

    auto capped=apply_wait(make_state(120),1.0);
    CHECK(capped.state.entity(2)->top_unit_hp==125);
    CHECK(capped.state.entity(2)->count==3); // no resurrection / count increase
    return true;
}


'''
replace_once(tests, anchor, test_fn + anchor)
replace_once(
    tests,
    '    if (!test_life_drain_exact_heal_resurrection_and_retaliation()) return EXIT_FAILURE;',
    '    if (!test_regeneration_exact_turn_start_no_resurrection()) return EXIT_FAILURE;\n    if (!test_life_drain_exact_heal_resurrection_and_retaliation()) return EXIT_FAILURE;'
)

# ---- Ability Registry ------------------------------------------------------
reg = 'python/hwm_solver/knowledge/build_ability_registry.py'
replace_once(
    reg,
    '    "takeroots", "fireattack", "battlethirst", "tasteofblood", "bloodfrenzy", "organicarmor", "shieldother", "concentration", "lizardbite", "lifedrain",\n',
    '    "takeroots", "fireattack", "battlethirst", "tasteofblood", "bloodfrenzy", "organicarmor", "shieldother", "concentration", "lizardbite", "lifedrain", "regeneration",\n'
)

run(
    'python', 'python/hwm_solver/knowledge/build_ability_registry.py',
    'data/catalog/generated_v4.json',
    '--out', 'data/catalog/ability_registry.json',
    '--ability-damage', 'models/ability_damage_model.csv',
    '--collateral', 'models/collateral_model.csv',
    '--proc', 'models/proc_model.csv',
    '--kill-trigger', 'models/kill_trigger_model.csv'
)
registry=json.loads(Path('data/catalog/ability_registry.json').read_text(encoding='utf-8'))
counts=registry['support_counts']
if counts.get('exact_search')!=83 or counts.get('learned_damage')!=179 or counts.get('unresolved')!=78:
    raise SystemExit(f'unexpected registry counts after Regeneration promotion: {counts}')
entry=next((x for x in registry['abilities'] if x.get('code')=='regeneration'),None)
if not entry or entry.get('support')!='exact_search':
    raise SystemExit(f'Regeneration was not promoted: {entry}')

# ---- Active specification / reports ---------------------------------------
for path in ['SPEC.md','HeroesWM_Solver_TZ_Status_0.3.0.md']:
    replace_once(
        path,
        '**Последнее обновление реализации:** 10.08.2026 — Life Drain переведён в exact-search.  \n',
        '**Последнее обновление реализации:** 10.08.2026 — Life Drain и Regeneration переведены в exact-search.  \n'
    )
    replace_once(
        path,
        '- Ability catalog: **421** ability code; registry: **82 exact-search**, 11 exact-targeting, 18 partial-exact, 8 modeled-proc, 5 modeled-collateral, 2 modeled-kill-trigger, dynamic spellbook; **78 unresolved**. `Life Drain` теперь моделируется точным transition-правилом лечения/воскрешения от 50% фактически нанесённого физического урона.',
        '- Ability catalog: **421** ability code; registry: **83 exact-search**, 11 exact-targeting, 18 partial-exact, 8 modeled-proc, 5 modeled-collateral, 2 modeled-kill-trigger, dynamic spellbook; **78 unresolved**. `Life Drain` моделируется точным transition-правилом лечения/воскрешения от 50% фактически нанесённого физического урона; `Regeneration` — точным start-of-turn лечением на 30–50 HP только текущего верхнего существа, без увеличения `count`.'
    )
    replace_once(
        path,
        '1. Закрытие high-impact unresolved creature abilities; `Life Drain` закрыт 10.08.2026, текущая точка исследования — remaining assist/counter/stateful abilities.',
        '1. Закрытие high-impact unresolved creature abilities; `Life Drain` и `Regeneration` закрыты 10.08.2026, текущая точка исследования — remaining assist/counter/stateful abilities.'
    )

for path in ['IMPLEMENTATION_REPORT.md','HeroesWM_Solver_Implementation_Report_0.3.0.md']:
    replace_once(path,'| Ability Registry exact-search | 82 |','| Ability Registry exact-search | 83 |')
    replace_once(path,'  "exact_search": 82,','  "exact_search": 83,')
    replace_once(path,'  "learned_damage": 180,','  "learned_damage": 179,')
    replace_once(
        path,
        'Examples already handled in runtime include core movement/shooter/large/flyer/retaliation rules; multi-hit; defense penetration/resistances/immunities; Defend/Take Roots/Entrenchment; Stone/Warding/Crippling observed state; Enraged/Pack Enrage; Battle Thirst/Taste of Blood; Mana Drain; Life Drain; Blood Frenzy; Organic Armor; Shield Other; Swift Attack; Impervious to Pain; Concentration; Lizard Bite; direct hero spells and several status spells.',
        'Examples already handled in runtime include core movement/shooter/large/flyer/retaliation rules; multi-hit; defense penetration/resistances/immunities; Defend/Take Roots/Entrenchment; Stone/Warding/Crippling observed state; Enraged/Pack Enrage; Battle Thirst/Taste of Blood; Mana Drain; Life Drain; Regeneration; Blood Frenzy; Organic Armor; Shield Other; Swift Attack; Impervious to Pain; Concentration; Lizard Bite; direct hero spells and several status spells.'
    )
    replace_once(
        path,
        '**Current research frontier:** remaining assist/counter/summon/control abilities. Life Drain was promoted to `exact_search` on 10.08.2026 after adding HP restoration/resurrection transitions and regression coverage.',
        '**Current research frontier:** remaining assist/counter/summon/control abilities. Life Drain and Regeneration were promoted to `exact_search` on 10.08.2026; Regeneration is modeled only on an actual rollout turn transition and cannot resurrect creatures.'
    )
    replace_once(
        path,
        '1. Continue high-impact unresolved abilities after the completed Life Drain transition.',
        '1. Continue high-impact unresolved abilities after the completed Life Drain and Regeneration transitions.'
    )

tr=Path('TEST_REPORT.md')
text=tr.read_text(encoding='utf-8')
if text.count('exact_search:           82')!=1:
    raise SystemExit('TEST_REPORT exact_search anchor mismatch')
text=text.replace('exact_search:           82','exact_search:           83',1)
old='Registry counts regenerated 10.08.2026 after exact Life Drain transition; held-out risk numbers below remain the 09.08.2026 checkpoint snapshot and are not relabeled.'
new='Registry counts regenerated 10.08.2026 after exact Life Drain and Regeneration transitions; held-out risk numbers below remain the 09.08.2026 checkpoint snapshot and are not relabeled.'
if text.count(old)!=1:
    raise SystemExit('TEST_REPORT registry note anchor mismatch')
tr.write_text(text.replace(old,new,1),encoding='utf-8')

# Temporary patch infrastructure must not survive the functional commit.
WORKFLOW.unlink(missing_ok=True)
SCRIPT.unlink(missing_ok=True)

# Targeted verification before the functional commit.
run('cmake','--preset','debug')
run('cmake','--build','build/debug','--parallel','2')
run('ctest','--test-dir','build/debug','--output-on-failure')
run('git','diff','--check','--','cpp/src/simulator.cpp','cpp/tests/test_main.cpp','python/hwm_solver/knowledge/build_ability_registry.py')

run('git','config','user.name','github-actions[bot]')
run('git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
run('git','add','-A')
run('git','commit','-m','feat: model exact Regeneration transition')
functional_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()

changelog=Path('changelog.md')
text=changelog.read_text(encoding='utf-8').rstrip()+'\n\n'
staging_sha=os.environ.get('GITHUB_SHA','unknown')
text += f'''### Regeneration patch tooling\n\n- Commit: `{staging_sha}`\n- Added a one-shot self-removing patch runner for the Regeneration source/spec change.\n- The temporary workflow and patch script were removed by the functional commit below.\n\n### Exact Regeneration turn-start transition\n\n- Commit: `{functional_sha}`\n- Implemented `regeneration` as a start-of-turn transition when the rollout advances to the next actor.\n- Uses an exact 30–50 HP integer roll and heals only the current top creature; stack `count` never increases.\n- Explicitly excludes Srn2 preparatory same-actor reactivation and terminal states to avoid duplicate/non-turn healing.\n- Added C++ regression coverage for 30/40/50 HP rolls, max-HP cap, next-actor timing, and no-resurrection invariant.\n- Promoted `regeneration` from `learned_damage` to `exact_search`; regenerated Ability Registry to 83 exact-search / 179 learned-damage / 78 unresolved.\n- Updated active Markdown specification, implementation reports, and test report status.\n- C++ Debug build and CTest passed before commit.\n'''
changelog.write_text(text,encoding='utf-8')
run('git','add','changelog.md')
run('git','commit','-m','docs: log exact Regeneration implementation')
run('git','push','origin','HEAD:main')
