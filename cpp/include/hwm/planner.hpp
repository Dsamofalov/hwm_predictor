#pragma once
#include "hwm/simulator.hpp"
#include "hwm/policy_prior.hpp"
#include "hwm/value_model.hpp"
#include "hwm/detail/planner_tree.hpp"
#include <chrono>
#include <functional>
#include <mutex>
#include <string>
namespace hwm {
struct Candidate{Action action; double score=0,p_win=0,uncertainty=0; uint64_t visits=0;};
struct Recommendation{
    std::string status="ok",state_hash;
    Candidate best;
    std::vector<Candidate> alternatives;
    std::vector<Action> pv;
    uint64_t simulations=0,nodes=0;
    double elapsed_ms=0;
    double ability_risk=0;
    bool tree_reused=false;
    uint64_t reused_root_visits=0,retained_nodes=0;
    std::vector<std::string>warnings;
};
struct PlannerConfig{uint64_t simulation_budget=5000; int max_depth=12; int self_top_k=12; double c_puct=1.4; uint32_t seed=1; uint64_t time_budget_ms=0; double risk_lambda=0.15; uint64_t cancellation_poll_interval=16; std::function<bool()> cancellation_requested;};
class Planner{
public:
    explicit Planner(PlannerConfig cfg={});
    Recommendation plan(const BattleState& root,Side perspective=Side::Player,std::function<bool()> cancellation_requested={}) const;
private:
    PlannerConfig cfg_;
    GenericSimulator sim_;
    PolicyPriorTable prior_;
    LinearValueModel value_;
    mutable std::mutex search_mutex_;
    mutable detail::SearchGraph graph_;
    mutable std::string graph_battle_id_;
    mutable Side graph_perspective_=Side::Unknown;
    mutable uint64_t graph_structure_fingerprint_=0;
};
}
