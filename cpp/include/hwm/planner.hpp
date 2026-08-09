#pragma once
#include "hwm/simulator.hpp"
#include "hwm/policy_prior.hpp"
#include "hwm/value_model.hpp"
#include <chrono>
namespace hwm {
struct Candidate{Action action; double score=0,p_win=0,uncertainty=0; uint64_t visits=0;};
struct Recommendation{std::string status="ok",state_hash; Candidate best; std::vector<Candidate> alternatives; std::vector<Action> pv; uint64_t simulations=0,nodes=0; double elapsed_ms=0; double ability_risk=0; std::vector<std::string>warnings;};
struct PlannerConfig{uint64_t simulation_budget=5000; int max_depth=12; int self_top_k=12; double c_puct=1.4; uint32_t seed=1; uint64_t time_budget_ms=0; double risk_lambda=0.15;};
class Planner{
public: explicit Planner(PlannerConfig cfg={}); Recommendation plan(const BattleState& root,Side perspective=Side::Player) const;
private: PlannerConfig cfg_; GenericSimulator sim_; PolicyPriorTable prior_; LinearValueModel value_;
};
}
