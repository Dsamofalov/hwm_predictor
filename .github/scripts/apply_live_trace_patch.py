from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / '.github/workflows/apply_live_trace_patch.yml'
SCRIPT = ROOT / '.github/scripts/apply_live_trace_patch.py'


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'{path}: expected one anchor, found {n}: {old[:120]!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')


def run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=str(cwd or ROOT), check=True)


# ---------------------------------------------------------------------------
# Capture contract: return the exact canonical revision/hash visible while the
# SessionStore lock is still held. This avoids a diagnostic race with a later XHR.
# ---------------------------------------------------------------------------
replace_once(
    'cpp/include/hwm/session.hpp',
    '''    bool canonical_state_updated = false;\n    std::string reason;\n};\n''',
    '''    bool canonical_state_updated = false;\n    uint64_t revision = 0;\n    std::string state_hash;\n    std::string reason;\n};\n''',
)
replace_once(
    'cpp/src/session.cpp',
    '''    CaptureOutcome out;\n    if (e.battle_id.empty()) e.battle_id = battle_id_;\n''',
    '''    CaptureOutcome out;\n    const auto stamp_outcome = [&] {\n        out.revision = revision_.load(std::memory_order_acquire);\n        out.state_hash = state_ ? state_hash(*state_) : std::string{};\n    };\n    if (e.battle_id.empty()) e.battle_id = battle_id_;\n''',
)
# Stamp all early capture exits individually; no body/token is added to diagnostics.
replace_once(
    'cpp/src/session.cpp',
    '''        out.reason = "battle_id_missing";\n        return out;\n''',
    '''        out.reason = "battle_id_missing";\n        stamp_outcome();\n        return out;\n''',
)
replace_once(
    'cpp/src/session.cpp',
    '''        out.reason = "empty_body";\n        return out;\n''',
    '''        out.reason = "empty_body";\n        stamp_outcome();\n        return out;\n''',
)
replace_once(
    'cpp/src/session.cpp',
    '''        out.reason = "duplicate_body";\n        return out;\n''',
    '''        out.reason = "duplicate_body";\n        stamp_outcome();\n        return out;\n''',
)
replace_once(
    'cpp/src/session.cpp',
    '''        out.reason = "captured_at_older_than_current_revision";\n        return out;\n''',
    '''        out.reason = "captured_at_older_than_current_revision";\n        stamp_outcome();\n        return out;\n''',
)
replace_once(
    'cpp/src/session.cpp',
    '''    out.accepted = true;\n    out.reason = out.canonical_state_updated ? (state_ && state_->protocol_ready ? "canonical_state_ready" : "canonical_state_partial") : "raw_accepted_state_partial";\n    return out;\n''',
    '''    out.accepted = true;\n    out.reason = out.canonical_state_updated ? (state_ && state_->protocol_ready ? "canonical_state_ready" : "canonical_state_partial") : "raw_accepted_state_partial";\n    stamp_outcome();\n    return out;\n''',
)

# Capture API exposes the binding; recommendation OK exposes the revision it planned.
replace_once(
    'cpp/src/http_server.cpp',
    '''            << ",\\\"canonical_state_updated\\\":" << (outcome.canonical_state_updated?"true":"false")\n            << ",\\\"reason\\\":\\\"" << outcome.reason << "\\\"}";\n''',
    '''            << ",\\\"canonical_state_updated\\\":" << (outcome.canonical_state_updated?"true":"false")\n            << ",\\\"revision\\\":" << outcome.revision\n            << ",\\\"state_hash\\\":\\\"" << outcome.state_hash << "\\\""\n            << ",\\\"reason\\\":\\\"" << outcome.reason << "\\\"}";\n''',
)
replace_once(
    'cpp/src/http_server.cpp',
    '''        o << "{\\\"status\\\":\\\"" << r.status << "\\\",\\\"state_hash\\\":\\\"" << r.state_hash\n          << "\\\",\\\"semantic_safety_tier\\\":\\\"" << semantic_safety_tier(s) << "\\\""\n''',
    '''        o << "{\\\"status\\\":\\\"" << r.status << "\\\",\\\"state_hash\\\":\\\"" << r.state_hash\n          << "\\\",\\\"state_revision\\\":" << requested_revision\n          << ",\\\"battle_id\\\":\\\"" << json_escape(s.battle_id) << "\\\""\n          << ",\\\"semantic_safety_tier\\\":\\\"" << semantic_safety_tier(s) << "\\\""\n''',
)

# ---------------------------------------------------------------------------
# Service worker: bounded metadata-only live trace. Never store raw body, bearer
# token, full URL/query, cookies, storage snapshots or runtime primitive values.
# ---------------------------------------------------------------------------
replace_once(
    'extension/src/service_worker.ts',
    '''let hwmRecommendationEpoch=0;\n\nasync function hwmDaemonJson''',
    '''let hwmRecommendationEpoch=0;\nconst HWM_TRACE_KEY="hwmLiveTrace";\nconst HWM_TRACE_MAX=80;\n\ntype HwmTraceEvent={at:number;stage:string;[key:string]:unknown};\nasync function hwmTrace(stage:string,details:Record<string,unknown>={}){\n  try{\n    const stored=await chrome.storage.local.get([HWM_TRACE_KEY]);\n    const trace:Array<HwmTraceEvent>=Array.isArray(stored[HWM_TRACE_KEY])?stored[HWM_TRACE_KEY].slice(-HWM_TRACE_MAX+1):[];\n    trace.push({at:Date.now(),stage,...details});\n    await chrome.storage.local.set({[HWM_TRACE_KEY]:trace});\n  }catch{}\n}\n\nasync function hwmDaemonJson''',
)
replace_once(
    'extension/src/service_worker.ts',
    '''async function hwmRequestRecommendation(epoch:number){\n  try{\n    const recommendation=await hwmDaemonJson("/recommend",{method:"POST"});\n    if(epoch!==hwmRecommendationEpoch)return;\n    await chrome.storage.local.set({hwmLastRecommendation:recommendation,hwmLastRecommendationAt:Date.now()});\n''',
    '''async function hwmRequestRecommendation(epoch:number){\n  await hwmTrace("plan_requested",{epoch});\n  try{\n    const recommendation=await hwmDaemonJson("/recommend",{method:"POST"});\n    if(epoch!==hwmRecommendationEpoch){await hwmTrace("plan_discarded_epoch",{epoch,currentEpoch:hwmRecommendationEpoch,status:recommendation?.status});return}\n    await hwmTrace("plan_result",{epoch,status:recommendation?.status,stateHash:recommendation?.state_hash??recommendation?.current_state_hash??"",revision:recommendation?.state_revision??recommendation?.current_revision??0,simulations:recommendation?.simulations??0,elapsedMs:recommendation?.elapsed_ms??0});\n    await chrome.storage.local.set({hwmLastRecommendation:recommendation,hwmLastRecommendationAt:Date.now()});\n''',
)
replace_once(
    'extension/src/service_worker.ts',
    '''  }catch(e){\n    if(epoch!==hwmRecommendationEpoch)return;\n    await chrome.storage.local.set({hwmLastRecommendation:{status:"offline",error:String(e)},hwmLastRecommendationAt:Date.now()});\n  }\n}\n''',
    '''  }catch(e){\n    if(epoch!==hwmRecommendationEpoch){await hwmTrace("plan_error_discarded_epoch",{epoch,currentEpoch:hwmRecommendationEpoch});return}\n    await hwmTrace("plan_error",{epoch,error:String(e).slice(0,240)});\n    await chrome.storage.local.set({hwmLastRecommendation:{status:"offline",error:String(e)},hwmLastRecommendationAt:Date.now()});\n  }\n}\n''',
)
replace_once(
    'extension/src/service_worker.ts',
    '''  if(msg?.type==="capture"){\n    hwmDaemonJson("/capture",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(msg.envelope)})\n      .then(r=>{sendResponse(r);if(r?.accepted)hwmScheduleRecommendation()})\n      .catch(e=>sendResponse({accepted:false,error:String(e)}));\n''',
    '''  if(msg?.type==="capture"){\n    const e=msg.envelope??{};\n    void hwmTrace("capture_forwarded",{battleId:String(e.battleId??"").slice(0,80),source:e.source??"",urlKind:e.urlKind??"",sequenceHint:e.sequenceHint??0,bodyBytes:typeof e.body==="string"?e.body.length:0});\n    hwmDaemonJson("/capture",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(e)})\n      .then(async r=>{await hwmTrace(r?.accepted?"capture_accepted":"capture_rejected",{battleId:String(e.battleId??"").slice(0,80),sequenceHint:e.sequenceHint??0,reason:r?.reason??r?.error??"",revision:r?.revision??0,stateHash:r?.state_hash??"",duplicate:!!r?.duplicate,outOfOrder:!!r?.out_of_order});sendResponse(r);if(r?.accepted)hwmScheduleRecommendation()})\n      .catch(async e=>{await hwmTrace("capture_error",{error:String(e).slice(0,240)});sendResponse({accepted:false,error:String(e)})});\n''',
)
replace_once(
    'extension/src/service_worker.ts',
    '''      .then(async r=>{await chrome.storage.local.set({hwmLastRuntimeProbe:r,hwmLastRuntimeProbeAt:Date.now()});sendResponse(r)})\n''',
    '''      .then(async r=>{await hwmTrace("runtime_probe_result",{accepted:!!r?.accepted,error:r?.error??""});await chrome.storage.local.set({hwmLastRuntimeProbe:r,hwmLastRuntimeProbeAt:Date.now()});sendResponse(r)})\n''',
)

# ---------------------------------------------------------------------------
# Side panel: one place to inspect the latest closed-loop path during a live fight.
# ---------------------------------------------------------------------------
replace_once(
    'extension/sidepanel.html',
    '''<details><summary>Session diagnostics</summary><pre id="status">-</pre></details>\n<script type="module" src="sidepanel.js"></script>\n''',
    '''<details open><summary>Live closed-loop trace</summary><div id="traceSummary" class="muted">No bridge events yet.</div><button id="clearTrace">Clear trace</button><pre id="liveTrace">-</pre></details>\n<details><summary>Session diagnostics</summary><pre id="status">-</pre></details>\n<script type="module" src="sidepanel.js"></script>\n''',
)
replace_once(
    'extension/src/sidepanel.ts',
    '''const HWM_D="http://127.0.0.1:38471",TOKEN_KEY="hwmPairingToken",hwm$=(id:string)=>document.getElementById(id)!;\n''',
    '''const HWM_D="http://127.0.0.1:38471",TOKEN_KEY="hwmPairingToken",TRACE_KEY="hwmLiveTrace",hwm$=(id:string)=>document.getElementById(id)!;\n''',
)
replace_once(
    'extension/src/sidepanel.ts',
    '''  try{const x=await chrome.storage.local.get(["hwmLastRecommendation","hwmLastRecommendationAt"]);if(x.hwmLastRecommendation){const guarded=await guardCurrentRecommendation(x.hwmLastRecommendation);renderRecommendation(guarded);hwm$("recommendationTime").textContent=x.hwmLastRecommendationAt?new Date(x.hwmLastRecommendationAt).toLocaleTimeString():""}}catch{}\n}\n''',
    '''  try{const x=await chrome.storage.local.get(["hwmLastRecommendation","hwmLastRecommendationAt",TRACE_KEY]);if(x.hwmLastRecommendation){const guarded=await guardCurrentRecommendation(x.hwmLastRecommendation);renderRecommendation(guarded);hwm$("recommendationTime").textContent=x.hwmLastRecommendationAt?new Date(x.hwmLastRecommendationAt).toLocaleTimeString():""}const trace=Array.isArray(x[TRACE_KEY])?x[TRACE_KEY]:[];hwm$("liveTrace").textContent=trace.length?JSON.stringify(trace.slice(-30),null,2):"-";const last=trace.at(-1);hwm$("traceSummary").textContent=last?`${new Date(last.at).toLocaleTimeString()} · ${last.stage}${last.revision?` · rev ${last.revision}`:""}${last.stateHash?` · ${String(last.stateHash).slice(0,12)}`:""}`:"No bridge events yet."}catch{}\n}\n''',
)
replace_once(
    'extension/src/sidepanel.ts',
    '''hwm$("pair").addEventListener("click",()=>void pair());hwm$("recommend").addEventListener("click",()=>void recommend());\n''',
    '''hwm$("pair").addEventListener("click",()=>void pair());hwm$("recommend").addEventListener("click",()=>void recommend());hwm$("clearTrace").addEventListener("click",()=>void chrome.storage.local.remove(TRACE_KEY).then(()=>refresh()));\n''',
)

# ---------------------------------------------------------------------------
# Daemon contract regression for a successful recommendation binding.
# ---------------------------------------------------------------------------
(ROOT / 'scripts/test_live_binding.py').write_text(
    '''from __future__ import annotations\n\nimport json,os,socket,subprocess,sys,tempfile,time,urllib.error,urllib.request\nfrom pathlib import Path\n\ndef free_port():\n    with socket.socket() as s:s.bind(("127.0.0.1",0));return int(s.getsockname()[1])\ndef req(base,path,method="GET",payload=None,token=None,timeout=8):\n    data=None if payload is None else json.dumps(payload).encode();headers={}\n    if data is not None:headers["Content-Type"]="application/json"\n    if token:headers["Authorization"]=f"Bearer {token}"\n    r=urllib.request.Request(base+path,data=data,method=method,headers=headers)\n    try:\n        with urllib.request.urlopen(r,timeout=timeout) as x:return x.status,json.loads(x.read().decode())\n    except urllib.error.HTTPError as e:return e.code,json.loads(e.read().decode())\ndef wait(base):\n    end=time.time()+8\n    while time.time()<end:\n        try:\n            if req(base,"/health",timeout=1)[0]==200:return\n        except Exception:pass\n        time.sleep(.05)\n    raise AssertionError("daemon not healthy")\ndef main():\n    exe=sys.argv[1] if len(sys.argv)>1 else "build/debug/solver-daemon"\n    with tempfile.TemporaryDirectory() as td:\n        port=free_port();base=f"http://127.0.0.1:{port}";env=os.environ.copy();env.update(HWM_TOKEN_FILE=str(Path(td)/"token"),HWM_PAIRING_CODE="123456",HWM_ENABLE_DEBUG="1",HWM_SEARCH_SIMS="64",HWM_SEARCH_MS="1000",HWM_SEARCH_DEPTH="4")\n        p=subprocess.Popen([exe,str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)\n        try:\n            wait(base);_,paired=req(base,"/pair","POST",{"code":"123456"});token=paired["token"]\n            assert req(base,"/debug/demo-state","POST",{},token)[0]==200\n            _,status=req(base,"/status",token=token);assert status["revision"]>=1 and status["state_hash"]\n            code,rec=req(base,"/recommend","POST",None,token);assert code==200,rec\n            assert rec.get("status")=="ok",rec\n            assert rec.get("state_hash")==status["state_hash"],(rec,status)\n            assert rec.get("state_revision")==status["revision"],(rec,status)\n            assert rec.get("battle_id")=="demo",rec\n            print("live recommendation binding contract: PASS",rec["state_revision"],rec["state_hash"])\n        finally:p.terminate();p.wait(timeout=5)\nif __name__=="__main__":main()\n''',
    encoding='utf-8',
)

# Honest spec status: instrumentation ready; an actual authenticated live battle
# still must be exercised by the user before M01/Phase 2 can be called COMPLETE.
for spec in ('SPEC.md','HeroesWM_Solver_TZ_Status_0.3.0.md'):
    p=ROOT/spec;text=p.read_text(encoding='utf-8')
    text=text.replace(
        'MV3 MAIN-world fetch/XHR passive capture, content/service-worker bridge, side panel, localhost forwarding и auto-replan реализованы. Не закрыто: проверка на реальном активном авторизованном бою и fallback через runtime objects.',
        'MV3 MAIN-world fetch/XHR passive capture, content/service-worker bridge, side panel, authenticated localhost forwarding, auto-replan и bounded metadata-only live closed-loop trace реализованы. Не закрыто: проверка на реальном активном авторизованном бою и полноценный fallback через runtime objects.',
        1,
    )
    text=text.replace(
        'Live validation расширения на **активном** бою и затем hard-PvE human-in-loop benchmark.',
        'Live validation расширения на **активном** бою (closed-loop trace уже подготовлен) и затем hard-PvE human-in-loop benchmark.',
        1,
    )
    p.write_text(text,encoding='utf-8')

WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True)
run('git','diff','--check')
run('cmake','--preset','debug');run('cmake','--build','build/debug','--parallel','2');run('ctest','--test-dir','build/debug','--output-on-failure')
run('python','scripts/test_local_api_auth.py','build/debug/solver-daemon');run('python','scripts/test_stale_cancellation.py','build/debug/solver-daemon');run('python','scripts/test_live_binding.py','build/debug/solver-daemon')
run('npm','install','--no-audit','--no-fund','--no-package-lock',cwd=ROOT/'extension');run('npm','run','typecheck',cwd=ROOT/'extension');run('npm','run','build',cwd=ROOT/'extension')

staging_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();run('git','config','user.name','github-actions[bot]');run('git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
run('git','add','-A');run('git','commit','-m','feat: add live closed-loop trace and state binding metadata');functional_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();run('git','push','origin','HEAD:main')
with (ROOT/'changelog.md').open('a',encoding='utf-8') as f:
    f.write(f'''\n\n### Live closed-loop trace and binding diagnostics\n\n- Commit: `{staging_sha}`\n  - Staged the self-removing live-validation instrumentation and binding contract regression.\n- Commit: `{functional_sha}`\n  - Capture responses now carry canonical `revision` and `state_hash`; successful recommendations carry `state_revision`, `state_hash` and `battle_id`.\n  - Extension stores a bounded 80-event metadata-only trace covering capture forwarding/result, planner requests/results, stale epoch discards and runtime-probe acknowledgements. Raw battle payloads, bearer tokens and full URLs are deliberately excluded.\n  - Side panel exposes the latest closed-loop trace and a clear action, allowing active-battle validation to localize failures across bridge -> daemon -> canonical state -> planner.\n  - Added `scripts/test_live_binding.py`, proving an OK recommendation is bound to the same daemon revision/hash as the observed demo state.\n  - M01 status remains MOSTLY COMPLETE: live trace tooling is ready, but a real authenticated active-battle exercise and full runtime-object fallback remain required.\n  - C++/CTest, pairing auth, stale cancellation, live binding, TypeScript typecheck and extension build passed before commit.\n''')
run('git','add','changelog.md');run('git','commit','-m','docs: log live closed-loop diagnostics');run('git','push','origin','HEAD:main')
