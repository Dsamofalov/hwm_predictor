#pragma once
#include "hwm/state.hpp"
#include <cstdint>
#include <optional>
#include <string>
#include <vector>
namespace hwm {
enum class ActionType:uint8_t{Unknown=0,Move=1,MeleeAttack=2,RangedAttack=3,Wait=4,Defend=5,Cast=6,Ability=7,HeroAction=8,Special=9,Pass=10};
struct Action{uint64_t action_id=0,actor_uid=0; ActionType type=ActionType::Unknown; std::optional<uint64_t> target_uid; std::optional<Cell> destination; std::optional<uint32_t> ability_id; std::string source="generator";};
std::string action_type_name(ActionType t);
std::string to_json(const Action& a);
}
