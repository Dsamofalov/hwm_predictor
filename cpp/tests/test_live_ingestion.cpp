#include "hwm/session.hpp"
#include "hwm/state.hpp"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

namespace fs = std::filesystem;

static std::string read_all(const fs::path& path) {
    std::ifstream in(path, std::ios::binary);
    std::ostringstream out;
    out << in.rdbuf();
    return out.str();
}

#define CHECK(expr) do { if (!(expr)) { std::cerr << "CHECK failed: " #expr " at line " << __LINE__ << "\n"; return 1; } } while (0)

int main() {
    const fs::path fixture = fs::path(HWM_PROJECT_ROOT) / "fixtures" / "live_closed_loop";

    // Do not broaden the evidence-backed classifier: an unknown bare numeric network
    // payload is not the observed `t=<digits>` heartbeat shape and must reach ingestion.
    hwm::SessionStore unknown_store;
    hwm::RawEnvelope unknown;
    unknown.battle_id = "sanitized-live";
    unknown.source = "xhr";
    unknown.url_kind = "battle_update";
    unknown.url = "https://example.invalid/battle.php?warid=sanitized-live";
    unknown.captured_at_ms = 9000;
    unknown.sequence_hint = 1;
    unknown.body = "950";
    const auto unknown_result = unknown_store.capture(unknown);
    CHECK(unknown_result.accepted);
    CHECK(unknown_result.reason != "heartbeat_noop");
    CHECK(!unknown_result.canonical_state_updated);
    CHECK(unknown_store.last_envelope().has_value());
    CHECK(unknown_store.last_envelope()->body == "950");

    hwm::SessionStore store;
    hwm::RawEnvelope snapshot;
    snapshot.battle_id = "sanitized-live";
    snapshot.source = "xhr";
    snapshot.url_kind = "battle_update";
    snapshot.url = "https://example.invalid/battle.php?warid=sanitized-live";
    snapshot.captured_at_ms = 10000;
    snapshot.sequence_hint = 1;
    snapshot.body = read_all(fixture / "semantic_snapshot.txt");

    const auto first = store.capture(snapshot);
    CHECK(first.accepted);
    CHECK(first.canonical_state_updated);
    CHECK(first.revision == 1);
    CHECK(!first.state_hash.empty());
    const auto before = store.snapshot();
    CHECK(before.has_value());
    const auto before_hash = hwm::state_hash(before->state);
    CHECK(before_hash == first.state_hash);
    CHECK(store.last_envelope().has_value());
    CHECK(store.last_envelope()->body == snapshot.body);

    hwm::RawEnvelope heartbeat = snapshot;
    heartbeat.captured_at_ms = 10050;
    heartbeat.sequence_hint = 2;
    heartbeat.body = read_all(fixture / "heartbeat.txt");
    const auto noop = store.capture(heartbeat);
    CHECK(noop.accepted);
    CHECK(!noop.canonical_state_updated);
    CHECK(noop.reason == "heartbeat_noop");
    CHECK(noop.revision == first.revision);
    CHECK(noop.state_hash == before_hash);
    CHECK(store.revision() == first.revision);
    CHECK(store.last_envelope().has_value());
    CHECK(store.last_envelope()->body == snapshot.body);

    hwm::RawEnvelope update = snapshot;
    update.captured_at_ms = 10100;
    update.sequence_hint = 3;
    update.body = read_all(fixture / "incremental_update.txt");
    const auto second = store.capture(update);
    CHECK(second.accepted);
    CHECK(second.canonical_state_updated);
    CHECK(second.revision == first.revision + 1);
    CHECK(second.state_hash != before_hash);
    CHECK(store.revision() == second.revision);
    const auto after = store.snapshot();
    CHECK(after.has_value());
    CHECK(hwm::state_hash(after->state) == second.state_hash);
    CHECK(after->state.halfturn == 2);
    CHECK(after->state.entity(2) != nullptr);
    CHECK(after->state.entity(2)->count == 7);

    std::cout << "hwm-live-ingestion-tests PASS\n";
    return 0;
}
