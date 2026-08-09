#pragma once
#include "hwm/state.hpp"
#include <string>
#include <vector>

namespace hwm {
class PhantomForcesModel {
public:
    PhantomForcesModel();
    explicit PhantomForcesModel(const std::string& path);
    bool load(const std::string& path);
    bool loaded() const { return loaded_; }
    Cell choose_anchor(const Entity& source,const std::vector<Cell>& candidates,double roll) const;
    double predict_atb(const Entity& source) const;
private:
    struct Placement { char side='*'; int footprint=1,dx=0,dy=0; double weight=0; };
    struct Atb { char side='*'; int footprint=0; double value=45.0; };
    std::vector<Placement> placements_;
    std::vector<Atb> atb_;
    double fallback_atb_=45.0;
    bool loaded_=false;
};
}
