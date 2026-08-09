#pragma once
#include <cstdint>
#include <optional>
#include <string>
#include <vector>
#include <unordered_set>
#include <string_view>
namespace hwm {
inline constexpr double kDefaultSemanticRiskLimit = 0.30;
enum class Side:uint8_t{Unknown=0,Player=1,Pve=2};
enum class Phase:uint8_t{Unknown=0,Deployment=1,Combat=2,Finished=3};
struct Cell{int x=0,y=0; auto operator<=>(const Cell&) const = default;};
struct Effect{uint32_t id=0; int duration=0; float magnitude=0; std::string raw;};
enum class SpellEffectKind:uint8_t{None=0,DirectDamage=1,Fast=2,Slow=3,Bless=4,Curse=5,Stoneskin=6,DeflectMissile=7,RighteousMight=8,Confusion=9,Suffering=10,RaiseDead=11,PhantomForces=12};
enum class SpellTarget:uint8_t{Enemy=0,Friendly=1};
struct BattleState;
struct SpellSpec{
  uint32_t id=0; std::string name; std::string wire_code; int mana_cost=0;
  bool direct_damage=false; bool mass=false; SpellEffectKind effect_kind=SpellEffectKind::None;
  SpellTarget target=SpellTarget::Enemy; float magnitude=0; float secondary=0;
};
struct Entity{
  uint64_t uid=0; uint32_t creature_id=0; int owner=0; Side side=Side::Unknown; Cell anchor{}; int footprint_w=1,footprint_h=1;
  bool alive=true; bool is_hero=false,is_big=false,is_flyer=false,is_shooter=false,is_warmachine=false,is_hidden=false,is_statix=false,is_phantom=false,shoot_only=false,double_shoot=false,unlimited_retaliation=false,no_retaliation=false,no_range_penalty=false,no_melee_penalty=false;
  bool rune_speed_available=false,rune_speed_active=false,rune_speed_consumed=false; std::string run_modifier;
  int max_count=0,count=0,top_unit_hp=0,max_hp_per_unit=0; float attack=0,defense=0,min_damage=0,max_damage=0,speed=0,atb=0,initiative=0,morale=0,luck=0;
  int shots=0,mana=0; uint64_t last_acted_seq=0; std::vector<uint32_t> ability_ids; std::vector<SpellSpec> spells; std::vector<Effect> effects; bool retaliation_available=true, waited_this_round=false, defending=false;
};
struct BattleState{
  std::string battle_id; uint64_t state_seq=0; uint32_t protocol_version=0,ruleset_version=0; int min_x=1,min_y=1,width=0,height=0; bool stream_contiguous=false; bool protocol_ready=false; bool recommendation_safe=false; double protocol_unknown_ratio=1.0; double semantic_unresolved_ratio=1.0; uint64_t protocol_bytes_total=0,protocol_bytes_classified=0,protocol_unknown_records=0,protocol_records_seen=0,semantic_unresolved_records=0;
  std::vector<Cell> blocked; std::vector<Entity> entities; uint64_t active_entity_uid=0; Side side_to_act=Side::Unknown; Phase phase=Phase::Unknown;
  uint32_t round=0,halfturn=0; uint64_t decision_seq=0; std::vector<std::string> recent_unknown;
  const Entity* entity(uint64_t uid) const; Entity* entity(uint64_t uid); bool inside(Cell c) const; bool occupied(Cell c,uint64_t ignore=0) const;
};
uint32_t stable_ability_id(std::string_view code);
bool has_ability(const Entity& e,std::string_view code);
uint32_t status_effect_id(std::string_view wire);
float effect_magnitude(const Entity& e,std::string_view wire);
float effective_initiative(const Entity& e);
float effective_speed(const Entity& e);
float effective_attack(const Entity& e);
float effective_defense(const Entity& e);
float effective_attack(const BattleState& s,const Entity& e);
float effective_defense(const BattleState& s,const Entity& e);
float effective_morale(const BattleState& s,const Entity& e);
float effective_min_damage(const Entity& e);
float effective_max_damage(const Entity& e);
float ranged_damage_multiplier(const Entity& attacker,const Entity& defender);
float retaliation_damage_multiplier(const Entity& attacker);
std::string state_hash(const BattleState& s);
const char* semantic_safety_tier(const BattleState& s);
std::vector<std::string> validate(const BattleState& s);
std::string to_json(const BattleState& s);
}
