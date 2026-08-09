#include "hwm/phantom_forces_model.hpp"
#include "hwm/assets.hpp"
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <sstream>

namespace hwm {
namespace {
std::vector<std::string> split(const std::string&s){std::vector<std::string>o;std::stringstream ss(s);std::string x;while(std::getline(ss,x,','))o.push_back(x);return o;}
char side_key(const Entity&e){return e.side==Side::Player?'P':'E';}
}
PhantomForcesModel::PhantomForcesModel(){const char*p=std::getenv("HWM_PHANTOM_FORCES_MODEL");if(p&&*p)load(p);else load(resolve_asset("models/phantom_forces_model.csv"));}
PhantomForcesModel::PhantomForcesModel(const std::string&path){load(path);}
bool PhantomForcesModel::load(const std::string&path){
    std::ifstream f(path);if(!f)return false;std::string line;std::getline(f,line);placements_.clear();atb_.clear();size_t n=0;
    while(std::getline(f,line)){
        auto c=split(line);if(c.size()<6)continue;
        try{
            if(c[0]=="placement"){
                Placement p;p.side=c[1].empty()?'*':c[1][0];p.footprint=std::stoi(c[2]);p.dx=std::stoi(c[3]);p.dy=std::stoi(c[4]);p.weight=std::stod(c[5]);
                if(p.weight>0){placements_.push_back(p);++n;}
            }else if(c[0]=="atb"){
                Atb a;a.side=c[1].empty()?'*':c[1][0];a.footprint=std::stoi(c[2]);a.value=std::stod(c[5]);atb_.push_back(a);
                if(a.side=='*')fallback_atb_=a.value;
            }
        }catch(...){continue;}
    }
    loaded_=n>0;return loaded_;
}
Cell PhantomForcesModel::choose_anchor(const Entity&source,const std::vector<Cell>&candidates,double roll)const{
    if(candidates.empty())return source.anchor;
    const char sk=side_key(source);const int fp=std::max(source.footprint_w,source.footprint_h);
    std::vector<double>w(candidates.size(),0.05);double z=0;
    for(size_t i=0;i<candidates.size();++i){
        const int dx=candidates[i].x-source.anchor.x,dy=candidates[i].y-source.anchor.y;
        for(const auto&p:placements_)if(p.side==sk&&p.footprint==fp&&p.dx==dx&&p.dy==dy)w[i]+=p.weight;
        z+=w[i];
    }
    if(z<=0)return candidates[std::min(candidates.size()-1,(size_t)std::floor(std::clamp(roll,0.0,0.999999)*candidates.size()))];
    double u=std::clamp(roll,0.0,1.0)*z,acc=0;
    for(size_t i=0;i<candidates.size();++i){acc+=w[i];if(u<=acc)return candidates[i];}
    return candidates.back();
}
double PhantomForcesModel::predict_atb(const Entity&source)const{
    const char sk=side_key(source);const int fp=std::max(source.footprint_w,source.footprint_h);
    for(const auto&a:atb_)if(a.side==sk&&a.footprint==fp)return a.value;
    return fallback_atb_;
}
}
