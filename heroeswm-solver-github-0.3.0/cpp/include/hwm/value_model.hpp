#pragma once
#include "hwm/state.hpp"
#include <array>
#include <string>
namespace hwm {
class LinearValueModel {
public:
    LinearValueModel();
    explicit LinearValueModel(const std::string& path);
    bool load(const std::string& path);
    bool loaded() const { return loaded_; }
    double p_win(const BattleState& s, Side perspective=Side::Player) const;
    double utility(const BattleState& s, Side perspective=Side::Player) const { return 2.0*p_win(s,perspective)-1.0; }
private:
    std::array<double,14> mean_{},scale_{},coef_{};double intercept_=0;bool loaded_=false;
};
}
