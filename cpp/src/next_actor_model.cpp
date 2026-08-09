#include "hwm/next_actor_model.hpp"
#include "hwm/assets.hpp"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <numeric>
#include <sstream>

namespace hwm {
namespace {
std::vector<std::string> split(const std::string& s) {
    std::vector<std::string> out; std::stringstream ss(s); std::string x;
    while (std::getline(ss,x,',')) out.push_back(x);
    return out;
}

}

NextActorModel::NextActorModel() {
    const char* p=std::getenv("HWM_NEXT_ACTOR_MODEL");
    if (p && *p) load(p); else load(resolve_asset("models/next_actor.csv"));
}
NextActorModel::NextActorModel(const std::string& p) { load(p); }

bool NextActorModel::load(const std::string& path) {
    std::ifstream f(path); if (!f) return false;
    std::string line; std::getline(f,line); // header
    bool have_mean=false,have_scale=false,have_coef=false,have_intercept=false;
    while (std::getline(f,line)) {
        auto c=split(line); if (c.empty()) continue;
        if (c[0]=="intercept") {
            if (c.size()<2) return false;
            try { intercept_=std::stod(c[1]); have_intercept=true; } catch (...) { return false; }
            continue;
        }
        if (c.size()<K+1) continue;
        auto* dst = c[0]=="mean" ? &mean_ : (c[0]=="scale" ? &scale_ : (c[0]=="coef" ? &coef_ : nullptr));
        if (!dst) continue;
        for (std::size_t i=0;i<K;++i) { try { (*dst)[i]=std::stod(c[i+1]); } catch (...) { return false; } }
        if (c[0]=="mean") have_mean=true; else if(c[0]=="scale")have_scale=true; else have_coef=true;
    }
    for (double& x:scale_) if(std::abs(x)<1e-12)x=1.0;
    loaded_=have_mean&&have_scale&&have_coef&&have_intercept; return loaded_;
}

double NextActorModel::score(const BattleState& s, const Entity& e, const Entity& current, ActionType current_action) const {
    if (!e.alive) return -1e30;
    const uint64_t next_seq=s.decision_seq+1;
    const double recency=e.last_acted_seq>0 ? double(next_seq-e.last_acted_seq) : 25.0;
    const std::array<double,K> x{
        double(effective_initiative(e))/30.0,
        double(e.atb)/100.0,
        double(effective_speed(e))/20.0,
        std::min(recency,30.0)/30.0,
        std::log1p(std::max(0,e.count))/8.0,
        e.is_hero?1.0:0.0,
        e.side==Side::Player?1.0:0.0,
        e.side==current.side?1.0:0.0,
        e.uid==current.uid?1.0:0.0,
        current_action==ActionType::Wait?1.0:0.0,
        double(effective_initiative(e)-effective_initiative(current))/30.0,
        double(e.atb-current.atb)/100.0,
        (effect_magnitude(e,"proc_shieldbash")>0.0f||effect_magnitude(e,"proc_warding")>0.0f)?1.0:0.0,
    };
    if (!loaded_) {
        // Better fallback than uid round-robin: initiative + recency pressure.
        return 0.7*std::min(recency,30.0)/30.0 + 0.3*double(effective_initiative(e))/30.0 - (e.uid==current.uid?0.4:0.0);
    }
    double z=intercept_;
    for(std::size_t i=0;i<K;++i) z+=coef_[i]*(x[i]-mean_[i])/scale_[i];
    return z;
}

std::vector<std::pair<uint64_t,double>> NextActorModel::probabilities(
    const BattleState& s, const Entity& current, ActionType current_action) const {
    std::vector<std::pair<uint64_t,double>> out;
    double maxz=-1e300;
    for (const auto& e:s.entities) if(e.alive) { const double z=score(s,e,current,current_action); out.push_back({e.uid,z}); maxz=std::max(maxz,z); }
    double sum=0;
    for(auto& p:out){p.second=std::exp(std::clamp(p.second-maxz,-50.0,50.0));sum+=p.second;}
    if(sum>0)for(auto& p:out)p.second/=sum;
    return out;
}

uint64_t NextActorModel::choose(const BattleState& s, const Entity& current, ActionType current_action) const {
    uint64_t best=0; double best_score=-1e300;
    for(const auto& e:s.entities) if(e.alive){double z=score(s,e,current,current_action);if(z>best_score){best_score=z;best=e.uid;}}
    return best;
}

} // namespace hwm
