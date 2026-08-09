#pragma once
#include "hwm/action.hpp"
#include "hwm/state.hpp"
#include <array>
#include <cstdint>
#include <string>
#include <vector>
namespace hwm {
enum class ProcEffect : uint8_t { Root=0, FerociousWound=1, Blind=2, Torpor=3, StunDelay=4, Suffering=5, Stone=6, AtbDelay=7 };
struct ProcRule {
    static constexpr std::size_t K=9;
    uint32_t ability_id=0; std::string code; ActionType action_type=ActionType::Unknown;
    ProcEffect effect=ProcEffect::Root; double probability=0; bool conditional=false;
    double intercept=0; std::array<double,K> mean{},scale{},coef{};
};
class ProcModel {
public:
    ProcModel(); explicit ProcModel(const std::string& path);
    bool load(const std::string& path); [[nodiscard]] bool loaded() const { return loaded_; }
    [[nodiscard]] std::vector<ProcRule> rules_for(const Entity& attacker, ActionType type) const;
    [[nodiscard]] double probability_for(const ProcRule& rule,const Entity& attacker,const Entity& target) const;
private:
    std::vector<ProcRule> rules_; bool loaded_=false;
};
}
