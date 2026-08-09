#pragma once
#include "hwm/action.hpp"
#include "hwm/state.hpp"
#include <cstdint>
#include <string>
#include <unordered_map>

namespace hwm {
// Regularized ability-level damage residual learned after exact mechanics and
// the creature-specific residual.  The same ability can therefore transfer a
// numeric correction to rare creature IDs without changing legal actions.
class AbilityDamageModel {
public:
    AbilityDamageModel();
    explicit AbilityDamageModel(const std::string& path);
    bool load(const std::string& path);
    [[nodiscard]] bool loaded() const { return loaded_; }
    [[nodiscard]] double multiplier(const Entity& attacker,const Entity& defender,ActionType type) const;
private:
    static uint64_t key(uint32_t ability_id,ActionType type,bool target_role);
    std::unordered_map<uint64_t,double> log_coef_;
    bool loaded_=false;
};
}
