#include "hwm/detail/planner_tree.hpp"
#include "hwm/planner.hpp"

#include <cstdlib>
#include <iostream>

using namespace hwm;
using namespace hwm::detail;

#define CHECK(expr) do { if (!(expr)) { std::cerr << "CHECK failed: " #expr << " at " << __FILE__ << ':' << __LINE__ << '\n'; return EXIT_FAILURE; } } while (0)

static BattleState planner_fixture(std::string battle_id) {
    BattleState s;
    s.battle_id=std::move(battle_id); s.state_seq=1; s.phase=Phase::Combat; s.width=12; s.height=10;
    s.protocol_ready=true; s.recommendation_safe=true;
    Entity a; a.uid=1; a.creature_id=10; a.side=Side::Player; a.anchor={1,1}; a.count=10; a.max_count=10;
    a.top_unit_hp=20; a.max_hp_per_unit=20; a.attack=10; a.defense=8; a.min_damage=2; a.max_damage=4; a.speed=4; a.shots=3; a.is_shooter=true;
    Entity b=a; b.uid=2; b.side=Side::Pve; b.anchor={5,1}; b.count=8; b.max_count=8; b.shots=0; b.is_shooter=false;
    s.entities={a,b}; s.active_entity_uid=1; s.side_to_act=Side::Player;
    return s;
}

int main() {
    SearchGraph graph;
    auto [root, root_created] = graph.acquire("root");
    CHECK(root_created); CHECK(root != nullptr);
    SearchEdge stochastic_edge; stochastic_edge.action.action_id=1; stochastic_edge.action.actor_uid=7; stochastic_edge.action.type=ActionType::MeleeAttack;
    auto [low, low_created]=graph.acquire("damage-low"); CHECK(low_created); low->initialized=true; SearchEdge low_legal; low_legal.action.type=ActionType::Wait; low->edges.push_back(std::move(low_legal));
    auto [low_outcome, low_bound]=graph.bind(stochastic_edge,"damage-low",*low); CHECK(low_bound); ++low_outcome->visits;
    auto [high, high_created]=graph.acquire("damage-high"); CHECK(high_created); high->initialized=true; SearchEdge high_legal; high_legal.action.type=ActionType::Defend; high->edges.push_back(std::move(high_legal));
    auto [high_outcome, high_bound]=graph.bind(stochastic_edge,"damage-high",*high); CHECK(high_bound); ++high_outcome->visits; ++high_outcome->visits;
    CHECK(stochastic_edge.outcomes.size()==2); CHECK(low_outcome->child!=high_outcome->child); CHECK(low->edges.front().action.type==ActionType::Wait); CHECK(high->edges.front().action.type==ActionType::Defend); CHECK(stochastic_edge.modal_child()==high);
    auto [low_again, duplicate_created]=graph.acquire("damage-low"); CHECK(!duplicate_created); CHECK(low_again==low); SearchEdge sibling_edge; sibling_edge.action.action_id=2; sibling_edge.action.type=ActionType::RangedAttack;
    auto [transposed, transposed_bound]=graph.bind(sibling_edge,"damage-low",*low_again); CHECK(transposed_bound); CHECK(transposed->child==low);
    auto [same_outcome,rebound]=graph.bind(stochastic_edge,"damage-low",*low_again); CHECK(!rebound); CHECK(same_outcome==low_outcome); CHECK(graph.size()==3);
    CHECK(graph.prune_to(*high)==1); CHECK(graph.find("damage-high")==high); CHECK(graph.find("damage-low")==nullptr); CHECK(graph.find("root")==nullptr);

    // Enemy expansion is defined by cumulative policy mass, independently from the
    // player's top-K cap. The input is sorted by descending prior, as planner nodes are.
    std::vector<SearchEdge> opponent_edges(5);
    opponent_edges[0].prior=0.55; opponent_edges[1].prior=0.30; opponent_edges[2].prior=0.10;
    opponent_edges[3].prior=0.04; opponent_edges[4].prior=0.01;
    CHECK(probability_mass_limit(opponent_edges,0.80,32)==2);
    CHECK(probability_mass_limit(opponent_edges,0.98,32)==4);
    CHECK(probability_mass_limit(opponent_edges,1.00,32)==5);
    CHECK(probability_mass_limit(opponent_edges,0.99,3)==3);
    CHECK(probability_mass_limit(opponent_edges,0.00,32)==1);
    std::vector<SearchEdge> zero_prior_edges(3);
    CHECK(probability_mass_limit(zero_prior_edges,0.98,2)==2);

    // NextActorModel consumes (decision_seq + 1 - last_acted_seq) as a recency feature.
    // Two otherwise identical canonical states with different activation history therefore
    // have different future transition semantics and must never share a transposition node.
    auto scheduler_a=planner_fixture("scheduler-history");
    scheduler_a.decision_seq=10; scheduler_a.halfturn=10; scheduler_a.entities[0].last_acted_seq=3;
    auto scheduler_b=scheduler_a; scheduler_b.entities[0].last_acted_seq=4;
    const auto scheduler_hash_a=state_hash(scheduler_a);
    const auto scheduler_hash_b=state_hash(scheduler_b);
    CHECK(scheduler_hash_a!=scheduler_hash_b);
    SearchGraph history_graph;
    auto [history_a,history_a_created]=history_graph.acquire(scheduler_hash_a);
    auto [history_b,history_b_created]=history_graph.acquire(scheduler_hash_b);
    CHECK(history_a_created); CHECK(history_b_created); CHECK(history_a!=history_b); CHECK(history_graph.size()==2);

    // Effect.raw is wire/model provenance only. Transition semantics consume id,
    // duration and magnitude, so equivalent observed/modelled effects must share a
    // canonical hash even if their textual provenance differs. Semantic effect changes
    // must still split hashes.
    auto observed_effect=planner_fixture("effect-provenance");
    Effect fx; fx.id=status_effect_id("sff"); fx.duration=3; fx.magnitude=9.0f; fx.raw="Ssff001002...";
    observed_effect.entities[0].effects.push_back(fx);
    auto modeled_effect=observed_effect;
    modeled_effect.entities[0].effects[0].raw="modeled cursingattack weakness";
    CHECK(state_hash(observed_effect)==state_hash(modeled_effect));
    auto changed_effect=modeled_effect;
    changed_effect.entities[0].effects[0].duration=2;
    CHECK(state_hash(observed_effect)!=state_hash(changed_effect));
    SearchGraph effect_graph;
    auto [observed_node,observed_created]=effect_graph.acquire(state_hash(observed_effect));
    auto [modeled_node,modeled_created]=effect_graph.acquire(state_hash(modeled_effect));
    CHECK(observed_created); CHECK(!modeled_created); CHECK(observed_node==modeled_node); CHECK(effect_graph.size()==1);

    PlannerConfig cfg; cfg.simulation_budget=40; cfg.max_depth=3; cfg.self_top_k=6; cfg.seed=7; cfg.time_budget_ms=0;
    Planner planner(cfg); const auto state=planner_fixture("reuse-battle");
    const auto first=planner.plan(state); CHECK(first.status=="ok"); CHECK(!first.tree_reused); CHECK(first.simulations==40); CHECK(first.nodes>0);
    const auto second=planner.plan(state); CHECK(second.status=="ok"); CHECK(second.tree_reused); CHECK(second.reused_root_visits>=first.simulations); CHECK(second.retained_nodes>0);

    // Current global state_hash intentionally omits several static geometry/capability flags.
    // Persistent reuse therefore has an additional structure fingerprint and must reset even
    // when state_hash alone would collide on a legal-action-relevant static change.
    auto changed_structure=state; changed_structure.entities.front().is_flyer=true;
    CHECK(state_hash(changed_structure)==state_hash(state));
    const auto structure_reset=planner.plan(changed_structure); CHECK(structure_reset.status=="ok"); CHECK(!structure_reset.tree_reused); CHECK(structure_reset.reused_root_visits==0);

    auto other=state; other.battle_id="different-battle";
    const auto reset=planner.plan(other); CHECK(reset.status=="ok"); CHECK(!reset.tree_reused); CHECK(reset.reused_root_visits==0);
    std::cout << "planner stochastic-outcome/transposition/re-root/opponent-mass tests passed\n";
    return EXIT_SUCCESS;
}
