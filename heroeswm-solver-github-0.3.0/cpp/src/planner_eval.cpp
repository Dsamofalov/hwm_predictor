#include "hwm/planner.hpp"
#include "hwm/protocol.hpp"
#include "hwm/state.hpp"

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

namespace fs=std::filesystem;
namespace {
std::string read_file(const fs::path&p){std::ifstream f(p,std::ios::binary);std::ostringstream s;s<<f.rdbuf();return s.str();}
bool digits(std::string_view s){return !s.empty()&&std::all_of(s.begin(),s.end(),[](unsigned char c){return std::isdigit(c);});}
struct Chunk{uint32_t turn=0;std::string body;};
std::vector<Chunk> split_turns(std::string_view p){
 struct Mark{size_t start=0,body=0;uint32_t turn=0;};std::vector<Mark>m;
 if(auto first=p.find("turns=>");first!=std::string_view::npos){size_t q=first+7,colon=p.find(':',q);if(colon!=std::string_view::npos&&digits(p.substr(q,colon-q)))m.push_back({first,colon+1,(uint32_t)std::stoul(std::string(p.substr(q,colon-q)))});}
 size_t pos=0;while((pos=p.find(";>",pos))!=std::string_view::npos){size_t q=pos+2,colon=p.find(':',q);if(colon==std::string_view::npos)break;if(digits(p.substr(q,colon-q)))m.push_back({pos,colon+1,(uint32_t)std::stoul(std::string(p.substr(q,colon-q)))});pos=colon+1;}
 std::sort(m.begin(),m.end(),[](auto&a,auto&b){return a.start<b.start;});std::vector<Chunk>out;for(size_t i=0;i<m.size();++i){size_t end=i+1<m.size()?m[i+1].start:p.size();if(end>m[i].body&&p[end-1]==';')--end;out.push_back({m[i].turn,std::string(p.substr(m[i].body,end-m[i].body))});}return out;
}
std::string payload(const Chunk&c){return "t=000turns=>"+std::to_string(c.turn)+":"+c.body;}
bool same_action(const hwm::Action&a,const hwm::Action&b){return a.type==b.type&&a.actor_uid==b.actor_uid&&a.target_uid==b.target_uid&&a.destination==b.destination;}
}

int main(int argc,char**argv){
 if(argc<2){std::cerr<<"usage: planner-eval <corpus-root-or-battles-dir> [limit=30] [low=300] [high=1200]\n";return 2;}
 fs::path root=argv[1];if(fs::is_directory(root/"battles"))root/="battles";size_t limit=argc>2?std::stoull(argv[2]):30;uint64_t low=argc>3?std::stoull(argv[3]):300,high=argc>4?std::stoull(argv[4]):1200;
 std::vector<fs::path>dirs;for(auto&de:fs::directory_iterator(root))if(de.is_directory()&&fs::exists(de.path()/"init.txt")&&fs::exists(de.path()/"turns0.txt"))dirs.push_back(de.path());std::sort(dirs.begin(),dirs.end(),[](auto&a,auto&b){return std::stoull(a.filename().string())<std::stoull(b.filename().string());});size_t cut=dirs.size()*8/10;
 hwm::ProtocolDecoder decoder;std::vector<hwm::BattleState>states;
 for(size_t bi=cut;bi<dirs.size()&&states.size()<limit;++bi){auto init=decoder.decode_initial(read_file(dirs[bi]/"init.txt"),dirs[bi].filename().string());auto s=init.state;for(auto&ch:split_turns(read_file(dirs[bi]/"turns0.txt"))){auto step=decoder.decode_update(s,payload(ch));s=std::move(step.state);if(states.size()>=limit)break;if(!s.protocol_ready||!s.recommendation_safe||s.phase==hwm::Phase::Finished||s.side_to_act!=hwm::Side::Player||!s.active_entity_uid)continue;auto*a=s.entity(s.active_entity_uid);if(!a||a->is_hero)continue;states.push_back(s);}}
 uint64_t ok_low=0,ok_high=0,stable_exact=0,stable_type=0,total_nodes_low=0,total_nodes_high=0;double ms_low=0,ms_high=0,p_low=0,p_high=0,ability_risk=0;
 for(size_t i=0;i<states.size();++i){hwm::PlannerConfig lc;lc.simulation_budget=low;lc.max_depth=8;lc.self_top_k=12;lc.seed=12345+i;lc.time_budget_ms=0;hwm::PlannerConfig hc=lc;hc.simulation_budget=high;hwm::Planner pl(lc),ph(hc);auto a=pl.plan(states[i]),b=ph.plan(states[i]);if(a.status=="ok"){++ok_low;ms_low+=a.elapsed_ms;total_nodes_low+=a.nodes;p_low+=a.best.p_win;ability_risk+=a.ability_risk;}if(b.status=="ok"){++ok_high;ms_high+=b.elapsed_ms;total_nodes_high+=b.nodes;p_high+=b.best.p_win;}if(a.status=="ok"&&b.status=="ok"){stable_type+=a.best.action.type==b.best.action.type;stable_exact+=same_action(a.best.action,b.best.action);}}
 auto div=[](double a,double b){return b?a/b:0.0;};
 std::cout<<"{\"heldout_battles\":"<<(dirs.size()-cut)<<",\"sampled_states\":"<<states.size()<<",\"low_budget\":"<<low<<",\"high_budget\":"<<high
          <<",\"low_ok\":"<<ok_low<<",\"high_ok\":"<<ok_high<<",\"action_type_stability\":"<<div(stable_type,std::min(ok_low,ok_high))<<",\"exact_action_stability\":"<<div(stable_exact,std::min(ok_low,ok_high))
          <<",\"low_avg_ms\":"<<div(ms_low,ok_low)<<",\"high_avg_ms\":"<<div(ms_high,ok_high)<<",\"low_avg_nodes\":"<<div(total_nodes_low,ok_low)<<",\"high_avg_nodes\":"<<div(total_nodes_high,ok_high)
          <<",\"low_avg_p_win\":"<<div(p_low,ok_low)<<",\"high_avg_p_win\":"<<div(p_high,ok_high)<<",\"avg_ability_risk\":"<<div(ability_risk,ok_low)<<"}\n";
 return states.empty()||ok_high!=states.size()?1:0;
}
