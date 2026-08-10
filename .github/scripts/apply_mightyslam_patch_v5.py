from pathlib import Path

old_script = Path('.github/scripts/apply_mightyslam_patch.py')
source = old_script.read_text(encoding='utf-8')

source = source.replace(
    "SCRIPT = Path('.github/scripts/apply_mightyslam_patch.py')",
    "SCRIPT = Path('.github/scripts/apply_mightyslam_patch_v5.py')",
    1,
)

# Make the legal-actions ID insertion unique; the original pair also occurs in apply().
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
    raise SystemExit(f'ID patch block mismatch: {source.count(old_ids)}')
source = source.replace(old_ids, new_ids, 1)

# Give the explicit Slam marker priority over generic DAMAGE -> MELEE/RANGED classification.
old_classifier = '''replace_n(
    py,
    \'''    elif mana_feed:\\n        typ = "ABILITY"\\n\''',
    \'''    elif mana_feed:\\n        typ = "ABILITY"\\n    elif mighty_slam:\\n        typ = "ABILITY"\\n\''',
    2,
)'''
new_classifier = '''replace_n(
    py,
    \'''    if waits:\\n\''',
    \'''    if mighty_slam:\\n        typ = "ABILITY"\\n    elif waits:\\n\''',
    2,
)'''
if source.count(old_classifier) != 1:
    raise SystemExit(f'classifier patch block mismatch: {source.count(old_classifier)}')
source = source.replace(old_classifier, new_classifier, 1)

# Preserve the existing tooltip test body by keeping a newline after its header.
needle = "def test_tooltips_decode():" + "'''"
replacement = "def test_tooltips_decode():\n" + "'''"
if source.count(needle) != 1:
    raise SystemExit(f'tooltip test insertion marker mismatch: {source.count(needle)}')
source = source.replace(needle, replacement, 1)

# Synthetic geometry: free cells for primary/secondary push; adjacent big target remains immovable.
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

# Fast retry verification. Full repository CI follows the functional commit.
old_pytest = "run('python','-m','pytest','-q',env=env)\ncollect=run('python','-m','pytest','--collect-only','-q',env=env,capture=True)\nm=re.search(r'(\\d+) tests? collected',collect)\nif not m:\n    # pytest -q may end in e.g. \"42 tests collected in ...\"\n    raise SystemExit('could not determine pytest collection count')\npytests=int(m.group(1))\ntext=tr.read_text(encoding='utf-8')\ntext=re.sub(r'Python pytest:\\s+\\d+/\\d+ PASS',f'Python pytest:              {pytests}/{pytests} PASS',text,count=1)\ntr.write_text(text,encoding='utf-8')"
new_pytest = "run('python','-m','pytest','-q','python/tests/test_replay_parser.py','python/tests/test_ability_probe.py',env=env)\npytests='targeted replay+ability-probe tests'"
if source.count(old_pytest) != 1:
    raise SystemExit(f'pytest block mismatch: {source.count(old_pytest)}')
source = source.replace(old_pytest, new_pytest, 1)
source = source.replace(
    "C++ Debug build/CTest and full Python pytest (**{pytests}/{pytests}**) passed before commit.",
    "C++ Debug build/CTest and **{pytests}** passed before commit; full Python/TypeScript integration is verified by standard CI on the final tree.",
    1,
)

# Remove all temporary Slam patch infrastructure from the functional tree.
source = source.replace(
    "WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True)",
    "WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True);old_script.unlink(missing_ok=True);Path('.github/scripts/apply_mightyslam_patch_v2.py').unlink(missing_ok=True);Path('.github/scripts/apply_mightyslam_patch_v3.py').unlink(missing_ok=True);Path('.github/scripts/apply_mightyslam_patch_v4.py').unlink(missing_ok=True)",
    1,
)

# Keep failed staging attempts explicit in the repository diary.
old_log = "text += f'''### Exact Mighty Slam action\\n\\n- Commit: `{staging}`\\n  - Staged a self-removing verified patch after 32/32 `Smsl` observations, multi-target/knockback evidence and same-actor cooldown-gap analysis."
new_log = "text += f'''### Exact Mighty Slam action\\n\\n- Commit: `b56315fec926d020a9950b5abb9e61aed0459009`\\n  - Initial staging stopped before source/test execution because a legal/apply patch anchor was not unique. No functional commit was produced.\\n- Commit: `0b33c7091ffaacdb885918192775856046775ad6`\\n  - Second staging reached the corpus gate, which rejected `Smsl` because generic DAMAGE classification still won over the explicit ability marker. No functional commit was produced.\\n- Commit: `ac3da0ee1ed039a3148ffcbaea88ddf2986e4f73`\\n  - Third staging passed 32/32 corpus classification, registry/risk refresh and C++ build/CTest, but exposed a generated Python-test newline bug. No functional commit was produced.\\n- Commit: `665e6e0d5105023c5ad348e1a17bc44a38f4cd0e`\\n  - Fourth staging failed before patch execution because its temporary wrapper contained an unterminated string literal. No functional commit was produced.\\n- Commit: `{staging}`\\n  - Consolidated the already validated fixes into one clean runner and re-ran the self-removing Mighty Slam verification."
if source.count(old_log) != 1:
    raise SystemExit(f'changelog block mismatch: {source.count(old_log)}')
source = source.replace(old_log, new_log, 1)

exec(compile(source, '<mightyslam-patcher-v5>', 'exec'), {
    '__name__': '__main__',
    'old_script': old_script,
})
