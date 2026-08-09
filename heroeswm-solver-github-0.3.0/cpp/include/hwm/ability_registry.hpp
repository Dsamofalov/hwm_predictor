#pragma once
#include "hwm/state.hpp"
#include <cstdint>
#include <string>
#include <unordered_map>
namespace hwm {
class AbilityRegistry {
public:
    AbilityRegistry();
    explicit AbilityRegistry(const std::string& path);
    bool load(const std::string& path);
    [[nodiscard]] bool loaded() const { return loaded_; }
    [[nodiscard]] double risk_for(uint32_t ability_id) const;
    [[nodiscard]] double state_risk(const BattleState& state) const;
private:
    std::unordered_map<uint32_t,double> risk_;
    bool loaded_=false;
};
}
