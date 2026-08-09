#pragma once
#include "hwm/action.hpp"
#include "hwm/next_actor_model.hpp"
#include "hwm/damage_model.hpp"
#include "hwm/ability_damage_model.hpp"
#include "hwm/ability_registry.hpp"
#include "hwm/collateral_model.hpp"
#include "hwm/proc_model.hpp"
#include "hwm/kill_trigger_model.hpp"
#include "hwm/hero_spell_model.hpp"
#include "hwm/raise_dead_model.hpp"
#include "hwm/phantom_forces_model.hpp"
#include <random>
namespace hwm {
struct Transition{BattleState state; double reward=0; bool terminal=false; bool valid=true; std::string warning;};
class GenericSimulator{
public:
 std::vector<Action> legal_actions(const BattleState& s) const;
 Transition apply(const BattleState& s,const Action& a,double damage_roll=0.5) const;
 double heuristic_value(const BattleState& s,Side perspective) const;
 bool scheduler_loaded() const { return next_actor_.loaded(); }
 bool damage_model_loaded() const { return damage_.loaded(); }
 bool ability_damage_model_loaded() const { return ability_damage_.loaded(); }
 bool ability_registry_loaded() const { return ability_registry_.loaded(); }
 bool collateral_model_loaded() const { return collateral_.loaded(); }
 bool proc_model_loaded() const { return proc_.loaded(); }
 bool kill_trigger_model_loaded() const { return kill_trigger_.loaded(); }
 bool load_proc_model(const std::string& path) { return proc_.load(path); }
 bool load_collateral_model(const std::string& path) { return collateral_.load(path); }
 bool load_kill_trigger_model(const std::string& path) { return kill_trigger_.load(path); }
 double ability_risk(const BattleState& s) const { return ability_registry_.state_risk(s); }
 bool hero_spell_model_loaded() const { return hero_spell_damage_.loaded(); }
 bool raise_dead_model_loaded() const { return raise_dead_.loaded(); }
 bool phantom_forces_model_loaded() const { return phantom_.loaded(); }
private:
 std::vector<Cell> reachable(const BattleState& s,const Entity& e) const;
 bool can_place(const BattleState& s,const Entity& e,Cell anchor) const;
 std::vector<Cell> phantom_placements(const BattleState& s,const Entity& source) const;
 NextActorModel next_actor_;
 DamageModel damage_;
 AbilityDamageModel ability_damage_;
 AbilityRegistry ability_registry_;
 CollateralModel collateral_;
 ProcModel proc_;
 KillTriggerModel kill_trigger_;
 HeroSpellDamageModel hero_spell_damage_;
 RaiseDeadModel raise_dead_;
 PhantomForcesModel phantom_;
};
}
