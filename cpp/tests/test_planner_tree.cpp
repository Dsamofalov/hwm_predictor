#include "hwm/detail/planner_tree.hpp"

#include <cstdlib>
#include <iostream>

using namespace hwm;
using namespace hwm::detail;

#define CHECK(expr) do { if (!(expr)) { std::cerr << "CHECK failed: " #expr << " at " << __FILE__ << ':' << __LINE__ << '\n'; return EXIT_FAILURE; } } while (0)

int main() {
    SearchGraph graph;
    auto [root, root_created] = graph.acquire("root");
    CHECK(root_created);
    CHECK(root != nullptr);

    // One stochastic action can lead to two different canonical states.  The edge must
    // retain both outcome bindings instead of reusing the first sampled child node.
    SearchEdge stochastic_edge;
    stochastic_edge.action.action_id = 1;
    stochastic_edge.action.actor_uid = 7;
    stochastic_edge.action.type = ActionType::MeleeAttack;

    auto [low, low_created] = graph.acquire("damage-low");
    CHECK(low_created);
    low->initialized = true;
    SearchEdge low_legal;
    low_legal.action.type = ActionType::Wait;
    low->edges.push_back(std::move(low_legal));
    auto [low_outcome, low_bound] = graph.bind(stochastic_edge, "damage-low", *low);
    CHECK(low_bound);
    ++low_outcome->visits;

    auto [high, high_created] = graph.acquire("damage-high");
    CHECK(high_created);
    high->initialized = true;
    SearchEdge high_legal;
    high_legal.action.type = ActionType::Defend;
    high->edges.push_back(std::move(high_legal));
    auto [high_outcome, high_bound] = graph.bind(stochastic_edge, "damage-high", *high);
    CHECK(high_bound);
    ++high_outcome->visits;
    ++high_outcome->visits;

    CHECK(stochastic_edge.outcomes.size() == 2);
    CHECK(low_outcome->child != high_outcome->child);
    CHECK(low_outcome->child->hash == "damage-low");
    CHECK(high_outcome->child->hash == "damage-high");

    // The second outcome keeps its own legal-action set.  It must never inherit the
    // node initialized from the first sampled outcome.
    CHECK(low->edges.size() == 1);
    CHECK(high->edges.size() == 1);
    CHECK(low->edges.front().action.type == ActionType::Wait);
    CHECK(high->edges.front().action.type == ActionType::Defend);
    CHECK(stochastic_edge.modal_child() == high);

    // Equal canonical state hashes are true transpositions: acquiring the same hash
    // returns the exact same node, including when reached through another action edge.
    auto [low_again, duplicate_created] = graph.acquire("damage-low");
    CHECK(!duplicate_created);
    CHECK(low_again == low);
    SearchEdge sibling_edge;
    sibling_edge.action.action_id = 2;
    sibling_edge.action.type = ActionType::RangedAttack;
    auto [transposed, transposed_bound] = graph.bind(sibling_edge, "damage-low", *low_again);
    CHECK(transposed_bound);
    CHECK(transposed->child == low);

    // Re-observing the same outcome on the original edge reuses its binding too.
    auto [same_outcome, rebound] = graph.bind(stochastic_edge, "damage-low", *low_again);
    CHECK(!rebound);
    CHECK(same_outcome == low_outcome);
    CHECK(graph.size() == 3);  // root + two distinct stochastic states

    std::cout << "planner stochastic-outcome/transposition tests passed\n";
    return EXIT_SUCCESS;
}
