#pragma once

#include "hwm/action.hpp"
#include <cstdint>
#include <string>
#include <unordered_map>

namespace hwm {

// Robust multiplicative residual learned from observed raw DAMAGE records. The
// generic attack/defence formula remains the base model; this table compensates
// systematic creature/action effects in speculative rollouts only.
class DamageModel {
public:
    DamageModel();
    explicit DamageModel(const std::string& path);
    bool load(const std::string& path);
    [[nodiscard]] bool loaded() const { return loaded_; }
    [[nodiscard]] double multiplier(uint32_t creature_id, ActionType type) const;
    [[nodiscard]] int sample_count(uint32_t creature_id, ActionType type) const;
private:
    static uint64_t key(uint32_t creature_id, ActionType type);
    std::unordered_map<uint64_t,double> rows_;
    std::unordered_map<uint64_t,int> samples_;
    bool loaded_=false;
};

} // namespace hwm
