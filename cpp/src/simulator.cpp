#include "hwm/simulator.hpp"
#include <algorithm>
#include <cmath>
#include <queue>
#include <unordered_set>
#include <string_view>

namespace hwm {
static int dist(Cell a,Cell b){return std::max(std::abs(a.x-b.x),std::abs(a.y-b.y));}
static bool footprints_adjacent(const Entity& a, Cell aa, const Entity& b, Cell ba);
static uint32_t stable_tag_id(std::string_view text){return stable_ability_id(text);}
static bool has_tag(const Entity&e,std::string_view tag){return has_ability(e,tag);}
static bool swarm_targetable(const Entity&e){return !e.is_warmachine&&!has_tag(e,"undead")&&!has_tag(e,"elemental")&&!has_tag(e,"mechanical");}
static bool direct_spell_targetable(const Entity& e,const SpellSpec& sp,const Entity& caster){
    if(!e.alive||e.is_hero||e.is_hidden||e.side==caster.side||e.side==Side::Unknown)return false;
    if(has_tag(e,"immunity"))return false;
    if(sp.wire_code=="swm"&&!swarm_targetable(e))return false;
    // Exact school-specific immunities for the direct spells whose schools are unambiguous.
    if(sp.wire_code=="ltn"&&(has_tag(e,"ilighting")||has_tag(e,"iair")))return false;
    if(sp.wire_code=="ice"&&has_tag(e,"icold"))return false;
    return true;
}
static double tag_percent(const Entity&e,std::string_view prefix){
    // Exact numeric suffix abilities such as ignoredefence40 / magicproof95.
    for(int pct: {95,90,80,75,60,50,40,30,25,20,15,10}){
        std::string code(prefix); code += std::to_string(pct);
        if(has_tag(e,code)) return pct/100.0;
    }
    return 0.0;
}
static double direct_spell_exact_multiplier(const Entity& target,const SpellSpec& sp){
    // Intrinsic target modifiers. A target-conditioned spell model may already learn these,
    // so callers may omit this component to avoid double-counting.
    double m=1.0-tag_percent(target,"magicproof");
    if(sp.wire_code=="mfs"&&has_tag(target,"organicarmor"))m*=0.20; // catalog: 80% Magic Fist resistance
    if(sp.wire_code=="ltn"){
        m*=1.0-tag_percent(target,"airproof");
        if(has_tag(target,"vulnerabilitytoair"))m*=1.25;
    }else if(sp.wire_code=="ice"){
        m*=1.0-tag_percent(target,"waterproof");
    }
    return std::max(0.0,m);
}
static double direct_spell_dynamic_multiplier(const BattleState& s,const Entity& target,const SpellSpec& sp){
    // Dynamic state/position modifiers are NOT encoded by creature-id-conditioned damage
    // tables and therefore must always be applied after the learned median prediction.
    double m=1.0;
    if(effect_magnitude(target,"proc_stone")>0.0f)m*=0.50;
    if(effect_magnitude(target,"proc_entrenchment")>0.0f)m*=0.50;

    // Aura of magic resistance: source itself and adjacent allies receive 30% resistance.
    bool resist=false;
    for(const auto&src:s.entities){
        if(!src.alive||src.is_hero||src.is_hidden||!has_tag(src,"auraofres")||src.side!=target.side)continue;
        if(src.uid==target.uid||footprints_adjacent(src,src.anchor,target,target.anchor)){resist=true;break;}
    }
    if(resist)m*=0.70;

    // Elemental vulnerability auras affect adjacent enemy stacks. We only apply schools
    // independently identified for currently supported direct spells: Lightning=Air, Ice=Water.
    const char* aura = sp.wire_code=="ltn" ? "auraofairvul" : (sp.wire_code=="ice" ? "auraofwatervul" : nullptr);
    if(aura){
        bool vulnerable=false;
        for(const auto&src:s.entities){
            if(!src.alive||src.is_hero||src.is_hidden||src.side==target.side||!has_tag(src,aura))continue;
            if(footprints_adjacent(src,src.anchor,target,target.anchor)){vulnerable=true;break;}
        }
        if(vulnerable)m*=1.50;
    }
    return std::max(0.0,m);
}
static double fire_damage_multiplier(const Entity& target){
    if(has_tag(target,"ifire"))return 0.0;
    double m=std::max(0.0,1.0-tag_percent(target,"fireproof"));
    if(has_tag(target,"demoniclineage"))m*=0.75; // catalog: 25% fire spell resistance
    if(has_tag(target,"fireprskin"))m*=0.80;      // volcanic skin: +20% fire resistance
    if(has_tag(target,"lifeguardmembrane"))m*=0.85;
    if(has_tag(target,"spirit")&&target.last_acted_seq==0)m*=0.50;
    return m;
}
static int physical_hit_count(const Entity&e,bool ranged){
    if(ranged) return (e.double_shoot||has_tag(e,"doubleshoot"))?2:1;
    if(has_tag(e,"triplestrike")) return 3;
    if(has_tag(e,"doublestrike")) return 2;
    return 1;
}
static double exact_passive_damage_multiplier(const Entity&attacker,const Entity&defender,bool ranged,int moved_cells){
    double m=1.0;
    // Stoning: while petrified the target receives 50% less physical damage.
    if(effect_magnitude(defender,"proc_stone")>0.0f)m*=0.50;
    if(effect_magnitude(defender,"proc_entrenchment")>0.0f)m*=0.50;
    // Daily Help reference: rangepenalty halves every ranged attack.
    if(ranged&&has_tag(attacker,"rangepenalty"))m*=0.5;
    // Daily Help reference: Diamond armor receives only 10% of ranged physical damage.
    if(ranged&&has_tag(defender,"diamondarmor"))m*=0.10;
    if(ranged&&has_tag(defender,"shielded"))m*=0.75;
    if(ranged&&(has_tag(defender,"lshield")||has_tag(defender,"hollowbones")))m*=0.50;
    if(has_tag(defender,"immaterial"))m*=0.65;
    if(has_tag(attacker,"giantkiller")&&defender.is_big)m*=2.0;
    // Reliable position: +50% melee physical damage when attacking without moving.
    if(!ranged&&moved_cells==0&&has_tag(attacker,"safeposition"))m*=1.50;
    // Shield wall: -10% incoming melee damage for every cell traversed by the attacker, cap 90%.
    if(!ranged&&moved_cells>0&&has_tag(defender,"shieldwall"))m*=std::max(0.10,1.0-0.10*std::min(9,moved_cells));
    // `charge` (Разбег): +10% physical damage for every cell traversed before the hit.
    if(!ranged&&moved_cells>0&&has_tag(attacker,"charge"))m*=1.0+0.10*moved_cells;
    if(!ranged&&moved_cells>0&&has_tag(attacker,"jousting"))m*=1.0+0.05*moved_cells;
    if(!ranged&&moved_cells>0&&has_tag(attacker,"agilesteed"))m*=std::max(0.0,1.0-0.05*moved_cells);
    if(!ranged&&moved_cells>0&&has_tag(attacker,"blindingcharge"))m*=1.0+0.10*moved_cells;
    if(!ranged&&has_tag(defender,"brittle"))m*=1.25;
    if(has_tag(defender,"deadflesh"))m*=0.80;
    if(has_tag(defender,"lifeguardmembrane"))m*=0.85;
    if(has_tag(defender,"spirit")&&defender.last_acted_seq==0)m*=0.50;
    if(!ranged&&has_tag(defender,"pleasureinpain"))m*=0.90;
    if(!ranged&&has_tag(defender,"raptureinagony"))m*=0.80;
    // Blood Frenzy: +30% against a stack currently suffering Ferocious Wound.
    if(has_tag(attacker,"bloodfrenzy") &&
       (effect_magnitude(defender,"proc_ferocious_speed")>0.0f || effect_magnitude(defender,"proc_ferocious_dot")>0.0f))m*=1.30;
    return m;
}
static double shieldother_ranged_multiplier(const BattleState&s,const Entity&defender,bool ranged){
    if(!ranged||has_tag(defender,"lshield"))return 1.0; // Big Shield supersedes ally protection.
    for(const auto&src:s.entities){
        if(!src.alive||src.is_hero||src.is_hidden||src.uid==defender.uid||src.side!=defender.side||!has_tag(src,"shieldother"))continue;
        if(footprints_adjacent(src,src.anchor,defender,defender.anchor))return 0.75;
    }
    return 1.0;
}
static double ability_transfer_multiplier(const DamageModel& damage,const AbilityDamageModel& ability,const Entity&attacker,const Entity&defender,ActionType type){
    // Held-out gate: ability transfer improves both median and mean error for creature
    // profiles with <=50 training attacks, but slightly hurts the median on heavily-seen
    // creatures. Use it only where cross-creature transfer is actually beneficial.
    return damage.sample_count(attacker.creature_id,type)<=50 ? ability.multiplier(attacker,defender,type) : 1.0;
}
static int total_hp(const Entity&e);
static bool raise_dead_targetable(const Entity&e,const Entity&caster){
    if(e.is_hero||e.is_warmachine||e.is_statix||e.side==Side::Unknown||e.side!=caster.side||!has_tag(e,"undead"))return false;
    if(caster.owner>0&&e.owner>0&&caster.owner!=e.owner)return false;
    if(e.max_count<=0||e.max_hp_per_unit<=0)return false;
    return total_hp(e)<e.max_count*std::max(1,e.max_hp_per_unit);
}
static bool status_targetable(const Entity& e,const SpellSpec& sp,const Entity& caster){
    if(!e.alive||e.is_hero||e.is_hidden||e.is_warmachine||e.is_statix||e.side==Side::Unknown)return false;
    if(has_tag(e,"immunity"))return false;
    const bool friendly=e.side==caster.side;
    if((sp.target==SpellTarget::Friendly)!=friendly)return false;
    // Official description for Confusion excludes these categories.  Other target
    // immunities/modifiers remain semantic uncertainty until independently recovered.
    if(sp.effect_kind==SpellEffectKind::Confusion &&
       (has_tag(e,"undead")||has_tag(e,"elemental")||has_tag(e,"mechanical")||has_tag(e,"imind")))return false;
    if(sp.effect_kind==SpellEffectKind::Slow&&has_tag(e,"islow"))return false;
    return true;
}
static void put_status_effect(Entity& target,const SpellSpec& sp,int duration){
    const uint32_t id=status_effect_id(sp.wire_code);
    auto it=std::find_if(target.effects.begin(),target.effects.end(),[&](const Effect&fx){return fx.id==id;});
    Effect fx{id,std::max(1,duration),sp.magnitude,"speculative:"+sp.name};
    if(it==target.effects.end())target.effects.push_back(std::move(fx)); else *it=std::move(fx);
}
static void deal_damage(Entity& target,int dmg);
static void tick_effects_after_action(Entity& e){
    const uint32_t dot_id=status_effect_id("proc_ferocious_dot");
    for(const auto&fx:e.effects)if(fx.id==dot_id&&fx.duration>0&&fx.magnitude>0)deal_damage(e,std::max(1,(int)std::llround(fx.magnitude)));
    for(auto&fx:e.effects)if(fx.duration>0)--fx.duration;
    e.effects.erase(std::remove_if(e.effects.begin(),e.effects.end(),[](const Effect&fx){return fx.duration<=0;}),e.effects.end());
}
static int hero_basic_attack_damage(const Entity& hero){
    // Independent raw-corpus invariant for the standard single-target hero attack:
    // 50/50 `Spsc...062` decisions across seven hero creature IDs and both sides satisfy
    // damage = 16 + 4 * M-field[11] (`max_count`) exactly.  The target's defence does not
    // alter this wire damage in those observations.  Other Spsc modes are deliberately
    // excluded because they represent different hero/faction mechanics.
    return std::max(1,16+4*std::max(0,hero.max_count));
}

static bool footprints_adjacent(const Entity& a, Cell aa, const Entity& b, Cell ba){
    for(int ax=0;ax<a.footprint_w;++ax)for(int ay=0;ay<a.footprint_h;++ay)
        for(int bx=0;bx<b.footprint_w;++bx)for(int by=0;by<b.footprint_h;++by)
            if(dist(Cell{aa.x+ax,aa.y+ay},Cell{ba.x+bx,ba.y+by})<=1)return true;
    return false;
}

static bool footprints_overlap(const Entity&a,Cell aa,const Entity&b,Cell ba){
    for(int ax=0;ax<a.footprint_w;++ax)for(int ay=0;ay<a.footprint_h;++ay)
        for(int bx=0;bx<b.footprint_w;++bx)for(int by=0;by<b.footprint_h;++by)
            if(Cell{aa.x+ax,aa.y+ay}==Cell{ba.x+bx,ba.y+by})return true;
    return false;
}
static bool occupies_cell(const Entity&e,Cell c){
    for(int dx=0;dx<e.footprint_w;++dx)for(int dy=0;dy<e.footprint_h;++dy)if(Cell{e.anchor.x+dx,e.anchor.y+dy}==c)return true;
    return false;
}
static int signum(double v){return (v>0)-(v<0);}
static std::vector<uint64_t> collateral_candidates(const BattleState&s,const Entity&actor,const Entity&primary,CollateralZone zone){
    std::vector<uint64_t> out;
    double acx=actor.anchor.x+(actor.footprint_w-1)*0.5,acy=actor.anchor.y+(actor.footprint_h-1)*0.5;
    double tcx=primary.anchor.x+(primary.footprint_w-1)*0.5,tcy=primary.anchor.y+(primary.footprint_h-1)*0.5;
    const int sx=signum(tcx-acx),sy=signum(tcy-acy);
    for(const auto&e:s.entities){
        if(!e.alive||e.is_hero||e.is_hidden||e.is_statix||e.uid==actor.uid||e.uid==primary.uid)continue;
        bool candidate=false;
        if(zone==CollateralZone::ActorAdjacent)candidate=footprints_adjacent(actor,actor.anchor,e,e.anchor);
        else if(zone==CollateralZone::TargetAdjacent)candidate=footprints_adjacent(primary,primary.anchor,e,e.anchor);
        else if(zone==CollateralZone::Behind){
            for(int dx=0;dx<primary.footprint_w&&!candidate;++dx)for(int dy=0;dy<primary.footprint_h&&!candidate;++dy){
                const Cell behind{primary.anchor.x+dx+sx,primary.anchor.y+dy+sy};
                if(!occupies_cell(primary,behind)&&occupies_cell(e,behind))candidate=true;
            }
        }
        if(candidate)out.push_back(e.uid);
    }
    std::sort(out.begin(),out.end());return out;
}
static double collateral_roll(double roll,uint64_t uid,uint32_t ability){
    // Deterministic per-candidate pseudo-random variate derived from the rollout draw.
    const double x=std::clamp(roll,0.0,1.0)*0.731050141 + double(uid%1009)*0.6180339887498948 + double(ability%65521)*0.0000152590219;
    return x-std::floor(x);
}
static double proc_roll(double roll,uint64_t actor,uint64_t target,uint32_t ability){
    const double x=std::clamp(roll,0.0,1.0)*0.41421356237 + double(actor%1009)*0.754877666 + double(target%1013)*0.569840291 + double(ability%65521)*0.000017;
    return x-std::floor(x);
}
static bool has_live_effect(const Entity&e,std::string_view name){return effect_magnitude(e,name)>0.0f;}
static bool incapacitated(const Entity&e){return has_live_effect(e,"proc_blind")||has_live_effect(e,"proc_torpor")||has_live_effect(e,"proc_stone");}
static bool retaliation_suppressed(const Entity&e){return incapacitated(e)||has_live_effect(e,"proc_shieldbash");}
static bool root_active(const BattleState&s,const Entity&e){
    const uint32_t id=status_effect_id("proc_root");
    for(const auto&fx:e.effects)if(fx.id==id&&fx.duration>0){const uint64_t source=static_cast<uint64_t>(std::max(0.0f,fx.magnitude));const auto*r=s.entity(source);if(r&&r->alive)return true;}
    return false;
}
static void clear_roots_from_source(BattleState&s,uint64_t source){
    const uint32_t id=status_effect_id("proc_root");
    for(auto&e:s.entities)e.effects.erase(std::remove_if(e.effects.begin(),e.effects.end(),[&](const Effect&fx){return fx.id==id&&static_cast<uint64_t>(std::max(0.0f,fx.magnitude))==source;}),e.effects.end());
}
static void set_proc_effect(Entity&target,std::string_view name,int duration,float magnitude,std::string raw){
    const uint32_t id=status_effect_id(name);auto it=std::find_if(target.effects.begin(),target.effects.end(),[&](const Effect&fx){return fx.id==id;});
    Effect fx{id,std::max(1,duration),magnitude,std::move(raw)};if(it==target.effects.end())target.effects.push_back(std::move(fx));else *it=std::move(fx);
}
static void add_persistent_effect(Entity&target,std::string_view name,float delta,std::string raw){
    const float current=effect_magnitude(target,name);
    set_proc_effect(target,name,10000,std::max(0.0f,current+delta),std::move(raw));
}

static bool phantom_source_targetable(const Entity&e,const Entity&caster){
    if(!e.alive||e.is_hero||e.is_phantom||e.is_warmachine||e.is_statix||e.side==Side::Unknown||e.side!=caster.side)return false;
    if(caster.owner>0&&e.owner>0&&caster.owner!=e.owner)return false;
    return e.count>0&&e.max_hp_per_unit>0;
}
static bool carrier_targetable(const Entity&target,const Entity&carrier){
    if(!target.alive||target.is_hero||target.is_big||target.is_hidden||target.is_warmachine||target.is_statix)return false;
    if(target.side!=carrier.side||target.side==Side::Unknown)return false;
    if(carrier.owner>0&&target.owner>0&&carrier.owner!=target.owner)return false;
    return target.count>0&&target.count<=2*std::max(0,carrier.count);
}
static int carrier_destination_distance(const Entity&carrier,Cell dest){
    int best=1<<20;
    for(int dx=0;dx<carrier.footprint_w;++dx)for(int dy=0;dy<carrier.footprint_h;++dy)
        best=std::min(best,dist(Cell{carrier.anchor.x+dx,carrier.anchor.y+dy},dest));
    return best;
}

bool GenericSimulator::can_place(const BattleState&s,const Entity&e,Cell anchor) const{
    if(e.is_hero||e.is_warmachine)return false;
    for(int dx=0;dx<e.footprint_w;++dx)for(int dy=0;dy<e.footprint_h;++dy){
        Cell c{anchor.x+dx,anchor.y+dy};
        if(!s.inside(c)||s.occupied(c,e.uid)||std::find(s.blocked.begin(),s.blocked.end(),c)!=s.blocked.end())return false;
    }
    return true;
}

std::vector<Cell> GenericSimulator::reachable(const BattleState&s,const Entity&e) const{
    std::vector<Cell> out;if(e.is_hero||e.is_warmachine||!s.inside(e.anchor))return out;
    // Exact Srn2 follow-up: ordinary obstacle-aware movement gets a 2x budget.
    const double move_mult=e.rune_speed_active?2.0:1.0;
    const int maxd=std::max(0,(int)std::floor(effective_speed(e)*move_mult));if(maxd<=0)return out;
    if(e.is_flyer){for(int y=s.min_y;y<s.height;++y)for(int x=s.min_x;x<s.width;++x){Cell c{x,y};if(c==e.anchor||dist(e.anchor,c)>maxd)continue;if(can_place(s,e,c))out.push_back(c);}return out;}
    const int rows=std::max(0,s.height-s.min_y),cols=std::max(0,s.width-s.min_x);if(rows<=0||cols<=0)return out;
    auto idx=[&](Cell c){return std::pair<int,int>{c.y-s.min_y,c.x-s.min_x};};std::queue<std::pair<Cell,int>>q;std::vector<std::vector<uint8_t>>seen(rows,std::vector<uint8_t>(cols,0));auto[sy,sx]=idx(e.anchor);if(sy<0||sx<0||sy>=rows||sx>=cols)return out;q.push({e.anchor,0});seen[sy][sx]=1;
    while(!q.empty()){auto[c,d]=q.front();q.pop();if(d>0)out.push_back(c);if(d==maxd)continue;for(int dx=-1;dx<=1;++dx)for(int dy=-1;dy<=1;++dy){if(!dx&&!dy)continue;Cell n{c.x+dx,c.y+dy};if(!s.inside(n)||!can_place(s,e,n))continue;auto[iy,ix]=idx(n);if(iy<0||ix<0||iy>=rows||ix>=cols||seen[iy][ix])continue;seen[iy][ix]=1;q.push({n,d+1});}}
    return out;
}

std::vector<Cell> GenericSimulator::phantom_placements(const BattleState&s,const Entity&source) const{
    std::vector<Cell> out; Entity clone=source; clone.uid=UINT64_MAX; clone.is_phantom=true; clone.is_hidden=false;
    for(int y=s.min_y;y<s.height;++y)for(int x=s.min_x;x<s.width;++x){
        Cell c{x,y};
        if(footprints_overlap(clone,c,source,source.anchor))continue;
        if(!footprints_adjacent(clone,c,source,source.anchor))continue;
        if(can_place(s,clone,c))out.push_back(c);
    }
    return out;
}

std::vector<Action> GenericSimulator::legal_actions(const BattleState&s) const{
    std::vector<Action>a;auto* actor=s.entity(s.active_entity_uid);if(!actor||!actor->alive)return a;uint64_t id=1;
    if(incapacitated(*actor)){Action wait;wait.action_id=id++;wait.actor_uid=actor->uid;wait.type=ActionType::Wait;wait.source="modeled-proc-forced-skip";a.push_back(wait);return a;}
    if(actor->is_hero){
        // Standard hero hit: raw mode 062 is independently verified as a single-target,
        // zero-mana enemy action.  We keep statix/warmachine objects out until their hero
        // targetability is independently observed; ordinary, hidden-tagged and phantom
        // creature stacks are included because all three occur as mode-062 targets.
        for(const auto&target:s.entities){
            if(!target.alive||target.is_hero||target.is_statix||target.is_warmachine||
               target.side==actor->side||target.side==Side::Unknown)continue;
            Action hit;hit.action_id=id++;hit.actor_uid=actor->uid;hit.type=ActionType::HeroAction;
            hit.target_uid=target.uid;hit.source="raw-corpus-hero-basic-attack";a.push_back(std::move(hit));
        }
        for(const auto&sp:actor->spells){
            if(actor->mana<sp.mana_cost)continue;
            if(sp.direct_damage){
                for(const auto&target:s.entities){
                    if(!direct_spell_targetable(target,sp,*actor))continue;
                    Action cast;cast.action_id=id++;cast.actor_uid=actor->uid;cast.type=ActionType::Cast;cast.target_uid=target.uid;cast.ability_id=sp.id;cast.source="server-spellbook+corpus-model";a.push_back(std::move(cast));
                }
                continue;
            }
            if(sp.effect_kind==SpellEffectKind::RaiseDead){
                for(const auto&target:s.entities)if(raise_dead_targetable(target,*actor)){
                    Action cast;cast.action_id=id++;cast.actor_uid=actor->uid;cast.type=ActionType::Cast;cast.target_uid=target.uid;cast.ability_id=sp.id;cast.source="server-spellbook+raise-dead-model";a.push_back(std::move(cast));
                }
                continue;
            }
            if(sp.effect_kind==SpellEffectKind::PhantomForces){
                // In 250/250 raw observations Phantom Forces is a hero spell targeting a
                // living friendly non-phantom stack. The server chooses the adjacent clone
                // cell; destination is therefore intentionally NOT part of the user action.
                for(const auto&target:s.entities)if(phantom_source_targetable(target,*actor)&&!phantom_placements(s,target).empty()){
                    Action cast;cast.action_id=id++;cast.actor_uid=actor->uid;cast.type=ActionType::Cast;cast.target_uid=target.uid;cast.ability_id=sp.id;cast.source="server-spellbook+phantom-chance-model";a.push_back(std::move(cast));
                }
                continue;
            }
            if(sp.effect_kind==SpellEffectKind::None)continue;
            if(sp.mass){
                const bool any=std::any_of(s.entities.begin(),s.entities.end(),[&](const Entity&e){return status_targetable(e,sp,*actor);});
                if(any){Action cast;cast.action_id=id++;cast.actor_uid=actor->uid;cast.type=ActionType::Cast;cast.ability_id=sp.id;cast.source="server-spellbook+raw-status-model";a.push_back(std::move(cast));}
            }else{
                for(const auto&target:s.entities)if(status_targetable(target,sp,*actor)){
                    Action cast;cast.action_id=id++;cast.actor_uid=actor->uid;cast.type=ActionType::Cast;cast.target_uid=target.uid;cast.ability_id=sp.id;cast.source="server-spellbook+raw-status-model";a.push_back(std::move(cast));
                }
            }
        }
        // Both records are directly observed for heroes in the supplied corpus (`wUID`
        // and `SdefUID...030`). They provide valid conservative alternatives when a more
        // complex unsupported buff/summon is not yet modeled.
        a.push_back({id++,actor->uid,ActionType::Wait,std::nullopt,std::nullopt,std::nullopt,"raw-corpus"});
        a.push_back({id++,actor->uid,ActionType::Defend,std::nullopt,std::nullopt,std::nullopt,"raw-corpus"});
        return a;
    }
    const uint32_t rune_speed_id=stable_tag_id("rn2");
    if(actor->rune_speed_available&&!actor->rune_speed_consumed&&!actor->rune_speed_active){
        Action rune;rune.action_id=id++;rune.actor_uid=actor->uid;rune.type=ActionType::Ability;
        rune.ability_id=rune_speed_id;rune.source="exact:server-run-modifier+Srn2";a.push_back(std::move(rune));
    }
    const uint32_t carrier_wire_id=stable_tag_id("car");
    if(!actor->rune_speed_active&&has_tag(*actor,"carrier")){
        const int radius=std::max(0,(int)std::floor(actor->speed));
        for(const auto&target:s.entities){
            if(!carrier_targetable(target,*actor))continue;
            for(int y=s.min_y;y<s.height;++y)for(int x=s.min_x;x<s.width;++x){
                const Cell dest{x,y};
                if(dest==target.anchor||carrier_destination_distance(*actor,dest)>radius)continue;
                if(!can_place(s,target,dest))continue;
                Action carry;carry.action_id=id++;carry.actor_uid=actor->uid;carry.type=ActionType::Ability;
                carry.target_uid=target.uid;carry.destination=dest;carry.ability_id=carrier_wire_id;
                carry.source="exact:server-carrier-tooltip+Scar";a.push_back(std::move(carry));
            }
        }
    }

    // Ordinary caster stacks also carry an authoritative server spellbook.  Enable only
    // spell families whose transition is independently modeled from the new raw corpus.
    // Status spells are intentionally not generated here yet because their non-hero
    // duration semantics still need a held-out model; observed decoding is exact already.
    if(!actor->rune_speed_active) for(const auto&sp:actor->spells){
        if(actor->mana<sp.mana_cost)continue;
        if(sp.direct_damage){
            for(const auto&target:s.entities){
                if(!direct_spell_targetable(target,sp,*actor))continue;
                Action cast;cast.action_id=id++;cast.actor_uid=actor->uid;cast.type=ActionType::Cast;cast.target_uid=target.uid;cast.ability_id=sp.id;cast.source="server-spellbook+corpus-model";a.push_back(std::move(cast));
            }
        }else if(sp.effect_kind==SpellEffectKind::RaiseDead){
            for(const auto&target:s.entities)if(raise_dead_targetable(target,*actor)){
                Action cast;cast.action_id=id++;cast.actor_uid=actor->uid;cast.type=ActionType::Cast;cast.target_uid=target.uid;cast.ability_id=sp.id;cast.source="server-spellbook+raise-dead-model";a.push_back(std::move(cast));
            }
        }
    }

    const auto reach=root_active(s,*actor)?std::vector<Cell>{}:reachable(s,*actor);
    for(auto c:reach)a.push_back({id++,actor->uid,ActionType::Move,std::nullopt,c,std::nullopt,"generic"});

    std::vector<Cell> attack_anchors;attack_anchors.reserve(reach.size()+1);attack_anchors.push_back(actor->anchor);attack_anchors.insert(attack_anchors.end(),reach.begin(),reach.end());
    bool shooter_blocked=false;
    // Server tooltip for `warmachine`: adjacent enemies do not block its shooting.
    if(!actor->is_warmachine)
        for(const auto&e:s.entities)if(e.alive&&!e.is_hero&&!e.is_hidden&&e.side!=actor->side&&e.side!=Side::Unknown&&footprints_adjacent(*actor,actor->anchor,e,e.anchor)){shooter_blocked=true;break;}

    for(const auto& e:s.entities){
        if(!e.alive||e.is_hero||e.is_hidden||e.side==actor->side||e.side==Side::Unknown)continue;
        if(!actor->shoot_only) for(const Cell anchor:attack_anchors){
            if(!footprints_adjacent(*actor,anchor,e,e.anchor))continue;
            Action hit;hit.action_id=id++;hit.actor_uid=actor->uid;hit.type=ActionType::MeleeAttack;hit.target_uid=e.uid;hit.source="generic";if(anchor!=actor->anchor)hit.destination=anchor;a.push_back(std::move(hit));
        }
        if(!actor->rune_speed_active&&actor->is_shooter&&actor->shots>0&&!shooter_blocked)a.push_back({id++,actor->uid,ActionType::RangedAttack,e.uid,std::nullopt,std::nullopt,"generic"});
    }
    if(actor->rune_speed_active)return a; // 100 paired Srn2 follow-ups are MOVE/MELEE (one MOVE plus passive proc).
    Action wait;wait.action_id=id++;wait.actor_uid=actor->uid;wait.type=ActionType::Wait;wait.source="generic";a.push_back(wait);
    Action defend;defend.action_id=id++;defend.actor_uid=actor->uid;defend.type=ActionType::Defend;defend.source="generic";a.push_back(defend);return a;
}

static int total_hp(const Entity&e){if(!e.alive||e.count<=0)return 0;return (e.count-1)*std::max(1,e.max_hp_per_unit)+std::max(0,e.top_unit_hp);}

static int roll_damage(const BattleState& state,const Entity& attacker,const Entity& defender,double roll,bool ranged,bool retaliation=false,int moved_cells=0){
    const double defend_mult=defender.defending?(has_tag(defender,"takeroots")?1.50:1.30):1.0;
    double def=effective_defense(state,defender)*defend_mult;
    double atk=effective_attack(state,attacker);
    // Exact physical penetration rules recovered from the supplied catalog.
    double ignore_def=tag_percent(attacker,"ignoredefence");
    if(ranged&&has_tag(attacker,"armorpiercing"))ignore_def=std::max(ignore_def,0.50);
    if(ranged&&has_tag(attacker,"forcearrow"))ignore_def=std::max(ignore_def,0.20);
    if(!ranged&&moved_cells>0&&has_tag(attacker,"ridercharge"))ignore_def=std::max(ignore_def,std::min(1.0,0.20*moved_cells));
    def*=1.0-ignore_def;
    atk*=1.0-tag_percent(defender,"ignoreattack");
    const double lo=effective_min_damage(attacker), hi=std::max(lo,(double)effective_max_damage(attacker));
    const double damage_roll=has_tag(attacker,"accuracy")?1.0:std::clamp(roll,0.0,1.0);
    double base=attacker.count*(lo+(hi-lo)*damage_roll);
    double mult=atk>=def?1.0+0.05*(atk-def):1.0/(1.0+0.05*(def-atk));
    if(ranged){
        if(!attacker.no_range_penalty&&dist(attacker.anchor,defender.anchor)>6)mult*=0.5;
        mult*=ranged_damage_multiplier(attacker,defender);
    }
    if(!ranged&&attacker.is_shooter&&!attacker.no_melee_penalty)mult*=0.5;
    if(retaliation)mult*=retaliation_damage_multiplier(attacker);
    mult*=exact_passive_damage_multiplier(attacker,defender,ranged,moved_cells);
    mult*=shieldother_ranged_multiplier(state,defender,ranged);
    int result=std::max(0,(int)std::llround(base*mult));
    // Death strike guarantees at least one kill on targets below 400 HP/unit.
    if(has_tag(attacker,"deathstrike")&&defender.max_hp_per_unit>0&&defender.max_hp_per_unit<400&&defender.alive)
        result=std::max(result,std::max(1,defender.top_unit_hp));
    return result;
}

static void deal_damage(Entity& target,int dmg){
    // Impervious to Pain: the stack receives no damage until its first activation.
    // `last_acted_seq` is part of canonical state, so this is a deterministic tree
    // mechanic rather than a heuristic value bonus.
    if(dmg>0 && target.last_acted_seq==0 && has_tag(target,"impervioustopain"))return;
    if(dmg>0){const auto blind=status_effect_id("proc_blind"),torpor=status_effect_id("proc_torpor");target.effects.erase(std::remove_if(target.effects.begin(),target.effects.end(),[&](const Effect&fx){return fx.id==blind||fx.id==torpor;}),target.effects.end());}
    if(dmg>0 && target.is_phantom){target.count=0;target.top_unit_hp=0;target.alive=false;return;}
    const int before=total_hp(target);
    int hp=before-std::max(0,dmg);
    if(hp<=0){target.count=0;target.top_unit_hp=0;target.alive=false;return;}
    int mh=std::max(1,target.max_hp_per_unit);target.count=(hp+mh-1)/mh;target.top_unit_hp=hp-(target.count-1)*mh;target.alive=true;
    if(before>hp&&has_tag(target,"tasteofblood"))add_persistent_effect(target,"tob",1.0f,"exact:tasteofblood damaged");
}
static void restore_hp(Entity& target,int heal){
    if(heal<=0||target.max_count<=0||target.max_hp_per_unit<=0)return;
    const int mh=std::max(1,target.max_hp_per_unit);
    const int64_t cap=static_cast<int64_t>(target.max_count)*mh;
    const int64_t hp=std::min(cap,static_cast<int64_t>(total_hp(target))+heal);
    if(hp<=0)return;
    target.count=static_cast<int>((hp+mh-1)/mh);target.top_unit_hp=static_cast<int>(hp-static_cast<int64_t>(target.count-1)*mh);target.alive=true;
}
static void heal_top_unit_only(Entity& target,int heal){
    // HeroesWM Regeneration restores only the currently living top creature.
    // It must never increase stack count (unlike Raise Dead / Life Drain).
    if(heal<=0||!target.alive||target.count<=0||target.max_hp_per_unit<=0)return;
    const int mh=std::max(1,target.max_hp_per_unit);
    const int current=target.top_unit_hp>0?std::min(mh,target.top_unit_hp):mh;
    target.top_unit_hp=std::min(mh,current+heal);
}
static int regeneration_heal(int count,double roll){
    // HeroesWM formula: random integer 3..5 HP per living creature, capped at
    // the first 10 creatures in the stack. This yields the documented 3..50 range.
    const double r=std::clamp(roll,0.0,1.0);
    const int per_creature=3+std::min(2,static_cast<int>(std::floor(r*3.0)));
    return per_creature*std::min(10,std::max(0,count));
}

Transition GenericSimulator::apply(const BattleState&s,const Action&a,double roll) const{
    Transition tr;tr.state=s;auto* actor=tr.state.entity(a.actor_uid);if(!actor||!actor->alive){tr.valid=false;tr.warning="actor_missing";return tr;}
    std::vector<uint64_t> alive_nonhero_before;alive_nonhero_before.reserve(tr.state.entities.size());
    for(const auto&e:tr.state.entities)if(e.alive&&!e.is_hero)alive_nonhero_before.push_back(e.uid);
    auto legal=legal_actions(s);auto eq=[&](const Action&x){return x.type==a.type&&x.actor_uid==a.actor_uid&&x.target_uid==a.target_uid&&x.destination==a.destination&&x.ability_id==a.ability_id;};if(std::none_of(legal.begin(),legal.end(),eq)){tr.valid=false;tr.warning="illegal_action";return tr;}
    const uint32_t rune_speed_id=stable_tag_id("rn2");
    const uint32_t carrier_wire_id=stable_tag_id("car");
    const bool rune_activation=a.type==ActionType::Ability&&a.ability_id&&*a.ability_id==rune_speed_id;
    const bool carrier_action=a.type==ActionType::Ability&&a.ability_id&&*a.ability_id==carrier_wire_id;
    const bool had_rune_speed_active=actor->rune_speed_active;
    // DEFEND lasts until this stack receives its next action. Clear the previous stance
    // before applying the new action; choosing DEFEND below immediately re-enables it.
    actor->defending=false;
    const bool self_moves=(a.type==ActionType::Move&&a.destination&&*a.destination!=actor->anchor)||(a.type==ActionType::MeleeAttack&&a.destination&&*a.destination!=actor->anchor);
    if(self_moves){
        clear_roots_from_source(tr.state,actor->uid);
        const auto entrench_id=status_effect_id("proc_entrenchment");
        actor->effects.erase(std::remove_if(actor->effects.begin(),actor->effects.end(),[&](const Effect&fx){return fx.id==entrench_id;}),actor->effects.end());
    }
    if(rune_activation){
        if(!actor->rune_speed_available||actor->rune_speed_consumed||actor->rune_speed_active){tr.valid=false;tr.warning="rune_speed_unavailable";return tr;}
        actor->rune_speed_active=true;actor->rune_speed_consumed=true;
        tr.warning="exact_rune_speed_activation";
    } else if(carrier_action){
        if(!a.target_uid||!a.destination){tr.valid=false;tr.warning="carrier_target_or_destination_missing";return tr;}
        auto*target=tr.state.entity(*a.target_uid);
        if(!target||!carrier_targetable(*target,*actor)||!has_tag(*actor,"carrier")||
           carrier_destination_distance(*actor,*a.destination)>std::max(0,(int)std::floor(actor->speed))||
           !can_place(tr.state,*target,*a.destination)){tr.valid=false;tr.warning="carrier_action_invalid";return tr;}
        target->anchor=*a.destination;tr.warning="exact_carrier_relocation";
    } else if(a.type==ActionType::Move&&a.destination)actor->anchor=*a.destination;
    else if((a.type==ActionType::MeleeAttack||a.type==ActionType::RangedAttack)&&a.target_uid){
        const Cell origin=actor->anchor;
        if(a.destination)actor->anchor=*a.destination;
        const int moved_cells=a.destination?dist(origin,*a.destination):0;
        auto*t=tr.state.entity(*a.target_uid);if(t){
            const bool ranged=a.type==ActionType::RangedAttack;
            int hits=physical_hit_count(*actor,ranged);
            if(ranged){
                hits=std::min(hits,std::max(0,actor->shots));
                actor->shots=std::max(0,actor->shots-hits);
            }
            // Predator Reflexes / concentration: the defender retaliates BEFORE the
            // incoming melee hit and explicitly ignores the attacker's no-retaliation
            // property.  It still requires an available retaliation and a legal adjacent
            // melee relation; self-no-retaliation / warmachine restrictions remain intact.
            bool concentration_preempted=false;
            if(!ranged&&t->alive&&actor->alive&&has_tag(*t,"concentration")&&!retaliation_suppressed(*t)&&
               !t->shoot_only&&!t->is_warmachine&&!has_tag(*t,"noselfret")&&t->retaliation_available&&
               footprints_adjacent(*actor,actor->anchor,*t,t->anchor)){
                const int rdmg=std::max(1,(int)std::llround(roll_damage(tr.state,*t,*actor,1.0-std::clamp(roll,0.0,1.0),false,true)*damage_.multiplier(t->creature_id,ActionType::MeleeAttack)*ability_transfer_multiplier(damage_,ability_damage_,*t,*actor,ActionType::MeleeAttack)));
                const int retaliation_target_hp_before=total_hp(*actor);
                const bool retaliation_target_was_phantom=actor->is_phantom;
                deal_damage(*actor,rdmg);
                const int retaliation_actual_damage=std::max(0,retaliation_target_hp_before-total_hp(*actor));
                const int retaliation_drain_damage=(retaliation_target_was_phantom&&retaliation_actual_damage>0)?std::min(rdmg,retaliation_target_hp_before):retaliation_actual_damage;
                if(retaliation_drain_damage>0&&has_tag(*t,"lifedrain"))restore_hp(*t,retaliation_drain_damage/2);
                if(has_tag(*t,"battlethirst"))set_proc_effect(*t,"btt",10000,0.0f,"exact:battlethirst retaliation reset");
                const bool rooted_unlimited=t->defending&&has_tag(*t,"takeroots");
                if(!t->unlimited_retaliation&&!rooted_unlimited)t->retaliation_available=false;
                concentration_preempted=true;
            }
            for(int hit=0;hit<hits && actor->alive && t->alive;++hit){
                // Use deterministic spread around the sampled roll for multi-hit skills so
                // the total is stochastic without making every hit identical.
                const double hit_roll=std::clamp(roll + (hit-(hits-1)/2.0)*0.08,0.0,1.0);
                const bool incorporeal_miss=has_tag(*t,"incorporeal")&&proc_roll(hit_roll,actor->uid,t->uid,stable_tag_id("incorporeal"))>=0.50;
                const int dmg=incorporeal_miss?0:std::max(1,(int)std::llround(roll_damage(tr.state,*actor,*t,hit_roll,ranged,false,moved_cells)*damage_.multiplier(actor->creature_id,a.type)*ability_transfer_multiplier(damage_,ability_damage_,*actor,*t,a.type)));
                const int target_hp_before=total_hp(*t);
                const bool target_was_phantom=t->is_phantom;
                if(dmg>0)deal_damage(*t,dmg);
                const int actual_damage=std::max(0,target_hp_before-total_hp(*t));
                // Life Drain: restore 50% of physical damage actually inflicted. The
                // existing helper also resurrects creatures up to max_count.
                // Phantom stacks dissipate on any positive hit; cap their drain basis by
                // the rolled hit so disappearance of the whole phantom stack cannot heal.
                const int drain_damage=(target_was_phantom&&actual_damage>0)?std::min(dmg,target_hp_before):actual_damage;
                if(drain_damage>0&&has_tag(*actor,"lifedrain"))restore_hp(*actor,drain_damage/2);
                // Lizard Bite: when another friendly stack makes a melee attack against
                // a target adjacent to this creature, the lizard immediately assists for
                // half of its ordinary melee damage and receives no retaliation.  Raw
                // corpus evidence: 486 extra helper->same-target damage events, 483/486
                // helpers adjacent, with explicit Slzb<helper_uid> markers.
                if(hit==0&&!ranged&&actual_damage>0&&t->alive){
                    std::vector<uint64_t> helpers;
                    for(const auto&h:tr.state.entities){
                        if(!h.alive||h.is_hero||h.is_hidden||h.uid==actor->uid||h.side!=actor->side||!has_tag(h,"lizardbite"))continue;
                        if(footprints_adjacent(h,h.anchor,*t,t->anchor))helpers.push_back(h.uid);
                    }
                    for(uint64_t huid:helpers){
                        auto*h=tr.state.entity(huid); t=tr.state.entity(*a.target_uid);
                        if(!h||!h->alive||!t||!t->alive)continue;
                        const double hroll=std::clamp(roll+0.04*(collateral_roll(roll,huid,stable_tag_id("lizardbite"))-0.5),0.0,1.0);
                        const int bite=std::max(1,(int)std::llround(0.50*roll_damage(tr.state,*h,*t,hroll,false,false,0)*damage_.multiplier(h->creature_id,ActionType::MeleeAttack)*ability_transfer_multiplier(damage_,ability_damage_,*h,*t,ActionType::MeleeAttack)));
                        deal_damage(*t,bite);
                    }
                    t=tr.state.entity(*a.target_uid); if(!t)break;
                }
                // Fire Attack is a separate elemental component, not physical damage.
                // Apply it once per physical action (first hit only) so physical reflect
                // mechanics do not incorrectly mirror elemental damage.
                if(hit==0&&actor->alive&&t->alive&&has_tag(*actor,"fireattack")){
                    const int fire=std::max(0,(int)std::llround(5.0*actor->count*fire_damage_multiplier(*t)));
                    if(fire>0)deal_damage(*t,fire);
                }
                if(hit==0&&actual_damage>0&&actor->alive&&t->alive&&has_tag(*actor,"manadrain")&&
                   has_tag(*t,"caster")&&!t->is_statix&&!t->is_warmachine&&t->mana>0){
                    // Catalog rule + raw z/Srgl invariant: drain one mana per attacking
                    // creature (bounded by target mana), and each drained mana restores
                    // exactly one full creature worth of HP to the attacking stack.
                    const int drained=std::min(std::max(0,actor->count),std::max(0,t->mana));
                    t->mana-=drained;restore_hp(*actor,drained*std::max(1,actor->max_hp_per_unit));
                }
                // Wire W<actor><target> occurs after primary damage and before retaliation in the raw corpus.
                if(hit==0&&actual_damage>0&&has_tag(*actor,"weakeningstrike")){
                    t->attack=std::max(0.0f,t->attack-4.0f);
                    if(!has_tag(*t,"armoured")&&!has_tag(*t,"organicarmor"))t->defense=std::max(0.0f,t->defense-4.0f);
                }
                // Fire Shield reflects 20% of actual melee damage independently of retaliation.
                if(!ranged&&actual_damage>0&&actor->alive&&has_tag(*t,"fireshield")){
                    const int reflected=std::max(0,(int)std::llround(actual_damage*0.20*fire_damage_multiplier(*actor)));
                    if(reflected>0)deal_damage(*actor,reflected);
                }
                if(!ranged&&actual_damage>0&&actor->alive&&has_tag(*t,"magmashield")){
                    const int reflected=std::max(0,(int)std::llround(actual_damage*0.40*fire_damage_multiplier(*actor)));
                    if(reflected>0)deal_damage(*actor,reflected);
                }
                if(!ranged&&actual_damage>0&&actor->alive&&has_tag(*t,"painmirror"))
                    deal_damage(*actor,std::max(0,(int)std::llround(actual_damage*0.10)));
                if(!ranged&&actual_damage>0&&actor->alive&&has_tag(*t,"pleasureinpain"))
                    deal_damage(*actor,std::max(0,(int)std::llround(actual_damage*(0.10/0.90))));
                if(!ranged&&actual_damage>0&&actor->alive&&has_tag(*t,"raptureinagony"))
                    deal_damage(*actor,std::max(0,(int)std::llround(actual_damage*(0.20/0.80))));
                if(hit==0&&actual_damage>0){
                    // Stochastic proc layer: probabilities are train-only estimates and
                    // every enabled rule passed a temporal held-out stability gate.
                    if(t->alive) for(const auto&pr:proc_.rules_for(*actor,a.type)){
                        const double proc_probability=proc_.probability_for(pr,*actor,*t);
                        if(proc_roll(roll,actor->uid,t->uid,pr.ability_id)>proc_probability)continue;
                        if((pr.effect==ProcEffect::Blind||pr.effect==ProcEffect::Torpor) &&
                           (has_tag(*t,"undead")||has_tag(*t,"elemental")||has_tag(*t,"mechanical")||has_tag(*t,"iblind")))continue;
                        switch(pr.effect){
                            case ProcEffect::Root:
                                set_proc_effect(*t,"proc_root",10000,(float)actor->uid,"source="+std::to_string(actor->uid));break;
                            case ProcEffect::FerociousWound:
                                set_proc_effect(*t,"proc_ferocious_speed",2,3.0f,"-3 speed / 2 turns");
                                set_proc_effect(*t,"proc_ferocious_dot",2,std::max(1.0f,(float)dmg*0.10f),"10% primary physical damage");break;
                            case ProcEffect::Blind:
                                set_proc_effect(*t,"proc_blind",2,1.0f,"modeled 1.6-turn blind");break;
                            case ProcEffect::Torpor:
                                set_proc_effect(*t,"proc_torpor",3,1.0f,"modeled 3-turn torpor");break;
                            case ProcEffect::StunDelay:
                                // Shield Bash: raw `o<actor>` marker independently identifies the
                                // proc. It suppresses immediate retaliation and empirically delays
                                // the target's next activation. The learned next-actor model carries
                                // the delay magnitude; this effect does NOT invent a forced skipped turn.
                                set_proc_effect(*t,"proc_shieldbash",10000,1.0f,"modeled shieldbash delay");break;
                            case ProcEffect::Suffering:
                                // Cursing Attack -> Weakness/Suffering. In the supplied raw corpus
                                // Ssff is temporally stable (~73% train/heldout) and 453/455 observed
                                // applications carry magnitude 9. Duration is min(actor count,50).
                                set_proc_effect(*t,"sff",std::max(1,std::min(50,actor->count)),9.0f,"modeled cursingattack weakness");break;
                            case ProcEffect::Stone:
                                // Stoning wire marker Ssta is exact; chance is a tiny train-only
                                // conditional model gated on temporal held-out Brier/AUC. One skipped
                                // activation and 50% incoming physical/magic damage are from the catalog.
                                set_proc_effect(*t,"proc_stone",1,1.0f,"modeled stoning: one activation");break;
                            case ProcEffect::AtbDelay:
                                // Warding Arrows: T<actor><target> is exclusive to this perk in the
                                // supplied corpus. Preserve the 0.2-ATB delay as a scheduler-control
                                // marker rather than guessing the server's absolute ATB coordinate.
                                set_proc_effect(*t,"proc_warding",10000,0.2f,"modeled wardingarrows ATB -0.2");break;
                        }
                    }
                    if(auto rule=collateral_.rule_for(*actor,a.type)){
                        int secondary_hits=0;
                        for(uint64_t uid:collateral_candidates(tr.state,*actor,*t,rule->zone)){
                            if(secondary_hits>=rule->max_secondary)break;
                            auto*secondary=tr.state.entity(uid);if(!secondary||!secondary->alive)continue;
                            if(collateral_roll(roll,uid,rule->ability_id)>rule->probability)continue;
                            const double sec_roll=std::clamp(hit_roll+0.06*(collateral_roll(1.0-roll,uid,rule->ability_id)-0.5),0.0,1.0);
                            const int sec_dmg=std::max(1,(int)std::llround(roll_damage(tr.state,*actor,*secondary,sec_roll,ranged,false,moved_cells)*damage_.multiplier(actor->creature_id,a.type)*ability_transfer_multiplier(damage_,ability_damage_,*actor,*secondary,a.type)));
                            deal_damage(*secondary,sec_dmg);++secondary_hits;
                        }
                    }
                }
                // Double/triple strike: retaliation occurs only after the first hit.
                const bool swift_no_retaliation = !ranged && has_tag(*actor,"swiftattack") && has_live_effect(*t,"slw");
                const bool charge_no_retaliation = !ranged && moved_cells>0 && has_tag(*actor,"blindingcharge");
                const bool attentive_override = has_tag(*t,"attentive");
                if(!ranged&&hit==0&&!concentration_preempted&&t->alive&&actor->alive&&!retaliation_suppressed(*t)&&!swift_no_retaliation&&!charge_no_retaliation&&(!actor->no_retaliation||attentive_override)&&!t->shoot_only&&!t->is_warmachine&&!has_tag(*t,"noselfret")&&t->retaliation_available&&footprints_adjacent(*actor,actor->anchor,*t,t->anchor)){
                    const int rdmg=std::max(1,(int)std::llround(roll_damage(tr.state,*t,*actor,1.0-std::clamp(roll,0.0,1.0),false,true)*damage_.multiplier(t->creature_id,ActionType::MeleeAttack)*ability_transfer_multiplier(damage_,ability_damage_,*t,*actor,ActionType::MeleeAttack)));
                    const int retaliation_target_hp_before=total_hp(*actor);
                    const bool retaliation_target_was_phantom=actor->is_phantom;
                    deal_damage(*actor,rdmg);
                    const int retaliation_actual_damage=std::max(0,retaliation_target_hp_before-total_hp(*actor));
                    const int retaliation_drain_damage=(retaliation_target_was_phantom&&retaliation_actual_damage>0)?std::min(rdmg,retaliation_target_hp_before):retaliation_actual_damage;
                    if(retaliation_drain_damage>0&&has_tag(*t,"lifedrain"))restore_hp(*t,retaliation_drain_damage/2);
                    if(has_tag(*t,"battlethirst"))set_proc_effect(*t,"btt",10000,0.0f,"exact:battlethirst retaliation reset");
                    const bool rooted_unlimited=t->defending&&has_tag(*t,"takeroots");
                    if(!t->unlimited_retaliation&&!rooted_unlimited)t->retaliation_available=false;
                }
            }
            if(!ranged&&has_tag(*actor,"strikeandreturn")&&actor->alive)actor->anchor=origin;
        }
    } else if(a.type==ActionType::HeroAction&&a.target_uid){
        auto*t=tr.state.entity(*a.target_uid);
        if(!actor->is_hero||!t||!t->alive||t->is_hero||t->is_statix||t->is_warmachine||
           t->side==actor->side||t->side==Side::Unknown){tr.valid=false;tr.warning="hero_basic_attack_target_invalid";return tr;}
        deal_damage(*t,hero_basic_attack_damage(*actor));
    } else if(a.type==ActionType::Cast&&a.ability_id){
        const auto sit=std::find_if(actor->spells.begin(),actor->spells.end(),[&](const SpellSpec&sp){return sp.id==*a.ability_id;});
        if(sit==actor->spells.end()||actor->mana<sit->mana_cost){tr.valid=false;tr.warning="spell_unavailable";return tr;}
        if(sit->direct_damage){
            if(!a.target_uid){tr.valid=false;tr.warning="spell_target_missing";return tr;}
            auto*t=tr.state.entity(*a.target_uid);
            if(!t||!direct_spell_targetable(*t,*sit,*actor)){tr.valid=false;tr.warning="spell_target_invalid_or_immune";return tr;}
            actor->mana-=sit->mana_cost;
            const double median=hero_spell_damage_.predict(sit->id,actor->creature_id,t->creature_id);
            const double uncertainty_mult=0.65+0.70*std::clamp(roll,0.0,1.0);
            // SAT/ST rows are target-conditioned and already contain observed target resistance.
            // Apply exact resistance/vulnerability only when falling back to SA/S.
            // The spell model is trained on damage normalized by intrinsic target
            // modifiers. Therefore exact resistances/vulnerabilities are always applied
            // here, including for target creature IDs seen during training.
            const double intrinsic_magic=direct_spell_exact_multiplier(*t,*sit);
            const double dynamic_magic=direct_spell_dynamic_multiplier(tr.state,*t,*sit);
            deal_damage(*t,std::max(1,(int)std::llround(median*uncertainty_mult*intrinsic_magic*dynamic_magic)));
        }else if(sit->effect_kind==SpellEffectKind::RaiseDead){
            if(!a.target_uid){tr.valid=false;tr.warning="raise_dead_target_missing";return tr;}
            auto*t=tr.state.entity(*a.target_uid);if(!t||!raise_dead_targetable(*t,*actor)){tr.valid=false;tr.warning="raise_dead_target_invalid";return tr;}
            actor->mana-=sit->mana_cost;
            const int heal=std::max(1,(int)std::llround(raise_dead_.predict(*actor,*sit)));
            restore_hp(*t,heal);
            tr.warning="raise_dead_heal_model_approximate";
        }else if(sit->effect_kind==SpellEffectKind::PhantomForces){
            if(!a.target_uid){tr.valid=false;tr.warning="phantom_forces_source_missing";return tr;}
            auto*source=tr.state.entity(*a.target_uid);
            if(!source||!phantom_source_targetable(*source,*actor)){tr.valid=false;tr.warning="phantom_forces_source_invalid";return tr;}
            const auto placements=phantom_placements(tr.state,*source);
            if(placements.empty()){tr.valid=false;tr.warning="phantom_forces_no_adjacent_cell";return tr;}
            actor->mana-=sit->mana_cost;
            Entity clone=*source;
            uint64_t next_uid=1;for(const auto&e:tr.state.entities)next_uid=std::max(next_uid,e.uid+1);clone.uid=next_uid;
            clone.anchor=phantom_.choose_anchor(*source,placements,roll);
            clone.max_count=std::max(1,source->count);clone.count=std::max(1,source->count);clone.top_unit_hp=std::max(1,source->max_hp_per_unit);
            clone.atb=static_cast<float>(phantom_.predict_atb(*source));clone.is_phantom=true;clone.effects.clear();clone.spells.clear();
            clone.defending=false;clone.waited_this_round=false;clone.retaliation_available=true;clone.last_acted_seq=0;
            // Spawned caster phantoms carry no selectable spellbook in 66/67 observed
            // caster-source clones, so do not let rollouts invent extra clone spells.
            tr.state.entities.push_back(std::move(clone));
            tr.warning="phantom_forces_placement_and_atb_modeled";
        }else if(sit->effect_kind!=SpellEffectKind::None){
            actor->mana-=sit->mana_cost;
            const int duration=std::max(1,actor->max_count);
            if(sit->mass){
                bool any=false;for(auto&e:tr.state.entities)if(status_targetable(e,*sit,*actor)){put_status_effect(e,*sit,duration);any=true;}
                if(!any){tr.valid=false;tr.warning="status_spell_no_targets";return tr;}
            }else{
                if(!a.target_uid){tr.valid=false;tr.warning="status_spell_target_missing";return tr;}
                auto*t=tr.state.entity(*a.target_uid);if(!t||!status_targetable(*t,*sit,*actor)){tr.valid=false;tr.warning="status_spell_target_invalid";return tr;}
                put_status_effect(*t,*sit,duration);
            }
            tr.warning="status_effect_target_modifier_approximate";
        }else{tr.valid=false;tr.warning="unsupported_spell";return tr;}
    } else if(a.type==ActionType::Wait)actor->waited_this_round=true;
    else if(a.type==ActionType::Defend)actor->defending=true;

    // Battle Thirst is deterministic from the catalog and its authoritative Sbtt
    // counter: non-attacking actions add +2 Attack (cap 20); any attack resets it.
    actor=tr.state.entity(a.actor_uid);
    if(actor&&actor->alive&&has_tag(*actor,"battlethirst")){
        const bool attacked=a.type==ActionType::MeleeAttack||a.type==ActionType::RangedAttack;
        if(attacked)set_proc_effect(*actor,"btt",10000,0.0f,"exact:battlethirst attack reset");
        else set_proc_effect(*actor,"btt",10000,std::min(20.0f,effect_magnitude(*actor,"btt")+2.0f),"exact:battlethirst nonattack +2");
    }

    // Entrenchment is deterministic from the catalog: finishing an action without
    // physical relocation grants 50% resistance to all damage until the stack moves.
    actor=tr.state.entity(a.actor_uid);
    if(actor&&actor->alive&&has_tag(*actor,"entrenchment")){
        if(!self_moves) set_proc_effect(*actor,"proc_entrenchment",10000,0.50f,"exact:entrenchment stationary turn");
    }

    // Kill-trigger layer is causal (a stack death), not an attack proc.  The model was
    // trained only on decisions with exactly one non-hero alive->dead transition, so keep
    // production inference inside that same support.  Enraged passed temporal held-out
    // stability; Bloodlust did not and therefore has no loaded/enabled rule.
    if(kill_trigger_.loaded()){
        std::vector<const Entity*> newly_dead;
        for(uint64_t uid:alive_nonhero_before){const auto*e=tr.state.entity(uid);if(e&&!e->alive)newly_dead.push_back(e);}
        if(newly_dead.size()==1){
            const Entity&dead=*newly_dead.front();
            if(const auto*rule=kill_trigger_.rule("enraged")){
                for(auto&survivor:tr.state.entities){
                    if(!survivor.alive||survivor.is_hero||survivor.uid==dead.uid||survivor.owner!=dead.owner)continue;
                    if(!has_tag(survivor,"enraged")&&!has_tag(survivor,"packenrage"))continue;
                    if(proc_roll(roll,survivor.uid,dead.uid,rule->ability_id)>rule->probability)continue;
                    add_persistent_effect(survivor,"enr",(float)rule->increment,"modeled kill-trigger: conservative +1 Attack");
                }
            }
        }
    }

    actor=tr.state.entity(a.actor_uid);
    if(actor&&!rune_activation){
        tick_effects_after_action(*actor);actor->last_acted_seq=tr.state.decision_seq;
        if(had_rune_speed_active)actor->rune_speed_active=false;
    }
    ++tr.state.decision_seq;++tr.state.halfturn;++tr.state.state_seq;
    // Srn2 is preparatory: in 101/101 paired observations the same UID is immediately active again.
    uint64_t next=rune_activation&&actor?actor->uid:(actor?next_actor_.choose(tr.state,*actor,a.type):0);
    tr.state.active_entity_uid=next;
    auto* next_entity=tr.state.entity(next);
    if(next_entity){
        tr.state.side_to_act=next_entity->side;
        if(!rune_activation){
            next_entity->retaliation_available=true;next_entity->defending=false;
            const auto shield_id=status_effect_id("proc_shieldbash");
            next_entity->effects.erase(std::remove_if(next_entity->effects.begin(),next_entity->effects.end(),[&](const Effect&fx){return fx.id==shield_id;}),next_entity->effects.end());
        }
    }else tr.state.side_to_act=Side::Unknown;
    bool p=false,e=false;for(auto&x:tr.state.entities)if(x.alive&&!x.is_hero){if(x.side==Side::Player)p=true;if(x.side==Side::Pve)e=true;}
    tr.terminal=!p||!e;
    // Regeneration is a start-of-turn mechanic. The root state already contains any
    // server-applied heal, so only apply it when this rollout actually advances to a
    // new actor. Srn2 is a preparatory immediate reactivation, not a new turn.
    if(!tr.terminal&&!rune_activation&&next_entity&&has_tag(*next_entity,"regeneration"))
        heal_top_unit_only(*next_entity,regeneration_heal(next_entity->count,roll));
    if(tr.terminal)tr.state.phase=Phase::Finished;
    return tr;
}

double GenericSimulator::heuristic_value(const BattleState&s,Side perspective) const{double us=0,them=0;for(auto&e:s.entities){if(e.is_hero)continue;double hp=total_hp(e);double morale_factor=std::clamp(1.0+0.01*effective_morale(s,e),0.90,1.10);double power=(hp*(1.0+0.03*effective_attack(s,e)+0.02*effective_defense(s,e))+e.count*(effective_min_damage(e)+effective_max_damage(e)))*morale_factor;if(e.side==perspective)us+=power;else if(e.side!=Side::Unknown)them+=power;}if(us+them<=0)return 0;return (us-them)/(us+them);}
}
