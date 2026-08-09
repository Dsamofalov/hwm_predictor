#include "hwm/protocol.hpp"
#include <fstream>
#include <iostream>
#include <sstream>
int main(int argc,char**argv){if(argc<2){std::cerr<<"usage: replay-inspect <payload-file> [battle-id]\n";return 2;}std::ifstream f(argv[1],std::ios::binary);if(!f)return 2;std::ostringstream ss;ss<<f.rdbuf();hwm::ProtocolDecoder d;auto r=d.decode_initial(ss.str(),argc>2?argv[2]:"");std::cout<<"raw_hash="<<r.raw_hash<<"\ncoverage="<<r.coverage.ratio()<<" records="<<r.coverage.records<<" unknown="<<r.coverage.unknown_records<<"\nstate_hash="<<hwm::state_hash(r.state)<<" entities="<<r.state.entities.size()<<" halfturn="<<r.state.halfturn<<"\n";for(auto&w:r.warnings)std::cout<<"warning "<<w.code<<": "<<w.message<<"\n";for(auto&e:r.events)std::cout<<e.seq<<'\t'<<e.type<<'\t'<<e.raw<<'\n';}
