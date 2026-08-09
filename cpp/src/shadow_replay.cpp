#include "hwm/protocol.hpp"
#include "hwm/simulator.hpp"
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

namespace fs = std::filesystem;

namespace {
std::string read_file(const fs::path& p) {
    std::ifstream f(p, std::ios::binary);
    std::ostringstream s;
    s << f.rdbuf();
    return s.str();
}

bool digits(std::string_view s) {
    return !s.empty() && std::all_of(s.begin(), s.end(), [](unsigned char c){ return std::isdigit(c); });
}

struct Chunk { uint32_t turn=0; std::string body; };
std::vector<Chunk> split_turns(std::string_view p) {
    struct Mark { size_t start=0, body=0; uint32_t turn=0; };
    std::vector<Mark> marks;
    if (auto first=p.find("turns=>"); first!=std::string_view::npos) {
        const size_t q=first+7, colon=p.find(':',q);
        if (colon!=std::string_view::npos && digits(p.substr(q,colon-q)))
            marks.push_back({first,colon+1,static_cast<uint32_t>(std::stoul(std::string(p.substr(q,colon-q))))});
    }
    size_t pos=0;
    while((pos=p.find(";>",pos))!=std::string_view::npos) {
        const size_t q=pos+2, colon=p.find(':',q);
        if(colon==std::string_view::npos) break;
        if(digits(p.substr(q,colon-q)))
            marks.push_back({pos,colon+1,static_cast<uint32_t>(std::stoul(std::string(p.substr(q,colon-q))))});
        pos=colon+1;
    }
    std::sort(marks.begin(),marks.end(),[](const Mark&a,const Mark&b){return a.start<b.start;});
    std::vector<Chunk> out;
    for(size_t i=0;i<marks.size();++i) {
        size_t end=i+1<marks.size()?marks[i+1].start:p.size();
        if(end>marks[i].body && p[end-1]==';') --end;
        out.push_back({marks[i].turn,std::string(p.substr(marks[i].body,end-marks[i].body))});
    }
    return out;
}

std::string single_payload(const Chunk& c) {
    return "t=000turns=>"+std::to_string(c.turn)+":"+c.body;
}

std::string semantic_hash(hwm::BattleState s) {
    // state_seq is transport revision, not battle semantics.
    s.state_seq=0;
    return hwm::state_hash(s);
}

struct Metrics {
    uint64_t battles=0, final_match=0, final_ready=0, final_valid=0;
    uint64_t decision_points=0, player_points=0, player_nonhero_points=0;
    uint64_t player_hero_points=0, player_hero_valid_points=0, player_hero_protocol_ready_points=0, player_hero_strict_safe_points=0, player_hero_with_supported_actions=0, total_hero_actions=0;
    uint64_t player_valid_points=0, player_protocol_ready_points=0, player_strict_safe_points=0;
    uint64_t player_with_basic_actions=0, total_basic_actions=0;
    uint64_t semantic_tainted_player_points=0, semantic_le_05=0, semantic_le_10=0, semantic_le_20=0, semantic_le_30=0;
    double semantic_ratio_sum=0.0;
};

void add(Metrics& a,const Metrics& b){
#define A(x) a.x+=b.x
    A(battles);A(final_match);A(final_ready);A(final_valid);A(decision_points);A(player_points);A(player_nonhero_points);A(player_hero_points);A(player_hero_valid_points);A(player_hero_protocol_ready_points);A(player_hero_strict_safe_points);A(player_hero_with_supported_actions);A(total_hero_actions);A(player_valid_points);A(player_protocol_ready_points);A(player_strict_safe_points);A(player_with_basic_actions);A(total_basic_actions);A(semantic_tainted_player_points);A(semantic_le_05);A(semantic_le_10);A(semantic_le_20);A(semantic_le_30);a.semantic_ratio_sum+=b.semantic_ratio_sum;
#undef A
}

void print_json(std::string_view name,const Metrics&m) {
    auto ratio=[](uint64_t a,uint64_t b){return b?double(a)/double(b):0.0;};
    std::cout << '"' << name << "\":{";
    std::cout << "\"battles\":"<<m.battles
              << ",\"incremental_final_match\":"<<m.final_match
              << ",\"incremental_final_match_rate\":"<<ratio(m.final_match,m.battles)
              << ",\"final_protocol_ready\":"<<m.final_ready
              << ",\"final_valid\":"<<m.final_valid
              << ",\"decision_points\":"<<m.decision_points
              << ",\"player_points\":"<<m.player_points
              << ",\"player_nonhero_points\":"<<m.player_nonhero_points
              << ",\"player_hero_points\":"<<m.player_hero_points
              << ",\"player_hero_valid_points\":"<<m.player_hero_valid_points
              << ",\"player_hero_protocol_ready_points\":"<<m.player_hero_protocol_ready_points
              << ",\"player_hero_protocol_ready_rate\":"<<ratio(m.player_hero_protocol_ready_points,m.player_hero_points)
              << ",\"player_hero_strict_safe_points\":"<<m.player_hero_strict_safe_points
              << ",\"player_hero_with_supported_actions\":"<<m.player_hero_with_supported_actions
              << ",\"player_hero_supported_action_rate\":"<<ratio(m.player_hero_with_supported_actions,m.player_hero_protocol_ready_points)
              << ",\"total_hero_actions\":"<<m.total_hero_actions
              << ",\"player_valid_points\":"<<m.player_valid_points
              << ",\"player_protocol_ready_points\":"<<m.player_protocol_ready_points
              << ",\"player_protocol_ready_rate\":"<<ratio(m.player_protocol_ready_points,m.player_nonhero_points)
              << ",\"player_strict_safe_points\":"<<m.player_strict_safe_points
              << ",\"player_strict_safe_rate\":"<<ratio(m.player_strict_safe_points,m.player_nonhero_points)
              << ",\"player_with_basic_actions\":"<<m.player_with_basic_actions
              << ",\"player_basic_action_rate\":"<<ratio(m.player_with_basic_actions,m.player_protocol_ready_points)
              << ",\"total_basic_actions\":"<<m.total_basic_actions
              << ",\"semantic_tainted_player_points\":"<<m.semantic_tainted_player_points
              << ",\"semantic_ratio_mean\":"<<(m.player_nonhero_points?m.semantic_ratio_sum/double(m.player_nonhero_points):0.0)
              << ",\"semantic_le_05\":"<<m.semantic_le_05
              << ",\"semantic_le_10\":"<<m.semantic_le_10
              << ",\"semantic_le_20\":"<<m.semantic_le_20
              << ",\"semantic_le_30\":"<<m.semantic_le_30
              << '}';
}
}

int main(int argc,char**argv){
    if(argc<2){std::cerr<<"usage: shadow-replay <corpus-root-or-battles-dir>\n";return 2;}
    fs::path root=argv[1]; if(fs::is_directory(root/"battles")) root/="battles";
    std::vector<fs::path> dirs;
    for(const auto& de:fs::directory_iterator(root)) if(de.is_directory()&&fs::exists(de.path()/"init.txt")&&fs::exists(de.path()/"turns0.txt")) dirs.push_back(de.path());
    std::sort(dirs.begin(),dirs.end(),[](const auto&a,const auto&b){return std::stoull(a.filename().string())<std::stoull(b.filename().string());});
    const size_t cut=dirs.size()*8/10;
    hwm::ProtocolDecoder decoder; hwm::GenericSimulator sim;
    Metrics all,train,held;
    for(size_t bi=0;bi<dirs.size();++bi){
        Metrics one; one.battles=1;
        const auto init=read_file(dirs[bi]/"init.txt"), turns=read_file(dirs[bi]/"turns0.txt");
        auto initial=decoder.decode_initial(init,dirs[bi].filename().string());
        auto state=initial.state;
        for(const auto& ch:split_turns(turns)){
            auto step=decoder.decode_update(state,single_payload(ch));
            state=std::move(step.state);
            ++one.decision_points;
            if(state.phase==hwm::Phase::Finished || state.active_entity_uid==0 || state.side_to_act!=hwm::Side::Player) continue;
            ++one.player_points;
            const auto* actor=state.entity(state.active_entity_uid);
            if(!actor) continue;
            if(actor->is_hero){
                ++one.player_hero_points;
                const bool valid=hwm::validate(state).empty();
                if(valid) ++one.player_hero_valid_points;
                if(state.protocol_ready) ++one.player_hero_protocol_ready_points;
                if(state.recommendation_safe) ++one.player_hero_strict_safe_points;
                if(state.protocol_ready){const auto acts=sim.legal_actions(state);if(!acts.empty()){++one.player_hero_with_supported_actions;one.total_hero_actions+=acts.size();}}
                continue;
            }
            ++one.player_nonhero_points;
            const bool valid=hwm::validate(state).empty();
            if(valid) ++one.player_valid_points;
            if(state.protocol_ready) ++one.player_protocol_ready_points;
            if(state.recommendation_safe) ++one.player_strict_safe_points;
            if(state.semantic_unresolved_records) ++one.semantic_tainted_player_points;
            one.semantic_ratio_sum += state.semantic_unresolved_ratio;
            if(state.semantic_unresolved_ratio<=0.05) ++one.semantic_le_05;
            if(state.semantic_unresolved_ratio<=0.10) ++one.semantic_le_10;
            if(state.semantic_unresolved_ratio<=0.20) ++one.semantic_le_20;
            if(state.semantic_unresolved_ratio<=0.30) ++one.semantic_le_30;
            if(state.protocol_ready){
                const auto acts=sim.legal_actions(state);
                if(!acts.empty()){++one.player_with_basic_actions;one.total_basic_actions+=acts.size();}
            }
        }
        auto one_shot=decoder.decode_update(initial.state,turns);
        if(semantic_hash(state)==semantic_hash(one_shot.state)) ++one.final_match;
        if(state.protocol_ready) ++one.final_ready;
        if(hwm::validate(state).empty()) ++one.final_valid;
        add(all,one); if(bi<cut)add(train,one);else add(held,one);
    }
    std::cout<<'{';print_json("all",all);std::cout<<',';print_json("train",train);std::cout<<',';print_json("heldout",held);std::cout<<"}\n";
    return all.final_match==all.battles?0:1;
}
