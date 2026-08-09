#include "hwm/ability_damage_model.hpp"
#include "hwm/assets.hpp"
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <vector>
namespace hwm { namespace {
std::vector<std::string> split(const std::string&s){std::vector<std::string>v;std::stringstream ss(s);std::string x;while(std::getline(ss,x,','))v.push_back(x);return v;}
ActionType parse_type(const std::string&s){if(s=="MELEE_ATTACK")return ActionType::MeleeAttack;if(s=="RANGED_ATTACK")return ActionType::RangedAttack;return ActionType::Unknown;}
}
AbilityDamageModel::AbilityDamageModel(){const char*p=std::getenv("HWM_ABILITY_DAMAGE_MODEL");if(p&&*p)load(p);else load(resolve_asset("models/ability_damage_model.csv"));}
AbilityDamageModel::AbilityDamageModel(const std::string&p){load(p);}
uint64_t AbilityDamageModel::key(uint32_t id,ActionType t,bool target){return (uint64_t(target)<<63)|(uint64_t(static_cast<uint8_t>(t))<<32)|id;}
bool AbilityDamageModel::load(const std::string&path){
 std::ifstream f(path);if(!f)return false;std::string line;std::getline(f,line);log_coef_.clear();size_t n=0;
 while(std::getline(f,line)){auto c=split(line);if(c.size()<6)continue;ActionType t=parse_type(c[0]);if(t==ActionType::Unknown)continue;bool target=c[1]=="target";if(!target&&c[1]!="actor")continue;
  try{const uint32_t id=stable_ability_id(c[2]);const double logc=std::clamp(std::stod(c[4]),-0.50,0.50);log_coef_[key(id,t,target)]=logc;++n;}catch(...){continue;}}
 loaded_=n>0;return loaded_;
}
double AbilityDamageModel::multiplier(const Entity&attacker,const Entity&defender,ActionType t)const{
 if(!loaded_||(t!=ActionType::MeleeAttack&&t!=ActionType::RangedAttack))return 1.0;
 double logm=0;
 for(auto id:attacker.ability_ids){auto it=log_coef_.find(key(id,t,false));if(it!=log_coef_.end())logm+=it->second;}
 for(auto id:defender.ability_ids){auto it=log_coef_.find(key(id,t,true));if(it!=log_coef_.end())logm+=it->second;}
 // Multiple correlated tags occur on the same creature. Keep this transfer layer
 // deliberately bounded so search cannot exploit a sparse coefficient stack.
 return std::exp(std::clamp(logm,-0.60,0.60));
}
}
