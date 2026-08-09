from __future__ import annotations

import os
import subprocess
from pathlib import Path

WORKFLOW=Path('.github/workflows/apply_regeneration_formula_fix.yml')
SCRIPT=Path('.github/scripts/apply_regeneration_formula_fix.py')


def replace_once(path:str,old:str,new:str)->None:
    p=Path(path); text=p.read_text(encoding='utf-8'); count=text.count(old)
    if count!=1: raise SystemExit(f'{path}: expected one anchor, found {count}')
    p.write_text(text.replace(old,new,1),encoding='utf-8')


def run(*args:str)->None:
    subprocess.run(args,check=True)

sim='cpp/src/simulator.cpp'
replace_once(sim,
'''static int regeneration_heal(double roll){
    // Exact HeroesWM range: a uniformly sampled integer 30..50 HP at turn start.
    const double r=std::clamp(roll,0.0,1.0);
    return 30+std::min(20,static_cast<int>(std::floor(r*21.0)));
}''',
'''static int regeneration_heal(int count,double roll){
    // HeroesWM formula: random integer 3..5 HP per living creature, capped at
    // the first 10 creatures in the stack. This yields the documented 3..50 range.
    const double r=std::clamp(roll,0.0,1.0);
    const int per_creature=3+std::min(2,static_cast<int>(std::floor(r*3.0)));
    return per_creature*std::min(10,std::max(0,count));
}''')
replace_once(sim,
'        heal_top_unit_only(*next_entity,regeneration_heal(roll));',
'        heal_top_unit_only(*next_entity,regeneration_heal(next_entity->count,roll));')

tests='cpp/tests/test_main.cpp'
replace_once(tests,
'''    auto make_state=[](int top_hp)->BattleState{
        BattleState s=fixture();
        auto* actor=s.entity(1); auto* regen=s.entity(2);
        if(!actor||!regen)return {};
        s.decision_seq=10;
        actor->last_acted_seq=9; actor->initiative=1; actor->atb=0;
        regen->max_count=10; regen->count=3; regen->max_hp_per_unit=125;
        regen->top_unit_hp=top_hp; regen->initiative=100; regen->atb=10000;''',
'''    auto make_state=[](int top_hp,int count=3)->BattleState{
        BattleState s=fixture();
        auto* actor=s.entity(1); auto* regen=s.entity(2);
        if(!actor||!regen)return {};
        s.decision_seq=10;
        actor->last_acted_seq=9; actor->initiative=1; actor->atb=0;
        regen->max_count=20; regen->count=count; regen->max_hp_per_unit=125;
        regen->top_unit_hp=top_hp; regen->initiative=100; regen->atb=10000;''')
replace_once(tests,
'''    CHECK(low.state.entity(2)->top_unit_hp==50);  // +30
    CHECK(low.state.entity(2)->count==3);

    auto mid=apply_wait(make_state(20),0.5); CHECK(mid.valid); CHECK(!mid.terminal); CHECK(mid.state.active_entity_uid==2); CHECK(mid.state.entity(2));
    CHECK(mid.state.entity(2)->top_unit_hp==60);  // +40
    CHECK(mid.state.entity(2)->count==3);

    auto high=apply_wait(make_state(20),1.0); CHECK(high.valid); CHECK(!high.terminal); CHECK(high.state.active_entity_uid==2); CHECK(high.state.entity(2));
    CHECK(high.state.entity(2)->top_unit_hp==70); // +50
    CHECK(high.state.entity(2)->count==3);

    auto capped=apply_wait(make_state(120),1.0); CHECK(capped.valid); CHECK(!capped.terminal); CHECK(capped.state.active_entity_uid==2); CHECK(capped.state.entity(2));
    CHECK(capped.state.entity(2)->top_unit_hp==125);
    CHECK(capped.state.entity(2)->count==3); // no resurrection / count increase''',
'''    CHECK(low.state.entity(2)->top_unit_hp==29);  // 3 HP * 3 creatures = +9
    CHECK(low.state.entity(2)->count==3);

    auto mid=apply_wait(make_state(20),0.5); CHECK(mid.valid); CHECK(!mid.terminal); CHECK(mid.state.active_entity_uid==2); CHECK(mid.state.entity(2));
    CHECK(mid.state.entity(2)->top_unit_hp==32);  // 4 HP * 3 creatures = +12
    CHECK(mid.state.entity(2)->count==3);

    auto high=apply_wait(make_state(20),1.0); CHECK(high.valid); CHECK(!high.terminal); CHECK(high.state.active_entity_uid==2); CHECK(high.state.entity(2));
    CHECK(high.state.entity(2)->top_unit_hp==35); // 5 HP * 3 creatures = +15
    CHECK(high.state.entity(2)->count==3);

    auto full_stack=apply_wait(make_state(20,10),1.0); CHECK(full_stack.valid); CHECK(full_stack.state.entity(2));
    CHECK(full_stack.state.entity(2)->top_unit_hp==70); // cap: 5 * min(10,10) = +50
    CHECK(full_stack.state.entity(2)->count==10);

    auto capped=apply_wait(make_state(120),1.0); CHECK(capped.valid); CHECK(!capped.terminal); CHECK(capped.state.active_entity_uid==2); CHECK(capped.state.entity(2));
    CHECK(capped.state.entity(2)->top_unit_hp==125);
    CHECK(capped.state.entity(2)->count==3); // no resurrection / count increase''')

for path in ['SPEC.md','HeroesWM_Solver_TZ_Status_0.3.0.md']:
    replace_once(path,
        '`Regeneration` — точным start-of-turn лечением на 30–50 HP только текущего верхнего существа, без увеличения `count`.',
        '`Regeneration` — точным start-of-turn лечением `random(3,5) * min(current_count, 10)` HP только текущего верхнего существа, без увеличения `count`.')

WORKFLOW.unlink(missing_ok=True); SCRIPT.unlink(missing_ok=True)
run('cmake','--preset','debug')
run('cmake','--build','build/debug','--parallel','2')
run('ctest','--test-dir','build/debug','--output-on-failure')
run('git','diff','--check','--','cpp/src/simulator.cpp','cpp/tests/test_main.cpp')
run('git','config','user.name','github-actions[bot]')
run('git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
run('git','add','-A')
run('git','commit','-m','fix: scale Regeneration heal by stack size')
functional_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()

p=Path('changelog.md'); text=p.read_text(encoding='utf-8').rstrip()+'\n\n'
staging=os.environ.get('GITHUB_SHA','unknown')
text += f'''### Regeneration formula correction\n\n- Commit: `{staging}`\n  - Staged a self-removing correction after cross-checking the HeroesWM reference formula against the fixed 30–50 implementation.\n- Commit: `{functional_sha}`\n  - Corrected Regeneration from a fixed 30–50 HP roll to `random(3,5) * min(current_count, 10)`.\n  - Preserved the already-correct start-of-turn timing, Srn2 exclusion, top-unit-only healing, and no-resurrection invariant from `ed108d79169bb21720bc830f846865fcf9c1a9b6`.\n  - Expanded regression coverage for 3-creature 9/12/15 HP healing and the 10-creature 50 HP cap.\n  - Updated the active Markdown specification formula. Ability Registry counts remain 83 exact-search / 179 learned-damage / 78 unresolved.\n  - C++ Debug build and CTest passed before commit.\n'''
p.write_text(text,encoding='utf-8')
run('git','add','changelog.md')
run('git','commit','-m','docs: log Regeneration formula correction')
run('git','push','origin','HEAD:main')
