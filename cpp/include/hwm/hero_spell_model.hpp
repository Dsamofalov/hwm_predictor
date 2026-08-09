#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace hwm {
class HeroSpellDamageModel {
public:
    HeroSpellDamageModel();
    explicit HeroSpellDamageModel(const std::string& path);
    bool load(const std::string& path);
    bool loaded() const { return loaded_; }
    double predict(uint32_t spell_id, uint32_t actor_creature_id, uint32_t target_creature_id) const;
    bool target_conditioned(uint32_t spell_id, uint32_t actor_creature_id, uint32_t target_creature_id) const;
private:
    struct Row { std::string scope; uint32_t spell_id=0, actor_creature_id=0, target_creature_id=0; double median_damage=1.0; };
    std::vector<Row> rows_;
    bool loaded_=false;
};
}
