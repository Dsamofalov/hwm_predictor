#pragma once
#include "hwm/state.hpp"
#include <string>
#include <string_view>
#include <vector>
namespace hwm {
struct BattleEvent{uint64_t seq=0; std::string type="UNKNOWN"; uint64_t actor_uid=0,target_uid=0; std::string raw;};
struct DecodeWarning{std::string code,message;};
struct Coverage{size_t bytes_total=0,bytes_classified=0,records=0,unknown_records=0; double ratio() const{return bytes_total?double(bytes_classified)/double(bytes_total):0.0;}};
struct DecodeResult{BattleState state; std::vector<BattleEvent> events; std::vector<DecodeWarning> warnings; Coverage coverage; std::string raw_hash;};
class ProtocolDecoder{
public:
 DecodeResult decode_initial(std::string_view payload,std::string battle_id="") const;
 DecodeResult decode_update(const BattleState& previous,std::string_view payload) const;
 static std::vector<std::string> tokenize(std::string_view payload);
};
}
