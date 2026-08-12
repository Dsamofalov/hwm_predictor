#include "hwm/session.hpp"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <chrono>
#include <string_view>

namespace hwm {
namespace {
std::string compact_hash(std::string_view s) {
    uint64_t h = 1469598103934665603ULL;
    for (unsigned char c : s) { h ^= c; h *= 1099511628211ULL; }
    std::ostringstream o; o << std::hex << h; return o.str();
}

bool is_noop_battle_heartbeat(const RawEnvelope& e) {
    if (e.url_kind != "battle_update") return false;
    const std::string_view body = e.body;
    size_t first = 0;
    while (first < body.size() && (body[first] == ' ' || body[first] == '\t' || body[first] == '\r' || body[first] == '\n')) ++first;
    size_t last = body.size();
    while (last > first && (body[last - 1] == ' ' || body[last - 1] == '\t' || body[last - 1] == '\r' || body[last - 1] == '\n')) --last;
    if (first == last) return false;
    for (size_t i = first; i < last; ++i) {
        if (body[i] < '0' || body[i] > '9') return false;
    }
    return true;
}

void persist_body_if_enabled(const RawEnvelope& e) {
    const char* dir = std::getenv("HWM_CAPTURE_DIR");
    if (!dir || !*dir) return;
    std::error_code ec;
    std::filesystem::create_directories(dir, ec);
    std::string id = e.battle_id.empty() ? "unknown" : e.battle_id;
    for (char& c : id) if (c < '0' || c > '9') c = '_';
    const auto suffix = e.captured_at_ms ? e.captured_at_ms : e.sequence_hint;
    std::ofstream f(std::filesystem::path(dir) / (id + "_" + std::to_string(suffix) + ".txt"), std::ios::binary);
    if (f) f << e.body;
}
}  // namespace

CaptureOutcome SessionStore::capture(RawEnvelope e) {
    std::scoped_lock lock(mu_);
    CaptureOutcome out;
    const auto stamp_outcome = [&] {
        out.revision = revision_.load(std::memory_order_acquire);
        out.state_hash = state_ ? state_hash(*state_) : std::string{};
    };
    if (e.battle_id.empty()) e.battle_id = battle_id_;
    if (e.battle_id.empty()) {
        out.reason = "battle_id_missing";
        stamp_outcome();
        return out;
    }
    if (e.body.empty()) {
        out.reason = "empty_body";
        stamp_outcome();
        return out;
    }

    // Official battle.php emits frequent numeric echo frames (for example "4416") that
    // carry no canonical battle semantics. Ignore them before battle reset, raw dedup/hash,
    // capture ordering and decoder bookkeeping so they cannot publish a revision or cancel
    // an in-flight search. The MAIN-world hook performs the same classification earlier;
    // this daemon guard keeps non-extension producers safe as well.
    if (is_noop_battle_heartbeat(e)) {
        out.accepted = true;
        out.reason = "heartbeat_noop";
        stamp_outcome();
        return out;
    }

    if (!battle_id_.empty() && e.battle_id != battle_id_) {
        state_.reset();
        initial_state_.reset();
        envelope_.reset();
        warnings_.clear();
        last_raw_hash_.clear();
        last_capture_ms_ = 0;
        pending_updates_.clear();
        out.session_reset = true;
    }
    battle_id_ = e.battle_id;

    const std::string raw_hash = compact_hash(e.body);
    if (!last_raw_hash_.empty() && raw_hash == last_raw_hash_) {
        ++duplicate_captures_;
        out.accepted = true;
        out.duplicate = true;
        out.reason = "duplicate_body";
        stamp_outcome();
        return out;
    }

    // sequence_hint resets on a page reload, therefore wall-clock capture time is the
    // stronger ordering signal. A one-second tolerance avoids rejecting near-simultaneous XHRs.
    if (last_capture_ms_ && e.captured_at_ms && e.captured_at_ms + 1000 < last_capture_ms_) {
        ++out_of_order_captures_;
        out.out_of_order = true;
        out.reason = "captured_at_older_than_current_revision";
        stamp_outcome();
        return out;
    }

    persist_body_if_enabled(e);
    const bool full_turn_stream = e.body.find("turns=>1:") != std::string::npos;
    DecodeResult decoded;
    if (state_ && initial_state_ && full_turn_stream && !state_->protocol_ready) {
        // Rebuild from the pristine static state after a gap/invariant failure. Applying a
        // full stream onto a partially advanced state would skip the missing history.
        decoded = decoder_.decode_update(*initial_state_, e.body);
    } else {
        decoded = state_ ? decoder_.decode_update(*state_, e.body) : decoder_.decode_initial(e.body, e.battle_id);
    }
    warnings_ = decoded.warnings;

    if (!decoded.state.entities.empty()) {
        // Keep a decoded static state even before it is safe to plan: a subsequent full
        // lastturn=0 stream can advance it to the real current position.
        state_ = std::move(decoded.state);
        if (state_->halfturn==0 && !initial_state_) initial_state_ = *state_;
        out.canonical_state_updated = true;

        // Every accepted canonical publication receives a new monotonic revision.
        // Duplicate/out-of-order payloads return before this point, so they do not
        // spuriously cancel an in-flight search.
        revision_.fetch_add(1, std::memory_order_release);

        // If the browser delivered the turn stream before the static lastturn=-3 payload,
        // replay the buffered payloads now. This makes capture order robust.
        if (!pending_updates_.empty() && state_ && !state_->protocol_ready) {
            for (const auto& pending : pending_updates_) {
                auto advanced = decoder_.decode_update(*state_, pending.body);
                if (!advanced.state.entities.empty()) state_ = std::move(advanced.state);
                warnings_.insert(warnings_.end(), advanced.warnings.begin(), advanced.warnings.end());
            }
            pending_updates_.clear();
        }
    } else {
        // No static state yet. Preserve a bounded number of turn-stream payloads rather than
        // discarding them; once lastturn=-3 arrives they can be applied deterministically.
        if (e.body.find("turns=>") != std::string::npos) {
            if (pending_updates_.size() >= 16) pending_updates_.erase(pending_updates_.begin());
            pending_updates_.push_back(e);
        }
    }

    last_raw_hash_ = std::move(raw_hash);
    if (e.captured_at_ms) last_capture_ms_ = e.captured_at_ms;
    envelope_ = std::move(e);
    ++accepted_captures_;
    out.accepted = true;
    out.reason = out.canonical_state_updated ? (state_ && state_->protocol_ready ? "canonical_state_ready" : "canonical_state_partial") : "raw_accepted_state_partial";
    stamp_outcome();
    return out;
}

void SessionStore::set_state(BattleState s) {
    std::scoped_lock lock(mu_);
    battle_id_ = s.battle_id;
    state_ = std::move(s);
    revision_.fetch_add(1, std::memory_order_release);
}

std::optional<BattleState> SessionStore::state() const {
    std::scoped_lock lock(mu_);
    return state_;
}

std::optional<SessionSnapshot> SessionStore::snapshot() const {
    std::scoped_lock lock(mu_);
    if (!state_) return std::nullopt;
    return SessionSnapshot{*state_, revision_.load(std::memory_order_acquire)};
}

std::optional<RawEnvelope> SessionStore::last_envelope() const {
    std::scoped_lock lock(mu_);
    return envelope_;
}


bool SessionStore::capture_runtime_probe(std::string body) {
    if (body.empty() || body.size() > 4 * 1024 * 1024) return false;
    std::scoped_lock lock(mu_);
    last_runtime_probe_ = std::move(body);
    ++runtime_probe_count_;
    runtime_probe_bytes_ = last_runtime_probe_.size();

    const char* dir = std::getenv("HWM_CAPTURE_DIR");
    if (dir && *dir) {
        std::error_code ec;
        std::filesystem::create_directories(dir, ec);
        std::string id = battle_id_.empty() ? "unknown" : battle_id_;
        for (char& c : id) if (c < '0' || c > '9') c = '_';
        const auto ts = static_cast<unsigned long long>(
            std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::system_clock::now().time_since_epoch()).count());
        std::ofstream f(std::filesystem::path(dir) /
            (id + "_runtime_probe_" + std::to_string(ts) + ".json"), std::ios::binary);
        if (f) f << last_runtime_probe_;
    }
    return true;
}

std::string SessionStore::status_json() const {
    std::scoped_lock lock(mu_);
    std::ostringstream o;
    o << "{\"battle_id\":\"" << battle_id_ << "\""
      << ",\"has_envelope\":" << (envelope_ ? "true" : "false")
      << ",\"has_state\":" << (state_ ? "true" : "false")
      << ",\"accepted_captures\":" << accepted_captures_
      << ",\"duplicate_captures\":" << duplicate_captures_
      << ",\"out_of_order_captures\":" << out_of_order_captures_
      << ",\"runtime_probe_count\":" << runtime_probe_count_
      << ",\"runtime_probe_bytes\":" << runtime_probe_bytes_
      << ",\"revision\":" << revision_.load(std::memory_order_acquire);
    if (envelope_) {
        o << ",\"source\":\"" << envelope_->source << "\""
          << ",\"sequence_hint\":" << envelope_->sequence_hint
          << ",\"captured_at_ms\":" << envelope_->captured_at_ms
          << ",\"raw_bytes\":" << envelope_->body.size();
    }
    if (state_) {
        o << ",\"state_seq\":" << state_->state_seq
          << ",\"state_hash\":\"" << state_hash(*state_) << "\""
          << ",\"phase\":" << static_cast<int>(state_->phase)
          << ",\"side_to_act\":" << static_cast<int>(state_->side_to_act)
          << ",\"active_entity_uid\":" << state_->active_entity_uid
          << ",\"protocol_ready\":" << (state_->protocol_ready ? "true" : "false")
          << ",\"recommendation_safe\":" << (state_->recommendation_safe ? "true" : "false")
          << ",\"semantic_safety_tier\":\"" << semantic_safety_tier(*state_) << "\""
          << ",\"protocol_unknown_ratio\":" << state_->protocol_unknown_ratio
          << ",\"semantic_unresolved_ratio\":" << state_->semantic_unresolved_ratio
          << ",\"protocol_records_seen\":" << state_->protocol_records_seen
          << ",\"semantic_unresolved_records\":" << state_->semantic_unresolved_records;
    }
    o << ",\"pending_updates\":" << pending_updates_.size();
    o << ",\"warnings\":[";
    for (size_t i = 0; i < warnings_.size(); ++i) {
        if (i) o << ',';
        o << "\"" << warnings_[i].code << "\"";
    }
    o << "]}";
    return o.str();
}
}  // namespace hwm
