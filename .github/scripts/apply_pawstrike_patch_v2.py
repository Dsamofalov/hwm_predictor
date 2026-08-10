from pathlib import Path

old_script=Path('.github/scripts/apply_pawstrike_patch.py')
source=old_script.read_text(encoding='utf-8')
source=source.replace(
    "SCRIPT = Path('.github/scripts/apply_pawstrike_patch.py')",
    "SCRIPT = Path('.github/scripts/apply_pawstrike_patch_v2.py')",
    1,
)

old_import='from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands'
new_import='from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, _decision_semantic_unresolved_flags'
if source.count(old_import)!=1:raise SystemExit(f'corpus import marker mismatch: {source.count(old_import)}')
source=source.replace(old_import,new_import,1)

old_loop='''            cmds=parse_commands(row["raw"])
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
new_loop='''            cmds=parse_commands(row["raw"])
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
if source.count(old_loop)!=1:raise SystemExit(f'corpus loop marker mismatch: {source.count(old_loop)}')
source=source.replace(old_loop,new_loop,1)
source=source.replace('(seen,exact,atb_zero)!=(150,150,150)','(seen,exact,atb_zero)!=(174,174,174)',1)

source=source.replace('Marked **150/150** observed Paw Strike I-records semantic-safe','Marked **174/174** observed Paw Strike I-records semantic-safe',1)
source=source.replace('150 isolated proc signatures and chronological probability validation','150 primary-target proc signatures, 24 additional secondary-hit I-records, and chronological primary probability validation',1)
source=source.replace('150/150 observed proc I-records identify actor->target','174/174 observed proc I-records identify actor->affected target',1)

old_log="text += f'''### Paw Strike hybrid modeled proc\\n\\n- Commit: `{staging}`\\n  - Staged a self-removing verified patch after 357 melee observations, 150 isolated proc signatures and chronological probability validation."
new_log="text += f'''### Paw Strike hybrid modeled proc\\n\\n- Commit: `d788f2884fd909e7d8617d6959a1b2388e11f8fe`\\n  - Initial production staging correctly failed its corpus gate after explicit I-record source parsing expanded the observed scope from 150 primary-target records to 174 total primary+secondary hit records. No functional Paw Strike commit was produced.\\n- Commits: `804e5f62200539e27af2d6f79a38adb23ea645fc`, `b1c584c292d4eeaaea09f7b531bfa2ec316c023c`\\n  - Follow-up corpus audits proved all 174 records are opposing damage targets with raw order DAMAGE -> FORCED_POSITION -> I and no ownership/order exceptions.\\n- Commit: `{staging}`\\n  - Switched the verification from row-level opcode-name aggregation to per-command semantic flags and re-ran the same self-removing hybrid patch."
if source.count(old_log)!=1:raise SystemExit(f'changelog marker mismatch: {source.count(old_log)}')
source=source.replace(old_log,new_log,1)

source=source.replace(
    "WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True)",
    "WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True);old_script.unlink(missing_ok=True)",
    1,
)

exec(compile(source,'<pawstrike-patcher-v2>','exec'),{'__name__':'__main__','old_script':old_script})
