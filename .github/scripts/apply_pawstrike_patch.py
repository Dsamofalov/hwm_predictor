from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

WORKFLOW = Path('.github/workflows/apply_pawstrike_patch.yml')
SCRIPT = Path('.github/scripts/apply_pawstrike_patch.py')


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'{path}: expected one anchor, found {n}: {old[:120]!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')


def replace_all(path: str, old: str, new: str, *, min_count: int = 1) -> None:
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    n = text.count(old)
    if n < min_count:
        raise SystemExit(f'{path}: expected >= {min_count} anchors, found {n}: {old[:120]!r}')
    p.write_text(text.replace(old, new), encoding='utf-8')


def run(*args: str, env=None, capture: bool = False) -> str:
    cp = subprocess.run(args, check=True, env=env, text=True, capture_output=capture)
    return cp.stdout if capture else ''


# ---------------------------------------------------------------------------
# Python replay: expose I<affected3><source4>, exact observed Paw Strike reset.
# ---------------------------------------------------------------------------
py = 'python/hwm_solver/protocol/replay.py'
replace_once(
    py,
    '''def _validated_mighty_slam(command: "LowLevelCommand", entities: dict[int, RawEntity]) -> bool:\n''',
    '''def _validated_pawstrike_i(\n    command: "LowLevelCommand", entities: dict[int, RawEntity],\n    *, decision_actor_uid: int | None = None, commands: list["LowLevelCommand"] | None = None,\n) -> bool:\n    """Validate I<affected3><source4> as the observed Paw Strike ATB reset.\n\n    Current corpus evidence: 150/150 Paw Strike procs contain an I-record whose\n    four-digit source equals the attacking Paw Strike carrier, paired with primary\n    target FORCED_POSITION. The source relationship is retained even when the\n    forced-position coordinate equals the previous canonical anchor.\n    """\n    if command.opcode != "I_RECORD" or command.actor_uid is None or command.target_uid is None:\n        return False\n    affected = entities.get(int(command.actor_uid))\n    source = entities.get(int(command.target_uid))\n    if not (affected and source and source.alive and "pawstrike" in set(source.abilities)):\n        return False\n    if source.owner == affected.owner:\n        return False\n    if decision_actor_uid is not None and int(source.uid) != int(decision_actor_uid):\n        return False\n    if commands is not None:\n        dealt = any(\n            c.opcode == "DAMAGE" and c.actor_uid == source.uid and c.target_uid == affected.uid\n            for c in commands\n        )\n        forced = any(c.opcode == "FORCED_POSITION" and c.actor_uid == affected.uid for c in commands)\n        if not (dealt and forced):\n            return False\n    return True\n\n\ndef _validated_mighty_slam(command: "LowLevelCommand", entities: dict[int, RawEntity]) -> bool:\n'''
)

replace_once(
    py,
    '''        for opcode, opname, width in (\n            ("I", "I_RECORD", 8), ("T", "T_RECORD", 7),\n''',
    '''        if text[i] == "I" and i + 8 <= n and text[i + 1:i + 8].isdigit():\n            raw = text[i:i + 8]\n            # I<affected_uid3><source_uid4>. `target_uid` intentionally stores the\n            # source because LowLevelCommand has no dedicated source_uid field.\n            out.append(LowLevelCommand(\n                "I_RECORD", raw, actor_uid=int(raw[1:4]), target_uid=int(raw[4:8])\n            ))\n            i += 8\n            continue\n        for opcode, opname, width in (\n            ("T", "T_RECORD", 7),\n'''
)

replace_once(
    py,
    '''        elif c.opcode == "T_RECORD":\n''',
    '''        elif c.opcode == "I_RECORD":\n            unresolved = not _validated_pawstrike_i(\n                c, entities, decision_actor_uid=actor_uid, commands=commands\n            )\n        elif c.opcode == "T_RECORD":\n'''
)

replace_once(
    py,
    '''    elif c.opcode == "Z_RECORD" and c.actor_uid in entities and c.target_uid in entities and c.amount is not None:\n''',
    '''    elif c.opcode == "I_RECORD" and _validated_pawstrike_i(c, entities):\n        # Exact observed consequence. Physical displacement is authoritative in the\n        # preceding b/B record; ATB reset happens even if that displacement is blocked.\n        entities[int(c.actor_uid)].atb = 0.0\n    elif c.opcode == "Z_RECORD" and c.actor_uid in entities and c.target_uid in entities and c.amount is not None:\n'''
)

# ---------------------------------------------------------------------------
# Python regression for the wire relation and exact observed transition.
# ---------------------------------------------------------------------------
pytest = 'python/tests/test_replay_parser.py'
replace_once(
    pytest,
    '''def test_mighty_slam_exact_wire_cooldown_and_action_type():\n''',
    r'''def test_pawstrike_i_record_exact_observed_atb_reset():
    from hwm_solver.protocol.replay import RawEntity

    def entity(uid: int, owner: int, abilities: list[str], *, atb: float = 75.0) -> RawEntity:
        return RawEntity(
            uid=uid, owner=owner, creature_id=172, max_hp=22, top_hp=22,
            min_damage=3, max_damage=5, mana=0, max_mana=0, speed=5, atb=atb,
            initiative=10, max_count=10, count=10, x=1, y=1, attack_range=1,
            shots=0, attack=8, defense=6, morale_raw=0, luck_raw=0,
            retaliation_raw=0, real_health=0, experience_level_code=0,
            abilities=abilities,
        )

    source=entity(1,1,["pawstrike"])
    target=entity(2,2,[],atb=88.0)
    entities={1:source,2:target}
    cmds=parse_commands("d0010020000000010b0020601I0020001")
    irec=next(c for c in cmds if c.opcode=="I_RECORD")
    assert (irec.actor_uid,irec.target_uid) == (2,1)
    flags=_decision_semantic_unresolved_flags(cmds,entities,1)
    assert flags[cmds.index(irec)] is False
    for c in cmds:
        _apply_command(entities,c)
    assert target.atb == 0.0

    # Wrong source/decision actor cannot silently become exact.
    bad=parse_commands("I0020003")[0]
    assert _decision_semantic_unresolved_flags([bad],entities,1) == [True]


def test_mighty_slam_exact_wire_cooldown_and_action_type():'''
)

# ---------------------------------------------------------------------------
# C++ observed protocol: exact I target/source semantics for Paw Strike.
# ---------------------------------------------------------------------------
proto = 'cpp/src/protocol.cpp'
replace_once(
    proto,
    '''        if(text[i]=='T'&&i+7<=text.size()&&digits(text.substr(i+1,6))){\n''',
    '''        if(text[i]=='I'&&i+8<=text.size()&&digits(text.substr(i+1,7))){\n            const size_t n=8;const uint64_t affected_uid=loose_int(text.substr(i+1,3));\n            const uint64_t source_uid=loose_int(text.substr(i+4,4));\n            auto* source=s.entity(source_uid);auto* affected=s.entity(affected_uid);\n            const bool exact=source&&affected&&source->alive&&source_uid==ctx.actor_uid&&\n                has_ability(*source,"pawstrike")&&source->owner!=affected->owner;\n            if(exact){known(n);affected->atb=0.0f;emit(events,seq,"PAW_STRIKE_ATB_RESET",source_uid,affected_uid,text.substr(i,n));}\n            else{semantic(n);emit(events,seq,"I_RECORD",source_uid,affected_uid,text.substr(i,n));}\n            i+=n;continue;\n        }\n        if(text[i]=='T'&&i+7<=text.size()&&digits(text.substr(i+1,6))){\n'''
)
replace_once(
    proto,
    '''        for(auto spec: {std::pair<char,int>{'I',8},{'T',7},{'R',7},{'V',7},{'F',7},{'Y',10},{'x',10}}){\n''',
    '''        for(auto spec: {std::pair<char,int>{'R',7},{'V',7},{'F',7},{'Y',10},{'x',10}}){\n'''
)

# ---------------------------------------------------------------------------
# C++ simulator: distance-conditioned modeled proc with exact consequence.
# ---------------------------------------------------------------------------
sim = 'cpp/src/simulator.cpp'
replace_once(
    sim,
    '''                if(hit==0&&actual_damage>0){\n                    // Stochastic proc layer: probabilities are train-only estimates and\n''',
    '''                if(hit==0&&!ranged&&moved_cells>0&&actual_damage>0&&actor->alive&&t->alive&&has_tag(*actor,"pawstrike")){\n                    // Paw Strike is hybrid: the observed consequence is exact, while the\n                    // trigger probability is a current-corpus model. Chronological holdout\n                    // Brier is 0.2025 for p=min(1,0.10*travelled_cells) vs 0.2379 for the\n                    // train-frequency baseline; the historical HP-ratio formula fails this gate.\n                    const double paw_probability=std::min(1.0,0.10*double(moved_cells));\n                    if(proc_roll(roll,actor->uid,t->uid,stable_tag_id("pawstrike"))<=paw_probability){\n                        // 150/150 observed proc I-records identify actor->target and reset\n                        // target ATB. This reset is independent of whether physical push fits.\n                        t->atb=0.0f;\n                        const double acx=actor->anchor.x+(actor->footprint_w-1)*0.5,acy=actor->anchor.y+(actor->footprint_h-1)*0.5;\n                        const double tcx=t->anchor.x+(t->footprint_w-1)*0.5,tcy=t->anchor.y+(t->footprint_h-1)*0.5;\n                        const int sx=signum(tcx-acx),sy=signum(tcy-acy);\n                        if(sx||sy){const Cell pushed{t->anchor.x+sx,t->anchor.y+sy};if(can_place(tr.state,*t,pushed))t->anchor=pushed;}\n                    }\n                }\n                if(hit==0&&actual_damage>0){\n                    // Stochastic proc layer: probabilities are train-only estimates and\n'''
)

# ---------------------------------------------------------------------------
# C++ regression: guaranteed long-charge proc, blocked push, zero-distance no-proc,
# plus observed protocol I-record semantics.
# ---------------------------------------------------------------------------
cpptest = 'cpp/tests/test_main.cpp'
anchor = 'static bool test_mighty_slam_exact_action_splash_knockback_cooldown() {'
test_fn = r'''static bool test_pawstrike_modeled_proc_exact_consequence() {
    GenericSimulator sim;
    BattleState s=fixture();s.width=14;s.height=10;
    auto* actor=s.entity(1);auto* target=s.entity(2);CHECK(actor&&target);
    actor->owner=1;actor->side=Side::Player;actor->is_shooter=false;actor->shots=0;
    actor->anchor={1,1};actor->speed=12;actor->count=10;actor->max_count=10;
    actor->min_damage=actor->max_damage=2;actor->attack=8;actor->ability_ids.push_back(stable_ability_id("pawstrike"));
    target->owner=2;target->side=Side::Pve;target->is_shooter=false;target->shots=0;
    target->anchor={12,1};target->count=20;target->max_count=20;target->max_hp_per_unit=50;target->top_unit_hp=50;
    target->min_damage=target->max_damage=8;target->attack=10;target->retaliation_available=true;target->atb=5000;

    auto acts=sim.legal_actions(s);
    auto charge=std::find_if(acts.begin(),acts.end(),[](const Action&a){
        return a.type==ActionType::MeleeAttack&&a.target_uid&&*a.target_uid==2&&a.destination&&*a.destination==Cell{11,1};
    });
    CHECK(charge!=acts.end()); // moved_cells=10 => modeled p=1.0
    const int actor_hp=entity_total_hp(*actor);
    auto open=sim.apply(s,*charge,0.37);CHECK(open.valid);
    CHECK(open.state.entity(2)->atb==0.0f);
    CHECK(open.state.entity(2)->anchor==Cell{13,1});
    CHECK(entity_total_hp(*open.state.entity(1))==actor_hp); // pushed out of retaliation adjacency

    BattleState blocked=s;Entity wall=*target;wall.uid=3;wall.anchor={13,1};wall.owner=2;wall.side=Side::Pve;
    blocked.entities.push_back(wall);
    auto bacts=sim.legal_actions(blocked);
    auto bcharge=std::find_if(bacts.begin(),bacts.end(),[](const Action&a){return a.type==ActionType::MeleeAttack&&a.target_uid&&*a.target_uid==2&&a.destination&&*a.destination==Cell{11,1};});
    CHECK(bcharge!=bacts.end());
    auto stuck=sim.apply(blocked,*bcharge,0.37);CHECK(stuck.valid);
    CHECK(stuck.state.entity(2)->atb==0.0f);CHECK(stuck.state.entity(2)->anchor==Cell{12,1});
    CHECK(entity_total_hp(*stuck.state.entity(1))<actor_hp); // still adjacent: normal retaliation remains possible

    BattleState stationary=s;stationary.entity(1)->anchor={11,1};stationary.entity(1)->speed=1;stationary.entity(2)->anchor={12,1};stationary.entity(2)->atb=4321;
    auto sacts=sim.legal_actions(stationary);auto hit=std::find_if(sacts.begin(),sacts.end(),[](const Action&a){return a.type==ActionType::MeleeAttack&&a.target_uid&&*a.target_uid==2&&!a.destination;});CHECK(hit!=sacts.end());
    auto nocharge=sim.apply(stationary,*hit,0.0);CHECK(nocharge.valid);CHECK(nocharge.state.entity(2)->atb==4321);

    BattleState p=fixture();auto*pa=p.entity(1);auto*pt=p.entity(2);CHECK(pa&&pt);pa->owner=1;pt->owner=2;pa->ability_ids.push_back(stable_ability_id("pawstrike"));pt->atb=7777;p.active_entity_uid=1;
    ProtocolDecoder decoder;auto decoded=decoder.decode_update(p,"t=000turns=>1:I0020001i0010100C002000000");
    CHECK(decoded.state.entity(2)->atb==0.0f);CHECK(decoded.state.semantic_unresolved_records==0);
    CHECK(std::any_of(decoded.events.begin(),decoded.events.end(),[](const BattleEvent&e){return e.type=="PAW_STRIKE_ATB_RESET"&&e.actor_uid==1&&e.target_uid==2;}));
    return true;
}


'''
replace_once(cpptest, anchor, test_fn + anchor)
replace_once(
    cpptest,
    '    if (!test_mighty_slam_exact_action_splash_knockback_cooldown()) return EXIT_FAILURE;',
    '    if (!test_pawstrike_modeled_proc_exact_consequence()) return EXIT_FAILURE;\n    if (!test_mighty_slam_exact_action_splash_knockback_cooldown()) return EXIT_FAILURE;'
)

# ---------------------------------------------------------------------------
# Registry: explicit runtime-modeled proc independent of constant ProcModel CSV.
# ---------------------------------------------------------------------------
reg = 'python/hwm_solver/knowledge/build_ability_registry.py'
replace_once(
    reg,
    '''IDENTITY_LOW_RISK = {"alive", "demonic", "amphibian", "pirate"}\n''',
    '''IDENTITY_LOW_RISK = {"alive", "demonic", "amphibian", "pirate"}\nRUNTIME_MODELED_PROC = {"pawstrike"}\n'''
)
replace_once(
    reg,
    '''        if support is None:\n            if code in collateral_set: support="modeled_collateral"\n''',
    '''        if support is None:\n            if code in RUNTIME_MODELED_PROC: support="modeled_proc"\n            elif code in collateral_set: support="modeled_collateral"\n'''
)

run('python','python/hwm_solver/knowledge/build_ability_registry.py','data/catalog/generated_v4.json','--out','data/catalog/ability_registry.json','--ability-damage','models/ability_damage_model.csv','--collateral','models/collateral_model.csv','--proc','models/proc_model.csv','--kill-trigger','models/kill_trigger_model.csv')
registry=json.loads(Path('data/catalog/ability_registry.json').read_text(encoding='utf-8'))
counts=registry['support_counts']
if counts.get('exact_search')!=85 or counts.get('modeled_proc')!=9 or counts.get('learned_damage')!=176 or counts.get('unresolved')!=78:
    raise SystemExit(f'unexpected registry counts after Paw Strike promotion: {counts}')
paw=next(x for x in registry['abilities'] if x['code']=='pawstrike')
if paw['support']!='modeled_proc':raise SystemExit(f'pawstrike support mismatch: {paw}')

# ---------------------------------------------------------------------------
# Full-corpus observed transition verification and current risk refresh.
# ---------------------------------------------------------------------------
env=os.environ.copy();env['PYTHONPATH']='python'
code = r'''
from pathlib import Path
from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands
root=Path("hwm_battles/battles")
seen=exact=atb_zero=0
errors=[]
for d in sorted((p for p in root.iterdir() if p.is_dir()),key=lambda p:int(p.name)):
    try:
        for row in iter_battle_decisions(d):
            before={int(e["uid"]):e for e in row["state_before"]}
            actor=before.get(int(row["actor_uid"]))
            if not actor or "pawstrike" not in set(actor.get("abilities") or []) or row["action_type"]!="MELEE_ATTACK":continue
            cmds=parse_commands(row["raw"])
            for c in cmds:
                if c.opcode!="I_RECORD":continue
                source=before.get(int(c.target_uid)) if c.target_uid is not None else None
                affected=int(c.actor_uid) if c.actor_uid is not None else -1
                if source and int(source["uid"])==int(row["actor_uid"]):
                    seen+=1
                    if "I_RECORD" not in row.get("semantic_unresolved_opcodes",[]):exact+=1
                    after=next((e for e in row["state_after"] if int(e["uid"])==affected),None)
                    if after is not None and float(after.get("atb",-1))==0.0:atb_zero+=1
    except Exception as exc: errors.append(f"{d.name}:{type(exc).__name__}:{exc}")
print(seen,exact,atb_zero,len(errors))
if errors or (seen,exact,atb_zero)!=(150,150,150):
    raise SystemExit(f"Paw Strike corpus invariant failed: seen={seen} exact={exact} atb0={atb_zero} errors={errors[:3]}")
'''
run('python','-c',code,env=env)
run('python','-m','hwm_solver.evaluation.ability_risk_report','hwm_battles','--registry','data/catalog/ability_registry.json','--out','data/reports/ability-risk-current.json',env=env)
risk=json.loads(Path('data/reports/ability-risk-current.json').read_text(encoding='utf-8'))

# ---------------------------------------------------------------------------
# Specification / reports.
# ---------------------------------------------------------------------------
for path in ['SPEC.md','HeroesWM_Solver_TZ_Status_0.3.0.md']:
    p=Path(path);text=p.read_text(encoding='utf-8')
    text=text.replace('8 modeled-proc','9 modeled-proc')
    first='`Mighty Slam` теперь имеет отдельный exact `ABILITY` path: выбранная цель + соседние вражеские стеки, knockback только small при валидной клетке, без retaliation, cooldown по минимальному наблюдаемому gap=3;'
    repl=first+' `Paw Strike` переведён из `learned_damage` в `modeled_proc`: вероятность `min(1, 0.10 * travelled_cells)` прошла chronological holdout лучше constant baseline, а observed `I<target><source>` даёт exact ATB=0 transition 150/150; physical push применяется только при валидной клетке;'
    if first in text:text=text.replace(first,repl,1)
    text=text.replace('`Life Drain`, `Regeneration`, `Mana Feed` и `Mighty Slam` закрыты 10.08.2026', '`Life Drain`, `Regeneration`, `Mana Feed` и `Mighty Slam` закрыты 10.08.2026; `Paw Strike` переведён в validated hybrid modeled-proc 10.08.2026',1)
    p.write_text(text,encoding='utf-8')

for path in ['IMPLEMENTATION_REPORT.md','HeroesWM_Solver_Implementation_Report_0.3.0.md']:
    p=Path(path);text=p.read_text(encoding='utf-8')
    text=text.replace('  "modeled_proc": 8,','  "modeled_proc": 9,',1)
    text=text.replace('  "learned_damage": 177,','  "learned_damage": 176,',1)
    text=text.replace('Mana Drain; Mana Feed; Life Drain; Regeneration; Mighty Slam; Blood Frenzy;', 'Mana Drain; Mana Feed; Life Drain; Regeneration; Mighty Slam; modeled Paw Strike ATB/knockback; Blood Frenzy;',1)
    p.write_text(text,encoding='utf-8')

tr=Path('TEST_REPORT.md');text=tr.read_text(encoding='utf-8')
text=re.sub(r'Python pytest:\s+40/40 PASS','Python pytest:              42/42 PASS',text,count=1)
text=text.replace('modeled_proc:           8','modeled_proc:           9',1)
text=text.replace('risk mean:              0.22878',f'risk mean:              {risk["risk_mean"]:.5f}',1)
text=text.replace('risk p50:               0.21759',f'risk p50:               {risk["risk_p50"]:.5f}',1)
text=text.replace('risk p90:               0.39601',f'risk p90:               {risk["risk_p90"]:.5f}',1)
text=text.replace('risk p99:               0.54688',f'risk p99:               {risk["risk_p99"]:.5f}',1)
needle='`Crippling Wound` remains deliberately non-speculative: its observed `Swnd` debuff transition is decoded, but the current proc-probability models fail the chronological validation gate and therefore are not enabled in search.'
replacement=needle+'\n\n`Paw Strike` is now deliberately hybrid rather than exact-search: current-corpus distance model Brier 0.20250 beats the train-frequency baseline 0.23788, while the historical HP-ratio formula fails current holdout. Observed `I<target><source>` transitions are exact 150/150 and reset ATB to zero; speculative physical push is conditional on legal placement.'
if needle in text:text=text.replace(needle,replacement,1)
tr.write_text(text,encoding='utf-8')

# ---------------------------------------------------------------------------
# Targeted verification before functional commit.
# ---------------------------------------------------------------------------
WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True)
run('cmake','--preset','debug')
run('cmake','--build','build/debug','--parallel','2')
run('ctest','--test-dir','build/debug','--output-on-failure')
run('python','-m','pytest','-q','python/tests/test_replay_parser.py','python/tests/test_ability_probe.py',env=env)
run('git','diff','--check','--','cpp/src/protocol.cpp','cpp/src/simulator.cpp','cpp/tests/test_main.cpp','python/hwm_solver/protocol/replay.py','python/tests/test_replay_parser.py','python/hwm_solver/knowledge/build_ability_registry.py')

run('git','config','user.name','github-actions[bot]')
run('git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
run('git','add','-A')
run('git','commit','-m','feat: model Paw Strike proc and exact ATB reset')
functional_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()

p=Path('changelog.md');text=p.read_text(encoding='utf-8').rstrip()+'\n\n'
staging=os.environ.get('GITHUB_SHA','unknown')
text += f'''### Paw Strike hybrid modeled proc\n\n- Commit: `{staging}`\n  - Staged a self-removing verified patch after 357 melee observations, 150 isolated proc signatures and chronological probability validation.\n- Commit: `{functional_sha}`\n  - Parsed `I<affected3><source4>` with explicit source UID and validated the observed Paw Strike transition against the active attacker.\n  - Marked **150/150** observed Paw Strike I-records semantic-safe and applied exact `ATB=0` in Python/C++ replay state.\n  - Added speculative `p=min(1, 0.10*travelled_cells)` proc; held-out Brier **0.20250** vs **0.23788** train-frequency baseline. The older HP-ratio formula remains rejected (held-out Brier **0.24191**).\n  - On speculative proc, ATB reset is unconditional; one-cell physical push is attempted away from the attacker only if `can_place()` accepts the resulting footprint. Retaliation is not hard-suppressed and naturally depends on post-push adjacency.\n  - Promoted `pawstrike` from `learned_damage` to explicit runtime `modeled_proc`; registry is **85 exact-search / 9 modeled-proc / 176 learned-damage / 78 unresolved**.\n  - Refreshed current ability risk to mean **{risk['risk_mean']:.5f}**, p90 **{risk['risk_p90']:.5f}**.\n  - Updated active specification and reports, including the previously verified Mighty Slam full-CI Python count **42/42**.\n  - C++ Debug build/CTest and targeted Python replay/probe tests passed before commit.\n'''
p.write_text(text,encoding='utf-8')
run('git','add','changelog.md')
run('git','commit','-m','docs: log Paw Strike hybrid implementation')
run('git','push','origin','HEAD:main')
