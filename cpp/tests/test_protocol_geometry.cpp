#include "hwm/protocol.hpp"
#include "hwm/state.hpp"

#include <algorithm>
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
    const fs::path battle = fs::path(HWM_PROJECT_ROOT) / "hwm_battles" / "battles" / "1631502382";
    hwm::ProtocolDecoder decoder;
    const auto initial = decoder.decode_initial(read_all(battle / "init.txt"), "1631502382");
    const auto final = decoder.decode_update(initial.state, read_all(battle / "turns0.txt"));

    CHECK(final.state.min_x == 1);
    CHECK(final.state.min_y == 1);
    CHECK(final.state.width == 13);
    CHECK(final.state.height == 21);

    const auto* actor = final.state.entity(20);
    CHECK(actor != nullptr);
    CHECK(actor->alive);
    CHECK((actor->anchor == hwm::Cell{12, 20}));

    const auto violations = hwm::validate(final.state);
    CHECK(std::find(violations.begin(), violations.end(), "overlap") == violations.end());

    std::cout << "hwm-protocol-tests PASS\n";
    return 0;
}
