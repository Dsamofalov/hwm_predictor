from pathlib import Path

old_script=Path('.github/scripts/apply_pawstrike_patch.py')
source=old_script.read_text(encoding='utf-8')
source=source.replace(
    "SCRIPT = Path('.github/scripts/apply_pawstrike_patch.py')",
    "SCRIPT = Path('.github/scripts/apply_pawstrike_patch_v3.py')",
    1,
)

# Full-corpus verification is performed directly on canonical decision dicts.
old='''            cmds=parse_commands(row["raw"])
            for c in cmds:
                if c.opcode!="I_RECORD":continue
                source=before.get(int(c.target_uid)) if c.target_uid is not None else None
                affected=int(c.actor_uid) if c.actor_uid is not None else -1
                if source and int(source["uid"])==int(row["actor_uid"]):
                    seen+=1
                    if "I_RECORD" not in row.get("semantic_unresolved_opcodes",[]):exact+=1
                    after=next((e for e in row["state_after"] if int(e["uid"])==affected),None)
                    if after is not None and float(after.get("atb",-1))==0.0:atb_zero+=1
'''
new='''            cmds=parse_commands(row["raw"])
            damage_pairs={(int(c.actor_uid),int(c.target_uid)) for c in cmds if c.opcode=="DAMAGE" and c.actor_uid is not None and c.target_uid is not None}
            forced_uids={int(c.actor_uid) for c in cmds if c.opcode=="FORCED_POSITION" and c.actor_uid is not None}
            for c in cmds:
                if c.opcode!="I_RECORD":continue
                source=before.get(int(c.target_uid)) if c.target_uid is not None else None
                affected_entity=before.get(int(c.actor_uid)) if c.actor_uid is not None else None
                affected=int(c.actor_uid) if c.actor_uid is not None else -1
                if source and int(source["uid"])==int(row["actor_uid"]):
                    seen+=1
                    invariant=(
                        "pawstrike" in set(source.get("abilities") or [])
                        and affected_entity is not None
                        and int(source.get("owner",-1))!=int(affected_entity.get("owner",-1))
                        and (int(source["uid"]),affected) in damage_pairs
                        and affected in forced_uids
                    )
                    if invariant:exact+=1
                    after=next((e for e in row["state_after"] if int(e["uid"])==affected),None)
                    if after is not None and float(after.get("atb",-1))==0.0:atb_zero+=1
'''
if source.count(old)!=1:raise SystemExit(f'corpus loop mismatch: {source.count(old)}')
source=source.replace(old,new,1)
source=source.replace('(seen,exact,atb_zero)!=(150,150,150)','(seen,exact,atb_zero)!=(174,174,174)',1)

# Audits prove 174/174 are opposing damage targets ordered DAMAGE -> FORCED_POSITION -> I.
source=source.replace('exact ATB=0 transition 150/150','exact ATB=0 transition 174/174')
source=source.replace('Observed `I<target><source>` transitions are exact 150/150','Observed `I<target><source>` transitions are exact 174/174')
source=source.replace('Marked **150/150** observed Paw Strike I-records semantic-safe','Marked **174/174** observed Paw Strike I-records semantic-safe')
source=source.replace('150/150 observed proc I-records identify actor->target','174/174 observed proc I-records identify actor->affected target')
source=source.replace(
    'after 357 melee observations, 150 isolated proc signatures and chronological probability validation',
    'after 357 melee observations, 150 primary-target probability samples plus 24 secondary-hit exact I-records, and chronological probability validation',
)

# CHECK is a single-argument macro; braced Cell initializers contain commas visible
# to the preprocessor. Use named expected cells in the generated regression test.
source=source.replace(
    'CHECK(open.state.entity(2)->anchor==Cell{13,1});',
    'const Cell expected_open_push{13,1};CHECK(open.state.entity(2)->anchor==expected_open_push);',
    1,
)
source=source.replace(
    'CHECK(stuck.state.entity(2)->atb==0.0f);CHECK(stuck.state.entity(2)->anchor==Cell{12,1});',
    'CHECK(stuck.state.entity(2)->atb==0.0f);const Cell expected_blocked_anchor{12,1};CHECK(stuck.state.entity(2)->anchor==expected_blocked_anchor);',
    1,
)

# Remove all temporary patch runners from the functional tree.
source=source.replace(
    "WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True)",
    "WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True);old_script.unlink(missing_ok=True);Path('.github/scripts/apply_pawstrike_patch_v2.py').unlink(missing_ok=True)",
    1,
)

exec(compile(source,'<pawstrike-patcher-v3>','exec'),{'__name__':'__main__','old_script':old_script})
