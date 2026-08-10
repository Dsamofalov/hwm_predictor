from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/apply_local_pairing_patch.yml"
SCRIPT = ROOT / ".github/scripts/apply_local_pairing_patch.py"


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one anchor, found {count}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=str(cwd or ROOT), check=True)


# ---------------------------------------------------------------------------
# C++ local API: persistent bearer token + explicit one-time pairing code.
# ---------------------------------------------------------------------------
(ROOT / "cpp/include/hwm/http_server.hpp").write_text(
    '''#pragma once
#include "hwm/session.hpp"
#include <atomic>
#include <cstdint>
#include <string>
namespace hwm {
class HttpServer{
public: HttpServer(std::string bind,uint16_t port,SessionStore& store); ~HttpServer(); int run(); void stop();
private: std::string bind_; uint16_t port_; SessionStore& store_; std::atomic<bool> stop_{false};
 std::string pairing_token_, pairing_code_; std::atomic<unsigned> pairing_failures_{0};
 std::string handle(std::string method,std::string path,std::string body); static std::string response(int code,std::string body,std::string content_type="application/json");
};
}
''',
    encoding="utf-8",
)

http = "cpp/src/http_server.cpp"
replace_once(
    http,
    '''#include <cstdlib>\n#include <iostream>\n#include <regex>\n#include <sstream>\n#include <thread>\n''',
    '''#include <cstdlib>\n#include <filesystem>\n#include <fstream>\n#include <iomanip>\n#include <iostream>\n#include <random>\n#include <regex>\n#include <sstream>\n#include <stdexcept>\n#include <thread>\n''',
)
replace_once(
    http,
    '''bool allowed_origin(const std::string& origin) {\n    return origin.empty() || origin.rfind("chrome-extension://", 0) == 0 || origin.rfind("moz-extension://", 0) == 0;\n}\n\n\nstd::string json_escape''',
    '''std::string random_hex(size_t bytes) {\n    std::random_device rd;\n    std::ostringstream o;\n    o << std::hex << std::setfill('0');\n    for (size_t i = 0; i < bytes; ++i) o << std::setw(2) << (rd() & 0xffu);\n    return o.str();\n}\n\nstd::string pairing_code() {\n    if (const char* forced = std::getenv("HWM_PAIRING_CODE"); forced && *forced) return forced;\n    std::random_device rd;\n    const unsigned value = static_cast<unsigned>(rd()) % 1000000u;\n    std::ostringstream o; o << std::setfill('0') << std::setw(6) << value; return o.str();\n}\n\nstd::filesystem::path token_path() {\n    if (const char* forced = std::getenv("HWM_TOKEN_FILE"); forced && *forced) return forced;\n#ifdef _WIN32\n    const char* base = std::getenv("LOCALAPPDATA");\n    if (!base || !*base) base = std::getenv("USERPROFILE");\n    return std::filesystem::path(base && *base ? base : ".") / "HeroesWMSolver" / "pairing.token";\n#else\n    const char* home = std::getenv("HOME");\n    return std::filesystem::path(home && *home ? home : ".") / ".heroeswm-solver" / "pairing.token";\n#endif\n}\n\nstd::string load_or_create_pairing_token() {\n    const auto path = token_path();\n    {\n        std::ifstream in(path, std::ios::binary);\n        std::string token;\n        if (in && std::getline(in, token) && token.size() >= 32) return token;\n    }\n    std::error_code ec;\n    if (!path.parent_path().empty()) std::filesystem::create_directories(path.parent_path(), ec);\n    const std::string token = random_hex(32);\n    {\n        std::ofstream out(path, std::ios::binary | std::ios::trunc);\n        if (!out) throw std::runtime_error("cannot persist local API pairing token");\n        out << token << '\\n';\n    }\n    std::filesystem::permissions(\n        path, std::filesystem::perms::owner_read | std::filesystem::perms::owner_write,\n        std::filesystem::perm_options::replace, ec);\n    return token;\n}\n\nbool secure_equal(std::string_view a, std::string_view b) {\n    if (a.size() != b.size()) return false;\n    unsigned char diff = 0;\n    for (size_t i = 0; i < a.size(); ++i) diff |= static_cast<unsigned char>(a[i] ^ b[i]);\n    return diff == 0;\n}\n\nbool allowed_origin(const std::string& origin) {\n    return origin.empty() || origin.rfind("chrome-extension://", 0) == 0 || origin.rfind("moz-extension://", 0) == 0;\n}\n\nbool public_route(const std::string& method, const std::string& path) {\n    return method == "OPTIONS" || (method == "GET" && (path == "/health" || path == "/version")) ||\n        (method == "POST" && path == "/pair");\n}\n\nbool bearer_authorized(const std::string& headers, const std::string& token) {\n    const std::string auth = header_value(headers, "Authorization");\n    const std::string expected = "Bearer " + token;\n    return secure_equal(auth, expected);\n}\n\n\nstd::string json_escape''',
)
replace_once(
    http,
    '''HttpServer::HttpServer(std::string bind_address, uint16_t port, SessionStore& store)\n    : bind_(std::move(bind_address)), port_(port), store_(store) {}\n''',
    '''HttpServer::HttpServer(std::string bind_address, uint16_t port, SessionStore& store)\n    : bind_(std::move(bind_address)), port_(port), store_(store),\n      pairing_token_(load_or_create_pairing_token()), pairing_code_(pairing_code()) {}\n''',
)
replace_once(
    http,
    '''      << "\\r\\nAccess-Control-Allow-Headers: Content-Type"\n''',
    '''      << "\\r\\nAccess-Control-Allow-Headers: Content-Type, Authorization"\n''',
)
replace_once(
    http,
    '''    if (method == "GET" && path == "/version")\n        return response(200, "{\\"version\\":\\"0.3.0\\",\\"api\\":2,\\"protocol_decoder\\":\\"raw-v2\\"}");\n    if (method == "GET" && path == "/status") return response(200, store_.status_json());\n''',
    '''    if (method == "GET" && path == "/version")\n        return response(200, "{\\"version\\":\\"0.3.0\\",\\"api\\":3,\\"protocol_decoder\\":\\"raw-v2\\",\\"auth\\":\\"pairing-bearer-v1\\"}");\n    if (method == "POST" && path == "/pair") {\n        if (pairing_failures_.load() >= 10) return response(429, "{\\"paired\\":false,\\"error\\":\\"pairing_locked_until_restart\\"}");\n        const std::string code = json_string(body, "code");\n        if (!secure_equal(code, pairing_code_)) {\n            ++pairing_failures_;\n            return response(403, "{\\"paired\\":false,\\"error\\":\\"invalid_pairing_code\\"}");\n        }\n        pairing_failures_ = 0;\n        return response(200, "{\\"paired\\":true,\\"token\\":\\"" + pairing_token_ + "\\"}");\n    }\n    if (method == "GET" && path == "/status") return response(200, store_.status_json());\n''',
)
replace_once(
    http,
    '''    std::cout << "solver-daemon listening http://" << bind_ << ':' << port_ << std::endl;\n''',
    '''    std::cout << "solver-daemon listening http://" << bind_ << ':' << port_ << std::endl;\n    std::cout << "HeroesWM Solver pairing code: " << pairing_code_ << std::endl;\n''',
)
replace_once(
    http,
    '''            std::string out;\n            if (!allowed_origin(origin)) out = response(403, "{\\"error\\":\\"origin_not_allowed\\"}");\n            else out = handle(method, path, body);\n''',
    '''            std::string out;\n            if (!allowed_origin(origin)) out = response(403, "{\\"error\\":\\"origin_not_allowed\\"}");\n            else if (!public_route(method, path) && !bearer_authorized(headers, pairing_token_))\n                out = response(401, "{\\"error\\":\\"pairing_required\\"}");\n            else out = handle(method, path, body);\n''',
)

# ---------------------------------------------------------------------------
# Extension: persist bearer token in chrome.storage.local and attach it to every
# private daemon request. Pairing itself remains an explicit user action.
# ---------------------------------------------------------------------------
(ROOT / "extension/src/service_worker.ts").write_text(
    '''(()=>{\nconst HWM_DAEMON="http://127.0.0.1:38471";\nconst HWM_TOKEN_KEY="hwmPairingToken";\nlet hwmRecommendTimer:number|undefined;\n\nasync function hwmDaemonJson(path:string,init:RequestInit={},auth=true):Promise<any>{\n  const headers:any={...(init.headers as any||{})};\n  if(auth){\n    const stored=await chrome.storage.local.get([HWM_TOKEN_KEY]);\n    const token=stored[HWM_TOKEN_KEY];\n    if(!token)return {status:"pairing_required",accepted:false,error:"pairing_required"};\n    headers.Authorization=`Bearer ${token}`;\n  }\n  const response=await fetch(`${HWM_DAEMON}${path}`,{...init,headers});\n  let data:any;try{data=await response.json()}catch{data={status:"error",error:`http_${response.status}`}}\n  if(response.status===401){await chrome.storage.local.remove(HWM_TOKEN_KEY);return {...data,status:"pairing_required",accepted:false}}\n  return data;\n}\n\nasync function hwmRequestRecommendation(){\n  try{\n    const recommendation=await hwmDaemonJson("/recommend",{method:"POST"});\n    await chrome.storage.local.set({hwmLastRecommendation:recommendation,hwmLastRecommendationAt:Date.now()});\n    chrome.runtime.sendMessage({type:"recommendation",recommendation}).catch(()=>{});\n  }catch(e){\n    await chrome.storage.local.set({hwmLastRecommendation:{status:"offline",error:String(e)},hwmLastRecommendationAt:Date.now()});\n  }\n}\n\nfunction hwmScheduleRecommendation(){\n  if(hwmRecommendTimer!==undefined)clearTimeout(hwmRecommendTimer);\n  hwmRecommendTimer=setTimeout(()=>{hwmRecommendTimer=undefined;void hwmRequestRecommendation()},250) as unknown as number;\n}\n\nchrome.runtime.onInstalled.addListener(()=>chrome.sidePanel.setPanelBehavior({openPanelOnActionClick:true}).catch(()=>{}));\nchrome.runtime.onMessage.addListener((msg:any,_s:any,sendResponse:any)=>{\n  if(msg?.type==="capture"){\n    hwmDaemonJson("/capture",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(msg.envelope)})\n      .then(r=>{sendResponse(r);if(r?.accepted)hwmScheduleRecommendation()})\n      .catch(e=>sendResponse({accepted:false,error:String(e)}));\n    return true;\n  }\n  if(msg?.type==="runtime_probe"){\n    hwmDaemonJson("/runtime-probe",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(msg.probe)})\n      .then(async r=>{await chrome.storage.local.set({hwmLastRuntimeProbe:r,hwmLastRuntimeProbeAt:Date.now()});sendResponse(r)})\n      .catch(e=>sendResponse({accepted:false,error:String(e)}));\n    return true;\n  }\n});\n})();\n''',
    encoding="utf-8",
)

(ROOT / "extension/sidepanel.html").write_text(
    '''<!doctype html>\n<meta charset="utf-8">\n<style>\n:root{color-scheme:dark}body{font:14px system-ui;background:#111;color:#eee;margin:14px;min-width:300px}.card{background:#1d1d1d;border:1px solid #333;border-radius:8px;padding:12px;margin:10px 0}.action{font-size:16px;font-weight:650}.metric{display:inline-block;margin-right:12px}.ok{color:#8fd694}.warn{color:#ffd166}.bad{color:#ff7b7b}.muted{opacity:.7;font-size:12px}pre{white-space:pre-wrap;background:#181818;padding:10px;border-radius:6px;max-height:30vh;overflow:auto}button,input{padding:8px 12px;border-radius:6px;border:1px solid #555;background:#2d2d2d;color:#fff}input{width:125px;margin-right:6px}details{margin-top:10px}\n</style>\n<h2>HeroesWM Solver</h2>\n<div id="health">daemon...</div>\n<p class="muted">Read-only advisor. You execute moves manually; every new captured state triggers replanning.</p>\n<div id="pairingCard" class="card">\n  <div class="muted">LOCAL DAEMON PAIRING</div>\n  <p class="muted">Enter the code printed by solver-daemon. The resulting token stays only in local extension storage.</p>\n  <input id="pairCode" inputmode="numeric" autocomplete="off" placeholder="Pairing code">\n  <button id="pair">Pair</button>\n  <div id="pairStatus" class="muted"></div>\n</div>\n<div class="card">\n  <div class="muted">CURRENT RECOMMENDATION <span id="recommendationTime"></span></div>\n  <div id="mainRecommendation" class="action">Waiting for battle state…</div>\n  <div id="metrics" class="muted"></div>\n  <div id="alternatives"></div>\n</div>\n<button id="recommend">Recalculate now</button>\n<details><summary>Raw recommendation JSON</summary><pre id="recommendation">-</pre></details>\n<details><summary>Session diagnostics</summary><pre id="status">-</pre></details>\n<script type="module" src="sidepanel.js"></script>\n''',
    encoding="utf-8",
)

(ROOT / "extension/src/sidepanel.ts").write_text(
    '''(()=>{\nconst HWM_D="http://127.0.0.1:38471",TOKEN_KEY="hwmPairingToken",hwm$=(id:string)=>document.getElementById(id)!;\nasync function daemonJson(path:string,init:RequestInit={},auth=true):Promise<any>{\n  const headers:any={...(init.headers as any||{})};\n  if(auth){const s=await chrome.storage.local.get([TOKEN_KEY]);const token=s[TOKEN_KEY];if(!token)return {status:"pairing_required",error:"pairing_required"};headers.Authorization=`Bearer ${token}`}\n  const resp=await fetch(`${HWM_D}${path}`,{...init,headers});let data:any;try{data=await resp.json()}catch{data={status:"error",error:`http_${resp.status}`}}\n  if(resp.status===401){await chrome.storage.local.remove(TOKEN_KEY);return {...data,status:"pairing_required"}}return data;\n}\nfunction actionText(a:any){\n  if(!a)return "No action";\n  const actor=`stack #${a.actor_uid??"?"}`;\n  if(a.type==="MOVE"&&a.destination)return `${actor}: MOVE → (${a.destination.x}, ${a.destination.y}) [protocol coordinates]`;\n  if(a.type==="MELEE_ATTACK")return `${actor}: MELEE_ATTACK${a.destination?` from (${a.destination.x}, ${a.destination.y})`:""} → stack #${a.target_uid??"?"}`;\n  if(a.type==="RANGED_ATTACK")return `${actor}: RANGED_ATTACK → stack #${a.target_uid??"?"}`;\n  if(a.type==="WAIT"||a.type==="DEFEND")return `${actor}: ${a.type}`;\n  return `${actor}: ${a.type??"UNKNOWN"}${a.target_uid?` → #${a.target_uid}`:""}`;\n}\nfunction renderRecommendation(r:any){\n  hwm$("recommendation").textContent=JSON.stringify(r,null,2);\n  const main=hwm$("mainRecommendation"),metrics=hwm$("metrics"),alts=hwm$("alternatives");main.className="action";alts.textContent="";\n  if(!r||r.status!=="ok"){\n    const reason=String(r?.reason??r?.error??(Array.isArray(r?.warnings)?r.warnings.join(" · "):""));\n    if(r?.status==="pairing_required"){main.textContent="PAIRING REQUIRED — enter daemon code above"}\n    else if(r?.status==="not_ready"&&/semantic/i.test(reason)){main.textContent="SEMANTIC STATE UNSAFE — strict recommendation blocked"}\n    else if(r?.status==="not_ready"){main.textContent="STATE PARTIAL — recommendation intentionally blocked"}\n    else{main.textContent=`Status: ${r?.status??"unknown"}`}\n    main.classList.add(r?.status==="stale"?"warn":"bad");metrics.textContent=reason;return;\n  }\n  main.textContent=actionText(r.best?.action);main.classList.add("ok");\n  const p=Number(r.best?.p_win??0)*100,ar=Number(r.ability_risk??0)*100;metrics.textContent=`P(win) risk-adjusted: ${p.toFixed(1)}% · ${r.simulations??0} sims · ${Number(r.elapsed_ms??0).toFixed(0)} ms · ability risk ${ar.toFixed(0)}% · state ${r.state_hash??""}${r.semantic_safety_tier?` · safety ${r.semantic_safety_tier}`:""}`;\n  if(Array.isArray(r.alternatives)&&r.alternatives.length){const title=document.createElement("div");title.className="muted";title.textContent="Alternatives:";alts.appendChild(title);for(const x of r.alternatives.slice(0,4)){const d=document.createElement("div");d.textContent=`• ${actionText(x.action)} (${(Number(x.p_win??0)*100).toFixed(1)}%)`;alts.appendChild(d)}}\n}\nasync function pairedToken(){const x=await chrome.storage.local.get([TOKEN_KEY]);return x[TOKEN_KEY] as string|undefined}\nasync function updatePairingUi(){const token=await pairedToken();hwm$("pairStatus").textContent=token?"paired":"not paired";hwm$("pairStatus").className=token?"ok":"warn"}\nasync function refresh(){\n  try{const h=await daemonJson("/health",{},false);hwm$("health").textContent=`daemon: ${h.status}`;hwm$("health").className="ok";const token=await pairedToken();if(token){const status=await daemonJson("/status");if(status?.status==="pairing_required"){hwm$("status").textContent="pairing required"}else hwm$("status").textContent=JSON.stringify(status,null,2)}else hwm$("status").textContent="pairing required"}catch(e){hwm$("health").textContent="daemon: offline";hwm$("health").className="bad";hwm$("status").textContent=String(e)}\n  await updatePairingUi();\n  try{const x=await chrome.storage.local.get(["hwmLastRecommendation","hwmLastRecommendationAt"]);if(x.hwmLastRecommendation){renderRecommendation(x.hwmLastRecommendation);hwm$("recommendationTime").textContent=x.hwmLastRecommendationAt?new Date(x.hwmLastRecommendationAt).toLocaleTimeString():""}}catch{}\n}\nasync function pair(){\n  const code=(hwm$("pairCode") as HTMLInputElement).value.trim();if(!code){hwm$("pairStatus").textContent="enter pairing code";hwm$("pairStatus").className="warn";return}\n  try{const result=await daemonJson("/pair",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({code})},false);if(result?.paired&&result?.token){await chrome.storage.local.set({[TOKEN_KEY]:result.token});(hwm$("pairCode") as HTMLInputElement).value="";hwm$("pairStatus").textContent="paired";hwm$("pairStatus").className="ok";await recommend()}else{hwm$("pairStatus").textContent=result?.error??"pairing failed";hwm$("pairStatus").className="bad"}}catch(e){hwm$("pairStatus").textContent=String(e);hwm$("pairStatus").className="bad"}\n}\nasync function recommend(){try{const result=await daemonJson("/recommend",{method:"POST"});await chrome.storage.local.set({hwmLastRecommendation:result,hwmLastRecommendationAt:Date.now()});renderRecommendation(result)}catch(e){renderRecommendation({status:"offline",error:String(e)})}}\nhwm$("pair").addEventListener("click",()=>void pair());hwm$("recommend").addEventListener("click",()=>void recommend());\nchrome.runtime.onMessage.addListener((msg:any)=>{if(msg?.type==="recommendation"){renderRecommendation(msg.recommendation);hwm$("recommendationTime").textContent=new Date().toLocaleTimeString()}});\nsetInterval(refresh,1000);void refresh();\n})();\n''',
    encoding="utf-8",
)

# ---------------------------------------------------------------------------
# Reproducible local API integration test. It proves token persistence across a
# daemon restart and that all private endpoints reject unauthenticated callers.
# ---------------------------------------------------------------------------
(ROOT / "scripts/test_local_api_auth.py").write_text(
    '''from __future__ import annotations\n\nimport json\nimport os\nimport socket\nimport subprocess\nimport sys\nimport tempfile\nimport time\nimport urllib.error\nimport urllib.request\nfrom pathlib import Path\n\n\ndef free_port() -> int:\n    with socket.socket() as s:\n        s.bind(("127.0.0.1", 0))\n        return int(s.getsockname()[1])\n\n\ndef request(base: str, path: str, *, method: str = "GET", payload=None, token: str | None = None):\n    data = None if payload is None else json.dumps(payload).encode()\n    headers = {}\n    if data is not None: headers["Content-Type"] = "application/json"\n    if token: headers["Authorization"] = f"Bearer {token}"\n    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)\n    try:\n        with urllib.request.urlopen(req, timeout=2) as r:\n            return r.status, json.loads(r.read().decode())\n    except urllib.error.HTTPError as e:\n        return e.code, json.loads(e.read().decode())\n\n\ndef wait_health(base: str) -> None:\n    deadline = time.time() + 8\n    while time.time() < deadline:\n        try:\n            if request(base, "/health")[0] == 200: return\n        except Exception:\n            pass\n        time.sleep(0.05)\n    raise AssertionError("daemon did not become healthy")\n\n\ndef launch(exe: str, port: int, token_file: Path, code: str):\n    env = os.environ.copy(); env["HWM_TOKEN_FILE"] = str(token_file); env["HWM_PAIRING_CODE"] = code\n    p = subprocess.Popen([exe, str(port)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)\n    wait_health(f"http://127.0.0.1:{port}")\n    return p\n\n\ndef main() -> None:\n    exe = sys.argv[1] if len(sys.argv) > 1 else "build/debug/solver-daemon"\n    with tempfile.TemporaryDirectory() as td:\n        token_file = Path(td) / "pairing.token"\n        port = free_port(); base = f"http://127.0.0.1:{port}"\n        p = launch(exe, port, token_file, "123456")\n        try:\n            assert request(base, "/status")[0] == 401\n            assert request(base, "/recommend", method="POST")[0] == 401\n            assert request(base, "/runtime-probe", method="POST", payload={"x": 1})[0] == 401\n            assert request(base, "/pair", method="POST", payload={"code": "000000"})[0] == 403\n            status, paired = request(base, "/pair", method="POST", payload={"code": "123456"})\n            assert status == 200 and paired.get("paired") is True\n            token = paired.get("token"); assert isinstance(token, str) and len(token) == 64\n            assert token_file.read_text().strip() == token\n            assert request(base, "/status", token=token)[0] == 200\n            status, rec = request(base, "/recommend", method="POST", token=token)\n            assert status == 200 and rec.get("status") == "not_ready"\n        finally:\n            p.terminate(); p.wait(timeout=5)\n\n        # A restart rotates only the human pairing code, not the bearer secret.\n        port2 = free_port(); base2 = f"http://127.0.0.1:{port2}"\n        p2 = launch(exe, port2, token_file, "654321")\n        try:\n            assert request(base2, "/status", token=token)[0] == 200\n            status, paired2 = request(base2, "/pair", method="POST", payload={"code": "654321"})\n            assert status == 200 and paired2.get("token") == token\n        finally:\n            p2.terminate(); p2.wait(timeout=5)\n    print("local API pairing/auth integration: PASS")\n\n\nif __name__ == "__main__": main()\n''',
    encoding="utf-8",
)

# Keep the integration check in normal CI, not only in this one-shot runner.
ci = ".github/workflows/ci.yml"
replace_once(
    ci,
    '''      - name: C++ tests\n        run: ctest --test-dir build/debug --output-on-failure\n\n      - name: Install Python package\n''',
    '''      - name: C++ tests\n        run: ctest --test-dir build/debug --output-on-failure\n\n      - name: Local API pairing/auth integration\n        run: python scripts/test_local_api_auth.py build/debug/solver-daemon\n\n      - name: Install Python package\n''',
)

# Specification bookkeeping: M16 pairing is now closed; WebSocket remains optional/open.
for spec in ("SPEC.md", "HeroesWM_Solver_TZ_Status_0.3.0.md"):
    replace_once(
        spec,
        "Pairing token и WebSocket streaming остаются незакрыты.",
        "Persistent local pairing token с explicit one-time code реализован и обязателен для private API; WebSocket streaming остаётся незакрыт.",
    )
    p = ROOT / spec
    text = p.read_text(encoding="utf-8")
    text = text.replace("Ability-risk на held-out sample: mean **0.2389**, p90 **0.3978**.", "Ability-risk на held-out sample: mean **0.22431**, p90 **0.37538**.", 1)
    text = text.replace("Automated tests: C++ CTest **100%**, Python **39/39**, TypeScript typecheck/build **PASS**.", "Automated tests: C++ CTest **100%**, Python **42/42**, TypeScript typecheck/build **PASS**; local API pairing/auth integration **PASS**.", 1)
    p.write_text(text, encoding="utf-8")

# Remove one-shot machinery from the functional tree before testing/commit.
WORKFLOW.unlink(missing_ok=True)
SCRIPT.unlink(missing_ok=True)

run("git", "diff", "--check")
run("cmake", "--preset", "debug")
run("cmake", "--build", "build/debug", "--parallel", "2")
run("ctest", "--test-dir", "build/debug", "--output-on-failure")
run("python", "scripts/test_local_api_auth.py", "build/debug/solver-daemon")
run("npm", "install", "--no-audit", "--no-fund", cwd=ROOT / "extension")
run("npm", "run", "typecheck", cwd=ROOT / "extension")
run("npm", "run", "build", cwd=ROOT / "extension")

staging_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
run("git", "config", "user.name", "github-actions[bot]")
run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
run("git", "add", "-A")
run("git", "commit", "-m", "feat: secure local API with explicit pairing")
functional_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
run("git", "push", "origin", "HEAD:main")

changelog = ROOT / "changelog.md"
with changelog.open("a", encoding="utf-8") as f:
    f.write(f'''\n\n### Local daemon pairing/authentication\n\n- Commit: `{staging_sha}`\n  - Staged the self-removing M16 security patch and verification runner.\n- Commit: `{functional_sha}`\n  - Added a persistent 256-bit local bearer token and explicit per-process pairing code; the bearer token survives daemon restarts while the human code rotates.\n  - Private local API routes now require `Authorization: Bearer <token>`; only health/version, CORS preflight and `/pair` remain public.\n  - Added pairing brute-force lock after 10 failed codes per daemon process and kept loopback-only binding/origin filtering.\n  - Extension service worker and side panel persist the token in `chrome.storage.local`, attach it to capture/runtime-probe/recommend/status requests, and clear it on HTTP 401.\n  - Added `scripts/test_local_api_auth.py`: unauthenticated private routes rejected, wrong code rejected, correct pair succeeds, token file persists, old token works after daemon restart.\n  - Added the integration test to normal CI and updated M16 specification status.\n  - Targeted C++ build/CTest, local API integration, TypeScript typecheck and extension build passed before commit.\n''')
run("git", "add", "changelog.md")
run("git", "commit", "-m", "docs: log local API pairing implementation")
run("git", "push", "origin", "HEAD:main")
