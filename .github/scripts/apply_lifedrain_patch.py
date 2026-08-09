from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

WORKFLOW = Path('.github/workflows/apply_lifedrain_patch.yml')
SCRIPT = Path('.github/scripts/apply_lifedrain_patch.py')


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected one patch anchor, found {count}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')


def run(*args: str) -> None:
    subprocess.run(args, check=True)


sim = 'cpp/src/simulator.cpp'

replace_once(
    sim,
    '''                const int rdmg=std::max(1,(int)std::llround(roll_damage(tr.state,*t,*actor,1.0-std::clamp(roll,0.0,1.0),false,true)*damage_.multiplier(t->creature_id,ActionType::MeleeAttack)*ability_transfer_multiplier(damage_,ability_damage_,*t,*actor,ActionType::MeleeAttack)));
                deal_damage(*actor,rdmg);
                if(has_tag(*t,"battlethirst"))set_proc_effect(*t,"btt",10000,0.0f,"exact:battlethirst retaliation reset");''',
    '''                const int rdmg=std::max(1,(int)std::llround(roll_damage(tr.state,*t,*actor,1.0-std::clamp(roll,0.0,1.0),false,true)*damage_.multiplier(t->creature_id,ActionType::MeleeAttack)*ability_transfer_multiplier(damage_,ability_damage_,*t,*actor,ActionType::MeleeAttack)));
                const int retaliation_target_hp_before=total_hp(*actor);
                const bool retaliation_target_was_phantom=actor->is_phantom;
                deal_damage(*actor,rdmg);
                const int retaliation_actual_damage=std::max(0,retaliation_target_hp_before-total_hp(*actor));
                const int retaliation_drain_damage=(retaliation_target_was_phantom&&retaliation_actual_damage>0)?std::min(rdmg,retaliation_target_hp_before):retaliation_actual_damage;
                if(retaliation_drain_damage>0&&has_tag(*t,"lifedrain"))restore_hp(*t,retaliation_drain_damage/2);
                if(has_tag(*t,"battlethirst"))set_proc_effect(*t,"btt",10000,0.0f,"exact:battlethirst retaliation reset");'''
)

replace_once(
    sim,
    '''                const int target_hp_before=total_hp(*t);
                if(dmg>0)deal_damage(*t,dmg);
                const int actual_damage=std::max(0,target_hp_before-total_hp(*t));
                // Lizard Bite: when another friendly stack makes a melee attack against''',
    '''                const int target_hp_before=total_hp(*t);
                const bool target_was_phantom=t->is_phantom;
                if(dmg>0)deal_damage(*t,dmg);
                const int actual_damage=std::max(0,target_hp_before-total_hp(*t));
                // Life Drain: restore 50% of physical damage actually inflicted. The
                // existing helper also resurrects creatures up to max_count.
                // Phantom stacks dissipate on any positive hit; cap their drain basis by
                // the rolled hit so disappearance of the whole phantom stack cannot heal.
                const int drain_damage=(target_was_phantom&&actual_damage>0)?std::min(dmg,target_hp_before):actual_damage;
                if(drain_damage>0&&has_tag(*actor,"lifedrain"))restore_hp(*actor,drain_damage/2);
                // Lizard Bite: when another friendly stack makes a melee attack against'''
)

replace_once(
    sim,
    '''                    const int rdmg=std::max(1,(int)std::llround(roll_damage(tr.state,*t,*actor,1.0-std::clamp(roll,0.0,1.0),false,true)*damage_.multiplier(t->creature_id,ActionType::MeleeAttack)*ability_transfer_multiplier(damage_,ability_damage_,*t,*actor,ActionType::MeleeAttack)));
                    deal_damage(*actor,rdmg);
                    if(has_tag(*t,"battlethirst"))set_proc_effect(*t,"btt",10000,0.0f,"exact:battlethirst retaliation reset");''',
    '''                    const int rdmg=std::max(1,(int)std::llround(roll_damage(tr.state,*t,*actor,1.0-std::clamp(roll,0.0,1.0),false,true)*damage_.multiplier(t->creature_id,ActionType::MeleeAttack)*ability_transfer_multiplier(damage_,ability_damage_,*t,*actor,ActionType::MeleeAttack)));
                    const int retaliation_target_hp_before=total_hp(*actor);
                    const bool retaliation_target_was_phantom=actor->is_phantom;
                    deal_damage(*actor,rdmg);
                    const int retaliation_actual_damage=std::max(0,retaliation_target_hp_before-total_hp(*actor));
                    const int retaliation_drain_damage=(retaliation_target_was_phantom&&retaliation_actual_damage>0)?std::min(rdmg,retaliation_target_hp_before):retaliation_actual_damage;
                    if(retaliation_drain_damage>0&&has_tag(*t,"lifedrain"))restore_hp(*t,retaliation_drain_damage/2);
                    if(has_tag(*t,"battlethirst"))set_proc_effect(*t,"btt",10000,0.0f,"exact:battlethirst retaliation reset");'''
)

tests = 'cpp/tests/test_main.cpp'
anchor = 'static bool test_kill_trigger_enraged_gate() {'
test_fn = r'''static bool test_life_drain_exact_heal_resurrection_and_retaliation() {
    GenericSimulator sim;

    // Primary attack: 50% of actually inflicted damage heals the attacker and may
    // resurrect previously lost creatures, but never beyond max_count.
    BattleState s=fixture(); auto* a=s.entity(1); auto* t=s.entity(2); CHECK(a&&t);
    a->owner=1; a->is_shooter=false; a->shots=0; a->anchor={1,1}; a->max_count=10;
    a->count=5; a->max_hp_per_unit=20; a->top_unit_hp=10; a->attack=30;
    a->min_damage=a->max_damage=8; add_tag(*a,"lifedrain");
    t->owner=2; t->anchor={2,1}; t->max_count=50; t->count=50;
    t->max_hp_per_unit=20; t->top_unit_hp=20; t->retaliation_available=false;
    auto acts=sim.legal_actions(s);
    auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});
    CHECK(hit!=acts.end());
    const int attacker_before=entity_total_hp(*a), target_before=entity_total_hp(*t);
    auto tr=sim.apply(s,*hit,0.5); CHECK(tr.valid);
    const int dealt=target_before-entity_total_hp(*tr.state.entity(2)); CHECK(dealt>0);
    CHECK(entity_total_hp(*tr.state.entity(1))==std::min(200,attacker_before+dealt/2));
    CHECK(tr.state.entity(1)->count>5);

    BattleState full=s; auto* fa=full.entity(1); CHECK(fa); fa->count=10; fa->top_unit_hp=20;
    auto facts=sim.legal_actions(full);
    auto fhit=std::find_if(facts.begin(),facts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});
    CHECK(fhit!=facts.end());
    auto capped=sim.apply(full,*fhit,0.5); CHECK(capped.valid);
    CHECK(entity_total_hp(*capped.state.entity(1))==200);

    // Retaliation uses the same rule. Compare against an otherwise identical branch
    // where retaliation is disabled to isolate target HP after the primary hit.
    BattleState r=fixture(); auto* ra=r.entity(1); auto* rt=r.entity(2); CHECK(ra&&rt);
    ra->is_shooter=false; ra->shots=0; ra->anchor={1,1}; ra->max_count=20; ra->count=20;
    ra->max_hp_per_unit=30; ra->top_unit_hp=30; ra->min_damage=ra->max_damage=1; ra->attack=1;
    rt->anchor={2,1}; rt->max_count=10; rt->count=5; rt->max_hp_per_unit=20; rt->top_unit_hp=10;
    rt->min_damage=rt->max_damage=10; rt->attack=30; rt->retaliation_available=true; add_tag(*rt,"lifedrain");
    auto racts=sim.legal_actions(r);
    auto rhit=std::find_if(racts.begin(),racts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});
    CHECK(rhit!=racts.end());
    BattleState no_ret=r; no_ret.entity(2)->retaliation_available=false;
    auto primary_only=sim.apply(no_ret,*rhit,0.5); CHECK(primary_only.valid);
    const int target_after_primary=entity_total_hp(*primary_only.state.entity(2));
    const int retaliation_target_before=entity_total_hp(*r.entity(1));
    auto with_ret=sim.apply(r,*rhit,0.5); CHECK(with_ret.valid);
    const int retaliation_dealt=retaliation_target_before-entity_total_hp(*with_ret.state.entity(1));
    CHECK(retaliation_dealt>0);
    CHECK(entity_total_hp(*with_ret.state.entity(2))==std::min(200,target_after_primary+retaliation_dealt/2));
    return true;
}


'''
replace_once(tests, anchor, test_fn + anchor)
replace_once(
    tests,
    '    if (!test_kill_trigger_enraged_gate()) return EXIT_FAILURE;',
    '    if (!test_life_drain_exact_heal_resurrection_and_retaliation()) return EXIT_FAILURE;\n    if (!test_kill_trigger_enraged_gate()) return EXIT_FAILURE;'
)

reg = 'python/hwm_solver/knowledge/build_ability_registry.py'
replace_once(
    reg,
    '    "takeroots", "fireattack", "battlethirst", "tasteofblood", "bloodfrenzy", "organicarmor", "shieldother", "concentration", "lizardbite",\n',
    '    "takeroots", "fireattack", "battlethirst", "tasteofblood", "bloodfrenzy", "organicarmor", "shieldother", "concentration", "lizardbite", "lifedrain",\n'
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

registry = json.loads(Path('data/catalog/ability_registry.json').read_text(encoding='utf-8'))
counts = registry['support_counts']
if counts.get('exact_search') != 82 or counts.get('learned_damage') != 180 or counts.get('unresolved') != 78:
    raise SystemExit(f'unexpected registry counts after Life Drain promotion: {counts}')

for path in ['SPEC.md', 'HeroesWM_Solver_TZ_Status_0.3.0.md']:
    replace_once(
        path,
        '**Статус:** Active implementation specification; checkpoint 0.3.0  \n',
        '**Статус:** Active implementation specification; checkpoint 0.3.0  \n**Последнее обновление реализации:** 10.08.2026 — Life Drain переведён в exact-search.  \n'
    )
    replace_once(
        path,
        '- Ability catalog: **421** ability code; registry: **81 exact-search**, 11 exact-targeting, 18 partial-exact, 8 modeled-proc, 5 modeled-collateral, 2 modeled-kill-trigger, dynamic spellbook; **78 unresolved**.',
        '- Ability catalog: **421** ability code; registry: **82 exact-search**, 11 exact-targeting, 18 partial-exact, 8 modeled-proc, 5 modeled-collateral, 2 modeled-kill-trigger, dynamic spellbook; **78 unresolved**. `Life Drain` теперь моделируется точным transition-правилом лечения/воскрешения от 50% фактически нанесённого физического урона.'
    )
    replace_once(
        path,
        '1. Закрытие high-impact unresolved creature abilities; текущая точка исследования — `Life Drain` и assist/counter/stateful abilities.',
        '1. Закрытие high-impact unresolved creature abilities; `Life Drain` закрыт 10.08.2026, текущая точка исследования — remaining assist/counter/stateful abilities.'
    )

for path in ['IMPLEMENTATION_REPORT.md', 'HeroesWM_Solver_Implementation_Report_0.3.0.md']:
    replace_once(path, '| Ability Registry exact-search | 81 |', '| Ability Registry exact-search | 82 |')
    replace_once(path, '  "exact_search": 81,', '  "exact_search": 82,')
    replace_once(path, '  "learned_damage": 181,', '  "learned_damage": 180,')
    replace_once(
        path,
        'Examples already handled in runtime include core movement/shooter/large/flyer/retaliation rules; multi-hit; defense penetration/resistances/immunities; Defend/Take Roots/Entrenchment; Stone/Warding/Crippling observed state; Enraged/Pack Enrage; Battle Thirst/Taste of Blood; Mana Drain; Blood Frenzy; Organic Armor; Shield Other; Swift Attack; Impervious to Pain; Concentration; Lizard Bite; direct hero spells and several status spells.',
        'Examples already handled in runtime include core movement/shooter/large/flyer/retaliation rules; multi-hit; defense penetration/resistances/immunities; Defend/Take Roots/Entrenchment; Stone/Warding/Crippling observed state; Enraged/Pack Enrage; Battle Thirst/Taste of Blood; Mana Drain; Life Drain; Blood Frenzy; Organic Armor; Shield Other; Swift Attack; Impervious to Pain; Concentration; Lizard Bite; direct hero spells and several status spells.'
    )
    replace_once(
        path,
        '**Current research frontier:** Life Drain and remaining assist/counter/summon/control abilities. Life Drain is not yet marked exact in this snapshot.',
        '**Current research frontier:** remaining assist/counter/summon/control abilities. Life Drain was promoted to `exact_search` on 10.08.2026 after adding HP restoration/resurrection transitions and regression coverage.'
    )
    replace_once(
        path,
        '1. Finish Life Drain / high-impact unresolved abilities.',
        '1. Continue high-impact unresolved abilities after the completed Life Drain transition.'
    )

tr = Path('TEST_REPORT.md')
text = tr.read_text(encoding='utf-8')
if text.count('exact_search:           81') != 1:
    raise SystemExit('TEST_REPORT.md: exact_search anchor mismatch')
text = text.replace('exact_search:           81', 'exact_search:           82', 1)
marker = 'held-out sampled player states: 1748\n'
if text.count(marker) != 1:
    raise SystemExit('TEST_REPORT.md: risk snapshot marker mismatch')
text = text.replace(
    marker,
    'Registry counts regenerated 10.08.2026 after exact Life Drain transition; held-out risk numbers below remain the 09.08.2026 checkpoint snapshot and are not relabeled.\n\n' + marker,
    1
)
tr.write_text(text, encoding='utf-8')

# Temporary patch infrastructure must not survive the functional commit.
if WORKFLOW.exists():
    WORKFLOW.unlink()
if SCRIPT.exists():
    SCRIPT.unlink()

run('cmake', '--preset', 'debug')
run('cmake', '--build', 'build/debug', '--parallel', '2')
run('ctest', '--test-dir', 'build/debug', '--output-on-failure')
run('git', 'diff', '--check')

run('git', 'config', 'user.name', 'github-actions[bot]')
run('git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
run('git', 'add', '-A')
run('git', 'commit', '-m', 'feat: model exact Life Drain transitions')
functional_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()

changelog = Path('changelog.md')
text = changelog.read_text(encoding='utf-8').rstrip() + '\n\n'
text += '''### Changelog initialization

- Commit: `b3c085477c0d55ea8aac6bf2f1be1a8fb36abc5a`
- Added `changelog.md` and established the commit-linked development diary convention.

### Life Drain patch tooling

- Commit: `4b4d18fd8727fe9e9c9fec72edd26eff1cc0cf08`
- First one-shot patch-runner staging commit; workflow did not start any jobs because the embedded multiline YAML was invalid. No functional source changes were produced by that failed run.

'''
script_commit = os.environ.get('PATCH_SCRIPT_COMMIT', 'unknown')
runner_commit = os.environ.get('GITHUB_SHA', 'unknown')
text += f'''- Temporary patch script commit: `{script_commit}`
- Corrected runner commit: `{runner_commit}`
- Moved the patch logic into a temporary Python script so GitHub Actions parses the workflow safely. Both temporary files are removed by the functional commit.

### Exact Life Drain transition

- Commit: `{functional_sha}`
- Implemented `lifedrain` healing from 50% of actually inflicted physical damage, including resurrection up to `max_count`.
- Applied the same rule to normal and concentration/pre-emptive retaliation paths.
- Added a phantom-damage guard so phantom dissipation cannot inflate healing.
- Added C++ regression coverage for primary healing/resurrection, max-count cap, and retaliation healing.
- Promoted `lifedrain` from `learned_damage` to `exact_search`; regenerated Ability Registry to 82 exact-search / 180 learned-damage / 78 unresolved.
- Updated active Markdown specification, implementation report, and test report status.
- C++ Debug build and CTest passed before commit.
'''
changelog.write_text(text, encoding='utf-8')
run('git', 'add', 'changelog.md')
run('git', 'commit', '-m', 'docs: log exact Life Drain implementation')
run('git', 'push', 'origin', 'HEAD:main')
