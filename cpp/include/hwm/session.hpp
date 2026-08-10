#pragma once
#include "hwm/planner.hpp"
#include "hwm/protocol.hpp"

#include <atomic>
#include <mutex>
#include <optional>
#include <string>
#include <vector>

namespace hwm {
struct RawEnvelope {
    std::string battle_id, source, url_kind, url, body;
    uint64_t captured_at_ms = 0, sequence_hint = 0;
};

struct CaptureOutcome {
    bool accepted = false;
    bool duplicate = false;
    bool out_of_order = false;
    bool session_reset = false;
    bool canonical_state_updated = false;
    uint64_t revision = 0;
    std::string state_hash;
    std::string reason;
};

struct SessionSnapshot {
    BattleState state;
    uint64_t revision = 0;
};

class SessionStore {
public:
    CaptureOutcome capture(RawEnvelope e);
    void set_state(BattleState s);
    std::optional<BattleState> state() const;
    std::optional<SessionSnapshot> snapshot() const;
    uint64_t revision() const noexcept { return revision_.load(std::memory_order_acquire); }
    std::optional<RawEnvelope> last_envelope() const;
    std::string status_json() const;
    bool capture_runtime_probe(std::string body);

private:
    mutable std::mutex mu_;
    std::optional<BattleState> state_;
    std::optional<BattleState> initial_state_;
    std::optional<RawEnvelope> envelope_;
    std::vector<DecodeWarning> warnings_;
    ProtocolDecoder decoder_;
    std::string battle_id_;
    std::string last_raw_hash_;
    uint64_t last_capture_ms_ = 0;
    uint64_t accepted_captures_ = 0;
    uint64_t duplicate_captures_ = 0;
    uint64_t out_of_order_captures_ = 0;
    std::vector<RawEnvelope> pending_updates_;
    uint64_t runtime_probe_count_ = 0;
    uint64_t runtime_probe_bytes_ = 0;
    std::string last_runtime_probe_;
    std::atomic<uint64_t> revision_{0};
};
}  // namespace hwm
