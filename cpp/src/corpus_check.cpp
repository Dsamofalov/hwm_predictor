#include "hwm/protocol.hpp"
#include "hwm/state.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <map>

namespace fs=std::filesystem;
static std::string read(const fs::path&p){std::ifstream f(p,std::ios::binary);std::ostringstream s;s<<f.rdbuf();return s.str();}
int main(int argc,char**argv){
 if(argc<2){std::cerr<<"usage: corpus-check <corpus-root-or-battles-dir>\n";return 2;}
 fs::path root=argv[1];if(fs::is_directory(root/"battles"))root/="battles";
 const bool verbose_invalid=argc>2&&std::string(argv[2])=="--verbose-invalid";
 hwm::ProtocolDecoder d;size_t battles=0,ready=0,failed=0,semantic_safe=0,semantic_unsafe=0,with_unknown=0,invalid=0;double cov_sum=0,min_cov=1,semantic_sum=0,max_semantic=0;size_t entities=0;uint64_t max_turn=0,total_semantic_records=0,total_protocol_records=0;std::map<std::string,size_t> inv;
 for(auto&de:fs::directory_iterator(root)){
  if(!de.is_directory())continue;auto initp=de.path()/"init.txt",turnp=de.path()/"turns0.txt";if(!fs::exists(initp)||!fs::exists(turnp))continue;++battles;
  try{
   auto a=d.decode_initial(read(initp),de.path().filename().string());auto b=d.decode_update(a.state,read(turnp));
   entities+=a.state.entities.size();cov_sum+=b.coverage.ratio();min_cov=std::min(min_cov,b.coverage.ratio());max_turn=std::max<uint64_t>(max_turn,b.state.halfturn);
   semantic_sum+=b.state.semantic_unresolved_ratio;max_semantic=std::max(max_semantic,b.state.semantic_unresolved_ratio);total_semantic_records+=b.state.semantic_unresolved_records;total_protocol_records+=b.state.protocol_records_seen;
   if(b.state.protocol_ready)++ready;else ++failed;if(b.state.recommendation_safe)++semantic_safe;else ++semantic_unsafe;if(b.coverage.unknown_records)++with_unknown;auto vv=hwm::validate(b.state);if(!vv.empty()){++invalid;if(verbose_invalid||invalid<=5){std::cerr<<"invalid "<<de.path().filename().string()<<":";for(auto&x:vv)std::cerr<<" "<<x;std::cerr<<"\n";for(auto&e:b.state.entities)if(e.alive&&!e.is_hero)std::cerr<<"  uid="<<e.uid<<" side="<<(int)e.side<<" c="<<e.count<<" cid="<<e.creature_id<<" xy="<<e.anchor.x<<","<<e.anchor.y<<" hero="<<e.is_hero<<" big="<<e.is_big<<" hidden="<<e.is_hidden<<" statix="<<e.is_statix<<"\n";}for(auto&x:vv){auto c=x.find(':');inv[x.substr(0,c)]++;}}
  }catch(const std::exception&e){++failed;std::cerr<<de.path().filename().string()<<" exception "<<e.what()<<"\n";}
 }
 std::cout<<"{\"battles\":"<<battles<<",\"structural_ready\":"<<ready<<",\"structural_not_ready\":"<<failed<<",\"semantic_safe\":"<<semantic_safe<<",\"semantic_unsafe\":"<<semantic_unsafe<<",\"with_unknown\":"<<with_unknown<<",\"invalid\":"<<invalid<<",\"initial_entities\":"<<entities<<",\"coverage_mean\":"<<(battles?cov_sum/battles:0)<<",\"coverage_min\":"<<min_cov<<",\"semantic_unresolved_ratio_mean\":"<<(battles?semantic_sum/battles:0)<<",\"semantic_unresolved_ratio_max\":"<<max_semantic<<",\"semantic_unresolved_records\":"<<total_semantic_records<<",\"protocol_records\":"<<total_protocol_records<<",\"max_turn\":"<<max_turn<<"}\n";
 std::cerr<<"invariants:";for(auto&[k,v]:inv)std::cerr<<" "<<k<<"="<<v;std::cerr<<"\n";
 return failed?1:0;
}
