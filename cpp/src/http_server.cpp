#include "hwm/http_server.hpp"
#include "hwm/planner.hpp"

#include <array>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <random>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <thread>
#include <vector>

#ifdef _WIN32
#define NOMINMAX
#include <winsock2.h>
#include <ws2tcpip.h>
using sock_t = SOCKET;
static constexpr sock_t bad_sock = INVALID_SOCKET;
static void close_sock(sock_t s) { closesocket(s); }
#else
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
using sock_t = int;
static constexpr sock_t bad_sock = -1;
static void close_sock(sock_t s) { close(s); }
#endif

namespace hwm {
namespace {
std::string json_string(const std::string& b, const std::string& key) {
    const std::string needle = "\"" + key + "\"";
    auto p = b.find(needle);
    if (p == std::string::npos) return {};
    p = b.find(':', p + needle.size());
    if (p == std::string::npos) return {};
    p = b.find('"', p + 1);
    if (p == std::string::npos) return {};
    std::string out;
    bool escaped = false;
    for (size_t i = p + 1; i < b.size(); ++i) {
        const char c = b[i];
        if (escaped) {
            switch (c) {
                case 'n': out += '\n'; break;
                case 'r': out += '\r'; break;
                case 't': out += '\t'; break;
                case 'b': out += '\b'; break;
                case 'f': out += '\f'; break;
                case '"': out += '"'; break;
                case '\\': out += '\\'; break;
                case '/': out += '/'; break;
                default: out += c; break;
            }
            escaped = false;
        } else if (c == '\\') {
            escaped = true;
        } else if (c == '"') {
            break;
        } else {
            out += c;
        }
    }
    return out;
}

uint64_t json_u64(const std::string& b, const std::string& key, uint64_t fallback = 0) {
    const std::string needle = "\"" + key + "\"";
    auto p = b.find(needle);
    if (p == std::string::npos) return fallback;
    p = b.find(':', p + needle.size());
    if (p == std::string::npos) return fallback;
    while (++p < b.size() && (b[p] == ' ' || b[p] == '\t')) {}
    uint64_t value = 0;
    bool any = false;
    for (; p < b.size() && b[p] >= '0' && b[p] <= '9'; ++p) {
        any = true;
        value = value * 10 + static_cast<unsigned>(b[p] - '0');
    }
    return any ? value : fallback;
}

std::string header_value(const std::string& headers, const std::string& name) {
    std::regex re("(?:^|\\r\\n)" + name + R"(:\s*([^\r\n]+))", std::regex::icase);
    std::smatch m;
    return std::regex_search(headers, m, re) ? m[1].str() : std::string{};
}

uint64_t env_u64(const char* name, uint64_t fallback) {
    const char* value = std::getenv(name);
    if (!value || !*value) return fallback;
    try { return std::stoull(value); } catch (...) { return fallback; }
}

std::string random_hex(size_t bytes) {
    std::random_device rd;
    std::ostringstream o;
    o << std::hex << std::setfill('0');
    for (size_t i = 0; i < bytes; ++i) o << std::setw(2) << (rd() & 0xffu);
    return o.str();
}

std::string pairing_code() {
    if (const char* forced = std::getenv("HWM_PAIRING_CODE"); forced && *forced) return forced;
    std::random_device rd;
    const unsigned value = static_cast<unsigned>(rd()) % 1000000u;
    std::ostringstream o; o << std::setfill('0') << std::setw(6) << value; return o.str();
}

std::filesystem::path token_path() {
    if (const char* forced = std::getenv("HWM_TOKEN_FILE"); forced && *forced) return forced;
#ifdef _WIN32
    const char* base = std::getenv("LOCALAPPDATA");
    if (!base || !*base) base = std::getenv("USERPROFILE");
    return std::filesystem::path(base && *base ? base : ".") / "HeroesWMSolver" / "pairing.token";
#else
    const char* home = std::getenv("HOME");
    return std::filesystem::path(home && *home ? home : ".") / ".heroeswm-solver" / "pairing.token";
#endif
}

std::string load_or_create_pairing_token() {
    const auto path = token_path();
    {
        std::ifstream in(path, std::ios::binary);
        std::string token;
        if (in && std::getline(in, token) && token.size() >= 32) return token;
    }
    std::error_code ec;
    if (!path.parent_path().empty()) std::filesystem::create_directories(path.parent_path(), ec);
    const std::string token = random_hex(32);
    {
        std::ofstream out(path, std::ios::binary | std::ios::trunc);
        if (!out) throw std::runtime_error("cannot persist local API pairing token");
        out << token << '\n';
    }
    std::filesystem::permissions(
        path, std::filesystem::perms::owner_read | std::filesystem::perms::owner_write,
        std::filesystem::perm_options::replace, ec);
    return token;
}

bool secure_equal(std::string_view a, std::string_view b) {
    if (a.size() != b.size()) return false;
    unsigned char diff = 0;
    for (size_t i = 0; i < a.size(); ++i) diff |= static_cast<unsigned char>(a[i] ^ b[i]);
    return diff == 0;
}

bool allowed_origin(const std::string& origin) {
    return origin.empty() || origin.rfind("chrome-extension://", 0) == 0 || origin.rfind("moz-extension://", 0) == 0;
}

bool public_route(const std::string& method, const std::string& path) {
    return method == "OPTIONS" || (method == "GET" && (path == "/health" || path == "/version")) ||
        (method == "POST" && path == "/pair");
}

bool bearer_authorized(const std::string& headers, const std::string& token) {
    const std::string auth = header_value(headers, "Authorization");
    const std::string expected = "Bearer " + token;
    return secure_equal(auth, expected);
}

bool websocket_protocol_authorized(const std::string& headers,const std::string& token){
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
        if(comma==std::string::npos) break;
        pos=comma+1;
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
    if(n<=0) return false;
    off+=static_cast<size_t>(n);
    }
    return true;
}

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

std::string json_escape(std::string_view s) {
    std::string out; out.reserve(s.size()+8);
    for (unsigned char c : s) {
        switch (c) {
            case '\\': out += "\\\\"; break;
            case '"': out += "\\\""; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default: if (c >= 0x20) out += static_cast<char>(c); break;
        }
    }
    return out;
}

std::string candidate_json(const Candidate& c) {
    std::ostringstream o;
    o << "{\"action\":" << to_json(c.action)
      << ",\"score\":" << c.score
      << ",\"p_win\":" << c.p_win
      << ",\"uncertainty\":" << c.uncertainty
      << ",\"visits\":" << c.visits << '}';
    return o.str();
}
}  // namespace

HttpServer::HttpServer(std::string bind_address, uint16_t port, SessionStore& store)
    : bind_(std::move(bind_address)), port_(port), store_(store),
      pairing_token_(load_or_create_pairing_token()), pairing_code_(pairing_code()) {}
HttpServer::~HttpServer() { stop(); }
void HttpServer::stop() { stop_ = true; }

std::string HttpServer::response(int code, std::string body, std::string type) {
    std::ostringstream o;
    o << "HTTP/1.1 " << code << (code == 200 ? " OK" : " Error")
      << "\r\nContent-Type: " << type
      << "\r\nAccess-Control-Allow-Origin: *"
      << "\r\nAccess-Control-Allow-Headers: Content-Type, Authorization"
      << "\r\nAccess-Control-Allow-Methods: GET,POST,OPTIONS"
      << "\r\nCache-Control: no-store"
      << "\r\nContent-Length: " << body.size()
      << "\r\nConnection: close\r\n\r\n" << body;
    return o.str();
}

std::string HttpServer::handle(std::string method, std::string path, std::string body) {
    if (method == "OPTIONS") return response(200, "{}");
    if (method == "GET" && path == "/health")
        return response(200, "{\"status\":\"ok\",\"service\":\"heroeswm-solver\",\"version\":\"0.3.0\"}");
    if (method == "GET" && path == "/version")
        return response(200, "{\"version\":\"0.3.0\",\"api\":3,\"protocol_decoder\":\"raw-v2\",\"auth\":\"pairing-bearer-v1\"}");
    if (method == "POST" && path == "/pair") {
        if (pairing_failures_.load() >= 10) return response(429, "{\"paired\":false,\"error\":\"pairing_locked_until_restart\"}");
        const std::string code = json_string(body, "code");
        if (!secure_equal(code, pairing_code_)) {
            ++pairing_failures_;
            return response(403, "{\"paired\":false,\"error\":\"invalid_pairing_code\"}");
        }
        pairing_failures_ = 0;
        return response(200, "{\"paired\":true,\"token\":\"" + pairing_token_ + "\"}");
    }
    if (method == "GET" && path == "/status") return response(200, store_.status_json());
    if (method == "GET" && (path == "/state" || path == "/session/current/state")) {
        auto s = store_.state();
        return s ? response(200, to_json(*s)) : response(404, "{\"status\":\"not_ready\",\"reason\":\"canonical_state_unavailable\"}");
    }
    if (method == "GET" && path == "/debug/last-raw") {
        auto e = store_.last_envelope();
        return e ? response(200, e->body, "text/plain; charset=utf-8") : response(404, "no envelope", "text/plain");
    }
    if (method == "POST" && path == "/debug/import-replay") {
        const char* enabled = std::getenv("HWM_ENABLE_DEBUG");
        if (!enabled || std::string(enabled) != "1") return response(403, "{\"error\":\"debug_disabled\"}");
        RawEnvelope e; e.battle_id="debug"; e.source="debug-import"; e.url_kind="raw"; e.sequence_hint=1; e.body=std::move(body);
        const auto outcome=store_.capture(std::move(e));
        return response(outcome.accepted?200:400, outcome.accepted?"{\"accepted\":true,\"mode\":\"debug-import\"}":"{\"accepted\":false}");
    }
    if (method == "POST" && path == "/debug/demo-state") {
        const char* enabled = std::getenv("HWM_ENABLE_DEBUG");
        if (!enabled || std::string(enabled) != "1") return response(403, "{\"error\":\"debug_disabled\"}");
        BattleState s; s.battle_id="demo"; s.state_seq=1; s.phase=Phase::Combat; s.width=13; s.height=11; s.protocol_ready=true;s.recommendation_safe=true;
        Entity a; a.uid=1; a.creature_id=101; a.side=Side::Player; a.anchor={1,4}; a.count=45; a.top_unit_hp=18; a.max_hp_per_unit=18; a.attack=14; a.defense=10; a.min_damage=3; a.max_damage=5; a.speed=5; a.shots=8;
        Entity b=a; b.uid=2; b.creature_id=202; b.side=Side::Pve; b.anchor={8,4}; b.count=50; b.attack=12; b.defense=12; b.shots=0;
        s.entities={a,b}; s.active_entity_uid=1; s.side_to_act=Side::Player; store_.set_state(std::move(s));
        return response(200, "{\"accepted\":true,\"mode\":\"demo-state\"}");
    }
    if (method == "POST" && path == "/runtime-probe") {
        if (body.empty()) return response(400, "{\"accepted\":false,\"error\":\"empty_probe\"}");
        const bool ok = store_.capture_runtime_probe(std::move(body));
        return response(ok ? 200 : 400, ok ?
            "{\"accepted\":true,\"kind\":\"runtime_structure_probe\"}" :
            "{\"accepted\":false,\"error\":\"probe_rejected\"}");
    }
    if (method == "POST" && (path == "/capture" || path == "/session/raw-envelope")) {
        RawEnvelope e;
        e.battle_id = json_string(body, "battleId");
        e.source = json_string(body, "source");
        e.url_kind = json_string(body, "urlKind");
        e.url = json_string(body, "url");
        e.captured_at_ms = json_u64(body, "capturedAt");
        e.sequence_hint = json_u64(body, "sequenceHint");
        e.body = json_string(body, "body");
        if (e.body.empty()) return response(400, "{\"accepted\":false,\"error\":\"empty_body\"}");
        const auto outcome = store_.capture(std::move(e));
        std::ostringstream reply; reply << "{\"accepted\":" << (outcome.accepted?"true":"false")
            << ",\"duplicate\":" << (outcome.duplicate?"true":"false")
            << ",\"out_of_order\":" << (outcome.out_of_order?"true":"false")
            << ",\"session_reset\":" << (outcome.session_reset?"true":"false")
            << ",\"canonical_state_updated\":" << (outcome.canonical_state_updated?"true":"false")
            << ",\"revision\":" << outcome.revision
            << ",\"state_hash\":\"" << outcome.state_hash << "\""
            << ",\"reason\":\"" << outcome.reason << "\"}";
        return response(outcome.accepted?200:400, reply.str());
    }
    if (method == "POST" && (path == "/recommend" || path == "/session/current/plan")) {
        auto snapshot = store_.snapshot();
        if (!snapshot) return response(200, "{\"status\":\"not_ready\",\"reason\":\"canonical state unavailable\"}");
        const BattleState& s = snapshot->state;
        const uint64_t requested_revision = snapshot->revision;
        if (!s.protocol_ready) return response(200, "{\"status\":\"not_ready\",\"reason\":\"waiting for contiguous turn stream / decoder confidence gate\"}");
        if (s.phase == Phase::Finished) return response(200, "{\"status\":\"finished\",\"reason\":\"battle ended\"}");
        if (s.side_to_act != Side::Player || s.active_entity_uid == 0) return response(200, "{\"status\":\"not_ready\",\"reason\":\"not a confirmed player decision state\"}");
        const auto requested_hash = state_hash(s);
        PlannerConfig cfg;
        cfg.simulation_budget = env_u64("HWM_SEARCH_SIMS", 10000);
        cfg.time_budget_ms = env_u64("HWM_SEARCH_MS", 5000);
        cfg.max_depth = static_cast<int>(env_u64("HWM_SEARCH_DEPTH", 12));
        cfg.cancellation_poll_interval = env_u64("HWM_SEARCH_CANCEL_POLL", 16);
        cfg.cancellation_requested = [this, requested_revision] { return store_.revision() != requested_revision; };
        Planner planner(cfg);
        auto r = planner.plan(s);
        const bool revision_changed = store_.revision() != requested_revision;
        if (r.status == "cancelled" || revision_changed) {
            auto latest = store_.snapshot();
            const std::string current_hash = latest ? state_hash(latest->state) : std::string{};
            std::ostringstream stale;
            stale << "{\"status\":\"stale\",\"reason\":\"battle state changed while planning\""
                  << ",\"requested_state_hash\":\"" << requested_hash << "\""
                  << ",\"current_state_hash\":\"" << current_hash << "\""
                  << ",\"requested_revision\":" << requested_revision
                  << ",\"current_revision\":" << store_.revision()
                  << ",\"cancelled_search\":" << (r.status == "cancelled" ? "true" : "false")
                  << ",\"simulations\":" << r.simulations
                  << ",\"elapsed_ms\":" << r.elapsed_ms << '}';
            return response(200, stale.str());
        }
        std::ostringstream o;
        o << "{\"status\":\"" << r.status << "\",\"state_hash\":\"" << r.state_hash
          << "\",\"state_revision\":" << requested_revision
          << ",\"battle_id\":\"" << json_escape(s.battle_id) << "\""
          << ",\"semantic_safety_tier\":\"" << semantic_safety_tier(s) << "\""
          << ",\"semantic_unresolved_ratio\":" << s.semantic_unresolved_ratio
          << ",\"ability_risk\":" << r.ability_risk
          << ",\"simulations\":" << r.simulations << ",\"nodes\":" << r.nodes
          << ",\"elapsed_ms\":" << r.elapsed_ms << ",\"best\":" << candidate_json(r.best)
          << ",\"alternatives\":[";
        for (size_t i = 0; i < r.alternatives.size(); ++i) {
            if (i) o << ',';
            o << candidate_json(r.alternatives[i]);
        }
        o << "],\"principal_variation\":[";
        for (size_t i = 0; i < r.pv.size(); ++i) {
            if (i) o << ',';
            o << to_json(r.pv[i]);
        }
        o << "],\"warnings\":[";
        for (size_t i = 0; i < r.warnings.size(); ++i) {
            if (i) o << ',';
            o << "\"" << json_escape(r.warnings[i]) << "\"";
        }
        o << "]}";
        return response(200, o.str());
    }
    return response(404, "{\"error\":\"not_found\"}");
}

int HttpServer::run() {
#ifdef _WIN32
    WSADATA wd;
    if (WSAStartup(MAKEWORD(2, 2), &wd) != 0) return 2;
#endif
    sock_t srv = socket(AF_INET, SOCK_STREAM, 0);
    if (srv == bad_sock) { std::cerr << "socket failed\n"; return 2; }
#ifndef _WIN32
    int yes = 1;
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
#endif
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port_);
    if (inet_pton(AF_INET, bind_.c_str(), &addr.sin_addr) != 1) { close_sock(srv); return 2; }
    if (bind(srv, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0 || listen(srv, 32) < 0) {
        std::cerr << "bind/listen failed\n";
        close_sock(srv);
        return 2;
    }
    std::cout << "solver-daemon listening http://" << bind_ << ':' << port_ << std::endl;
    std::cout << "HeroesWM Solver pairing code: " << pairing_code_ << std::endl;

    while (!stop_) {
        sock_t client = accept(srv, nullptr, nullptr);
        if (client == bad_sock) continue;
        std::thread([this, client] {
            std::string req;
            char buf[8192];
            int n = 0;
            while ((n = recv(client, buf, sizeof(buf), 0)) > 0) {
                req.append(buf, buf + n);
                const auto header_end = req.find("\r\n\r\n");
                if (header_end == std::string::npos) continue;
                const std::string headers = req.substr(0, header_end);
                const auto cl = header_value(headers, "Content-Length");
                size_t len = 0;
                if (!cl.empty()) {
                    try { len = std::stoull(cl); } catch (...) { len = 0; }
                }
                if (len > 8 * 1024 * 1024) {
                    auto out = response(413, "{\"error\":\"request_too_large\"}");
                    send(client, out.data(), static_cast<int>(out.size()), 0);
                    close_sock(client);
                    return;
                }
                if (req.size() >= header_end + 4 + len) break;
            }
            const auto eol = req.find("\r\n");
            if (eol == std::string::npos) { close_sock(client); return; }
            const std::string first = req.substr(0, eol);
            std::istringstream fs(first);
            std::string method, path, version;
            fs >> method >> path >> version;
            const auto header_end = req.find("\r\n\r\n");
            const std::string headers = header_end == std::string::npos ? std::string{} : req.substr(0, header_end);
            const std::string origin = header_value(headers, "Origin");
            const std::string body = header_end == std::string::npos ? std::string{} : req.substr(header_end + 4);
            const std::string upgrade=header_value(headers,"Upgrade");
            const bool ws_upgrade=method=="GET"&&path=="/ws"&&(upgrade=="websocket"||upgrade=="WebSocket");
            if(ws_upgrade){
                if(!allowed_origin(origin)){const auto out=response(403,"{\"error\":\"origin_not_allowed\"}");send_all(client,out);close_sock(client);return;}
                if(!websocket_protocol_authorized(headers,pairing_token_)){const auto out=response(401,"{\"error\":\"pairing_required\"}");send_all(client,out);close_sock(client);return;}
                const std::string key=header_value(headers,"Sec-WebSocket-Key"),version_ws=header_value(headers,"Sec-WebSocket-Version");
                if(key.empty()||version_ws!="13"){const auto out=response(400,"{\"error\":\"invalid_websocket_handshake\"}");send_all(client,out);close_sock(client);return;}
                std::ostringstream hs;hs<<"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: "<<websocket_accept(key)<<"\r\nSec-WebSocket-Protocol: hwm-v1\r\n\r\n";
                if(send_all(client,hs.str())) websocket_stream(client,store_,stop_);
                close_sock(client);
                return;
            }
            std::string out;
            if (!allowed_origin(origin)) out = response(403, "{\"error\":\"origin_not_allowed\"}");
            else if (!public_route(method, path) && !bearer_authorized(headers, pairing_token_))
                out = response(401, "{\"error\":\"pairing_required\"}");
            else out = handle(method, path, body);
            send_all(client,out);
            close_sock(client);
        }).detach();
    }
    close_sock(srv);
#ifdef _WIN32
    WSACleanup();
#endif
    return 0;
}
}  // namespace hwm
