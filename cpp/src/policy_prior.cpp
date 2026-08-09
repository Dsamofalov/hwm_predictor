#include "hwm/policy_prior.hpp"
#include "hwm/assets.hpp"
#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <numeric>
#include <sstream>

namespace hwm {
PolicyPriorTable::PolicyPriorTable(){const char* p=std::getenv("HWM_POLICY_PRIOR");if(p&&*p)load(p);else load(resolve_asset("models/policy_priors.csv"));}
PolicyPriorTable::PolicyPriorTable(const std::string&p){load(p);}
uint64_t PolicyPriorTable::key(Side s,uint32_t c){return (uint64_t(static_cast<uint8_t>(s))<<32)|c;}
int PolicyPriorTable::type_index(ActionType t){switch(t){case ActionType::Move:return 0;case ActionType::MeleeAttack:return 1;case ActionType::RangedAttack:return 2;case ActionType::Wait:return 3;case ActionType::Defend:return 4;case ActionType::HeroAction:return 5;case ActionType::Cast:return 6;case ActionType::Ability:return 7;default:return -1;}}
bool PolicyPriorTable::load(const std::string&path){std::ifstream f(path);if(!f)return false;std::string line;std::getline(f,line);size_t n=0;while(std::getline(f,line)){std::stringstream ss(line);std::string cell;std::vector<std::string> cols;while(std::getline(ss,cell,','))cols.push_back(cell);if(cols.size()<12)continue;Side side=cols[0]=="PLAYER"?Side::Player:(cols[0]=="PVE"?Side::Pve:Side::Unknown);uint32_t cid=0;try{cid=static_cast<uint32_t>(std::stoul(cols[1]));}catch(...){continue;}Dist d{};bool ok=true;for(int i=0;i<9;++i){try{d[i]=std::stod(cols[3+i]);}catch(...){ok=false;break;}}if(ok){rows_[key(side,cid)]=d;++n;}}loaded_=n>0;return loaded_;}
double PolicyPriorTable::type_probability(const BattleState&s,ActionType t)const{int idx=type_index(t);if(idx<0)return 0.01;auto* actor=s.entity(s.active_entity_uid);Side side=actor?actor->side:s.side_to_act;uint32_t cid=actor?actor->creature_id:0;auto it=rows_.find(key(side,cid));if(it==rows_.end())it=rows_.find(key(side,0));if(it==rows_.end()){static Dist fallback{.15,.25,.20,.08,.05,.10,.05,.07,.05};return fallback[idx];}return std::max(1e-6,it->second[idx]);}
std::vector<double> PolicyPriorTable::action_priors(const BattleState&s,const std::vector<Action>&actions)const{std::vector<double> p(actions.size(),0.0);std::array<int,11> counts{};for(auto&a:actions)counts[static_cast<int>(a.type)]++;for(size_t i=0;i<actions.size();++i){int c=std::max(1,counts[static_cast<int>(actions[i].type)]);p[i]=type_probability(s,actions[i].type)/c;}double z=std::accumulate(p.begin(),p.end(),0.0);if(z<=0)std::fill(p.begin(),p.end(),1.0/std::max<size_t>(1,p.size()));else for(auto&x:p)x/=z;return p;}
}
