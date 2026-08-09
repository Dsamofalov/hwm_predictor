#include "hwm/raise_dead_model.hpp"
#include "hwm/assets.hpp"
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <vector>

namespace hwm {
namespace {
std::vector<std::string> split(const std::string&s){std::vector<std::string>o;std::stringstream ss(s);std::string x;while(std::getline(ss,x,','))o.push_back(x);return o;}
}
RaiseDeadModel::RaiseDeadModel(){const char*p=std::getenv("HWM_RAISE_DEAD_MODEL");if(p&&*p)load(p);else load(resolve_asset("models/raise_dead_model.csv"));}
RaiseDeadModel::RaiseDeadModel(const std::string&path){load(path);}
bool RaiseDeadModel::load(const std::string&path){
    std::ifstream f(path);if(!f)return false;std::string line;std::getline(f,line);cid_bias_.clear();size_t n=0;
    while(std::getline(f,line)){
        auto c=split(line);if(c.size()<3)continue;double v=0;try{v=std::stod(c[2]);}catch(...){continue;}
        if(c[0]=="coef"){
            if(c[1]=="intercept")intercept_=v;else if(c[1]=="log_count")log_count_=v;else if(c[1]=="log_max_count")log_max_count_=v;
            else if(c[1]=="attack_100")attack_100_=v;else if(c[1]=="defense_100")defense_100_=v;else if(c[1]=="log_mana")log_mana_=v;
            else if(c[1]=="log_spell_effect")log_spell_effect_=v;else if(c[1]=="log_spell_secondary")log_spell_secondary_=v;else if(c[1]=="multi_unit")multi_unit_=v;
            ++n;
        }else if(c[0]=="cid"){
            try{cid_bias_[static_cast<uint32_t>(std::stoul(c[1]))]=v;}catch(...){continue;}
        }else if(c[0]=="meta"&&c[1]=="conservative_factor")conservative_factor_=std::clamp(v,0.1,1.0);
    }
    loaded_=n>=9;return loaded_;
}
double RaiseDeadModel::predict(const Entity& a,const SpellSpec& sp)const{
    if(!loaded_) return std::max(1.0,(double)sp.magnitude);
    double z=intercept_ + log_count_*std::log1p(std::max(0,a.count)) + log_max_count_*std::log1p(std::max(0,a.max_count))
        + attack_100_*(a.attack/100.0) + defense_100_*(a.defense/100.0) + log_mana_*std::log1p(std::max(0,a.mana))
        + log_spell_effect_*std::log1p(std::max(0.0f,sp.magnitude)) + log_spell_secondary_*std::log1p(std::max(0.0f,sp.secondary))
        + multi_unit_*(a.count>1?1.0:0.0);
    if(auto it=cid_bias_.find(a.creature_id);it!=cid_bias_.end())z+=it->second;
    return std::max(1.0,std::exp(std::clamp(z,-5.0,20.0))*conservative_factor_);
}
}
