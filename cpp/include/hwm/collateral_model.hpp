#pragma once
#include "hwm/action.hpp"
#include "hwm/state.hpp"
#include <cstdint>
#include <optional>
#include <string>
#include <vector>
namespace hwm {
enum class CollateralZone : uint8_t { Behind=0, ActorAdjacent=1, TargetAdjacent=2 };
struct CollateralRule { uint32_t ability_id=0; ActionType action_type=ActionType::Unknown; CollateralZone zone=CollateralZone::Behind; int max_secondary=0; double probability=0; std::string code; };
class CollateralModel {
public:
    CollateralModel(); explicit CollateralModel(const std::string& path);
    bool load(const std::string& path); [[nodiscard]] bool loaded() const { return loaded_; }
    [[nodiscard]] std::optional<CollateralRule> rule_for(const Entity& attacker,ActionType type) const;
private: std::vector<CollateralRule> rules_; bool loaded_=false;
};
}
