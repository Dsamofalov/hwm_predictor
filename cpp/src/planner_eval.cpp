#include "hwm/planner.hpp"
#include "hwm/protocol.hpp"
#include "hwm/simulator.hpp"
#include "hwm/state.hpp"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

namespace fs = std::filesystem;
namespace {
std::string read_file(const fs::path& p) {
    std::ifstream f(p, std::ios::binary);
    std::ostringstream s;
    s << f.rdbuf();
    return s.str();
}

bool digits(std::string_view s) {
    return !s.empty() && std::all_of(s.begin(), s.end(), [](unsigned char c) { return std::isdigit(c); });
}

struct Chunk {
    uint32_t turn = 0;
    std::string body;
};

std::vector<Chunk> split_turns(std::string_view p) {
    struct Mark {
        size_t start = 0, body = 0;
        uint32_t turn = 0;
    };
    std::vector<Mark> m;
    if (auto first = p.find("turns=>"); first != std::string_view::npos) {
        size_t q = first + 7, colon = p.find(':', q);
        if (colon != std::string_view::npos && digits(p.substr(q, colon - q))) {
            m.push_back({first, colon + 1, static_cast<uint32_t>(std::stoul(std::string(p.substr(q, colon - q))))});
        }
    }
    size_t pos = 0;
    while ((pos = p.find(";>", pos)) != std::string_view::npos) {
        size_t q = pos + 2, colon = p.find(':', q);
        if (colon == std::string_view::npos) break;
        if (digits(p.substr(q, colon - q))) {
            m.push_back({pos, colon + 1, static_cast<uint32_t>(std::stoul(std::string(p.substr(q, colon - q))))});
        }
        pos = colon + 1;
    }
    std::sort(m.begin(), m.end(), [](const auto& a, const auto& b) { return a.start < b.start; });
    std::vector<Chunk> out;
    for (size_t i = 0; i < m.size(); ++i) {
        size_t end = i + 1 < m.size() ? m[i + 1].start : p.size();
        if (end > m[i].body && p[end - 1] == ';') --end;
        out.push_back({m[i].turn, std::string(p.substr(m[i].body, end - m[i].body))});
    }
    return out;
}

std::string payload(const Chunk& c) {
    return "t=000turns=>" + std::to_string(c.turn) + ":" + c.body;
}

bool same_action(const hwm::Action& a, const hwm::Action& b) {
    return a.type == b.type && a.actor_uid == b.actor_uid && a.target_uid == b.target_uid &&
           a.destination == b.destination && a.ability_id == b.ability_id;
}

bool legal_contains(const std::vector<hwm::Action>& legal, const hwm::Action& action) {
    return std::any_of(legal.begin(), legal.end(), [&](const auto& candidate) { return same_action(candidate, action); });
}

struct CheckedRecommendation {
    bool valid = false;
    bool state_hash_ok = false;
    bool best_legal = false;
    bool alternatives_legal = false;
    bool finite_metrics = false;
};

CheckedRecommendation check_recommendation(
    const hwm::BattleState& state,
    const hwm::Recommendation& rec,
    const std::vector<hwm::Action>& legal) {
    CheckedRecommendation out;
    if (rec.status != "ok") return out;
    out.state_hash_ok = rec.state_hash == hwm::state_hash(state);
    out.best_legal = legal_contains(legal, rec.best.action);
    out.alternatives_legal = std::all_of(rec.alternatives.begin(), rec.alternatives.end(), [&](const auto& c) {
        return legal_contains(legal, c.action);
    });
    const auto finite_candidate = [](const hwm::Candidate& c) {
        return std::isfinite(c.score) && std::isfinite(c.p_win) && std::isfinite(c.uncertainty) &&
               c.p_win >= 0.0 && c.p_win <= 1.0 && c.uncertainty >= 0.0 && c.visits > 0;
    };
    out.finite_metrics = finite_candidate(rec.best) &&
                         std::all_of(rec.alternatives.begin(), rec.alternatives.end(), finite_candidate) &&
                         std::isfinite(rec.elapsed_ms) && std::isfinite(rec.ability_risk) &&
                         rec.simulations > 0 && rec.nodes > 0;
    out.valid = out.state_hash_ok && out.best_legal && out.alternatives_legal && out.finite_metrics;
    return out;
}

struct Sample {
    hwm::BattleState state;
};

std::vector<Sample> stratified_sample(const std::vector<Sample>& candidates, size_t limit) {
    if (candidates.size() <= limit) return candidates;
    std::vector<Sample> out;
    out.reserve(limit);
    for (size_t i = 0; i < limit; ++i) {
        const size_t index = (i * candidates.size()) / limit;
        out.push_back(candidates[index]);
    }
    return out;
}
}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "usage: planner-eval <corpus-root-or-battles-dir> [limit=30] [low=300] [high=1200] [include_heroes=0]\n";
        return 2;
    }
    fs::path root = argv[1];
    if (fs::is_directory(root / "battles")) root /= "battles";
    const size_t limit = argc > 2 ? std::stoull(argv[2]) : 30;
    const uint64_t low = argc > 3 ? std::stoull(argv[3]) : 300;
    const uint64_t high = argc > 4 ? std::stoull(argv[4]) : 1200;
    const bool include_heroes = argc > 5 && std::string_view(argv[5]) == "1";

    std::vector<fs::path> dirs;
    for (auto& de : fs::directory_iterator(root)) {
        if (de.is_directory() && fs::exists(de.path() / "init.txt") && fs::exists(de.path() / "turns0.txt")) {
            dirs.push_back(de.path());
        }
    }
    std::sort(dirs.begin(), dirs.end(), [](const auto& a, const auto& b) {
        return std::stoull(a.filename().string()) < std::stoull(b.filename().string());
    });
    const size_t cut = dirs.size() * 8 / 10;

    hwm::ProtocolDecoder decoder;
    std::vector<Sample> candidates;
    for (size_t bi = cut; bi < dirs.size(); ++bi) {
        auto init = decoder.decode_initial(read_file(dirs[bi] / "init.txt"), dirs[bi].filename().string());
        auto state = init.state;
        for (const auto& chunk : split_turns(read_file(dirs[bi] / "turns0.txt"))) {
            auto step = decoder.decode_update(state, payload(chunk));
            state = std::move(step.state);
            if (!state.protocol_ready || !state.recommendation_safe || state.phase == hwm::Phase::Finished ||
                state.side_to_act != hwm::Side::Player || !state.active_entity_uid) {
                continue;
            }
            const auto* actor = state.entity(state.active_entity_uid);
            if (!actor || (!include_heroes && actor->is_hero)) continue;
            if (!hwm::validate(state).empty()) continue;
            candidates.push_back({state});
        }
    }
    const auto samples = stratified_sample(candidates, limit);

    hwm::GenericSimulator simulator;
    uint64_t ok_low = 0, ok_high = 0, valid_low = 0, valid_high = 0;
    uint64_t invalid_low = 0, invalid_high = 0, illegal_best_high = 0, state_hash_mismatch_high = 0;
    uint64_t nonfinite_high = 0, illegal_alternatives_high = 0;
    uint64_t stable_exact = 0, stable_type = 0, total_nodes_low = 0, total_nodes_high = 0;
    double ms_low = 0, ms_high = 0, p_low = 0, p_high = 0, ability_risk = 0;
    std::set<std::string> sampled_battles;

    for (size_t i = 0; i < samples.size(); ++i) {
        const auto& state = samples[i].state;
        sampled_battles.insert(state.battle_id);
        const auto legal = simulator.legal_actions(state);
        if (legal.empty()) {
            ++invalid_low;
            ++invalid_high;
            continue;
        }
        hwm::PlannerConfig lc;
        lc.simulation_budget = low;
        lc.max_depth = 8;
        lc.self_top_k = 12;
        lc.seed = 12345 + static_cast<uint32_t>(i);
        lc.time_budget_ms = 0;
        hwm::PlannerConfig hc = lc;
        hc.simulation_budget = high;
        hwm::Planner pl(lc), ph(hc);
        const auto a = pl.plan(state);
        const auto b = ph.plan(state);
        const auto ca = check_recommendation(state, a, legal);
        const auto cb = check_recommendation(state, b, legal);
        if (a.status == "ok") {
            ++ok_low;
            ms_low += a.elapsed_ms;
            total_nodes_low += a.nodes;
            p_low += a.best.p_win;
            ability_risk += a.ability_risk;
        }
        if (b.status == "ok") {
            ++ok_high;
            ms_high += b.elapsed_ms;
            total_nodes_high += b.nodes;
            p_high += b.best.p_win;
        }
        valid_low += ca.valid;
        valid_high += cb.valid;
        invalid_low += !ca.valid;
        invalid_high += !cb.valid;
        state_hash_mismatch_high += b.status == "ok" && !cb.state_hash_ok;
        illegal_best_high += b.status == "ok" && !cb.best_legal;
        illegal_alternatives_high += b.status == "ok" && !cb.alternatives_legal;
        nonfinite_high += b.status == "ok" && !cb.finite_metrics;
        if (ca.valid && cb.valid) {
            stable_type += a.best.action.type == b.best.action.type;
            stable_exact += same_action(a.best.action, b.best.action);
        }
    }

    const auto div = [](double a, double b) { return b ? a / b : 0.0; };
    const auto comparable = std::min(valid_low, valid_high);
    std::cout << "{\"heldout_battles\":" << (dirs.size() - cut)
              << ",\"eligible_states\":" << candidates.size()
              << ",\"sampled_states\":" << samples.size()
              << ",\"sampled_battles\":" << sampled_battles.size()
              << ",\"include_heroes\":" << (include_heroes ? "true" : "false")
              << ",\"low_budget\":" << low << ",\"high_budget\":" << high
              << ",\"low_ok\":" << ok_low << ",\"high_ok\":" << ok_high
              << ",\"low_valid_recommendations\":" << valid_low
              << ",\"high_valid_recommendations\":" << valid_high
              << ",\"low_invalid_recommendations\":" << invalid_low
              << ",\"high_invalid_recommendations\":" << invalid_high
              << ",\"high_state_hash_mismatch\":" << state_hash_mismatch_high
              << ",\"high_illegal_best\":" << illegal_best_high
              << ",\"high_illegal_alternatives\":" << illegal_alternatives_high
              << ",\"high_nonfinite_metrics\":" << nonfinite_high
              << ",\"action_type_stability\":" << div(stable_type, comparable)
              << ",\"exact_action_stability\":" << div(stable_exact, comparable)
              << ",\"low_avg_ms\":" << div(ms_low, ok_low)
              << ",\"high_avg_ms\":" << div(ms_high, ok_high)
              << ",\"low_avg_nodes\":" << div(total_nodes_low, ok_low)
              << ",\"high_avg_nodes\":" << div(total_nodes_high, ok_high)
              << ",\"low_avg_p_win\":" << div(p_low, ok_low)
              << ",\"high_avg_p_win\":" << div(p_high, ok_high)
              << ",\"avg_ability_risk\":" << div(ability_risk, ok_low) << "}\n";

    return samples.empty() || samples.size() < std::min(limit, candidates.size()) ||
                   valid_high != samples.size() || invalid_high != 0
               ? 1
               : 0;
}
