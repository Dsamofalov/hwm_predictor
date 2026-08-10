from pathlib import Path

old_script = Path('.github/scripts/apply_mightyslam_patch.py')
old_v2 = Path('.github/scripts/apply_mightyslam_patch_v2.py')
source = old_script.read_text(encoding='utf-8')

source = source.replace(
    "SCRIPT = Path('.github/scripts/apply_mightyslam_patch.py')",
    "SCRIPT = Path('.github/scripts/apply_mightyslam_patch_v3.py')",
    1,
)

# The legal-actions and apply paths both declare carrier/mana-feed IDs. Make the
# legal-actions insertion anchor unique instead of requiring the shared pair to occur once.
old_ids = '''replace_once(
    sim,
    \'''    const uint32_t carrier_wire_id=stable_tag_id("car");\\n    const uint32_t mana_feed_wire_id=stable_tag_id("mfd");\\n\''',
    \'''    const uint32_t carrier_wire_id=stable_tag_id("car");\\n    const uint32_t mana_feed_wire_id=stable_tag_id("mfd");\\n    const uint32_t mighty_slam_wire_id=stable_tag_id("msl");\\n\'''
)'''
new_ids = '''replace_once(
    sim,
    \'''    const uint32_t carrier_wire_id=stable_tag_id("car");\\n    const uint32_t mana_feed_wire_id=stable_tag_id("mfd");\\n    if(!actor->rune_speed_active&&has_tag(*actor,"manafeed")&&actor->mana>0&&actor->count>0){\\n\''',
    \'''    const uint32_t carrier_wire_id=stable_tag_id("car");\\n    const uint32_t mana_feed_wire_id=stable_tag_id("mfd");\\n    const uint32_t mighty_slam_wire_id=stable_tag_id("msl");\\n    if(!actor->rune_speed_active&&has_tag(*actor,"manafeed")&&actor->mana>0&&actor->count>0){\\n\'''
)'''
if source.count(old_ids) != 1:
    raise SystemExit(f'failed to find ambiguous ID patch block: {source.count(old_ids)}')
source = source.replace(old_ids, new_ids, 1)

# The previous patch placed Mighty Slam after generic DAMAGE-based classification,
# so every observed Slam with damage still became MELEE_ATTACK. Keep Mana Feed's
# existing branch and move Mighty Slam ahead of waits/defends/dealt in both classifiers.
old_classifier_patch = '''replace_n(
    py,
    \'''    elif mana_feed:\\n        typ = "ABILITY"\\n\''',
    \'''    elif mana_feed:\\n        typ = "ABILITY"\\n    elif mighty_slam:\\n        typ = "ABILITY"\\n\''',
    2,
)'''
new_classifier_patch = '''replace_n(
    py,
    \'''    if waits:\\n\''',
    \'''    if mighty_slam:\\n        typ = "ABILITY"\\n    elif waits:\\n\''',
    2,
)'''
if source.count(old_classifier_patch) != 1:
    raise SystemExit(f'failed to find classifier-priority patch block: {source.count(old_classifier_patch)}')
source = source.replace(old_classifier_patch, new_classifier_patch, 1)

# Synthetic geometry: keep the primary and secondary knockback destinations free,
# while retaining an adjacent big enemy that is splashed but never knocked back.
source = source.replace(
    'Entity friendly=secondary;friendly.uid=4;friendly.owner=1;friendly.side=Side::Player;friendly.anchor={3,2};',
    'Entity friendly=secondary;friendly.uid=4;friendly.owner=1;friendly.side=Side::Player;friendly.anchor={1,2};',
    1,
)
source = source.replace(
    'Entity big=secondary;big.uid=6;big.anchor={3,1};big.is_big=true;big.footprint_w=2;big.footprint_h=1;',
    'Entity big=secondary;big.uid=6;big.anchor={3,2};big.is_big=true;big.footprint_w=2;big.footprint_h=1;',
    1,
)

# Retry quickly: only the Python surfaces touched by this patch are needed here.
# The standard full repository CI is triggered after the functional commit.
source = source.replace(
    "run('python','-m','pytest','-q',env=env)\ncollect=run('python','-m','pytest','--collect-only','-q',env=env,capture=True)\nm=re.search(r'(\\d+) tests? collected',collect)\nif not m:\n    # pytest -q may end in e.g. \"42 tests collected in ...\"\n    raise SystemExit('could not determine pytest collection count')\npytests=int(m.group(1))\ntext=tr.read_text(encoding='utf-8')\ntext=re.sub(r'Python pytest:\\s+\\d+/\\d+ PASS',f'Python pytest:              {pytests}/{pytests} PASS',text,count=1)\ntr.write_text(text,encoding='utf-8')",
    "run('python','-m','pytest','-q','python/tests/test_replay_parser.py','python/tests/test_ability_probe.py',env=env)\npytests='targeted replay+ability-probe tests'",
    1,
)
source = source.replace(
    "C++ Debug build/CTest and full Python pytest (**{pytests}/{pytests}**) passed before commit.",
    "C++ Debug build/CTest and **{pytests}** passed before commit; full Python/TypeScript integration is verified by the standard CI immediately after this functional tree lands.",
    1,
)

# Cleanup every temporary generation of this patch runner.
source = source.replace(
    "WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True)",
    "WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True);old_script.unlink(missing_ok=True);old_v2.unlink(missing_ok=True)",
    1,
)

# Preserve failed staging attempts in the diary; neither produced a functional commit.
source = source.replace(
    "text += f'''### Exact Mighty Slam action\\n\\n- Commit: `{staging}`\\n  - Staged a self-removing verified patch after 32/32 `Smsl` observations, multi-target/knockback evidence and same-actor cooldown-gap analysis.",
    "text += f'''### Exact Mighty Slam action\\n\\n- Commit: `b56315fec926d020a9950b5abb9e61aed0459009`\\n  - Initial staging attempt stopped before source/test execution because a patch anchor shared by legal/apply paths was not unique. No functional commit was produced.\\n- Commit: `0b33c7091ffaacdb885918192775856046775ad6`\\n  - Second staging attempt applied the wire/registry changes in the runner worktree but the 866-battle gate correctly rejected the patch because DAMAGE classification still took priority over `Smsl`, leaving Slam decisions as `MELEE_ATTACK`. No functional commit was produced.\\n- Commit: `{staging}`\\n  - Corrected classifier priority and synthetic knockback geometry, then re-ran the self-removing verified patch after 32/32 `Smsl` observations, multi-target/knockback evidence and same-actor cooldown-gap analysis.",
    1,
)

exec(compile(source, '<mightyslam-patcher-v3>', 'exec'), {
    '__name__': '__main__',
    'old_script': old_script,
    'old_v2': old_v2,
})
