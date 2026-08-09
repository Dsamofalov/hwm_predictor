#include "hwm/protocol.hpp"
#include "hwm/state.hpp"
#include <algorithm>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>
namespace fs=std::filesystem;
namespace {
std::string read_file(const fs::path&p){std::ifstream f(p,std::ios::binary);std::ostringstream s;s<<f.rdbuf();return s.str();}
bool digits(std::string_view s){return !s.empty()&&std::all_of(s.begin(),s.end(),[](unsigned char c){return std::isdigit(c);});}
struct Chunk{uint32_t turn=0;std::string body;};
std::vector<Chunk> split_turns(std::string_view p){struct Mark{size_t start=0,body=0;uint32_t turn=0;};std::vector<Mark>m;if(auto first=p.find("turns=>");first!=std::string_view::npos){size_t q=first+7,colon=p.find(':',q);if(colon!=std::string_view::npos&&digits(p.substr(q,colon-q)))m.push_back({first,colon+1,(uint32_t)std::stoul(std::string(p.substr(q,colon-q)))});}size_t pos=0;while((pos=p.find(";>",pos))!=std::string_view::npos){size_t q=pos+2,colon=p.find(':',q);if(colon==std::string_view::npos)break;if(digits(p.substr(q,colon-q)))m.push_back({pos,colon+1,(uint32_t)std::stoul(std::string(p.substr(q,colon-q)))});pos=colon+1;}std::sort(m.begin(),m.end(),[](auto&a,auto&b){return a.start<b.start;});std::vector<Chunk>out;for(size_t i=0;i<m.size();++i){size_t end=i+1<m.size()?m[i+1].start:p.size();if(end>m[i].body&&p[end-1]==';')--end;out.push_back({m[i].turn,std::string(p.substr(m[i].body,end-m[i].body))});}return out;}
std::string payload(const Chunk&c){return "t=000turns=>"+std::to_string(c.turn)+":"+c.body;}
std::vector<std::pair<uint64_t,uint64_t>> overlaps(const hwm::BattleState&s){std::vector<std::pair<uint64_t,uint64_t>> out;for(size_t i=0;i<s.entities.size();++i){auto&a=s.entities[i];if(!a.alive||a.is_hero||a.is_warmachine)continue;for(size_t j=i+1;j<s.entities.size();++j){auto&b=s.entities[j];if(!b.alive||b.is_hero||b.is_warmachine)continue;bool ov=false;for(int ax=0;ax<a.footprint_w&&!ov;++ax)for(int ay=0;ay<a.footprint_h&&!ov;++ay)for(int bx=0;bx<b.footprint_w&&!ov;++bx)for(int by=0;by<b.footprint_h&&!ov;++by)if(hwm::Cell{a.anchor.x+ax,a.anchor.y+ay}==hwm::Cell{b.anchor.x+bx,b.anchor.y+by})ov=true;if(ov)out.push_back({a.uid,b.uid});}}
return out;}
std::string esc(std::string_view s){std::string o;for(char c:s){if(c=='\\'||c=='\"')o+='\\';if(c=='\n'||c=='\r'||c=='\t')o+=' ';else o+=c;}return o;}
}
int main(int argc,char**argv){if(argc<2){std::cerr<<"usage: overlap-diagnose <corpus-root-or-battles-dir> [limit=0]\n";return 2;}fs::path root=argv[1];if(fs::is_directory(root/"battles"))root/="battles";size_t limit=argc>2?std::stoull(argv[2]):0;std::vector<fs::path>dirs;for(auto&de:fs::directory_iterator(root))if(de.is_directory()&&fs::exists(de.path()/"init.txt")&&fs::exists(de.path()/"turns0.txt"))dirs.push_back(de.path());std::sort(dirs.begin(),dirs.end(),[](auto&a,auto&b){return std::stoull(a.filename().string())<std::stoull(b.filename().string());});hwm::ProtocolDecoder dec;size_t emitted=0;std::cout<<"[\n";bool first=true;for(auto&d:dirs){auto init=dec.decode_initial(read_file(d/"init.txt"),d.filename().string());auto s=init.state;auto prev_ov=overlaps(s);for(auto&ch:split_turns(read_file(d/"turns0.txt"))){auto r=dec.decode_update(s,payload(ch));auto now_ov=overlaps(r.state);if(prev_ov.empty()&&!now_ov.empty()){
 if(!first)std::cout<<",\n";first=false;auto [ua,ub]=now_ov.front();auto*a=r.state.entity(ua);auto*b=r.state.entity(ub);std::cout<<"{\"battle_id\":\""<<d.filename().string()<<"\",\"turn\":"<<ch.turn<<",\"active_uid\":"<<r.state.active_entity_uid<<",\"pair\":["<<ua<<","<<ub<<"],\"a\":{\"cid\":"<<(a?a->creature_id:0)<<",\"x\":"<<(a?a->anchor.x:0)<<",\"y\":"<<(a?a->anchor.y:0)<<",\"big\":"<<(a&&a->is_big?"true":"false")<<"},\"b\":{\"cid\":"<<(b?b->creature_id:0)<<",\"x\":"<<(b?b->anchor.x:0)<<",\"y\":"<<(b?b->anchor.y:0)<<",\"big\":"<<(b&&b->is_big?"true":"false")<<"},\"body\":\""<<esc(ch.body)<<"\",\"events\":[";for(size_t i=0;i<r.events.size();++i){if(i)std::cout<<',';auto&e=r.events[i];std::cout<<"{\"type\":\""<<esc(e.type)<<"\",\"actor\":"<<e.actor_uid<<",\"target\":"<<e.target_uid<<",\"raw\":\""<<esc(e.raw)<<"\"}";}std::cout<<"]}"; ++emitted; if(limit&&emitted>=limit){std::cout<<"\n]\n";return 0;}
 }
 s=std::move(r.state);prev_ov=std::move(now_ov);
 }}std::cout<<"\n]\n";return 0;}
