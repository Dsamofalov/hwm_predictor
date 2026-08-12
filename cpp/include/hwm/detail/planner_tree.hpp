#pragma once
#include "hwm/action.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace hwm::detail {

struct SearchNode;

struct SearchOutcome {
    SearchNode* child = nullptr;
    uint64_t visits = 0;
};

struct SearchEdge {
    Action action;
    double prior = 0.0;
    double sum = 0.0;
    double sum_sq = 0.0;
    uint64_t visits = 0;
    std::unordered_map<std::string, SearchOutcome> outcomes;
    std::vector<double> root_returns;

    double q() const { return visits ? sum / static_cast<double>(visits) : 0.0; }
    double sd() const {
        if (visits < 2) return 1.0;
        const double mean = q();
        return std::sqrt(std::max(0.0, sum_sq / static_cast<double>(visits) - mean * mean));
    }

    SearchNode* modal_child() const {
        const SearchOutcome* best = nullptr;
        for (const auto& [hash, outcome] : outcomes) {
            (void)hash;
            if (!outcome.child) continue;
            if (!best || outcome.visits > best->visits) best = &outcome;
        }
        return best ? best->child : nullptr;
    }
};

inline size_t probability_mass_limit(const std::vector<SearchEdge>& edges, double target_mass, size_t hard_cap = 0) {
    if (edges.empty()) return 0;
    const size_t cap = hard_cap ? std::min(hard_cap, edges.size()) : edges.size();
    if (cap == 0) return 0;
    const double target = std::clamp(target_mass, 0.0, 1.0);
    if (target <= 0.0) return 1;
    double total = 0.0;
    for (const auto& edge : edges) total += std::max(0.0, edge.prior);
    if (total <= 0.0) return cap;
    const double threshold = target * total;
    double cumulative = 0.0;
    for (size_t i = 0; i < cap; ++i) {
        cumulative += std::max(0.0, edges[i].prior);
        if (cumulative + 1e-12 >= threshold) return i + 1;
    }
    return cap;
}

struct SearchNode {
    std::string hash;
    uint64_t visits = 0;
    bool initialized = false;
    std::vector<SearchEdge> edges;
};

class SearchGraph {
public:
    SearchNode* find(std::string_view hash) const {
        const auto it = nodes_.find(std::string(hash));
        return it == nodes_.end() ? nullptr : it->second.get();
    }

    std::pair<SearchNode*, bool> acquire(std::string hash) {
        if (auto it = nodes_.find(hash); it != nodes_.end()) return {it->second.get(), false};
        auto node = std::make_unique<SearchNode>();
        node->hash = hash;
        SearchNode* ptr = node.get();
        nodes_.emplace(std::move(hash), std::move(node));
        return {ptr, true};
    }

    std::pair<SearchOutcome*, bool> bind(SearchEdge& edge, const std::string& hash, SearchNode& node) {
        auto [it, inserted] = edge.outcomes.try_emplace(hash, SearchOutcome{&node, 0});
        if (!inserted && it->second.child != &node) {
            throw std::logic_error("planner outcome hash rebound to a different transposition node");
        }
        return {&it->second, inserted};
    }

    size_t prune_to(SearchNode& root) {
        std::unordered_set<SearchNode*> reachable;
        std::vector<SearchNode*> pending{&root};
        while (!pending.empty()) {
            SearchNode* node = pending.back();
            pending.pop_back();
            if (!node || !reachable.insert(node).second) continue;
            for (auto& edge : node->edges) {
                for (auto& [hash, outcome] : edge.outcomes) {
                    (void)hash;
                    if (outcome.child) pending.push_back(outcome.child);
                }
            }
        }
        for (auto it = nodes_.begin(); it != nodes_.end();) {
            if (!reachable.contains(it->second.get())) it = nodes_.erase(it);
            else ++it;
        }
        return nodes_.size();
    }

    void clear() { nodes_.clear(); }
    size_t size() const { return nodes_.size(); }

private:
    std::unordered_map<std::string, std::unique_ptr<SearchNode>> nodes_;
};

}  // namespace hwm::detail
