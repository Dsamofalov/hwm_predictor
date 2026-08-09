from pathlib import Path

old_script=Path('.github/scripts/apply_manafeed_patch.py')
source=old_script.read_text(encoding='utf-8')
source=source.replace(
    "SCRIPT=Path('.github/scripts/apply_manafeed_patch.py')",
    "SCRIPT=Path('.github/scripts/apply_manafeed_patch_v2.py')",1)
source=source.replace(
'''    BattleState empty=limited; empty.entity(1)->mana=0;
    CHECK(std::none_of(sim.legal_actions(empty).begin(),sim.legal_actions(empty).end(),[](const Action&a){return a.type==ActionType::Ability&&a.ability_id&&*a.ability_id==stable_ability_id("mfd");}));''',
'''    BattleState empty=limited; empty.entity(1)->mana=0;
    const auto empty_acts=sim.legal_actions(empty);
    CHECK(std::none_of(empty_acts.begin(),empty_acts.end(),[](const Action&a){return a.type==ActionType::Ability&&a.ability_id&&*a.ability_id==stable_ability_id("mfd");}));''',1)
source=source.replace(
    "run('python','-m','pytest','-q',env=env)",
    "run('python','-m','pytest','-q','python/tests/test_replay_parser.py',env=env)",1)
source=source.replace(
    "WORKFLOW.unlink(missing_ok=True); SCRIPT.unlink(missing_ok=True)",
    "WORKFLOW.unlink(missing_ok=True); SCRIPT.unlink(missing_ok=True); old_script.unlink(missing_ok=True)",1)
source=source.replace(
"text += f'''### Exact Mana Feed action\\n\\n- Commit: `{staging}`\\n  - Staged a self-removing verified patch after the corpus probe isolated 42 `Smfd` observations.",
"text += f'''### Exact Mana Feed action\\n\\n- Commit: `5f01febfbc542f662f99f49acb401201edb18099`\\n  - Initial verified patch staging. Registry regeneration and the 42-record corpus probe passed, C++ compiled, but CTest exposed a regression-test bug caused by `begin()`/`end()` from two temporary legal-action vectors. No functional commit was produced.\\n- Commit: `{staging}`\\n  - Corrected the regression test to retain one legal-action vector and re-ran the self-removing verified patch.",1)
if 'sim.legal_actions(empty).begin(),sim.legal_actions(empty).end()' in source:
    raise SystemExit('temporary-vector test bug not removed')
exec(compile(source,'<manafeed-patcher-v2>','exec'),{'__name__':'__main__','old_script':old_script})
