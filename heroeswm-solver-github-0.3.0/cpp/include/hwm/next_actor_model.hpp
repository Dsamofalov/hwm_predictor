#pragma once

#include "hwm/action.hpp"
#include "hwm/state.hpp"

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace hwm {

// Lightweight candidate ranker learned from raw C<uid> activation sequences.
// It is used only for speculative rollouts. Observed live turn order is always
// authoritative and comes from ProtocolDecoder.
class NextActorModel {
public:
    NextActorModel();
    explicit NextActorModel(const std::string& path);

    bool load(const std::string& path);
    [[nodiscard]] bool loaded() const { return loaded_; }
    [[nodiscard]] double score(const BattleState& state, const Entity& candidate,
                               const Entity& current, ActionType current_action) const;
    [[nodiscard]] uint64_t choose(const BattleState& state, const Entity& current,
                                  ActionType current_action) const;
    [[nodiscard]] std::vector<std::pair<uint64_t,double>> probabilities(
        const BattleState& state, const Entity& current, ActionType current_action) const;

private:
    static constexpr std::size_t K = 13;
    std::array<double,K> mean_{};
    std::array<double,K> scale_{};
    std::array<double,K> coef_{};
    double intercept_ = 0.0;
    bool loaded_ = false;
};

} // namespace hwm
