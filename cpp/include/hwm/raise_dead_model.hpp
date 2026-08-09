#pragma once
#include "hwm/state.hpp"
#include <cstdint>
#include <string>
#include <unordered_map>

namespace hwm {
class RaiseDeadModel {
public:
    RaiseDeadModel();
    explicit RaiseDeadModel(const std::string& path);
    bool load(const std::string& path);
    bool loaded() const { return loaded_; }
    double predict(const Entity& actor, const SpellSpec& spell) const;
private:
    double intercept_=0, log_count_=0, log_max_count_=0, attack_100_=0, defense_100_=0;
    double log_mana_=0, log_spell_effect_=0, log_spell_secondary_=0, multi_unit_=0;
    double conservative_factor_=0.95;
    std::unordered_map<uint32_t,double> cid_bias_;
    bool loaded_=false;
};
}
