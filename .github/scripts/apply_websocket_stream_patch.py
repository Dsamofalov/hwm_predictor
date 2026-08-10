from __future__ import annotations

import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
WORKFLOW=ROOT/'.github/workflows/apply_websocket_stream_patch.yml'
SCRIPT=ROOT/'.github/scripts/apply_websocket_stream_patch.py'

def replace_once(path:str,old:str,new:str)->None:
    p=ROOT/path;text=p.read_text(encoding='utf-8');n=text.count(old)
    if n!=1:raise SystemExit(f'{path}: expected one anchor, found {n}: {old[:120]!r}')
    p.write_text(text.replace(old,new,1),encoding='utf-8')

def run(*args:str,cwd:Path|None=None)->None:subprocess.run(args,cwd=str(cwd or ROOT),check=True)

# ---------------------------------------------------------------------------
# HTTP server: RFC6455 handshake + server-to-client text frames. Authentication
# uses Sec-WebSocket-Protocol rather than a URL query parameter.
# ---------------------------------------------------------------------------
replace_once('cpp/src/http_server.cpp',
'''#include <cstdlib>\n#include <filesystem>\n''',
'''#include <array>\n#include <chrono>\n#include <cstdlib>\n#include <filesystem>\n''')
replace_once('cpp/src/http_server.cpp',
'''#include <thread>\n''',
'''#include <thread>\n#include <vector>\n''')

ws_helpers=r'''bool websocket_protocol_authorized(const std::string& headers,const std::string& token){
    const std::string offered=header_value(headers,"Sec-WebSocket-Protocol");
    const std::string expected="hwm-bearer."+token;
    bool version=false,authorized=false;
    size_t pos=0;
    while(pos<=offered.size()){
        const size_t comma=offered.find(',',pos);const size_t end=comma==std::string::npos?offered.size():comma;
        size_t a=pos,b=end;while(a<b&&(offered[a]==' '||offered[a]=='\t'))++a;while(b>a&&(offered[b-1]==' '||offered[b-1]=='\t'))--b;
        const std::string_view item(offered.data()+a,b-a);
        if(item=="hwm-v1")version=true;
        if(secure_equal(item,expected))authorized=true;
        if(comma==std::string::npos)break;pos=comma+1;
    }
    return version&&authorized;
}

uint32_t rol32(uint32_t v,unsigned n){return (v<<n)|(v>>(32-n));}
std::array<unsigned char,20> sha1(std::string_view input){
    std::vector<unsigned char> msg(input.begin(),input.end());const uint64_t bits=uint64_t(msg.size())*8u;
    msg.push_back(0x80);while((msg.size()%64)!=56)msg.push_back(0);
    for(int i=7;i>=0;--i)msg.push_back(static_cast<unsigned char>((bits>>(i*8))&0xffu));
    uint32_t h0=0x67452301u,h1=0xefcdab89u,h2=0x98badcfeu,h3=0x10325476u,h4=0xc3d2e1f0u;
    for(size_t chunk=0;chunk<msg.size();chunk+=64){
        uint32_t w[80]{};for(int i=0;i<16;++i){const size_t j=chunk+size_t(i)*4;w[i]=(uint32_t(msg[j])<<24)|(uint32_t(msg[j+1])<<16)|(uint32_t(msg[j+2])<<8)|uint32_t(msg[j+3]);}
        for(int i=16;i<80;++i)w[i]=rol32(w[i-3]^w[i-8]^w[i-14]^w[i-16],1);
        uint32_t a=h0,b=h1,c=h2,d=h3,e=h4;
        for(int i=0;i<80;++i){uint32_t f=0,k=0;if(i<20){f=(b&c)|((~b)&d);k=0x5a827999u;}else if(i<40){f=b^c^d;k=0x6ed9eba1u;}else if(i<60){f=(b&c)|(b&d)|(c&d);k=0x8f1bbcdcu;}else{f=b^c^d;k=0xca62c1d6u;}const uint32_t temp=rol32(a,5)+f+e+k+w[i];e=d;d=c;c=rol32(b,30);b=a;a=temp;}
        h0+=a;h1+=b;h2+=c;h3+=d;h4+=e;
    }
    std::array<unsigned char,20> out{};const uint32_t h[5]={h0,h1,h2,h3,h4};for(int i=0;i<5;++i)for(int j=0;j<4;++j)out[size_t(i)*4+j]=static_cast<unsigned char>((h[i]>>(24-j*8))&0xffu);return out;
}

std::string base64_bytes(const unsigned char* data,size_t n){
    static constexpr char tab[]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";std::string out;out.reserve(((n+2)/3)*4);
    for(size_t i=0;i<n;i+=3){const uint32_t a=data[i],b=i+1<n?data[i+1]:0,c=i+2<n?data[i+2]:0,v=(a<<16)|(b<<8)|c;out.push_back(tab[(v>>18)&63]);out.push_back(tab[(v>>12)&63]);out.push_back(i+1<n?tab[(v>>6)&63]:'=');out.push_back(i+2<n?tab[v&63]:'=');}return out;
}

std::string websocket_accept(std::string_view key){const std::string material=std::string(key)+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11";const auto digest=sha1(material);return base64_bytes(digest.data(),digest.size());}

bool send_all(sock_t s,std::string_view data){size_t off=0;while(off<data.size()){
#ifdef _WIN32
    const int n=send(s,data.data()+off,static_cast<int>(data.size()-off),0);
#else
    const ssize_t n=send(s,data.data()+off,data.size()-off,MSG_NOSIGNAL);
#endif
    if(n<=0)return false;off+=static_cast<size_t>(n);}return true;}

std::string websocket_frame(std::string_view payload){std::string out;out.reserve(payload.size()+10);out.push_back(static_cast<char>(0x81));const uint64_t n=payload.size();if(n<=125){out.push_back(static_cast<char>(n));}else if(n<=65535){out.push_back(static_cast<char>(126));out.push_back(static_cast<char>((n>>8)&0xff));out.push_back(static_cast<char>(n&0xff));}else{out.push_back(static_cast<char>(127));for(int i=7;i>=0;--i)out.push_back(static_cast<char>((n>>(i*8))&0xff));}out.append(payload);return out;}

bool websocket_send_json(sock_t s,std::string_view payload){const std::string frame=websocket_frame(payload);return send_all(s,frame);}

void websocket_stream(sock_t client,SessionStore& store,std::atomic<bool>& stop){
    uint64_t last_revision=~uint64_t{0};auto last_send=std::chrono::steady_clock::now()-std::chrono::seconds(30);
    while(!stop.load(std::memory_order_acquire)){
        const uint64_t revision=store.revision();const auto now=std::chrono::steady_clock::now();
        if(revision!=last_revision){const std::string payload="{\"type\":\"state\",\"status\":"+store.status_json()+"}";if(!websocket_send_json(client,payload))return;last_revision=revision;last_send=now;}
        else if(now-last_send>=std::chrono::seconds(20)){std::ostringstream o;o<<"{\"type\":\"heartbeat\",\"revision\":"<<revision<<'}';if(!websocket_send_json(client,o.str()))return;last_send=now;}
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}

'''
replace_once('cpp/src/http_server.cpp',
'''bool bearer_authorized(const std::string& headers, const std::string& token) {\n    const std::string auth = header_value(headers, "Authorization");\n    const std::string expected = "Bearer " + token;\n    return secure_equal(auth, expected);\n}\n\n\nstd::string json_escape''',
'''bool bearer_authorized(const std::string& headers, const std::string& token) {\n    const std::string auth = header_value(headers, "Authorization");\n    const std::string expected = "Bearer " + token;\n    return secure_equal(auth, expected);\n}\n\n'''+ws_helpers+'''std::string json_escape''')

# Expose enough canonical scheduling context in pushed status.
replace_once('cpp/src/session.cpp',
'''        o << ",\\\"state_seq\\\":" << state_->state_seq\n          << ",\\\"state_hash\\\":\\\"" << state_hash(*state_) << "\\\""\n          << ",\\\"phase\\\":" << static_cast<int>(state_->phase)\n''',
'''        o << ",\\\"state_seq\\\":" << state_->state_seq\n          << ",\\\"state_hash\\\":\\\"" << state_hash(*state_) << "\\\""\n          << ",\\\"phase\\\":" << static_cast<int>(state_->phase)\n          << ",\\\"side_to_act\\\":" << static_cast<int>(state_->side_to_act)\n          << ",\\\"active_entity_uid\\\":" << state_->active_entity_uid\n''')

# Upgrade branch must happen before HTTP bearer auth because browsers cannot set
# Authorization on WebSocket constructor; the bearer travels as a subprotocol.
replace_once('cpp/src/http_server.cpp',
'''            std::string out;\n            if (!allowed_origin(origin)) out = response(403, "{\\\"error\\\":\\\"origin_not_allowed\\\"}");\n            else if (!public_route(method, path) && !bearer_authorized(headers, pairing_token_))\n                out = response(401, "{\\\"error\\\":\\\"pairing_required\\\"}");\n            else out = handle(method, path, body);\n            send(client, out.data(), static_cast<int>(out.size()), 0);\n            close_sock(client);\n''',
'''            const std::string upgrade=header_value(headers,"Upgrade");\n            const bool ws_upgrade=method=="GET"&&path=="/ws"&&(upgrade=="websocket"||upgrade=="WebSocket");\n            if(ws_upgrade){\n                if(!allowed_origin(origin)){const auto out=response(403,"{\\\"error\\\":\\\"origin_not_allowed\\\"}");send_all(client,out);close_sock(client);return;}\n                if(!websocket_protocol_authorized(headers,pairing_token_)){const auto out=response(401,"{\\\"error\\\":\\\"pairing_required\\\"}");send_all(client,out);close_sock(client);return;}\n                const std::string key=header_value(headers,"Sec-WebSocket-Key"),version_ws=header_value(headers,"Sec-WebSocket-Version");\n                if(key.empty()||version_ws!="13"){const auto out=response(400,"{\\\"error\\\":\\\"invalid_websocket_handshake\\\"}");send_all(client,out);close_sock(client);return;}\n                std::ostringstream hs;hs<<"HTTP/1.1 101 Switching Protocols\\r\\nUpgrade: websocket\\r\\nConnection: Upgrade\\r\\nSec-WebSocket-Accept: "<<websocket_accept(key)<<"\\r\\nSec-WebSocket-Protocol: hwm-v1\\r\\n\\r\\n";\n                if(send_all(client,hs.str()))websocket_stream(client,store_,stop_);close_sock(client);return;\n            }\n            std::string out;\n            if (!allowed_origin(origin)) out = response(403, "{\\\"error\\\":\\\"origin_not_allowed\\\"}");\n            else if (!public_route(method, path) && !bearer_authorized(headers, pairing_token_))\n                out = response(401, "{\\\"error\\\":\\\"pairing_required\\\"}");\n            else out = handle(method, path, body);\n            send_all(client,out);\n            close_sock(client);\n''')

# ---------------------------------------------------------------------------
# MV3 service worker: authenticated WebSocket, bounded reconnect, revision-level
# recommendation dedupe. HTTP remains the capture/request path and fallback.
# ---------------------------------------------------------------------------
replace_once('extension/src/service_worker.ts',
'''const HWM_TRACE_MAX=80;\n''',
'''const HWM_TRACE_MAX=80;\nconst HWM_WS="ws://127.0.0.1:38471/ws";\nlet hwmWs:WebSocket|undefined;\nlet hwmWsReconnectTimer:number|undefined;\nlet hwmLastScheduledRevision=0;\n''')
replace_once('extension/src/service_worker.ts',
'''function hwmScheduleRecommendation(){\n  const epoch=++hwmRecommendationEpoch;\n  if(hwmRecommendTimer!==undefined)clearTimeout(hwmRecommendTimer);\n  hwmRecommendTimer=setTimeout(()=>{hwmRecommendTimer=undefined;void hwmRequestRecommendation(epoch)},250) as unknown as number;\n}\n\nchrome.runtime.onInstalled''',
'''function hwmScheduleRecommendation(revision=0){\n  if(revision>0&&revision===hwmLastScheduledRevision)return;\n  if(revision>0)hwmLastScheduledRevision=revision;\n  const epoch=++hwmRecommendationEpoch;\n  if(hwmRecommendTimer!==undefined)clearTimeout(hwmRecommendTimer);\n  hwmRecommendTimer=setTimeout(()=>{hwmRecommendTimer=undefined;void hwmRequestRecommendation(epoch)},250) as unknown as number;\n}\n\nasync function hwmConnectWebSocket(){\n  if(hwmWs&&(hwmWs.readyState===WebSocket.OPEN||hwmWs.readyState===WebSocket.CONNECTING))return;\n  const stored=await chrome.storage.local.get([HWM_TOKEN_KEY]);const token=stored[HWM_TOKEN_KEY];if(!token)return;\n  try{\n    const ws=new WebSocket(HWM_WS,["hwm-v1",`hwm-bearer.${token}`]);hwmWs=ws;\n    ws.onopen=()=>{void hwmTrace("ws_connected")};\n    ws.onmessage=(event)=>{void (async()=>{try{const msg=JSON.parse(String(event.data));if(msg?.type==="state"&&msg.status){const status=msg.status;await chrome.storage.local.set({hwmLastDaemonStatus:status,hwmLastDaemonStatusAt:Date.now()});await hwmTrace("ws_state",{revision:status.revision??0,stateHash:status.state_hash??"",protocolReady:!!status.protocol_ready,recommendationSafe:!!status.recommendation_safe,sideToAct:status.side_to_act??0});if(status.protocol_ready&&status.recommendation_safe&&status.side_to_act===1&&status.active_entity_uid)hwmScheduleRecommendation(Number(status.revision??0));}else if(msg?.type==="heartbeat"){await chrome.storage.local.set({hwmLastDaemonStreamAt:Date.now()})}}catch(e){await hwmTrace("ws_message_error",{error:String(e).slice(0,160)})}})()};\n    ws.onerror=()=>{void hwmTrace("ws_error")};\n    ws.onclose=()=>{if(hwmWs===ws)hwmWs=undefined;void hwmTrace("ws_closed");if(hwmWsReconnectTimer!==undefined)clearTimeout(hwmWsReconnectTimer);hwmWsReconnectTimer=setTimeout(()=>{hwmWsReconnectTimer=undefined;void hwmConnectWebSocket()},1500) as unknown as number};\n  }catch(e){await hwmTrace("ws_connect_error",{error:String(e).slice(0,160)})}\n}\n\nchrome.storage.onChanged.addListener((changes,area)=>{if(area==="local"&&changes[HWM_TOKEN_KEY]){if(hwmWs){hwmWs.close();hwmWs=undefined}void hwmConnectWebSocket()}});\nvoid hwmConnectWebSocket();\n\nchrome.runtime.onInstalled''')
replace_once('extension/src/service_worker.ts',
'''reason:r?.reason??r?.error??"",revision:r?.revision??0,stateHash:r?.state_hash??"",duplicate:!!r?.duplicate,outOfOrder:!!r?.out_of_order});sendResponse(r);if(r?.accepted)hwmScheduleRecommendation()})\n''',
'''reason:r?.reason??r?.error??"",revision:r?.revision??0,stateHash:r?.state_hash??"",duplicate:!!r?.duplicate,outOfOrder:!!r?.out_of_order});sendResponse(r);if(r?.accepted&&r?.canonical_state_updated)hwmScheduleRecommendation(Number(r?.revision??0))})\n''')

# Side panel consumes the streamed status and falls back to HTTP only if stream
# status is missing/stale. This removes the hard dependency on 1 Hz /status polling.
replace_once('extension/src/sidepanel.ts',
'''async function guardCurrentRecommendation(r:any){\n  if(!r||r.status!=="ok"||!r.state_hash)return r;\n  const status=await daemonJson("/status");\n''',
'''async function currentDaemonStatus(){const x=await chrome.storage.local.get(["hwmLastDaemonStatus","hwmLastDaemonStatusAt"]);if(x.hwmLastDaemonStatus&&Date.now()-Number(x.hwmLastDaemonStatusAt??0)<5000)return x.hwmLastDaemonStatus;return daemonJson("/status")}\nasync function guardCurrentRecommendation(r:any){\n  if(!r||r.status!=="ok"||!r.state_hash)return r;\n  const status=await currentDaemonStatus();\n''')
replace_once('extension/src/sidepanel.ts',
'''  try{const h=await daemonJson("/health",{},false);hwm$("health").textContent=`daemon: ${h.status}`;hwm$("health").className="ok";const token=await pairedToken();if(token){const status=await daemonJson("/status");if(status?.status==="pairing_required"){hwm$("status").textContent="pairing required"}else hwm$("status").textContent=JSON.stringify(status,null,2)}else hwm$("status").textContent="pairing required"}catch(e){hwm$("health").textContent="daemon: offline";hwm$("health").className="bad";hwm$("status").textContent=String(e)}\n''',
'''  try{const h=await daemonJson("/health",{},false);hwm$("health").textContent=`daemon: ${h.status}`;hwm$("health").className="ok";const token=await pairedToken();if(token){const status=await currentDaemonStatus();if(status?.status==="pairing_required"){hwm$("status").textContent="pairing required"}else hwm$("status").textContent=JSON.stringify(status,null,2)}else hwm$("status").textContent="pairing required"}catch(e){hwm$("health").textContent="daemon: offline";hwm$("health").className="bad";hwm$("status").textContent=String(e)}\n''')
replace_once('extension/src/sidepanel.ts','setInterval(refresh,1000);void refresh();','setInterval(refresh,2000);void refresh();')

# ---------------------------------------------------------------------------
# Raw socket integration test: auth, RFC6455 accept, initial state frame and
# pushed revision after local state publication.
# ---------------------------------------------------------------------------
(ROOT/'scripts/test_websocket_stream.py').write_text(r'''from __future__ import annotations
import base64,hashlib,json,os,socket,subprocess,sys,tempfile,time,urllib.error,urllib.request
from pathlib import Path
GUID="258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
def free_port():
    with socket.socket() as s:s.bind(("127.0.0.1",0));return int(s.getsockname()[1])
def req(base,path,method="GET",payload=None,token=None,timeout=5):
    data=None if payload is None else json.dumps(payload).encode();headers={}
    if data is not None:headers["Content-Type"]="application/json"
    if token:headers["Authorization"]=f"Bearer {token}"
    r=urllib.request.Request(base+path,data=data,method=method,headers=headers)
    try:
        with urllib.request.urlopen(r,timeout=timeout) as x:return x.status,json.loads(x.read().decode())
    except urllib.error.HTTPError as e:return e.code,json.loads(e.read().decode())
def wait(base):
    end=time.time()+8
    while time.time()<end:
        try:
            if req(base,"/health",timeout=1)[0]==200:return
        except Exception:pass
        time.sleep(.05)
    raise AssertionError("daemon not healthy")
def recv_until(s,marker):
    data=b""
    while marker not in data:data+=s.recv(4096)
    return data
def recv_frame(s):
    h=s.recv(2);assert len(h)==2 and (h[0]&0x0f)==1,h
    n=h[1]&0x7f
    if n==126:n=int.from_bytes(s.recv(2),"big")
    elif n==127:n=int.from_bytes(s.recv(8),"big")
    assert not (h[1]&0x80)
    data=b""
    while len(data)<n:data+=s.recv(n-len(data))
    return json.loads(data.decode())
def connect_ws(port,token):
    s=socket.create_connection(("127.0.0.1",port),timeout=3);s.settimeout(4);key=base64.b64encode(os.urandom(16)).decode()
    request=(f"GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: hwm-v1, hwm-bearer.{token}\r\nOrigin: chrome-extension://integration-test\r\n\r\n").encode();s.sendall(request);headers=recv_until(s,b"\r\n\r\n").decode();assert "101 Switching Protocols" in headers,headers
    expected=base64.b64encode(hashlib.sha1((key+GUID).encode()).digest()).decode();assert f"Sec-WebSocket-Accept: {expected}" in headers,headers;assert "Sec-WebSocket-Protocol: hwm-v1" in headers;return s
def main():
    exe=sys.argv[1] if len(sys.argv)>1 else "build/debug/solver-daemon"
    with tempfile.TemporaryDirectory() as td:
        port=free_port();base=f"http://127.0.0.1:{port}";env=os.environ.copy();env.update(HWM_TOKEN_FILE=str(Path(td)/"token"),HWM_PAIRING_CODE="123456",HWM_ENABLE_DEBUG="1")
        p=subprocess.Popen([exe,str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
        try:
            wait(base);_,paired=req(base,"/pair","POST",{"code":"123456"});token=paired["token"]
            bad=socket.create_connection(("127.0.0.1",port),timeout=3);bad.sendall((f"GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: hwm-v1, hwm-bearer.bad\r\nOrigin: chrome-extension://integration-test\r\n\r\n").encode());assert b"401 Unauthorized" in recv_until(bad,b"\r\n\r\n");bad.close()
            ws=connect_ws(port,token);first=recv_frame(ws);assert first["type"]=="state" and first["status"]["revision"]==0,first
            assert req(base,"/debug/demo-state","POST",{},token)[0]==200
            pushed=recv_frame(ws);assert pushed["type"]=="state",pushed;st=pushed["status"];assert st["revision"]>=1 and st["state_hash"] and st["side_to_act"]==1 and st["active_entity_uid"],st
            ws.close();print("local websocket revision stream: PASS",st["revision"],st["state_hash"])
        finally:p.terminate();p.wait(timeout=5)
if __name__=="__main__":main()
''',encoding='utf-8')

# ---------------------------------------------------------------------------
# Documentation/status synchronization.
# ---------------------------------------------------------------------------
for spec in ('SPEC.md','HeroesWM_Solver_TZ_Status_0.3.0.md'):
    p=ROOT/spec;text=p.read_text(encoding='utf-8')
    text=text.replace(
        '> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE.** Loopback C++ HTTP daemon, health/status/state/capture/recommend/debug endpoints, origin filtering, capture persistence и concurrency реализованы. Persistent local pairing token с explicit one-time code реализован и обязателен для private API; WebSocket streaming остаётся незакрыт.',
        '> **Статус checkpoint 0.3.0 — COMPLETE FOR CURRENT LOCAL API.** Loopback C++ HTTP daemon, health/status/state/capture/recommend/debug endpoints, origin filtering, persistent pairing bearer и authenticated WebSocket revision/status streaming реализованы; transport/auth contracts закреплены integration tests.',1)
    text=text.replace(
        '> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE.** Local capture/session/API/auto-replan, cooperative stale-search cancellation и UI state-hash guard реализованы и regression-tested. Нужна live-browser validation.',
        '> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE.** Local capture/session/API/auto-replan, authenticated WebSocket extension connection, cooperative stale-search cancellation и UI state-hash guard реализованы и regression-tested. Нужна live-browser validation.',1)
    text=text.replace('Automated tests: C++ CTest **100%**, Python **42/42**, TypeScript typecheck/build **PASS**; local API pairing/auth integration **PASS**.', 'Automated tests: C++ CTest **100%**, Python **42/42**, TypeScript typecheck/build **PASS**; local API pairing/auth, stale-search cancellation, live binding и WebSocket streaming integration **PASS**.',1)
    p.write_text(text,encoding='utf-8')

for report in ('IMPLEMENTATION_REPORT.md','HeroesWM_Solver_Implementation_Report_0.3.0.md'):
    p=ROOT/report;text=p.read_text(encoding='utf-8')
    text=text.replace('| M16 Local API | MOSTLY COMPLETE | loopback HTTP, persistent bearer pairing, capture/state/status/plan/debug, origin guard, auth/stale/live binding CI contracts | WebSocket streaming |','| M16 Local API | COMPLETE CURRENT API | loopback HTTP, persistent bearer pairing, authenticated WebSocket revision/status stream, capture/state/status/plan/debug, origin guard, auth/stale/live/WS CI contracts | — |',1)
    text=text.replace('After stable live acquisition is proven, continue main-only original-TZ work: WebSocket streaming and persistent tree re-root/transpositions/opponent branching.','After stable live acquisition is proven, continue main-only original-TZ work: persistent tree re-root/transpositions/opponent branching.',1)
    p.write_text(text,encoding='utf-8')

p=ROOT/'TEST_REPORT.md';text=p.read_text(encoding='utf-8')
text=text.replace('Live recommendation binding contract:   PASS\nPython pytest:', 'Live recommendation binding contract:   PASS\nWebSocket revision streaming:            PASS\nPython pytest:',1)
text=text.replace('The snapshot above is enforced by the standard GitHub CI. The current three closed-loop integration gates all passed together in CI commit `676da42b754ee9d1409cc27e8ad1dfec26d17e6c`.', 'The snapshot above is enforced by the standard GitHub CI. Pairing/auth, stale cancellation and live binding passed together in `676da42b754ee9d1409cc27e8ad1dfec26d17e6c`; WebSocket streaming is additionally covered by `scripts/test_websocket_stream.py` and is promoted to the standard CI in the follow-up CI wiring commit.',1)
p.write_text(text,encoding='utf-8')

p=ROOT/'docs/MAIN_FRONT_STATUS.md';text=p.read_text(encoding='utf-8')
text=text.replace('The next correctness step is a real authenticated active-battle smoke validation using `docs/LIVE_VALIDATION.md`.', '### M16 authenticated WebSocket streaming\n\nThe local daemon now exposes an authenticated `ws://127.0.0.1:<port>/ws` state stream. The bearer is carried as `Sec-WebSocket-Protocol: hwm-bearer.<token>` rather than in the URL. The daemon pushes canonical status immediately and whenever SessionStore revision changes, plus a 20-second heartbeat. The MV3 service worker consumes this stream, stores the last daemon status, deduplicates replanning by revision and falls back to HTTP status only when streamed status is stale/unavailable.\n\nThe next correctness step is a real authenticated active-battle smoke validation using `docs/LIVE_VALIDATION.md`.',1)
p.write_text(text,encoding='utf-8')

WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True)
run('git','diff','--check');run('cmake','--preset','debug');run('cmake','--build','build/debug','--parallel','2');run('ctest','--test-dir','build/debug','--output-on-failure')
run('python','scripts/test_local_api_auth.py','build/debug/solver-daemon');run('python','scripts/test_stale_cancellation.py','build/debug/solver-daemon');run('python','scripts/test_live_binding.py','build/debug/solver-daemon');run('python','scripts/test_websocket_stream.py','build/debug/solver-daemon')
run('npm','install','--no-audit','--no-fund','--no-package-lock',cwd=ROOT/'extension');run('npm','run','typecheck',cwd=ROOT/'extension');run('npm','run','build',cwd=ROOT/'extension')

staging_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();run('git','config','user.name','github-actions[bot]');run('git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com');run('git','add','-A');run('git','commit','-m','feat: stream canonical revisions over authenticated websocket');functional_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();run('git','push','origin','HEAD:main')
with (ROOT/'changelog.md').open('a',encoding='utf-8') as f:
    f.write(f'''\n\n### Authenticated local WebSocket revision stream\n\n- Commit: `{staging_sha}`\n  - Staged the self-removing M16 WebSocket streaming patch and raw RFC6455 integration test.\n- Commit: `{functional_sha}`\n  - Added RFC6455 `/ws` on the existing loopback daemon with SHA-1/WebSocket handshake and authenticated subprotocol `hwm-bearer.<token>`; the bearer is not placed in the URL.\n  - Server pushes canonical `status` immediately and on every SessionStore revision change, plus a 20-second heartbeat for MV3 service-worker liveness.\n  - Status now exposes `side_to_act` and `active_entity_uid` so the service worker schedules planning only for confirmed player decision states.\n  - MV3 service worker reconnects the authenticated stream, stores streamed daemon status, logs WS events in the bounded live trace and deduplicates replanning by canonical revision; capture remains passive HTTP and no extra HeroesWM traffic is introduced.\n  - Side panel uses fresh streamed status for stale guards/diagnostics and falls back to HTTP `/status` only when stream data is absent or older than five seconds.\n  - Added `scripts/test_websocket_stream.py`: wrong bearer -> 401, valid RFC6455 accept verified, initial revision frame received, debug state publication produces pushed newer revision/hash.\n  - M16 is now COMPLETE FOR CURRENT LOCAL API; Phase 2 remains MOSTLY COMPLETE until a real active authenticated browser battle is exercised.\n  - C++/CTest, pairing, stale cancellation, live binding, WebSocket integration, TypeScript typecheck and extension build passed before commit.\n''')
run('git','add','changelog.md');run('git','commit','-m','docs: log authenticated websocket streaming');run('git','push','origin','HEAD:main')
