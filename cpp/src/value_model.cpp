#include "hwm/value_model.hpp"
#include "hwm/assets.hpp"
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <vector>
namespace hwm {
namespace {
std::vector<std::string> split(const std::string&s){std::vector<std::string>v;std::stringstream ss(s);std::string x;while(std::getline(ss,x,','))v.push_back(x);return v;}
double total_hp(const Entity&e){if(!e.alive||e.is_hero||e.count<=0)return 0;return double(e.count-1)*std::max(1,e.max_hp_per_unit)+std::max(0,e.top_unit_hp);}
std::array<double,14> features(const BattleState&s,Side perspective){struct A{double hp=0,cnt=0,dmg=0,atk=0,def=0,spd=0,ini=0,stacks=0,shoot=0,mana=0;};A a,b;auto add=[&](A&z,const Entity&e){if(e.is_hero){z.mana+=e.mana;return;}z.hp+=total_hp(e);z.cnt+=std::max(0,e.count);z.dmg+=std::max(0,e.count)*(effective_min_damage(e)+effective_max_damage(e))/2.0;z.atk+=effective_attack(s,e);z.def+=effective_defense(s,e);z.spd+=e.speed;z.ini+=effective_initiative(e);z.stacks+=1;z.shoot+=(e.shots>0);};for(auto&e:s.entities)if(e.alive){if(e.side==perspective)add(a,e);else if(e.side!=Side::Unknown)add(b,e);}auto avg=[](double x,double n){return x/std::max(1.0,n);};a.atk=avg(a.atk,a.stacks);a.def=avg(a.def,a.stacks);a.spd=avg(a.spd,a.stacks);a.ini=avg(a.ini,a.stacks);b.atk=avg(b.atk,b.stacks);b.def=avg(b.def,b.stacks);b.spd=avg(b.spd,b.stacks);b.ini=avg(b.ini,b.stacks);double eps=1;double actor_player=s.side_to_act==perspective?1.0:0.0;return {std::log((a.hp+eps)/(b.hp+eps)),std::log((a.cnt+eps)/(b.cnt+eps)),std::log((a.dmg+eps)/(b.dmg+eps)),(a.atk-b.atk)/100.0,(a.def-b.def)/100.0,(a.spd-b.spd)/20.0,(a.ini-b.ini)/30.0,(a.stacks-b.stacks)/10.0,(a.shoot-b.shoot)/10.0,(a.mana-b.mana)/100.0,actor_player,std::log1p(double(s.halfturn))/5.0,std::log1p(a.hp)/15.0,std::log1p(b.hp)/15.0};}
}
LinearValueModel::LinearValueModel(){const char*p=std::getenv("HWM_VALUE_MODEL");if(p&&*p)load(p);else load(resolve_asset("models/value_linear.csv"));}
LinearValueModel::LinearValueModel(const std::string&p){load(p);}
bool LinearValueModel::load(const std::string&path){std::ifstream f(path);if(!f)return false;std::string line;std::getline(f,line);while(std::getline(f,line)){auto c=split(line);if(c.empty())continue;if(c[0]=="intercept"&&c.size()>1){try{intercept_=std::stod(c[1]);}catch(...){return false;}continue;}if(c.size()<15)continue;auto* dst=c[0]=="mean"?&mean_:(c[0]=="scale"?&scale_:(c[0]=="coef"?&coef_:nullptr));if(!dst)continue;for(int i=0;i<14;++i){try{(*dst)[i]=std::stod(c[i+1]);}catch(...){return false;}}}for(auto&x:scale_)if(std::abs(x)<1e-12)x=1;loaded_=true;return true;}
double LinearValueModel::p_win(const BattleState&s,Side perspective)const{if(!loaded_)return .5;auto x=features(s,perspective);double z=intercept_;for(int i=0;i<14;++i)z+=coef_[i]*(x[i]-mean_[i])/scale_[i];if(z>=0){double e=std::exp(-z);return 1.0/(1.0+e);}double e=std::exp(z);return e/(1.0+e);}
}
