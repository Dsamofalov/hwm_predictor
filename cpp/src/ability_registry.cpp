#include "hwm/ability_registry.hpp"
#include "hwm/assets.hpp"
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <vector>
namespace hwm { namespace {
std::vector<std::string> split(const std::string&s){std::vector<std::string>v;std::stringstream ss(s);std::string x;while(std::getline(ss,x,','))v.push_back(x);return v;}
double hp(const Entity&e){if(!e.alive||e.is_hero||e.count<=0)return 0.0;return double(e.count-1)*std::max(1,e.max_hp_per_unit)+std::max(0,e.top_unit_hp);}
}
AbilityRegistry::AbilityRegistry(){const char*p=std::getenv("HWM_ABILITY_REGISTRY");if(p&&*p)load(p);else load(resolve_asset("data/catalog/ability_registry.csv"));}
AbilityRegistry::AbilityRegistry(const std::string&p){load(p);}
bool AbilityRegistry::load(const std::string&path){std::ifstream f(path);if(!f)return false;std::string line;std::getline(f,line);risk_.clear();size_t n=0;while(std::getline(f,line)){auto c=split(line);if(c.size()<4)continue;try{uint32_t id=static_cast<uint32_t>(std::stoul(c[0]));double r=std::clamp(std::stod(c[3]),0.0,1.0);risk_[id]=r;++n;}catch(...){continue;}}loaded_=n>0;return loaded_;}
double AbilityRegistry::risk_for(uint32_t id)const{if(!loaded_)return 0.35;auto it=risk_.find(id);return it==risk_.end()?0.85:it->second;}
double AbilityRegistry::state_risk(const BattleState&s)const{
 const uint32_t caster_id=stable_ability_id("caster");
 double weighted=0,total=0;
 for(const auto&e:s.entities){
  if(!e.alive||e.is_hero||e.is_hidden||e.ability_ids.empty())continue;
  double er=0.0; bool caster=false;
  for(auto id:e.ability_ids){
   if(id==caster_id){caster=true;continue;} // evaluated from the authoritative per-stack spellbook below
   const double r=risk_for(id);er=1.0-(1.0-er)*(1.0-0.45*r);
  }
  if(caster){
   double spell_risk=0.60;
   if(!e.spells.empty()){
    size_t supported=0;
    for(const auto&sp:e.spells){
     // Non-hero rollout currently has exact/validated transitions for direct damage
     // and Raise Dead.  Status/phantom/summon families remain uncertainty until
     // their creature-caster duration/target semantics are held-out validated.
     if(sp.direct_damage||sp.effect_kind==SpellEffectKind::RaiseDead)++supported;
    }
    const double unsupported=1.0-double(supported)/double(e.spells.size());
    spell_risk=std::clamp(0.10+0.75*unsupported,0.10,0.85);
   }
   er=1.0-(1.0-er)*(1.0-0.45*spell_risk);
  }
  er=std::clamp(er,0.0,1.0);
  const double power=std::max(1.0,hp(e))*(1.0+0.01*std::max(0.0f,e.attack)+0.005*std::max(0.0f,e.defense));weighted+=power*er;total+=power;
 }
 return total>0?std::clamp(weighted/total,0.0,1.0):0.0;
}
}
