#include "hwm/state.hpp"
#include "hwm/action.hpp"
#include <algorithm>
#include <iomanip>
#include <sstream>
#include <cstring>
namespace hwm {
uint32_t stable_ability_id(std::string_view code){uint32_t h=2166136261u;for(unsigned char c:code){h^=c;h*=16777619u;}return h?h:1u;}
bool has_ability(const Entity& e,std::string_view code){const auto id=stable_ability_id(code);return std::find(e.ability_ids.begin(),e.ability_ids.end(),id)!=e.ability_ids.end();}
uint32_t status_effect_id(std::string_view wire){
 uint32_t h=2166136261u;for(unsigned char c:wire){h^=c;h*=16777619u;}return h?h:1u;
}
float effect_magnitude(const Entity& e,std::string_view wire){
 const uint32_t id=status_effect_id(wire);float value=0.0f;
 for(const auto&fx:e.effects)if(fx.id==id&&fx.duration>0)value=std::max(value,fx.magnitude);
 return value;
}
float effective_initiative(const Entity& e){
 // Official post-2017 mechanic: Fast and Slow add algebraically rather than multiply.
 const float net=(effect_magnitude(e,"fst")-effect_magnitude(e,"slw"))/100.0f;
 const float cripple=effect_magnitude(e,"proc_cripple")>0.0f?0.70f:1.0f;
 return std::max(0.0f,e.initiative*std::max(0.0f,1.0f+net)*cripple);
}
float effective_speed(const Entity& e){
 // Ferocious Wound contributes an independently described -3 speed component.
 // Crippling Wound is an observed two-activation -50% speed control effect.
 const float cripple=effect_magnitude(e,"proc_cripple")>0.0f?0.50f:1.0f;
 return std::max(0.0f,(e.speed-effect_magnitude(e,"proc_ferocious_speed"))*cripple);
}
float effective_attack(const Entity& e){return std::max(0.0f,e.attack+effect_magnitude(e,"rgm")-effect_magnitude(e,"sff")+effect_magnitude(e,"enr")+effect_magnitude(e,"blt")+effect_magnitude(e,"btt"));}
float effective_defense(const Entity& e){return std::max(0.0f,e.defense+effect_magnitude(e,"stn"));}
namespace {
bool aura_adjacent(const Entity& a,const Entity& b){
 if(!a.alive||!b.alive||a.is_hero||b.is_hero||a.is_hidden||b.is_hidden)return false;
 for(int ax=0;ax<a.footprint_w;++ax)for(int ay=0;ay<a.footprint_h;++ay)
  for(int bx=0;bx<b.footprint_w;++bx)for(int by=0;by<b.footprint_h;++by){
   const int dx=std::abs((a.anchor.x+ax)-(b.anchor.x+bx));
   const int dy=std::abs((a.anchor.y+ay)-(b.anchor.y+by));
   if(std::max(dx,dy)==1)return true;
  }
 return false;
}
int festering_aura_sources(const BattleState& s,const Entity& e){
 if(has_ability(e,"undead"))return 0;
 int n=0;
 for(const auto&src:s.entities){
  if(src.uid==e.uid||!src.alive||src.is_hero||src.is_hidden||!has_ability(src,"festeringaura"))continue;
  if(aura_adjacent(src,e))++n;
 }
 return n;
}
bool frightful_aura_active(const BattleState& s,const Entity& e){
 for(const auto&src:s.entities){
  if(src.uid==e.uid||!src.alive||src.is_hero||src.is_hidden||src.side==Side::Unknown||src.side==e.side||!has_ability(src,"frightfulaura"))continue;
  if(aura_adjacent(src,e))return true;
 }
 return false;
}
}
float effective_attack(const BattleState& s,const Entity& e){return std::max(0.0f,effective_attack(e)-4.0f*festering_aura_sources(s,e));}
float effective_defense(const BattleState& s,const Entity& e){return std::max(0.0f,effective_defense(e)-4.0f*festering_aura_sources(s,e));}
float effective_morale(const BattleState& s,const Entity& e){
 float m=e.morale-2.0f*festering_aura_sources(s,e)-(frightful_aura_active(s,e)?3.0f:0.0f);
 bool brave=has_ability(e,"auraofbravery");
 if(!brave)for(const auto&src:s.entities){if(src.uid!=e.uid&&src.alive&&!src.is_hero&&!src.is_hidden&&src.side==e.side&&has_ability(src,"auraofbravery")&&aura_adjacent(src,e)){brave=true;break;}}
 return brave?std::max(3.0f,m):m;
}
float effective_min_damage(const Entity& e){
 const float lo=std::max(0.0f,e.min_damage+effect_magnitude(e,"tob")),hi=std::max(lo,e.max_damage);
 const float delta=(effect_magnitude(e,"bls")-effect_magnitude(e,"crs"))/100.0f;
 return delta>0?std::min(hi,lo+(hi-lo)*delta):lo;
}
float effective_max_damage(const Entity& e){
 const float lo=std::max(0.0f,e.min_damage),hi=std::max(lo,e.max_damage);
 const float delta=(effect_magnitude(e,"bls")-effect_magnitude(e,"crs"))/100.0f;
 return delta<0?std::max(lo,hi-(hi-lo)*(-delta)):hi;
}
float ranged_damage_multiplier(const Entity& attacker,const Entity& defender){
 const float confusion=std::clamp(effect_magnitude(attacker,"cnf")/100.0f,0.0f,1.0f);
 const float deflect=std::clamp(effect_magnitude(defender,"dfm")/100.0f,0.0f,1.0f);
 return std::max(0.0f,(1.0f-confusion)*(1.0f-deflect));
}
float retaliation_damage_multiplier(const Entity& attacker){
 float m=std::max(0.0f,1.0f-std::clamp(effect_magnitude(attacker,"cnf")/100.0f,0.0f,1.0f));
 if(has_ability(attacker,"fierceretaliation"))m*=2.0f;
 return m;
}
const Entity* BattleState::entity(uint64_t uid) const{for(auto& e:entities)if(e.uid==uid)return &e;return nullptr;}
Entity* BattleState::entity(uint64_t uid){for(auto& e:entities)if(e.uid==uid)return &e;return nullptr;}
bool BattleState::inside(Cell c) const{return c.x>=min_x&&c.y>=min_y&&c.x<width&&c.y<height;}
bool BattleState::occupied(Cell c,uint64_t ignore) const{
 for(auto& e:entities){if(!e.alive||e.is_hero||e.is_hidden||e.uid==ignore)continue; if(e.is_warmachine&&!inside(e.anchor))continue; for(int dx=0;dx<e.footprint_w;++dx)for(int dy=0;dy<e.footprint_h;++dy)if(Cell{e.anchor.x+dx,e.anchor.y+dy}==c)return true;} return false;
}
static void mix(uint64_t& h,uint64_t v){h^=v+0x9e3779b97f4a7c15ULL+(h<<6)+(h>>2);}
const char* semantic_safety_tier(const BattleState& s){
 if(!s.protocol_ready)return "structural_blocked";
 if(s.semantic_unresolved_records==0)return "exact_core";
 if(s.semantic_unresolved_ratio<=0.10)return "guarded";
 if(s.semantic_unresolved_ratio<=kDefaultSemanticRiskLimit)return "degraded";
 return "semantic_blocked";
}
std::string state_hash(const BattleState& s){
 uint64_t h=1469598103934665603ULL;for(char c:s.battle_id)mix(h,(unsigned char)c);mix(h,s.active_entity_uid);mix(h,(uint64_t)s.side_to_act);mix(h,s.halfturn);mix(h,s.round);mix(h,s.decision_seq);mix(h,(uint64_t)s.phase);
 auto mf=[&](float v){uint32_t u=0;static_assert(sizeof(u)==sizeof(v));std::memcpy(&u,&v,sizeof(u));mix(h,u);};
 std::vector<const Entity*> es;es.reserve(s.entities.size());for(const auto&e:s.entities)es.push_back(&e);std::sort(es.begin(),es.end(),[](auto*a,auto*b){return a->uid<b->uid;});
 for(auto*ep:es){const auto&e=*ep;mix(h,e.uid);mix(h,e.creature_id);mix(h,(uint64_t)e.side);mix(h,e.max_count);mix(h,e.count);mix(h,e.top_unit_hp);mix(h,e.max_hp_per_unit);mix(h,(uint64_t)(e.anchor.x+128));mix(h,(uint64_t)(e.anchor.y+128));mix(h,e.alive);mix(h,e.is_hidden);mix(h,e.is_statix);mix(h,e.is_phantom);mix(h,e.shots);mix(h,e.mana);mix(h,e.last_acted_seq);mix(h,e.waited_this_round);mix(h,e.defending);mix(h,e.retaliation_available);mix(h,e.rune_speed_available);mix(h,e.rune_speed_active);mix(h,e.rune_speed_consumed);for(char c:e.run_modifier)mix(h,(unsigned char)c);mf(e.attack);mf(e.defense);mf(e.min_damage);mf(e.max_damage);mf(e.speed);mf(e.atb);mf(e.initiative);mf(e.morale);mf(e.luck);for(auto id:e.ability_ids)mix(h,id);for(const auto&sp:e.spells){mix(h,sp.id);mix(h,(uint64_t)sp.mana_cost);mix(h,sp.direct_damage);mix(h,sp.mass);mix(h,(uint64_t)sp.effect_kind);mix(h,(uint64_t)sp.target);mf(sp.magnitude);for(char c:sp.wire_code)mix(h,(unsigned char)c);}for(const auto&fx:e.effects){mix(h,fx.id);mix(h,(uint64_t)(fx.duration+0x10000));mf(fx.magnitude);}}
 std::ostringstream o;o<<std::hex<<std::setw(16)<<std::setfill('0')<<h;return o.str();}
std::vector<std::string> validate(const BattleState& s){
 std::vector<std::string> w;
 if(s.width<=0||s.height<=0) w.push_back("invalid_board");
 if(s.phase==Phase::Combat&&s.active_entity_uid&&!s.entity(s.active_entity_uid)) w.push_back("active_entity_missing");
 auto blocks=[&](const Entity&e){return e.alive&&!e.is_hero&&!e.is_warmachine&&!e.is_hidden;};
 auto overlap=[&](const Entity&a,const Entity&b){
  for(int ax=0;ax<a.footprint_w;++ax)for(int ay=0;ay<a.footprint_h;++ay)
   for(int bx=0;bx<b.footprint_w;++bx)for(int by=0;by<b.footprint_h;++by)
    if(Cell{a.anchor.x+ax,a.anchor.y+ay}==Cell{b.anchor.x+bx,b.anchor.y+by}) return true;
  return false;
 };
 auto allowed_overlay=[&](const Entity&a,const Entity&b){
  // Independently observed in the supplied raw corpus: creature 760 ("Cell") is a
  // `statix` 2x2 overlay spawned on exactly the same anchor as Battle boars in two
  // initial states. This is a narrow validation exception, not a generic "statix is
  // non-blocking" rule; the object still occupies cells for movement legality.
  return (a.creature_id==760&&a.is_statix)||(b.creature_id==760&&b.is_statix);
 };
 for(size_t i=0;i<s.entities.size();++i){
  const auto&e=s.entities[i];
  if(e.count<0) w.push_back("negative_count:"+std::to_string(e.uid));
  if(!e.is_hero&&!e.is_warmachine&&e.alive&&!s.inside(e.anchor)) w.push_back("entity_outside:"+std::to_string(e.uid));
  if(!e.is_hero&&e.max_hp_per_unit>0&&(e.top_unit_hp<0||e.top_unit_hp>e.max_hp_per_unit)) w.push_back("top_hp_invalid:"+std::to_string(e.uid));
  if(!blocks(e)) continue;
  for(size_t j=i+1;j<s.entities.size();++j){
   const auto&other=s.entities[j]; if(!blocks(other)) continue;
   if(overlap(e,other)&&!allowed_overlay(e,other)) w.push_back("overlap");
  }
 }
 return w;
}
std::string esc(std::string_view s){std::string o;for(char c:s){if(c=='"'||c=='\\')o+='\\';o+=c;}return o;}
std::string to_json(const BattleState& s){
 std::ostringstream o;
 const double semantic_confidence=std::clamp(1.0-s.semantic_unresolved_ratio,0.0,1.0);
 o<<"{\"battle_id\":\""<<esc(s.battle_id)<<"\",\"state_seq\":"<<s.state_seq
  <<",\"state_hash\":\""<<state_hash(s)<<"\",\"stream_contiguous\":"<<(s.stream_contiguous?"true":"false")
  <<",\"protocol_ready\":"<<(s.protocol_ready?"true":"false")<<",\"recommendation_safe\":"<<(s.recommendation_safe?"true":"false")
  <<",\"semantic_safety_tier\":\""<<semantic_safety_tier(s)<<"\""
  <<",\"protocol_unknown_ratio\":"<<s.protocol_unknown_ratio<<",\"semantic_unresolved_ratio\":"<<s.semantic_unresolved_ratio
  <<",\"semantic_confidence\":"<<semantic_confidence<<",\"protocol_unknown_records\":"<<s.protocol_unknown_records
  <<",\"protocol_records_seen\":"<<s.protocol_records_seen<<",\"semantic_unresolved_records\":"<<s.semantic_unresolved_records
  <<",\"min_x\":"<<s.min_x<<",\"min_y\":"<<s.min_y<<",\"width\":"<<s.width<<",\"height\":"<<s.height
  <<",\"active_entity_uid\":"<<s.active_entity_uid<<",\"side_to_act\":"<<(int)s.side_to_act<<",\"halfturn\":"<<s.halfturn<<",\"entities\":[";
 for(size_t i=0;i<s.entities.size();++i){const auto&e=s.entities[i];if(i)o<<',';o<<"{\"uid\":"<<e.uid<<",\"creature_id\":"<<e.creature_id<<",\"side\":"<<(int)e.side<<",\"x\":"<<e.anchor.x<<",\"y\":"<<e.anchor.y<<",\"max_count\":"<<e.max_count<<",\"count\":"<<e.count<<",\"hp\":"<<e.top_unit_hp<<",\"alive\":"<<(e.alive?"true":"false")<<",\"is_hero\":"<<(e.is_hero?"true":"false")<<",\"hidden\":"<<(e.is_hidden?"true":"false")<<",\"shooter\":"<<(e.is_shooter?"true":"false")<<",\"flyer\":"<<(e.is_flyer?"true":"false")<<",\"big\":"<<(e.is_big?"true":"false")<<",\"phantom\":"<<(e.is_phantom?"true":"false")<<",\"defending\":"<<(e.defending?"true":"false")<<",\"spells\":[";for(size_t si=0;si<e.spells.size();++si){if(si)o<<',';const auto&sp=e.spells[si];o<<"{\"id\":"<<sp.id<<",\"name\":\""<<esc(sp.name)<<"\",\"wire_code\":\""<<esc(sp.wire_code)<<"\",\"mana_cost\":"<<sp.mana_cost<<",\"direct_damage\":"<<(sp.direct_damage?"true":"false")<<",\"mass\":"<<(sp.mass?"true":"false")<<",\"effect_kind\":"<<(int)sp.effect_kind<<",\"magnitude\":"<<sp.magnitude<<"}";}o<<"],\"effects\":[";for(size_t fi=0;fi<e.effects.size();++fi){if(fi)o<<',';const auto&fx=e.effects[fi];o<<"{\"id\":"<<fx.id<<",\"duration\":"<<fx.duration<<",\"magnitude\":"<<fx.magnitude<<"}";}o<<"]}";}
 o<<"]}";return o.str();
}
}

namespace hwm {
std::string action_type_name(ActionType t){switch(t){case ActionType::Move:return "MOVE";case ActionType::MeleeAttack:return "MELEE_ATTACK";case ActionType::RangedAttack:return "RANGED_ATTACK";case ActionType::Wait:return "WAIT";case ActionType::Defend:return "DEFEND";case ActionType::Cast:return "CAST";case ActionType::Ability:return "ABILITY";case ActionType::HeroAction:return "HERO_ACTION";case ActionType::Special:return "SPECIAL";case ActionType::Pass:return "PASS";default:return "UNKNOWN";}}
std::string to_json(const Action&a){std::ostringstream o;o<<"{\"action_id\":"<<a.action_id<<",\"actor_uid\":"<<a.actor_uid<<",\"type\":\""<<action_type_name(a.type)<<"\"";if(a.target_uid)o<<",\"target_uid\":"<<*a.target_uid;if(a.destination)o<<",\"destination\":{\"x\":"<<a.destination->x<<",\"y\":"<<a.destination->y<<"}";if(a.ability_id)o<<",\"ability_id\":"<<*a.ability_id;o<<",\"source\":\""<<a.source<<"\"}";return o.str();}
}
