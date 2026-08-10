from pathlib import Path

old_script=Path('.github/scripts/apply_pawstrike_patch.py')
source=old_script.read_text(encoding='utf-8')
source=source.replace(
    "SCRIPT = Path('.github/scripts/apply_pawstrike_patch.py')",
    "SCRIPT = Path('.github/scripts/apply_pawstrike_patch_v3.py')",
    1,
)

# Per-command semantic verification: one decision can contain multiple I records.
source=source.replace(
    'from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands',
    'from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, _decision_semantic_unresolved_flags',
    1,
)
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
            flags=_decision_semantic_unresolved_flags(cmds,before,int(row["actor_uid"]))
            for c,unresolved in zip(cmds,flags,strict=True):
                if c.opcode!="I_RECORD":continue
                source=before.get(int(c.target_uid)) if c.target_uid is not None else None
                affected=int(c.actor_uid) if c.actor_uid is not None else -1
                if source and int(source["uid"])==int(row["actor_uid"]):
                    seen+=1
                    if not unresolved:exact+=1
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

# Remove all temporary patch runners from the functional tree. History of failed
# staging attempts is appended in the post-success bookkeeping commit.
source=source.replace(
    "WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True)",
    "WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True);old_script.unlink(missing_ok=True);Path('.github/scripts/apply_pawstrike_patch_v2.py').unlink(missing_ok=True)",
    1,
)

exec(compile(source,'<pawstrike-patcher-v3>','exec'),{'__name__':'__main__','old_script':old_script})
