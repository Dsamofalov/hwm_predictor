#include "hwm/damage_model.hpp"
#include "hwm/assets.hpp"

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <vector>

namespace hwm {
namespace {
std::vector<std::string> split(const std::string&s){std::vector<std::string>o;std::stringstream ss(s);std::string x;while(std::getline(ss,x,','))o.push_back(x);return o;}
ActionType parse_type(const std::string&s){if(s=="MELEE_ATTACK")return ActionType::MeleeAttack;if(s=="RANGED_ATTACK")return ActionType::RangedAttack;return ActionType::Unknown;}
}

DamageModel::DamageModel(){const char*p=std::getenv("HWM_DAMAGE_MODEL");if(p&&*p)load(p);else load(resolve_asset("models/damage_model.csv"));}
DamageModel::DamageModel(const std::string&p){load(p);}
uint64_t DamageModel::key(uint32_t cid,ActionType t){return (uint64_t(static_cast<uint8_t>(t))<<32)|cid;}

bool DamageModel::load(const std::string&path){
    std::ifstream f(path);if(!f)return false;std::string line;std::getline(f,line);size_t n=0;rows_.clear();samples_.clear();
    while(std::getline(f,line)){
        auto c=split(line);if(c.size()<4)continue;ActionType t=parse_type(c[0]);if(t==ActionType::Unknown)continue;
        try{uint32_t cid=static_cast<uint32_t>(std::stoul(c[1]));int samples=c.size()>2?std::max(0,std::stoi(c[2])):0;double m=std::clamp(std::stod(c[3]),0.05,20.0);const auto k=key(cid,t);rows_[k]=m;samples_[k]=samples;++n;}catch(...){continue;}
    }
    loaded_=n>0;return loaded_;
}

double DamageModel::multiplier(uint32_t cid,ActionType t)const{
    if(t!=ActionType::MeleeAttack&&t!=ActionType::RangedAttack)return 1.0;
    auto it=rows_.find(key(cid,t));if(it!=rows_.end())return it->second;
    // For a creature ID absent from training, the exact mechanics are safer than
    // a global residual learned from the historical creature mix. Ability-level
    // transfer (if available) is applied separately by the simulator.
    return 1.0;
}
int DamageModel::sample_count(uint32_t cid,ActionType t)const{
    auto it=samples_.find(key(cid,t));return it==samples_.end()?0:it->second;
}

}
