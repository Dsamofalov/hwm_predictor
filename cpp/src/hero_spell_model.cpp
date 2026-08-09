#include "hwm/hero_spell_model.hpp"
#include "hwm/assets.hpp"
#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <sstream>

namespace hwm {
HeroSpellDamageModel::HeroSpellDamageModel(){
    const char* p=std::getenv("HWM_HERO_SPELL_DAMAGE");
    if(p&&*p) load(p); else load(resolve_asset("models/hero_spell_damage.csv"));
}
HeroSpellDamageModel::HeroSpellDamageModel(const std::string& path){ load(path); }

bool HeroSpellDamageModel::load(const std::string& path){
    rows_.clear(); loaded_=false; std::ifstream f(path); if(!f) return false;
    std::string line; std::getline(f,line);
    while(std::getline(f,line)){
        std::stringstream ss(line); std::string cell; std::vector<std::string> c;
        while(std::getline(ss,cell,',')) c.push_back(cell);
        if(c.size()<7) continue;
        Row r; r.scope=c[0];
        try{
            r.spell_id=static_cast<uint32_t>(std::stoul(c[1]));
            r.actor_creature_id=static_cast<uint32_t>(std::stoul(c[3]));
            r.target_creature_id=static_cast<uint32_t>(std::stoul(c[4]));
            r.median_damage=std::stod(c[6]);
        }catch(...){continue;}
        rows_.push_back(std::move(r));
    }
    loaded_=!rows_.empty(); return loaded_;
}

double HeroSpellDamageModel::predict(uint32_t spell_id,uint32_t actor_cid,uint32_t target_cid) const{
    const char* scopes[]={"SAT","SA","ST","S"};
    for(const char* scope:scopes){
        for(const auto&r:rows_){
            if(r.scope!=scope||r.spell_id!=spell_id) continue;
            if(r.scope=="SAT" && (r.actor_creature_id!=actor_cid||r.target_creature_id!=target_cid)) continue;
            if(r.scope=="SA" && r.actor_creature_id!=actor_cid) continue;
            if(r.scope=="ST" && r.target_creature_id!=target_cid) continue;
            return std::max(1.0,r.median_damage);
        }
    }
    return 1.0;
}
bool HeroSpellDamageModel::target_conditioned(uint32_t spell_id,uint32_t actor_cid,uint32_t target_cid) const{
    for(const auto&r:rows_){
        if(r.spell_id!=spell_id) continue;
        if(r.scope=="SAT" && r.actor_creature_id==actor_cid && r.target_creature_id==target_cid) return true;
        if(r.scope=="ST" && r.target_creature_id==target_cid) return true;
    }
    return false;
}

}
