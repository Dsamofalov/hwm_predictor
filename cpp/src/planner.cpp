#include "hwm/planner.hpp"

#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <numeric>
#include <random>
#include <string_view>

namespace hwm {
namespace {
using Node = detail::SearchNode;
using Edge = detail::SearchEdge;

double cvar10(const std::vector<double>& v, double fallback) {
    if (v.empty()) return fallback;
    auto x = v;
    std::sort(x.begin(), x.end());
    const size_t n = std::max<size_t>(1, (x.size() + 9) / 10);
    return std::accumulate(x.begin(), x.begin() + n, 0.0) / static_cast<double>(n);
}

size_t widening_limit(const Node& n, size_t total, int hard_top_k) {
    if (total <= 4) return total;
    const size_t dynamic = 4 + static_cast<size_t>(2.0 * std::sqrt(static_cast<double>(n.visits + 1)));
    const size_t cap = hard_top_k > 0 ? std::max<size_t>(4, static_cast<size_t>(hard_top_k)) : total;
    return std::min(total, std::min(cap, dynamic));
}

uint64_t search_structure_fingerprint(const BattleState& s) {
    uint64_t h=1469598103934665603ULL;
    const auto mix=[&](uint64_t v){h^=v+0x9e3779b97f4a7c15ULL+(h<<6)+(h>>2);};
    const auto mf=[&](float v){uint32_t u=0;std::memcpy(&u,&v,sizeof(u));mix(u);};
    mix(s.protocol_version); mix(s.ruleset_version); mix(static_cast<uint64_t>(s.min_x+0x10000)); mix(static_cast<uint64_t>(s.min_y+0x10000)); mix(s.width); mix(s.height);
    auto blocked=s.blocked;
    std::sort(blocked.begin(),blocked.end(),[](const Cell&a,const Cell&b){return a.x==b.x?a.y<b.y:a.x<b.x;});
    for(const auto&c:blocked){mix(static_cast<uint64_t>(c.x+0x10000));mix(static_cast<uint64_t>(c.y+0x10000));}
    std::vector<const Entity*> entities; entities.reserve(s.entities.size());
    for(const auto&e:s.entities)entities.push_back(&e);
    std::sort(entities.begin(),entities.end(),[](const Entity*a,const Entity*b){return a->uid<b->uid;});
    for(const auto*ep:entities){
        const auto&e=*ep;
        mix(e.uid);mix(e.creature_id);mix(static_cast<uint64_t>(e.owner+0x10000));mix(static_cast<uint64_t>(e.side));
        mix(e.footprint_w);mix(e.footprint_h);mix(e.is_hero);mix(e.is_big);mix(e.is_flyer);mix(e.is_shooter);mix(e.is_warmachine);mix(e.is_statix);mix(e.shoot_only);mix(e.double_shoot);mix(e.unlimited_retaliation);mix(e.no_retaliation);mix(e.no_range_penalty);mix(e.no_melee_penalty);
        for(const auto&sp:e.spells){mix(sp.id);mf(sp.secondary);}
    }
    return h;
}
}  // namespace

Planner::Planner(PlannerConfig c) : cfg_(std::move(c)), prior_(), value_() {}

Recommendation Planner::plan(const BattleState& root, Side perspective, std::function<bool()> cancellation_requested) const {
    const auto started = std::chrono::steady_clock::now();
    Recommendation rec;
    rec.state_hash = state_hash(root);
    const auto cancelled = [&]() {
        return (cancellation_requested && cancellation_requested()) ||
               (cfg_.cancellation_requested && cfg_.cancellation_requested());
    };
    if (cancelled()) {
        rec.status = "cancelled";
        rec.warnings.push_back("planning cancelled before search because observed session revision changed");
        return rec;
    }
    if (!root.protocol_ready) {
        rec.status = "not_ready";
        rec.warnings.push_back("protocol state is not structurally ready for planning");
        return rec;
    }
    const char* degraded_env = std::getenv("HWM_ALLOW_SEMANTIC_DEGRADED");
    const bool allow_degraded = degraded_env && (std::string_view(degraded_env) == "1" || std::string_view(degraded_env) == "true");
    if (!root.recommendation_safe && !allow_degraded) {
        rec.status = "not_ready";
        rec.warnings.push_back("state contains semantically unresolved battle mechanics; strict planning is blocked (set HWM_ALLOW_SEMANTIC_DEGRADED=1 only for research/shadow mode)");
        return rec;
    }
    if (root.semantic_unresolved_records > 0) {
        const std::string_view tier = semantic_safety_tier(root);
        if (tier == "guarded") rec.warnings.push_back("GUARDED semantic state: a small fraction of mechanics is unresolved; confidence is risk-adjusted");
        else if (tier == "degraded") rec.warnings.push_back("DEGRADED semantic state: recommendation uses approximate state for some buffs/effects/mechanics; uncertainty penalty applied");
        else rec.warnings.push_back("SEMANTIC BLOCK: state contains unresolved mechanics above the configured safety gate");
    }

    auto root_legal = sim_.legal_actions(root);
    if (root_legal.empty()) {
        rec.status = "not_ready";
        rec.warnings.push_back("No legal basic actions for canonical state");
        return rec;
    }

    std::unique_lock graph_lock(search_mutex_);
    if (cancelled()) {
        rec.status = "cancelled";
        rec.warnings.push_back("planning cancelled while waiting for the persistent search tree");
        return rec;
    }

    const uint64_t structure_fingerprint=search_structure_fingerprint(root);
    Node* tree = nullptr;
    if (!root.battle_id.empty() && graph_battle_id_ == root.battle_id && graph_perspective_ == perspective && graph_structure_fingerprint_ == structure_fingerprint) {
        tree = graph_.find(rec.state_hash);
    }
    if (tree) {
        rec.tree_reused = true;
        rec.reused_root_visits = tree->visits;
        rec.retained_nodes = graph_.prune_to(*tree);
    } else {
        graph_.clear();
        graph_battle_id_ = root.battle_id;
        graph_perspective_ = perspective;
        graph_structure_fingerprint_ = structure_fingerprint;
        auto acquired = graph_.acquire(rec.state_hash);
        tree = acquired.first;
    }

    std::mt19937 rng(cfg_.seed);
    std::uniform_real_distribution<double> roll(0.0, 1.0);

    auto init_node = [&](Node& node, const BattleState& s) {
#ifndef NDEBUG
        assert(node.hash == state_hash(s));
#endif
        if (node.initialized) return;
        auto actions = sim_.legal_actions(s);
        auto pri = prior_.action_priors(s, actions);
        std::vector<size_t> order(actions.size());
        std::iota(order.begin(), order.end(), 0);
        std::stable_sort(order.begin(), order.end(), [&](size_t a, size_t b) { return pri[a] > pri[b]; });
        for (const auto i : order) {
            Edge e;
            e.action = actions[i];
            e.prior = pri[i];
            node.edges.push_back(std::move(e));
        }
        node.initialized = true;
    };

    std::function<double(Node&, BattleState, int, bool)> simulate;
    simulate = [&](Node& node, BattleState s, int depth, bool is_root) -> double {
        if (depth >= cfg_.max_depth || s.phase == Phase::Finished) {
            return value_.loaded() ? value_.utility(s, perspective) : sim_.heuristic_value(s, perspective);
        }
        init_node(node, s);
        if (node.edges.empty()) return value_.loaded() ? value_.utility(s, perspective) : sim_.heuristic_value(s, perspective);

        const bool opponent_turn = s.side_to_act != Side::Unknown &&
            (perspective == Side::Unknown ? s.side_to_act == Side::Pve : s.side_to_act != perspective);
        const int hard_top_k = opponent_turn ? cfg_.opponent_top_k : cfg_.self_top_k;
        const size_t expansion_total = opponent_turn
            ? detail::probability_mass_limit(
                node.edges,
                cfg_.opponent_probability_mass,
                cfg_.opponent_top_k > 0 ? static_cast<size_t>(cfg_.opponent_top_k) : 0)
            : node.edges.size();
        const size_t lim = widening_limit(node, expansion_total, hard_top_k);
        size_t pick = 0;
        if (opponent_turn) {
            double z = 0.0;
            for (size_t i = 0; i < lim; ++i) z += node.edges[i].prior;
            const double u = std::generate_canonical<double, 32>(rng) * std::max(1e-12, z);
            double acc = 0.0;
            for (size_t i = 0; i < lim; ++i) {
                acc += node.edges[i].prior;
                if (u <= acc) { pick = i; break; }
            }
        } else {
            double best = -1e100;
            const double root_sqrt = std::sqrt(static_cast<double>(node.visits) + 1.0);
            for (size_t i = 0; i < lim; ++i) {
                auto& e = node.edges[i];
                const double q = e.q();
                const double u = cfg_.c_puct * e.prior * root_sqrt / (1.0 + static_cast<double>(e.visits));
                const double score = q + u;
                if (score > best) { best = score; pick = i; }
            }
        }

        auto& e = node.edges[pick];
        auto tr = sim_.apply(s, e.action, roll(rng));
        double value = 0.0;
        if (!tr.valid) value = -1.0;
        else if (tr.terminal) value = value_.loaded() ? value_.utility(tr.state, perspective) : sim_.heuristic_value(tr.state, perspective);
        else {
            const std::string outcome_hash = state_hash(tr.state);
            auto [child, child_created] = graph_.acquire(outcome_hash);
            (void)child_created;
            auto [outcome, outcome_created] = graph_.bind(e, outcome_hash, *child);
            (void)outcome_created;
            value = simulate(*child, std::move(tr.state), depth + 1, false);
            ++outcome->visits;
        }

        ++e.visits; e.sum += value; e.sum_sq += value * value; ++node.visits;
        if (is_root && e.root_returns.size() < 512) e.root_returns.push_back(value);
        return value;
    };

    uint64_t sims = 0;
    const uint64_t cancel_every = std::max<uint64_t>(1, cfg_.cancellation_poll_interval);
    for (; sims < cfg_.simulation_budget; ++sims) {
        if ((sims % cancel_every) == 0 && cancelled()) { rec.status = "cancelled"; break; }
        if (cfg_.time_budget_ms && sims > 0 &&
            std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - started).count() >= static_cast<long long>(cfg_.time_budget_ms)) break;
        simulate(*tree, root, 0, true);
    }
    if (rec.status == "cancelled") {
        rec.simulations = sims; rec.nodes = graph_.size();
        rec.elapsed_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - started).count();
        rec.warnings.push_back("observed session revision changed during search");
        return rec;
    }

    init_node(*tree, root);
    const double semantic_risk = std::clamp(root.semantic_unresolved_ratio, 0.0, 1.0);
    const double ability_risk = std::clamp(sim_.ability_risk(root), 0.0, 1.0);
    rec.ability_risk = ability_risk;
    std::vector<Candidate> cand;
    for (auto& e : tree->edges) {
        if (!e.visits) continue;
        const double q = e.q(), sd = e.sd(), tail = cvar10(e.root_returns, q);
        const double combined_uncertainty = std::min(1.0, std::sqrt(sd * sd + 0.25 * semantic_risk * semantic_risk + 0.36 * ability_risk * ability_risk));
        const double risk_score = 0.75 * q + 0.25 * tail - cfg_.risk_lambda * combined_uncertainty;
        const double raw_p = std::clamp(0.5 + 0.5 * q, 0.0, 1.0);
        const double confidence_scale = std::max(0.10, 1.0 - 1.75 * semantic_risk - 0.75 * ability_risk);
        const double calibrated_p = 0.5 + (raw_p - 0.5) * confidence_scale;
        cand.push_back({e.action, risk_score, std::clamp(calibrated_p, 0.0, 1.0), combined_uncertainty, e.visits});
    }
    if (cand.empty()) { rec.status = "not_ready"; rec.warnings.push_back("Search produced no visited action"); return rec; }
    std::sort(cand.begin(), cand.end(), [](const Candidate& a, const Candidate& b) { return a.visits != b.visits ? a.visits > b.visits : a.score > b.score; });
    rec.best = cand.front();
    for (size_t i = 1; i < cand.size() && i < 5; ++i) rec.alternatives.push_back(cand[i]);

    Node* n = tree;
    for (int d = 0; d < cfg_.max_depth && n && n->initialized && !n->edges.empty(); ++d) {
        auto it = std::max_element(n->edges.begin(), n->edges.end(), [](const auto& a, const auto& b) { return a.visits < b.visits; });
        if (it == n->edges.end() || !it->visits) break;
        rec.pv.push_back(it->action); n = it->modal_child();
    }

    rec.simulations = sims; rec.nodes = graph_.size();
    rec.elapsed_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - started).count();
    if (!prior_.loaded()) rec.warnings.push_back("learned policy-prior table not loaded; using fallback priors");
    if (!value_.loaded()) rec.warnings.push_back("learned linear value model not loaded; using heuristic leaves");
    if (!sim_.scheduler_loaded()) rec.warnings.push_back("learned next-actor scheduler not loaded; using initiative/recency fallback");
    if (!sim_.ability_registry_loaded()) rec.warnings.push_back("ability registry not loaded; unknown-perk risk is using conservative fallback");
    else if (ability_risk > 0.45) rec.warnings.push_back("high ability-mechanics uncertainty: important stacks contain perks that are not fully exact in speculative rollouts");
    else if (ability_risk > 0.20) rec.warnings.push_back("ability-mechanics uncertainty is included in risk-adjusted P(win)");
    if (!sim_.ability_damage_model_loaded()) rec.warnings.push_back("ability-conditioned damage residual not loaded; rare-perk transfer disabled");
    if (!sim_.collateral_model_loaded()) rec.warnings.push_back("collateral ability model not loaded; AoE/breath secondary-stack value is disabled");
    if (!sim_.proc_model_loaded()) rec.warnings.push_back("proc ability model not loaded; stochastic control/wound mechanics are disabled");
    if (auto* a = root.entity(root.active_entity_uid); a && a->is_hero) {
        if (!sim_.hero_spell_model_loaded()) rec.warnings.push_back("hero spell damage model not loaded; supported spell rollouts are low-confidence");
        rec.warnings.push_back("hero action space is partially exact: basic hit, WAIT/DEFEND, independently decoded direct/status spells, Raise Dead and Phantom Forces are supported; remaining faction/summon mechanics stay uncertainty-gated");
    }
    return rec;
}

}  // namespace hwm
