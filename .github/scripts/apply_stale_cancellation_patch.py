from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / '.github/workflows/apply_stale_cancellation_patch.yml'
SCRIPT = ROOT / '.github/scripts/apply_stale_cancellation_patch.py'


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
# Session revision: atomically bind a planner snapshot to the observed state.
# ---------------------------------------------------------------------------
replace_once(
    'cpp/include/hwm/session.hpp',
    '#include <mutex>\n',
    '#include <atomic>\n#include <mutex>\n',
)
replace_once(
    'cpp/include/hwm/session.hpp',
    '''struct CaptureOutcome {\n    bool accepted = false;\n    bool duplicate = false;\n    bool out_of_order = false;\n    bool session_reset = false;\n    bool canonical_state_updated = false;\n    std::string reason;\n};\n\nclass SessionStore {\n''',
    '''struct CaptureOutcome {\n    bool accepted = false;\n    bool duplicate = false;\n    bool out_of_order = false;\n    bool session_reset = false;\n    bool canonical_state_updated = false;\n    std::string reason;\n};\n\nstruct SessionSnapshot {\n    BattleState state;\n    uint64_t revision = 0;\n};\n\nclass SessionStore {\n''',
)
replace_once(
    'cpp/include/hwm/session.hpp',
    '''    std::optional<BattleState> state() const;\n    std::optional<RawEnvelope> last_envelope() const;\n''',
    '''    std::optional<BattleState> state() const;\n    std::optional<SessionSnapshot> snapshot() const;\n    uint64_t revision() const noexcept { return revision_.load(std::memory_order_acquire); }\n    std::optional<RawEnvelope> last_envelope() const;\n''',
)
replace_once(
    'cpp/include/hwm/session.hpp',
    '''    std::string last_runtime_probe_;\n};\n''',
    '''    std::string last_runtime_probe_;\n    std::atomic<uint64_t> revision_{0};\n};\n''',
)

replace_once(
    'cpp/src/session.cpp',
    '''        out.canonical_state_updated = true;\n\n        // If the browser delivered the turn stream before the static lastturn=-3 payload,\n''',
    '''        out.canonical_state_updated = true;\n\n        // Every accepted canonical publication receives a new monotonic revision.\n        // Duplicate/out-of-order payloads return before this point, so they do not\n        // spuriously cancel an in-flight search.\n        revision_.fetch_add(1, std::memory_order_release);\n\n        // If the browser delivered the turn stream before the static lastturn=-3 payload,\n''',
)
replace_once(
    'cpp/src/session.cpp',
    '''void SessionStore::set_state(BattleState s) {\n    std::scoped_lock lock(mu_);\n    battle_id_ = s.battle_id;\n    state_ = std::move(s);\n}\n''',
    '''void SessionStore::set_state(BattleState s) {\n    std::scoped_lock lock(mu_);\n    battle_id_ = s.battle_id;\n    state_ = std::move(s);\n    revision_.fetch_add(1, std::memory_order_release);\n}\n''',
)
replace_once(
    'cpp/src/session.cpp',
    '''std::optional<BattleState> SessionStore::state() const {\n    std::scoped_lock lock(mu_);\n    return state_;\n}\n\nstd::optional<RawEnvelope> SessionStore::last_envelope() const {\n''',
    '''std::optional<BattleState> SessionStore::state() const {\n    std::scoped_lock lock(mu_);\n    return state_;\n}\n\nstd::optional<SessionSnapshot> SessionStore::snapshot() const {\n    std::scoped_lock lock(mu_);\n    if (!state_) return std::nullopt;\n    return SessionSnapshot{*state_, revision_.load(std::memory_order_acquire)};\n}\n\nstd::optional<RawEnvelope> SessionStore::last_envelope() const {\n''',
)
replace_once(
    'cpp/src/session.cpp',
    '''      << ",\\\"runtime_probe_bytes\\\":" << runtime_probe_bytes_;\n''',
    '''      << ",\\\"runtime_probe_bytes\\\":" << runtime_probe_bytes_\n      << ",\\\"revision\\\":" << revision_.load(std::memory_order_acquire);\n''',
)

# ---------------------------------------------------------------------------
# Planner cooperative cancellation between simulations.
# ---------------------------------------------------------------------------
replace_once(
    'cpp/include/hwm/planner.hpp',
    '#include <chrono>\n',
    '#include <chrono>\n#include <functional>\n',
)
replace_once(
    'cpp/include/hwm/planner.hpp',
    '''struct PlannerConfig{uint64_t simulation_budget=5000; int max_depth=12; int self_top_k=12; double c_puct=1.4; uint32_t seed=1; uint64_t time_budget_ms=0; double risk_lambda=0.15;};\n''',
    '''struct PlannerConfig{uint64_t simulation_budget=5000; int max_depth=12; int self_top_k=12; double c_puct=1.4; uint32_t seed=1; uint64_t time_budget_ms=0; double risk_lambda=0.15; uint64_t cancellation_poll_interval=16; std::function<bool()> cancellation_requested;};\n''',
)
replace_once(
    'cpp/src/planner.cpp',
    '''Recommendation Planner::plan(const BattleState& root,Side perspective) const{\n    auto started=std::chrono::steady_clock::now();Recommendation rec;rec.state_hash=state_hash(root);\n''',
    '''Recommendation Planner::plan(const BattleState& root,Side perspective) const{\n    auto started=std::chrono::steady_clock::now();Recommendation rec;rec.state_hash=state_hash(root);\n    const auto cancelled=[&](){return cfg_.cancellation_requested && cfg_.cancellation_requested();};\n    if(cancelled()){rec.status="cancelled";rec.warnings.push_back("planning cancelled before search because observed session revision changed");return rec;}\n''',
)
replace_once(
    'cpp/src/planner.cpp',
    '''    uint64_t sims=0;for(;sims<cfg_.simulation_budget;++sims){if(cfg_.time_budget_ms&&sims>0&&std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-started).count()>=(long long)cfg_.time_budget_ms)break;simulate(tree,root,0,true);}\n    init_node(tree,root);\n''',
    '''    uint64_t sims=0;const uint64_t cancel_every=std::max<uint64_t>(1,cfg_.cancellation_poll_interval);\n    for(;sims<cfg_.simulation_budget;++sims){\n        if((sims%cancel_every)==0&&cancelled()){rec.status="cancelled";break;}\n        if(cfg_.time_budget_ms&&sims>0&&std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-started).count()>=(long long)cfg_.time_budget_ms)break;\n        simulate(tree,root,0,true);\n    }\n    if(rec.status=="cancelled"){rec.simulations=sims;rec.nodes=nodes;rec.elapsed_ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-started).count();rec.warnings.push_back("observed session revision changed during search");return rec;}\n    init_node(tree,root);\n''',
)

# ---------------------------------------------------------------------------
# HTTP planner endpoint: atomically snapshot state+revision and cancel when a
# newer observed revision is published, even if the resulting state hash matches.
# ---------------------------------------------------------------------------
replace_once(
    'cpp/src/http_server.cpp',
    '''    if (method == "POST" && (path == "/recommend" || path == "/session/current/plan")) {\n        auto s = store_.state();\n        if (!s) return response(200, "{\\\"status\\\":\\\"not_ready\\\",\\\"reason\\\":\\\"canonical state unavailable\\\"}");\n        if (!s->protocol_ready) return response(200, "{\\\"status\\\":\\\"not_ready\\\",\\\"reason\\\":\\\"waiting for contiguous turn stream / decoder confidence gate\\\"}");\n        if (s->phase == Phase::Finished) return response(200, "{\\\"status\\\":\\\"finished\\\",\\\"reason\\\":\\\"battle ended\\\"}");\n        if (s->side_to_act != Side::Player || s->active_entity_uid == 0) return response(200, "{\\\"status\\\":\\\"not_ready\\\",\\\"reason\\\":\\\"not a confirmed player decision state\\\"}");\n        const auto requested_hash = state_hash(*s);\n        PlannerConfig cfg;\n''',
    '''    if (method == "POST" && (path == "/recommend" || path == "/session/current/plan")) {\n        auto snapshot = store_.snapshot();\n        if (!snapshot) return response(200, "{\\\"status\\\":\\\"not_ready\\\",\\\"reason\\\":\\\"canonical state unavailable\\\"}");\n        const BattleState& s = snapshot->state;\n        const uint64_t requested_revision = snapshot->revision;\n        if (!s.protocol_ready) return response(200, "{\\\"status\\\":\\\"not_ready\\\",\\\"reason\\\":\\\"waiting for contiguous turn stream / decoder confidence gate\\\"}");\n        if (s.phase == Phase::Finished) return response(200, "{\\\"status\\\":\\\"finished\\\",\\\"reason\\\":\\\"battle ended\\\"}");\n        if (s.side_to_act != Side::Player || s.active_entity_uid == 0) return response(200, "{\\\"status\\\":\\\"not_ready\\\",\\\"reason\\\":\\\"not a confirmed player decision state\\\"}");\n        const auto requested_hash = state_hash(s);\n        PlannerConfig cfg;\n''',
)
replace_once(
    'cpp/src/http_server.cpp',
    '''        cfg.max_depth = static_cast<int>(env_u64("HWM_SEARCH_DEPTH", 12));\n        Planner planner(cfg);\n        auto r = planner.plan(*s);\n        auto latest = store_.state();\n        if (!latest || state_hash(*latest) != requested_hash) {\n            return response(200, "{\\\"status\\\":\\\"stale\\\",\\\"reason\\\":\\\"battle state changed while planning\\\"}");\n        }\n''',
    '''        cfg.max_depth = static_cast<int>(env_u64("HWM_SEARCH_DEPTH", 12));\n        cfg.cancellation_poll_interval = env_u64("HWM_SEARCH_CANCEL_POLL", 16);\n        cfg.cancellation_requested = [this, requested_revision] { return store_.revision() != requested_revision; };\n        Planner planner(cfg);\n        auto r = planner.plan(s);\n        const bool revision_changed = store_.revision() != requested_revision;\n        if (r.status == "cancelled" || revision_changed) {\n            auto latest = store_.snapshot();\n            const std::string current_hash = latest ? state_hash(latest->state) : std::string{};\n            std::ostringstream stale;\n            stale << "{\\\"status\\\":\\\"stale\\\",\\\"reason\\\":\\\"battle state changed while planning\\\""\n                  << ",\\\"requested_state_hash\\\":\\\"" << requested_hash << "\\\""\n                  << ",\\\"current_state_hash\\\":\\\"" << current_hash << "\\\""\n                  << ",\\\"requested_revision\\\":" << requested_revision\n                  << ",\\\"current_revision\\\":" << store_.revision()\n                  << ",\\\"cancelled_search\\\":" << (r.status == "cancelled" ? "true" : "false")\n                  << ",\\\"simulations\\\":" << r.simulations\n                  << ",\\\"elapsed_ms\\\":" << r.elapsed_ms << '}';\n            return response(200, stale.str());\n        }\n''',
)
# Remaining serialization uses s as a value/reference now, not optional.
replace_once('cpp/src/http_server.cpp', 'semantic_safety_tier(*s)', 'semantic_safety_tier(s)')
replace_once('cpp/src/http_server.cpp', 's->semantic_unresolved_ratio', 's.semantic_unresolved_ratio')

# ---------------------------------------------------------------------------
# Extension auto-replan epoch: a newer accepted capture invalidates any older
# in-flight recommendation before it can overwrite chrome.storage/UI.
# ---------------------------------------------------------------------------
replace_once(
    'extension/src/service_worker.ts',
    '''let hwmRecommendTimer:number|undefined;\n''',
    '''let hwmRecommendTimer:number|undefined;\nlet hwmRecommendationEpoch=0;\n''',
)
replace_once(
    'extension/src/service_worker.ts',
    '''async function hwmRequestRecommendation(){\n  try{\n    const recommendation=await hwmDaemonJson("/recommend",{method:"POST"});\n    await chrome.storage.local.set({hwmLastRecommendation:recommendation,hwmLastRecommendationAt:Date.now()});\n    chrome.runtime.sendMessage({type:"recommendation",recommendation}).catch(()=>{});\n  }catch(e){\n    await chrome.storage.local.set({hwmLastRecommendation:{status:"offline",error:String(e)},hwmLastRecommendationAt:Date.now()});\n  }\n}\n\nfunction hwmScheduleRecommendation(){\n  if(hwmRecommendTimer!==undefined)clearTimeout(hwmRecommendTimer);\n  hwmRecommendTimer=setTimeout(()=>{hwmRecommendTimer=undefined;void hwmRequestRecommendation()},250) as unknown as number;\n}\n''',
    '''async function hwmRequestRecommendation(epoch:number){\n  try{\n    const recommendation=await hwmDaemonJson("/recommend",{method:"POST"});\n    if(epoch!==hwmRecommendationEpoch)return;\n    await chrome.storage.local.set({hwmLastRecommendation:recommendation,hwmLastRecommendationAt:Date.now()});\n    chrome.runtime.sendMessage({type:"recommendation",recommendation}).catch(()=>{});\n  }catch(e){\n    if(epoch!==hwmRecommendationEpoch)return;\n    await chrome.storage.local.set({hwmLastRecommendation:{status:"offline",error:String(e)},hwmLastRecommendationAt:Date.now()});\n  }\n}\n\nfunction hwmScheduleRecommendation(){\n  const epoch=++hwmRecommendationEpoch;\n  if(hwmRecommendTimer!==undefined)clearTimeout(hwmRecommendTimer);\n  hwmRecommendTimer=setTimeout(()=>{hwmRecommendTimer=undefined;void hwmRequestRecommendation(epoch)},250) as unknown as number;\n}\n''',
)

# ---------------------------------------------------------------------------
# Side panel defense-in-depth: never render/store an OK recommendation whose
# state_hash no longer equals current daemon status.
# ---------------------------------------------------------------------------
replace_once(
    'extension/src/sidepanel.ts',
    '''async function pairedToken(){const x=await chrome.storage.local.get([TOKEN_KEY]);return x[TOKEN_KEY] as string|undefined}\n''',
    '''async function pairedToken(){const x=await chrome.storage.local.get([TOKEN_KEY]);return x[TOKEN_KEY] as string|undefined}\nasync function guardCurrentRecommendation(r:any){\n  if(!r||r.status!=="ok"||!r.state_hash)return r;\n  const status=await daemonJson("/status");\n  if(status?.state_hash&&status.state_hash!==r.state_hash)return {status:"stale",reason:"recommendation state hash no longer matches current daemon state",requested_state_hash:r.state_hash,current_state_hash:status.state_hash};\n  return r;\n}\n''',
)
replace_once(
    'extension/src/sidepanel.ts',
    '''async function recommend(){try{const result=await daemonJson("/recommend",{method:"POST"});await chrome.storage.local.set({hwmLastRecommendation:result,hwmLastRecommendationAt:Date.now()});renderRecommendation(result)}catch(e){renderRecommendation({status:"offline",error:String(e)})}}\n''',
    '''async function recommend(){try{const raw=await daemonJson("/recommend",{method:"POST"});const result=await guardCurrentRecommendation(raw);await chrome.storage.local.set({hwmLastRecommendation:result,hwmLastRecommendationAt:Date.now()});renderRecommendation(result)}catch(e){renderRecommendation({status:"offline",error:String(e)})}}\n''',
)
replace_once(
    'extension/src/sidepanel.ts',
    '''chrome.runtime.onMessage.addListener((msg:any)=>{if(msg?.type==="recommendation"){renderRecommendation(msg.recommendation);hwm$("recommendationTime").textContent=new Date().toLocaleTimeString()}});\n''',
    '''chrome.runtime.onMessage.addListener((msg:any)=>{if(msg?.type==="recommendation"){void guardCurrentRecommendation(msg.recommendation).then(r=>{renderRecommendation(r);hwm$("recommendationTime").textContent=new Date().toLocaleTimeString()})}});\n''',
)
# Stored recommendation check in periodic refresh.
replace_once(
    'extension/src/sidepanel.ts',
    '''if(x.hwmLastRecommendation){renderRecommendation(x.hwmLastRecommendation);hwm$("recommendationTime").textContent=x.hwmLastRecommendationAt?new Date(x.hwmLastRecommendationAt).toLocaleTimeString():""}}catch{}\n''',
    '''if(x.hwmLastRecommendation){const guarded=await guardCurrentRecommendation(x.hwmLastRecommendation);renderRecommendation(guarded);hwm$("recommendationTime").textContent=x.hwmLastRecommendationAt?new Date(x.hwmLastRecommendationAt).toLocaleTimeString():""}}catch{}\n''',
)

# ---------------------------------------------------------------------------
# End-to-end cancellation regression. It deliberately republishes the exact same
# demo state: state_hash stays equal, but revision changes and must cancel search.
# ---------------------------------------------------------------------------
(ROOT / 'scripts/test_stale_cancellation.py').write_text(
    '''from __future__ import annotations\n\nimport concurrent.futures\nimport json\nimport os\nimport socket\nimport subprocess\nimport sys\nimport tempfile\nimport time\nimport urllib.error\nimport urllib.request\nfrom pathlib import Path\n\n\ndef free_port():\n    with socket.socket() as s:s.bind(("127.0.0.1",0));return int(s.getsockname()[1])\n\ndef req(base,path,method="GET",payload=None,token=None,timeout=15):\n    data=None if payload is None else json.dumps(payload).encode();headers={}\n    if data is not None:headers["Content-Type"]="application/json"\n    if token:headers["Authorization"]=f"Bearer {token}"\n    r=urllib.request.Request(base+path,data=data,method=method,headers=headers)\n    try:\n        with urllib.request.urlopen(r,timeout=timeout) as x:return x.status,json.loads(x.read().decode())\n    except urllib.error.HTTPError as e:return e.code,json.loads(e.read().decode())\n\ndef wait_health(base):\n    end=time.time()+8\n    while time.time()<end:\n        try:\n            if req(base,"/health",timeout=1)[0]==200:return\n        except Exception:pass\n        time.sleep(.05)\n    raise AssertionError("daemon not healthy")\n\ndef main():\n    exe=sys.argv[1] if len(sys.argv)>1 else "build/debug/solver-daemon"\n    with tempfile.TemporaryDirectory() as td:\n        port=free_port();base=f"http://127.0.0.1:{port}";env=os.environ.copy()\n        env.update(HWM_TOKEN_FILE=str(Path(td)/"token"),HWM_PAIRING_CODE="123456",HWM_ENABLE_DEBUG="1",HWM_SEARCH_SIMS="100000000",HWM_SEARCH_MS="10000",HWM_SEARCH_DEPTH="20",HWM_SEARCH_CANCEL_POLL="1")\n        p=subprocess.Popen([exe,str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)\n        try:\n            wait_health(base)\n            _,paired=req(base,"/pair","POST",{"code":"123456"});token=paired["token"]\n            assert req(base,"/debug/demo-state","POST",{},token)[0]==200\n            _,before=req(base,"/status",token=token);assert before["revision"]>=1\n            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:\n                fut=pool.submit(req,base,"/recommend","POST",None,token,15)\n                time.sleep(.15)\n                assert req(base,"/debug/demo-state","POST",{},token)[0]==200\n                status,result=fut.result(timeout=8)\n            _,after=req(base,"/status",token=token)\n            assert status==200 and result.get("status")=="stale",result\n            assert result.get("cancelled_search") is True,result\n            assert result.get("requested_revision")<result.get("current_revision"),result\n            assert before["state_hash"]==after["state_hash"],"test must prove revision invalidation even with equal hash"\n            assert result.get("elapsed_ms",99999)<5000,result\n            print("stale search cooperative cancellation: PASS",result.get("simulations"),result.get("elapsed_ms"))\n        finally:\n            p.terminate();p.wait(timeout=5)\n\nif __name__=="__main__":main()\n''',
    encoding='utf-8',
)

# Specification: clarify that stale invalidation is now cooperative in-flight,
# not merely a post-search hash rejection.
for spec in ('SPEC.md','HeroesWM_Solver_TZ_Status_0.3.0.md'):
    p=ROOT/spec;text=p.read_text(encoding='utf-8')
    text=text.replace(
        'Thread-safe session, battle reset, duplicate/out-of-order handling, immutable observed state, state hash, stale-plan invalidation и incremental decode реализованы.',
        'Thread-safe session, battle reset, duplicate/out-of-order handling, immutable observed state, state hash, revision-bound cooperative stale-search cancellation и incremental decode реализованы.',
        1,
    )
    text=text.replace(
        'Local capture/session/API/auto-replan/stale invalidation реализованы и replay-tested.',
        'Local capture/session/API/auto-replan, cooperative stale-search cancellation и UI state-hash guard реализованы и regression-tested.',
        1,
    )
    p.write_text(text,encoding='utf-8')

WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True)
run('git','diff','--check')
run('cmake','--preset','debug')
run('cmake','--build','build/debug','--parallel','2')
run('ctest','--test-dir','build/debug','--output-on-failure')
run('python','scripts/test_local_api_auth.py','build/debug/solver-daemon')
run('python','scripts/test_stale_cancellation.py','build/debug/solver-daemon')
run('npm','install','--no-audit','--no-fund','--no-package-lock',cwd=ROOT/'extension')
run('npm','run','typecheck',cwd=ROOT/'extension')
run('npm','run','build',cwd=ROOT/'extension')

staging_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
run('git','config','user.name','github-actions[bot]');run('git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
run('git','add','-A');run('git','commit','-m','feat: cancel planning when observed state revision changes')
functional_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();run('git','push','origin','HEAD:main')
with (ROOT/'changelog.md').open('a',encoding='utf-8') as f:
    f.write(f'''\n\n### Revision-bound stale-search cancellation\n\n- Commit: `{staging_sha}`\n  - Staged the self-removing closed-loop cancellation patch and end-to-end regression.\n- Commit: `{functional_sha}`\n  - Added monotonic SessionStore revision and atomic state+revision snapshots.\n  - Planner now polls a cancellation callback between simulations and returns early when a newer observed revision arrives.\n  - `/recommend` binds planning to the snapshot revision and returns structured `stale` metadata instead of spending the full search budget on an obsolete state.\n  - Revision invalidation is intentionally stronger than hash-only invalidation: the regression republishes the same demo state (equal state hash) and still cancels the old search.\n  - Extension auto-replanning uses an epoch so older in-flight results cannot overwrite newer storage/UI; side panel additionally checks recommendation `state_hash` against current daemon status before rendering.\n  - Added `scripts/test_stale_cancellation.py`; C++/CTest, pairing auth, stale cancellation, TypeScript typecheck and extension build passed before commit.\n''')
run('git','add','changelog.md');run('git','commit','-m','docs: log stale-search cancellation');run('git','push','origin','HEAD:main')
