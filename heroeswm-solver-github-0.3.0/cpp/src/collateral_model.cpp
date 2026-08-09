#include "hwm/collateral_model.hpp"
#include "hwm/assets.hpp"
#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <vector>
namespace hwm { namespace {
std::vector<std::string> split(const std::string&s){std::vector<std::string>v;std::stringstream ss(s);std::string x;while(std::getline(ss,x,','))v.push_back(x);return v;}
ActionType type_of(const std::string&s){if(s=="MELEE_ATTACK")return ActionType::MeleeAttack;if(s=="RANGED_ATTACK")return ActionType::RangedAttack;return ActionType::Unknown;}
std::optional<CollateralZone> zone_of(const std::string&s){if(s=="behind")return CollateralZone::Behind;if(s=="actor_adjacent")return CollateralZone::ActorAdjacent;if(s=="target_adjacent")return CollateralZone::TargetAdjacent;return std::nullopt;}
}
CollateralModel::CollateralModel(){const char*p=std::getenv("HWM_COLLATERAL_MODEL");if(p&&*p)load(p);else load(resolve_asset("models/collateral_model.csv"));}
CollateralModel::CollateralModel(const std::string&p){load(p);}
bool CollateralModel::load(const std::string&path){std::ifstream f(path);if(!f)return false;std::string line;std::getline(f,line);rules_.clear();while(std::getline(f,line)){auto c=split(line);if(c.size()<7)continue;auto t=type_of(c[1]);auto z=zone_of(c[2]);if(t==ActionType::Unknown||!z)continue;try{if(std::stoi(c[4])==0)continue;CollateralRule r;r.code=c[0];r.ability_id=stable_ability_id(c[0]);r.action_type=t;r.zone=*z;r.max_secondary=std::max(0,std::stoi(c[3]));r.probability=std::clamp(std::stod(c[6]),0.0,1.0);rules_.push_back(std::move(r));}catch(...){continue;}}loaded_=!rules_.empty();return loaded_;}
std::optional<CollateralRule> CollateralModel::rule_for(const Entity&a,ActionType t)const{const CollateralRule*best=nullptr;for(const auto&r:rules_){if(r.action_type!=t||std::find(a.ability_ids.begin(),a.ability_ids.end(),r.ability_id)==a.ability_ids.end())continue;if(!best||r.probability>best->probability)best=&r;}return best?std::optional<CollateralRule>(*best):std::nullopt;}
}
