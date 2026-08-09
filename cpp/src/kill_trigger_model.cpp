#include "hwm/kill_trigger_model.hpp"
#include "hwm/assets.hpp"
#include "hwm/state.hpp"
#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <sstream>
namespace hwm { namespace {
std::vector<std::string> split_csv(const std::string&s){std::vector<std::string>v;std::stringstream ss(s);std::string x;while(std::getline(ss,x,','))v.push_back(x);return v;}
}
KillTriggerModel::KillTriggerModel(){const char*p=std::getenv("HWM_KILL_TRIGGER_MODEL");if(p&&*p)load(p);else load(resolve_asset("models/kill_trigger_model.csv"));}
KillTriggerModel::KillTriggerModel(const std::string&path){load(path);}
bool KillTriggerModel::load(const std::string&path){
    std::ifstream f(path);if(!f)return false;std::string line;std::getline(f,line);rules_.clear();
    while(std::getline(f,line)){
        const auto c=split_csv(line);if(c.size()<11)continue;
        try{
            KillTriggerRule r;r.code=c[0];r.ability_id=stable_ability_id(r.code);
            r.probability=std::clamp(std::stod(c[4]),0.0,1.0); // train-only probability
            r.increment=std::max(1,std::stoi(c[9]));r.enabled=std::stoi(c[10])!=0;
            if(r.enabled)rules_.push_back(std::move(r));
        }catch(...){continue;}
    }
    loaded_=!rules_.empty();return loaded_;
}
const KillTriggerRule* KillTriggerModel::rule(std::string_view code) const{
    const auto id=stable_ability_id(code);for(const auto&r:rules_)if(r.ability_id==id)return &r;return nullptr;
}
}
