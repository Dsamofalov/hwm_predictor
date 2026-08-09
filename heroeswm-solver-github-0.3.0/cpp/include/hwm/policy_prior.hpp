#pragma once
#include "hwm/action.hpp"
#include <array>
#include <string>
#include <unordered_map>
#include <vector>

namespace hwm {
class PolicyPriorTable {
public:
    PolicyPriorTable();
    explicit PolicyPriorTable(const std::string& csv_path);
    bool load(const std::string& csv_path);
    bool loaded() const { return loaded_; }
    double type_probability(const BattleState& state, ActionType type) const;
    std::vector<double> action_priors(const BattleState& state, const std::vector<Action>& actions) const;
private:
    using Dist=std::array<double,9>;
    static int type_index(ActionType t);
    static uint64_t key(Side side,uint32_t creature_id);
    std::unordered_map<uint64_t,Dist> rows_;
    bool loaded_=false;
};
}
