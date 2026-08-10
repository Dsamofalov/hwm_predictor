from pathlib import Path

old_script = Path('.github/scripts/apply_mightyslam_patch.py')
source = old_script.read_text(encoding='utf-8')

source = source.replace(
    "SCRIPT = Path('.github/scripts/apply_mightyslam_patch.py')",
    "SCRIPT = Path('.github/scripts/apply_mightyslam_patch_v2.py')",
    1,
)

old_block = '''replace_once(\n    sim,\n    \'\'\'    const uint32_t carrier_wire_id=stable_tag_id("car");\\n    const uint32_t mana_feed_wire_id=stable_tag_id("mfd");\\n\'\'\',\n    \'\'\'    const uint32_t carrier_wire_id=stable_tag_id("car");\\n    const uint32_t mana_feed_wire_id=stable_tag_id("mfd");\\n    const uint32_t mighty_slam_wire_id=stable_tag_id("msl");\\n\'\'\'\n)'''
new_block = '''replace_once(\n    sim,\n    \'\'\'    const uint32_t carrier_wire_id=stable_tag_id("car");\\n    const uint32_t mana_feed_wire_id=stable_tag_id("mfd");\\n    if(!actor->rune_speed_active&&has_tag(*actor,"manafeed")&&actor->mana>0&&actor->count>0){\\n\'\'\',\n    \'\'\'    const uint32_t carrier_wire_id=stable_tag_id("car");\\n    const uint32_t mana_feed_wire_id=stable_tag_id("mfd");\\n    const uint32_t mighty_slam_wire_id=stable_tag_id("msl");\\n    if(!actor->rune_speed_active&&has_tag(*actor,"manafeed")&&actor->mana>0&&actor->count>0){\\n\'\'\'\n)'''
if source.count(old_block) != 1:
    raise SystemExit(f'expected one ambiguous legal-id patch block, found {source.count(old_block)}')
source = source.replace(old_block, new_block, 1)

source = source.replace(
    "WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True)",
    "WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True);old_script.unlink(missing_ok=True)",
    1,
)
source = source.replace(
    "text += f'''### Exact Mighty Slam action\\n\\n- Commit: `{staging}`\\n  - Staged a self-removing verified patch after 32/32 `Smsl` observations, multi-target/knockback evidence and same-actor cooldown-gap analysis.",
    "text += f'''### Exact Mighty Slam action\\n\\n- Commit: `b56315fec926d020a9950b5abb9e61aed0459009`\\n  - Initial staging attempt; patch execution stopped before any source/test run because a legal/apply ID anchor was intentionally required to be unique but occurred twice. No functional commit was produced.\\n- Commit: `{staging}`\\n  - Corrected the patch anchors and re-ran the self-removing verified patch after 32/32 `Smsl` observations, multi-target/knockback evidence and same-actor cooldown-gap analysis.",
    1,
)

if "expected one ambiguous legal-id" in source:
    raise SystemExit('wrapper accidentally rewrote itself')

exec(compile(source, '<mightyslam-patcher-v2>', 'exec'), {'__name__': '__main__', 'old_script': old_script})
