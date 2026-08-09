#include "hwm/proc_model.hpp"
#include "hwm/assets.hpp"
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <sstream>
namespace hwm { namespace {
std::vector<std::string> split(const std::string&s,char delim=','){std::vector<std::string>v;std::stringstream ss(s);std::string x;while(std::getline(ss,x,delim))v.push_back(x);return v;}
bool effect_of(const std::string&s,ProcEffect&out){if(s=="root")out=ProcEffect::Root;else if(s=="ferocious_wound")out=ProcEffect::FerociousWound;else if(s=="blind")out=ProcEffect::Blind;else if(s=="torpor")out=ProcEffect::Torpor;else if(s=="stun_delay")out=ProcEffect::StunDelay;else if(s=="suffering")out=ProcEffect::Suffering;else if(s=="stone")out=ProcEffect::Stone;else if(s=="atb_delay")out=ProcEffect::AtbDelay;else return false;return true;}
double stack_hp(const Entity&e){if(!e.alive||e.count<=0)return 0;return std::max(0,e.count-1)*std::max(1,e.max_hp_per_unit)+std::max(1,e.top_unit_hp);}
bool parse_vec(const std::string&s,std::array<double,ProcRule::K>&out){auto v=split(s,'|');if(v.size()!=ProcRule::K)return false;for(std::size_t i=0;i<v.size();++i)try{out[i]=std::stod(v[i]);}catch(...){return false;}return true;}
}
ProcModel::ProcModel(){const char*p=std::getenv("HWM_PROC_MODEL");if(p&&*p)load(p);else load(resolve_asset("models/proc_model.csv"));}
ProcModel::ProcModel(const std::string&p){load(p);}
bool ProcModel::load(const std::string&path){std::ifstream f(path);if(!f)return false;std::string line;std::getline(f,line);rules_.clear();while(std::getline(f,line)){auto c=split(line);if(c.size()<12)continue;try{if(std::stoi(c[11])==0)continue;ProcEffect e;if(!effect_of(c[2],e))continue;ProcRule r;r.code=c[0];r.ability_id=stable_ability_id(c[0]);r.effect=e;r.probability=std::clamp(std::stod(c[6]),0.0,1.0);
        if(c.size()>=17&&c[12]=="logistic"){r.conditional=true;r.intercept=std::stod(c[13]);if(!parse_vec(c[14],r.mean)||!parse_vec(c[15],r.scale)||!parse_vec(c[16],r.coef))continue;for(double&x:r.scale)if(std::abs(x)<1e-12)x=1.0;}
        if(c[1].find("MELEE_ATTACK")!=std::string::npos){r.action_type=ActionType::MeleeAttack;rules_.push_back(r);}if(c[1].find("RANGED_ATTACK")!=std::string::npos){r.action_type=ActionType::RangedAttack;rules_.push_back(r);}}catch(...){continue;}}loaded_=!rules_.empty();return loaded_;}
std::vector<ProcRule> ProcModel::rules_for(const Entity&a,ActionType t)const{std::vector<ProcRule>out;for(const auto&r:rules_)if(r.action_type==t&&has_ability(a,r.code))out.push_back(r);return out;}
double ProcModel::probability_for(const ProcRule&r,const Entity&a,const Entity&t)const{
    if(r.effect==ProcEffect::StunDelay&&has_ability(t,"mechanical"))return 0.0;
    if(!r.conditional)return r.probability;
    const std::array<double,ProcRule::K>x{
        std::log1p(std::max(1.0,stack_hp(a))),std::log1p(std::max(1.0,stack_hp(t))),
        std::log1p(std::max(1,a.count)),std::log1p(std::max(1,t.count)),
        double(a.attack),double(t.defense),double(a.speed),double(t.speed),t.is_big?1.0:0.0};
    double z=r.intercept;for(std::size_t i=0;i<ProcRule::K;++i)z+=r.coef[i]*(x[i]-r.mean[i])/r.scale[i];
    if(z>=0){const double q=std::exp(-std::min(z,50.0));return 1.0/(1.0+q);}const double q=std::exp(std::max(z,-50.0));return q/(1.0+q);
}
}
