#include "hwm/protocol.hpp"
#include "hwm/state.hpp"

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <string_view>

namespace fs = std::filesystem;

static std::string read_all(const fs::path& path) {
    std::ifstream in(path, std::ios::binary);
    std::ostringstream out;
    out << in.rdbuf();
    return out.str();
}

static hwm::BattleState replay_final(std::string_view battle_id) {
    const fs::path battle = fs::path(HWM_PROJECT_ROOT) / "hwm_battles" / "battles" / std::string(battle_id);
    hwm::ProtocolDecoder decoder;
    const auto initial = decoder.decode_initial(read_all(battle / "init.txt"), std::string(battle_id));
    return decoder.decode_update(initial.state, read_all(battle / "turns0.txt")).state;
}

static bool has_overlap(const hwm::BattleState& state) {
    const auto violations = hwm::validate(state);
    return std::find(violations.begin(), violations.end(), "overlap") != violations.end();
}

#define CHECK(expr) do { if (!(expr)) { std::cerr << "CHECK failed: " #expr " at line " << __LINE__ << "\n"; return 1; } } while (0)

int main() {
    {
        const auto final = replay_final("1631502382");
        CHECK(final.min_x == 1);
        CHECK(final.min_y == 1);
        CHECK(final.width == 13);
        CHECK(final.height == 21);
        const auto* actor = final.entity(20);
        CHECK(actor != nullptr);
        CHECK(actor->alive);
        CHECK((actor->anchor == hwm::Cell{12, 20}));
        CHECK(!has_overlap(final));
    }

    // These three corpus finals were false-positive overlaps caused by treating an
    // impossible special-free shooter mUUUXXYY position marker as literal relocation.
    for (const std::string_view battle_id : {"1626319743", "1632012084", "1632715976"}) {
        CHECK(!has_overlap(replay_final(battle_id)));
    }

    // The raw mUUUXXYY may have several globally legal target-adjacent landings. If exactly
    // one lies within one Chebyshev cell of the raw hint, distant alternatives are not a
    // plausible interpretation of that local position hint. This closes the remaining
    // false overlap in this ordinary, special-free melee replay.
    CHECK(!has_overlap(replay_final("1633877663")));

    // Corrected corpus evidence: the blocked ordinary marker is two cells from exactly one
    // legal+reachable target-adjacent landing. Distance-3 movement-semantics controls stay unresolved.
    CHECK(!has_overlap(replay_final("1633884421")));

    // The remaining ordinary marker in this battle lands on a friendly 2x2 stack while
    // the attacker is already legal and adjacent to its sole damage target. The marker is
    // therefore position telemetry, not a legal relocation into the ally.
    CHECK(!has_overlap(replay_final("1625534409")));

    std::cout << "hwm-protocol-tests PASS\n";
    return 0;
}
