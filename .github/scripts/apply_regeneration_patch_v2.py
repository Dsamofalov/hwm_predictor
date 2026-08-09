from pathlib import Path

old_script = Path('.github/scripts/apply_regeneration_patch.py')
source = old_script.read_text(encoding='utf-8')

source = source.replace(
    "SCRIPT = Path('.github/scripts/apply_regeneration_patch.py')",
    "SCRIPT = Path('.github/scripts/apply_regeneration_patch_v2.py')",
    1,
)

old_test = r'''    auto make_state=[](int top_hp){
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
'''
new_test = r'''    auto make_state=[](int top_hp)->BattleState{
        BattleState s=fixture();
        auto* actor=s.entity(1); auto* regen=s.entity(2);
        if(!actor||!regen)return {};
        s.decision_seq=10;
        actor->last_acted_seq=9; actor->initiative=1; actor->atb=0;
        regen->max_count=10; regen->count=3; regen->max_hp_per_unit=125;
        regen->top_unit_hp=top_hp; regen->initiative=100; regen->atb=10000;
        regen->last_acted_seq=0; add_tag(*regen,"regeneration");
        return s;
    };

    auto apply_wait=[&](BattleState s,double roll)->Transition{
        auto acts=sim.legal_actions(s);
        auto it=std::find_if(acts.begin(),acts.end(),[](const Action&a){return a.type==ActionType::Wait;});
        if(it==acts.end()){Transition bad;bad.valid=false;bad.warning="wait_missing";return bad;}
        return sim.apply(s,*it,roll);
    };
'''
if source.count(old_test) != 1:
    raise SystemExit('failed to locate Regeneration lambda test block')
source = source.replace(old_test, new_test, 1)

for var in ('low','mid','high','capped'):
    old = f'    auto {var}=apply_wait('
    # Checks are added after each construction below by targeted replacements.
    if source.count(old) != 1:
        raise SystemExit(f'missing {var} construction')
source = source.replace(
    '    auto low=apply_wait(make_state(20),0.0);\n    CHECK(low.state.entity(2)->top_unit_hp==50);',
    '    auto low=apply_wait(make_state(20),0.0); CHECK(low.valid); CHECK(!low.terminal); CHECK(low.state.active_entity_uid==2); CHECK(low.state.entity(2));\n    CHECK(low.state.entity(2)->top_unit_hp==50);',
    1,
)
source = source.replace(
    '    auto mid=apply_wait(make_state(20),0.5);\n    CHECK(mid.state.entity(2)->top_unit_hp==60);',
    '    auto mid=apply_wait(make_state(20),0.5); CHECK(mid.valid); CHECK(!mid.terminal); CHECK(mid.state.active_entity_uid==2); CHECK(mid.state.entity(2));\n    CHECK(mid.state.entity(2)->top_unit_hp==60);',
    1,
)
source = source.replace(
    '    auto high=apply_wait(make_state(20),1.0);\n    CHECK(high.state.entity(2)->top_unit_hp==70);',
    '    auto high=apply_wait(make_state(20),1.0); CHECK(high.valid); CHECK(!high.terminal); CHECK(high.state.active_entity_uid==2); CHECK(high.state.entity(2));\n    CHECK(high.state.entity(2)->top_unit_hp==70);',
    1,
)
source = source.replace(
    '    auto capped=apply_wait(make_state(120),1.0);\n    CHECK(capped.state.entity(2)->top_unit_hp==125);',
    '    auto capped=apply_wait(make_state(120),1.0); CHECK(capped.valid); CHECK(!capped.terminal); CHECK(capped.state.active_entity_uid==2); CHECK(capped.state.entity(2));\n    CHECK(capped.state.entity(2)->top_unit_hp==125);',
    1,
)

source = source.replace(
    '    if(tr.terminal)tr.state.phase=Phase::Finished;return tr;',
    '    if(tr.terminal)tr.state.phase=Phase::Finished;\n    return tr;',
    1,
)
source = source.replace(
    "WORKFLOW.unlink(missing_ok=True)\nSCRIPT.unlink(missing_ok=True)",
    "WORKFLOW.unlink(missing_ok=True)\nSCRIPT.unlink(missing_ok=True)\nold_script.unlink(missing_ok=True)",
    1,
)
source = source.replace(
    "text += f'''### Regeneration patch tooling\\n\\n- Commit: `{staging_sha}`\\n- Added a one-shot self-removing patch runner for the Regeneration source/spec change.\\n- The temporary workflow and patch script were removed by the functional commit below.\\n\\n### Exact Regeneration turn-start transition",
    "text += f'''### Regeneration patch tooling\\n\\n- Commit: `9ae958b2bc2aed3382bb05af0578d3db3224b27d`\\n  - Initial Regeneration staging runner. Production code and registry generation compiled far enough to verify 83/179/78 counts, but the new C++ test did not compile because the project `CHECK` macro returns `false` inside lambdas. No functional commit was produced.\\n- Commit: `{staging_sha}`\\n  - Corrected the regression helper lambdas and the scheduler indentation warning; re-ran the self-removing patch pipeline.\\n- The temporary workflow and patch scripts were removed by the functional commit below.\\n\\n### Exact Regeneration turn-start transition",
    1,
)

exec(compile(source, '<regeneration-patcher-v2>', 'exec'), {'__name__': '__main__', 'old_script': old_script})
