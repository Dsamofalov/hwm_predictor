#include "hwm/protocol.hpp"

#include <algorithm>
#include <charconv>
#include <cmath>
#include <cctype>
#include <iomanip>
#include <sstream>
#include <string>
#include <unordered_set>

namespace hwm {
namespace {

std::string hexhash(std::string_view s) {
    uint64_t h = 1469598103934665603ULL;
    for (unsigned char c : s) { h ^= c; h *= 1099511628211ULL; }
    std::ostringstream o; o << std::hex << h; return o.str();
}

bool digits(std::string_view s) {
    return !s.empty() && std::all_of(s.begin(), s.end(), [](unsigned char c){ return std::isdigit(c); });
}

int loose_int(std::string_view s) {
    try { return static_cast<int>(std::llround(std::stod(std::string(s)))); }
    catch (...) { return 0; }
}

double loose_double(std::string_view s) {
    try { return std::stod(std::string(s)); }
    catch (...) { return 0.0; }
}

bool special_direct_damage_code(std::string_view code) {
    return code=="mfs" || code=="ltn" || code=="ice" || code=="mar" || code=="swm";
}

uint32_t stable_id(std::string_view s) {
    uint32_t h = 2166136261u;
    for (unsigned char c : s) { h ^= c; h *= 16777619u; }
    return h ? h : 1;
}


std::string_view status_wire_for(std::string_view base) {
    if(base=="fast") return "fst";
    if(base=="slow") return "slw";
    if(base=="bless") return "bls";
    if(base=="curse") return "crs";
    if(base=="stoneskin") return "stn";
    if(base=="deflect_missile") return "dfm";
    if(base=="righteous_might") return "rgm";
    if(base=="confusion") return "cnf";
    if(base=="suffering") return "sff";
    return {};
}

SpellEffectKind status_kind_for(std::string_view base) {
    if(base=="fast") return SpellEffectKind::Fast;
    if(base=="slow") return SpellEffectKind::Slow;
    if(base=="bless") return SpellEffectKind::Bless;
    if(base=="curse") return SpellEffectKind::Curse;
    if(base=="stoneskin") return SpellEffectKind::Stoneskin;
    if(base=="deflect_missile") return SpellEffectKind::DeflectMissile;
    if(base=="righteous_might") return SpellEffectKind::RighteousMight;
    if(base=="confusion") return SpellEffectKind::Confusion;
    if(base=="suffering") return SpellEffectKind::Suffering;
    return SpellEffectKind::None;
}

SpellTarget status_target_for(SpellEffectKind k) {
    switch(k){
        case SpellEffectKind::Fast:
        case SpellEffectKind::Bless:
        case SpellEffectKind::Stoneskin:
        case SpellEffectKind::DeflectMissile:
        case SpellEffectKind::RighteousMight: return SpellTarget::Friendly;
        default: return SpellTarget::Enemy;
    }
}

std::vector<std::string> split_dash(std::string_view text) {
    std::vector<std::string> out; size_t p=0;
    while(p<=text.size()){
        const size_t q=text.find('-',p);
        out.emplace_back(text.substr(p,q==std::string_view::npos?text.size()-p:q-p));
        if(q==std::string_view::npos) break;
        p=q+1;
    }
    return out;
}


const SpellSpec* status_spell_for_wire_and_cost(const Entity& caster, std::string_view wire, int mana_cost) {
    const SpellSpec* found=nullptr;
    for(const auto&sp:caster.spells){
        if(sp.direct_damage || sp.effect_kind==SpellEffectKind::None || sp.effect_kind==SpellEffectKind::RaiseDead ||
           sp.wire_code!=wire || mana_cost<=0 || mana_cost>sp.mana_cost) continue;
        // Normal and mass variants may share a wire code. For an observed S-record the
        // target delta is the same; prefer the smallest declared base cost explaining
        // the effective wire cost rather than rejecting server-side mana reductions.
        if(!found || sp.mana_cost<found->mana_cost) found=&sp;
    }
    return found;
}

const SpellSpec* direct_spell_for_wire_and_cost(const Entity& caster,std::string_view wire,int effective_cost){
    const SpellSpec* found=nullptr;
    for(const auto&sp:caster.spells){
        if(!sp.direct_damage||sp.wire_code!=wire||effective_cost<=0||effective_cost>sp.mana_cost)continue;
        if(!found||sp.mana_cost<found->mana_cost)found=&sp;
    }
    return found;
}

void upsert_status_effect(Entity& target,std::string_view wire,int duration,float magnitude,std::string_view raw){
    const uint32_t id=stable_id(wire);
    auto it=std::find_if(target.effects.begin(),target.effects.end(),[&](const Effect&e){return e.id==id;});
    Effect fx{id,std::max(0,duration),magnitude,std::string(raw)};
    if(it==target.effects.end())target.effects.push_back(std::move(fx));else *it=std::move(fx);
}

struct ParsedEntity {
    Entity entity;
    int owner = 0;
    size_t end = 0;
    bool valid = false;
};

size_t entity_end(std::string_view text, size_t start) {
    // Mddd: + 24 fixed fields of six characters, then textual traits, ^, and optional
    // 3-letter + 12-digit modifiers. This mirrors only grammar visible in the new raw corpus.
    const size_t fixed_end = start + 5 + 144;
    if (fixed_end > text.size()) return text.size();
    const size_t caret = text.find('^', fixed_end);
    if (caret == std::string_view::npos) return fixed_end;
    size_t pos = caret + 1;
    while (pos + 15 <= text.size()) {
        const auto key = text.substr(pos, 3);
        const auto val = text.substr(pos + 3, 12);
        const bool key_ok = std::all_of(key.begin(), key.end(), [](unsigned char c){ return std::isalpha(c) || c == '_'; });
        if (!key_ok || !digits(val)) break;
        pos += 15;
    }
    return pos;
}

ParsedEntity parse_entity(std::string_view raw, size_t start = 0) {
    ParsedEntity out;
    size_t p = start;
    if (p < raw.size() && raw[p] == '/') ++p;
    if (p + 5 > raw.size() || raw[p] != 'M' || !digits(raw.substr(p + 1, 3)) || raw[p + 4] != ':') return out;
    const uint64_t uid = static_cast<uint64_t>(loose_int(raw.substr(p + 1, 3)));
    const size_t fixed = p + 5;
    if (fixed + 144 > raw.size()) return out;
    std::string_view fields[24];
    for (int i = 0; i < 24; ++i) fields[i] = raw.substr(fixed + i * 6, 6);

    Entity e;
    e.uid = uid;
    out.owner = loose_int(fields[0]);
    e.creature_id = static_cast<uint32_t>(std::max(0, loose_int(fields[1])));
    e.owner = out.owner;
    e.max_hp_per_unit = std::max(0, loose_int(fields[2]));
    e.top_unit_hp = std::max(0, loose_int(fields[3]));
    e.min_damage = static_cast<float>(loose_double(fields[4]));
    e.max_damage = static_cast<float>(loose_double(fields[5]));
    e.mana = loose_int(fields[6]);
    e.speed = static_cast<float>(loose_double(fields[8]));
    e.atb = static_cast<float>(loose_double(fields[9]));
    e.initiative = static_cast<float>(loose_double(fields[10]));
    e.max_count = std::max(0, loose_int(fields[11]));
    e.count = std::max(0, loose_int(fields[12]));
    e.anchor.x = loose_int(fields[13]);
    e.anchor.y = loose_int(fields[14]);
    e.shots = std::max(0, loose_int(fields[16]));
    e.attack = static_cast<float>(loose_double(fields[17]));
    e.defense = static_cast<float>(loose_double(fields[18]));
    e.morale = static_cast<float>(loose_double(fields[19]));
    e.luck = static_cast<float>(loose_double(fields[20]));
    e.alive = e.count > 0;
    // In all 866 supplied PvE battles the player's primary hero is owner 1. Keep neutral
    // owner 0 Unknown rather than forcing it onto either side.
    e.side = out.owner == 1 ? Side::Player : (out.owner > 1 ? Side::Pve : Side::Unknown);

    const size_t end = entity_end(raw, p);
    out.end = end;
    const std::string tail(raw.substr(fixed + 144, end - (fixed + 144)));
    e.is_hero = tail.find("|hero|") != std::string::npos;
    e.is_big = tail.find("|big|") != std::string::npos;
    e.is_flyer = tail.find("|flyer|") != std::string::npos;
    e.is_shooter = tail.find("|shooter|") != std::string::npos;
    e.is_warmachine = tail.find("|warmachine|") != std::string::npos;
    // `hidden` is an authoritative server ability tag. Hidden/preloaded entities are
    // not treated as ordinary blocking board occupants until a later exact mechanic
    // plugin establishes their visible-board presence.
    e.is_hidden = tail.find("|hidden|") != std::string::npos;
    e.is_statix = tail.find("|statix|") != std::string::npos;
    // Spawned Phantom Forces objects carry an authoritative post-^ modifier
    // `phmXXXXXXXXXXXX` in every one of the 250 independently observed Sphm spawns.
    // Keep it as explicit state so damage/lifecycle rules do not depend on localized names.
    const auto mods_pos = tail.find('^');
    e.is_phantom = mods_pos != std::string::npos && tail.find("phm", mods_pos + 1) != std::string::npos;
    if(mods_pos != std::string::npos){
        const auto rp=tail.find("run",mods_pos+1);
        if(rp!=std::string::npos && rp+15<=tail.size() && digits(std::string_view(tail).substr(rp+3,12))){
            e.run_modifier=tail.substr(rp+3,12);
            // New 866-battle corpus: all 501 rune-capable entities have exactly this
            // server modifier; all 102 Srn2 activations are from this set and no UID
            // activates the mechanic more than once in a battle.
            e.rune_speed_available=e.run_modifier=="100000000001";
        }
    }
    e.shoot_only = tail.find("|shootonly|") != std::string::npos;
    e.double_shoot = tail.find("|doubleshoot|") != std::string::npos;
    e.unlimited_retaliation = tail.find("|uretalation|") != std::string::npos;
    e.no_retaliation = tail.find("|noretalation|") != std::string::npos;
    e.no_range_penalty = tail.find("|norangepenalty|") != std::string::npos;
    // The server catalog names this trait `nopenalty`: it removes the normal
    // shooter melee penalty. Keep the historical alias for protocol drift.
    e.no_melee_penalty = tail.find("|nopenalty|") != std::string::npos ||
                         tail.find("|nomeleepenalty|") != std::string::npos;
    if (e.is_big) { e.footprint_w=2; e.footprint_h=2; }

    // Selectable spellbook is carried by the authoritative server M-record after the `~` marker.
    // This appears on heroes and on a smaller set of caster creatures; parse it for both. 
    // Record grammar is repeated 7-token groups:
    // name-mana-level-effect-secondary-persistent-school-.  This parser is based only on
    // the new raw corpus.  For status spells, the S-record independently proves that the
    // first non-zero two-digit field equals the selected spell mana cost and the following
    // four-digit field equals 100*M-field[11] for hero casts.  The mass form is named with
    // an `m` prefix in the server spellbook (mfast/mslow/...).
    {
        // Real tails can contain an earlier sprite-prefix marker (e.g. `|~leaderinkani`).
        // The authoritative selectable spellbook is the LAST `|~` before the `^` modifier
        // section. Using tail.find('~') silently produced zero real spells in such records.
        const size_t magic_end=tail.find('^');
        const size_t marker=tail.rfind("|~",magic_end);
        const size_t magic_start=marker==std::string::npos?std::string::npos:marker+2;
        if(magic_start!=std::string::npos){
            const std::string magic=tail.substr(magic_start,
                magic_end==std::string::npos?std::string::npos:magic_end-magic_start);
            const auto tok=split_dash(magic);
            for(size_t t=0;t+6<tok.size();t+=7){
                const std::string& name=tok[t]; if(name.empty()) continue;
                int cost=0; float effect=0,secondary=0;
                try{cost=std::stoi(tok[t+1]);effect=std::stof(tok[t+3]);secondary=std::stof(tok[t+4]);}catch(...){continue;}
                std::string base=name; bool mass=false;
                if(name.size()>1 && name[0]=='m' && !status_wire_for(std::string_view(name).substr(1)).empty()){
                    mass=true;base=name.substr(1);
                }
                std::string wire; bool direct=false; SpellEffectKind kind=SpellEffectKind::None;
                if(base=="magicfist"){wire="mfs";direct=true;kind=SpellEffectKind::DirectDamage;}
                else if(base=="lighting"){wire="ltn";direct=true;kind=SpellEffectKind::DirectDamage;}
                else if(base=="icebolt"){wire="ice";direct=true;kind=SpellEffectKind::DirectDamage;}
                else if(base=="magicarrow"){wire="mar";direct=true;kind=SpellEffectKind::DirectDamage;}
                else if(base=="swarm"){wire="swm";direct=true;kind=SpellEffectKind::DirectDamage;}
                else if(base=="raisedead"){wire="rsd";kind=SpellEffectKind::RaiseDead;}
                else if(base=="phantom_forces"){wire="phm";kind=SpellEffectKind::PhantomForces;}
                else { auto w=status_wire_for(base); if(!w.empty()){wire=std::string(w);kind=status_kind_for(base);} }
                if(wire.empty()) continue;
                const uint32_t id=stable_id(name);
                if(std::any_of(e.spells.begin(),e.spells.end(),[&](const SpellSpec&sp){return sp.id==id;}))continue;
                const SpellTarget target = (kind==SpellEffectKind::RaiseDead||kind==SpellEffectKind::PhantomForces) ? SpellTarget::Friendly :
                    (kind==SpellEffectKind::None||direct?SpellTarget::Enemy:status_target_for(kind));
                e.spells.push_back({id,name,wire,std::max(0,cost),direct,mass,kind,target,effect,secondary});
            }
        }
    }

    // Hash textual ability tags into stable uint32 IDs. Raw strings remain recoverable from
    // the Python catalog; runtime needs compact IDs only.
    size_t version = tail.find("|[");
    if (version != std::string::npos) {
        size_t after_version = tail.find('|', version + 2);
        if (after_version != std::string::npos) {
            size_t name_end = tail.find('|', after_version + 1);
            size_t pos = name_end == std::string::npos ? tail.size() : name_end + 1;
            while (pos < tail.size()) {
                size_t q = tail.find('|', pos);
                std::string token = tail.substr(pos, q == std::string::npos ? tail.size() - pos : q - pos);
                if (token.empty() || token[0] == '~') break;
                if (token.find('^') != std::string::npos) break;
                e.ability_ids.push_back(stable_id(token));
                pos = q == std::string::npos ? tail.size() : q + 1;
            }
        }
    }
    out.entity = std::move(e);
    out.valid = true;
    return out;
}

void grow_bounds(BattleState& s, Cell c) {
    if (c.x >= 0) s.width = std::max(s.width, c.x + 1);
    if (c.y >= 0) s.height = std::max(s.height, c.y + 1);
}

void apply_damage(Entity& e, int amount) {
    if (amount <= 0 || e.count <= 0 || e.max_hp_per_unit <= 0) return;
    // Raw-corpus invariant for Phantom Forces: 87/87 phantoms that receive positive
    // d-record damage never activate or deal damage afterwards; 81 of those hits are
    // sub-lethal under ordinary stack HP. Zero-damage hits do NOT show this invariant.
    // The server emits no h<uid> removal record, so dissipation belongs to damage semantics.
    if (e.is_phantom) { e.count=0; e.top_unit_hp=0; e.alive=false; return; }
    const int mh = std::max(1, e.max_hp_per_unit);
    const int top = e.top_unit_hp > 0 ? e.top_unit_hp : mh;
    const int64_t total = static_cast<int64_t>(e.count - 1) * mh + top;
    const int64_t remaining = total - amount;
    if (remaining <= 0) { e.count = 0; e.top_unit_hp = 0; e.alive = false; return; }
    e.count = static_cast<int>((remaining + mh - 1) / mh);
    e.top_unit_hp = static_cast<int>(remaining - static_cast<int64_t>(e.count - 1) * mh);
    e.alive = true;
}

int64_t entity_total_hp(const Entity& e) {
    if(!e.alive || e.count<=0 || e.max_hp_per_unit<=0) return 0;
    const int mh=std::max(1,e.max_hp_per_unit);
    const int top=e.top_unit_hp>0?e.top_unit_hp:mh;
    return static_cast<int64_t>(e.count-1)*mh+top;
}

void apply_heal(Entity& e, int amount) {
    if(amount<=0 || e.max_count<=0 || e.max_hp_per_unit<=0) return;
    const int mh=std::max(1,e.max_hp_per_unit);
    const int64_t cap=static_cast<int64_t>(e.max_count)*mh;
    const int64_t restored=std::min(cap,entity_total_hp(e)+static_cast<int64_t>(amount));
    if(restored<=0) return;
    e.count=static_cast<int>((restored+mh-1)/mh);
    e.top_unit_hp=static_cast<int>(restored-static_cast<int64_t>(e.count-1)*mh);
    e.alive=true;
}

bool has_ability_local(const Entity& e,std::string_view name){
    const uint32_t id=stable_id(name);
    return std::find(e.ability_ids.begin(),e.ability_ids.end(),id)!=e.ability_ids.end();
}

const SpellSpec* validated_phantom_forces_spell(const Entity& caster,const Entity& source,const Entity& clone,int effective_cost){
    if(!caster.is_hero || source.is_hero || source.is_phantom || !source.alive || !clone.is_phantom)return nullptr;
    if(caster.owner!=source.owner || clone.owner!=source.owner || clone.creature_id!=source.creature_id)return nullptr;
    const SpellSpec* found=nullptr;
    for(const auto& sp:caster.spells){
        if(sp.effect_kind!=SpellEffectKind::PhantomForces || sp.name!="phantom_forces")continue;
        if(effective_cost<=0 || effective_cost>sp.mana_cost)continue;
        if(found && found->id!=sp.id)return nullptr;
        found=&sp;
    }
    return found;
}

const SpellSpec* validated_raise_dead_spell(const Entity& caster,const Entity& target,int effective_cost){
    if(effective_cost<=0 || caster.owner!=target.owner || !has_ability_local(target,"undead")) return nullptr;
    if(target.max_count<=0 || target.max_hp_per_unit<=0 || entity_total_hp(target)>=static_cast<int64_t>(target.max_count)*target.max_hp_per_unit) return nullptr;
    const SpellSpec* found=nullptr;
    for(const auto&sp:caster.spells){
        if(sp.effect_kind!=SpellEffectKind::RaiseDead || sp.wire_code!="rsd" || effective_cost>sp.mana_cost) continue;
        if(found) return nullptr;
        found=&sp;
    }
    return found;
}

struct TurnSlice { uint32_t turn = 0; std::string_view body; };

std::vector<TurnSlice> turn_slices(std::string_view p) {
    struct Mark { size_t start, body; uint32_t turn; };
    std::vector<Mark> marks;
    const auto first = p.find("turns=>");
    if (first != std::string_view::npos) {
        size_t q = first + 7, colon = p.find(':', q);
        if (colon != std::string_view::npos && digits(p.substr(q, colon - q)))
            marks.push_back({first, colon + 1, static_cast<uint32_t>(loose_int(p.substr(q, colon-q)))});
    }
    size_t pos = 0;
    while ((pos = p.find(";>", pos)) != std::string_view::npos) {
        size_t q = pos + 2, colon = p.find(':', q);
        if (colon == std::string_view::npos) break;
        if (digits(p.substr(q, colon - q))) marks.push_back({pos, colon + 1, static_cast<uint32_t>(loose_int(p.substr(q,colon-q)))});
        pos = colon + 1;
    }
    std::sort(marks.begin(), marks.end(), [](const Mark&a,const Mark&b){ return a.start < b.start; });
    std::vector<TurnSlice> out;
    for (size_t i=0;i<marks.size();++i) {
        size_t end = i+1<marks.size()?marks[i+1].start:p.size();
        if (end>marks[i].body && p[end-1]==';') --end;
        out.push_back({marks[i].turn,p.substr(marks[i].body,end-marks[i].body)});
    }
    return out;
}

bool has_static(std::string_view p) {
    return p.find(";/M") != std::string_view::npos && p.find("bm_tooltips=") != std::string_view::npos;
}

void parse_static(BattleState& s, std::string_view payload, std::vector<DecodeWarning>& warnings) {
    // Static state is the third |# section in observed lastturn=-3 payloads.
    // Across all 866 supplied battles ordinary combat units occupy the complete raw
    // coordinate domain x=1..12, y=1..20. x=0/13 are reserved for heroes/warmachines.
    // Keep this protocol-space board fixed instead of shrinking legality to cells happened
    // to be visited in one replay.
    s.min_x=1; s.min_y=1; s.width=13; s.height=21;
    size_t a = payload.find("|#");
    size_t b = a == std::string_view::npos ? std::string_view::npos : payload.find("|#", a + 2);
    std::string_view state_part = b == std::string_view::npos ? payload : payload.substr(b + 2);
    size_t pos = 0;
    while ((pos = state_part.find("M", pos)) != std::string_view::npos) {
        if (pos + 5 > state_part.size() || !digits(state_part.substr(pos+1,3)) || state_part[pos+4] != ':') { ++pos; continue; }
        auto pe = parse_entity(state_part, pos);
        if (!pe.valid) { warnings.push_back({"ENTITY_PARSE", "Could not parse M record near offset " + std::to_string(pos)}); ++pos; continue; }
        if (auto* existing = s.entity(pe.entity.uid)) *existing = pe.entity; else s.entities.push_back(pe.entity);
        if(!pe.entity.is_hero && !pe.entity.is_warmachine) grow_bounds(s, pe.entity.anchor);
        pos = std::max(pos + 1, pe.end);
    }
}

struct CommandStats { size_t total=0, classified=0, records=0, unknown=0, semantic_unresolved=0; bool result=false; bool saw_turn1=false; };

void emit(std::vector<BattleEvent>& events, uint64_t& seq, std::string type, uint64_t actor, uint64_t target, std::string_view raw) {
    events.push_back({seq++,std::move(type),actor,target,std::string(raw)});
}

void apply_commands(BattleState& s, std::string_view text, std::vector<BattleEvent>& events, CommandStats& st, uint64_t& seq) {
    struct PendingMove { Cell cell{}; std::string raw; };
    struct DecisionCtx {
        uint64_t actor_uid=0;
        std::vector<PendingMove> moves;
        bool move_mode_decided=false;
        bool apply_actor_moves=false;
        bool saw_active_damage=false;
        bool active_attack_was_ranged=false;
        bool saw_wait=false;
        bool saw_defend=false;
        bool saw_active_special=false;
        bool saw_shieldbash_proc=false;
        std::string exact_status_wire;
        uint64_t pending_p_uid=0;
    } ctx;

    auto reset_ctx=[&](uint64_t actor_uid){
        ctx=DecisionCtx{};
        ctx.actor_uid=actor_uid;
    };
    reset_ctx(s.active_entity_uid);

    auto resolve_observed_big_anchor=[&](const Entity& e, Cell raw)->Cell {
        if(!e.is_big) return raw;
        auto legal=[&](Cell anchor)->bool {
            if(anchor.x < 1 || anchor.y < 1) return false;
            for(const auto& other:s.entities){
                if(other.uid==e.uid || !other.alive || other.is_hero || other.is_hidden) continue;
                for(int ex=0;ex<e.footprint_w;++ex) for(int ey=0;ey<e.footprint_h;++ey){
                    const Cell ec{anchor.x+ex,anchor.y+ey};
                    for(int ox=0;ox<other.footprint_w;++ox) for(int oy=0;oy<other.footprint_h;++oy)
                        if(ec==Cell{other.anchor.x+ox,other.anchor.y+oy}) return false;
                }
            }
            return true;
        };
        if(legal(raw)) return raw;
        const Cell candidates[]={{raw.x,raw.y},{raw.x-1,raw.y},{raw.x,raw.y-1},{raw.x-1,raw.y-1}};
        bool found=false; Cell best=raw; int best_cheb=0,best_man=0,best_idx=0;
        for(int idx=0;idx<4;++idx){
            const Cell c=candidates[idx]; if(!legal(c)) continue;
            const int dx=std::abs(c.x-e.anchor.x),dy=std::abs(c.y-e.anchor.y);
            const int cheb=std::max(dx,dy),man=dx+dy;
            if(!found || cheb<best_cheb || (cheb==best_cheb && (man<best_man || (man==best_man && idx<best_idx)))){
                found=true;best=c;best_cheb=cheb;best_man=man;best_idx=idx;
            }
        }
        return found?best:raw;
    };
    auto apply_one_move=[&](uint64_t uid,const PendingMove& pm){
        if(auto*e=s.entity(uid)){
            e->anchor=resolve_observed_big_anchor(*e,pm.cell);
            if(!e->is_hero)grow_bounds(s,e->anchor);
        }
        emit(events,seq,"MOVE",uid,0,pm.raw);
    };
    auto flush_moves=[&](bool apply){
        if(apply) for(const auto&pm:ctx.moves) apply_one_move(ctx.actor_uid,pm);
        else for(const auto&pm:ctx.moves) emit(events,seq,"POSITION_MARKER",ctx.actor_uid,0,pm.raw);
        ctx.moves.clear();
    };
    auto finalize_decision=[&](){
        auto* before_actor=s.entity(ctx.actor_uid);
        const Cell before_anchor=before_actor?before_actor->anchor:Cell{};
        bool apply=ctx.apply_actor_moves;
        if(!ctx.move_mode_decided){
            const auto* actor=s.entity(ctx.actor_uid);
            if(ctx.saw_wait||ctx.saw_defend) apply=false;
            else if(ctx.saw_active_damage) apply=ctx.apply_actor_moves;
            else if(ctx.saw_active_special) apply=actor && !actor->is_hero;
            else apply=!ctx.moves.empty(); // plain MOVE; empty decisions stay stationary.
        }
        flush_moves(apply);
        if(auto* actor=s.entity(ctx.actor_uid);actor&&actor->alive&&has_ability(*actor,"entrenchment")){
            const bool moved=actor->anchor!=before_anchor;
            const auto id=status_effect_id("proc_entrenchment");
            if(moved) actor->effects.erase(std::remove_if(actor->effects.begin(),actor->effects.end(),[&](const Effect&fx){return fx.id==id;}),actor->effects.end());
            else upsert_status_effect(*actor,"proc_entrenchment",10000,0.50f,"observed:stationary action");
        }
        // Ordinary ranged attacks do not carry an explicit ammo-delta record. The
        // authoritative ammo of 250 Phantom Forces clones independently verifies
        // one ammo per shot and two for `doubleshoot` in 238/250 histories.
        if(ctx.active_attack_was_ranged){
            if(auto* actor=s.entity(ctx.actor_uid); actor && actor->shots>0){
                const int spent=actor->double_shoot?2:1;
                actor->shots=std::max(0,actor->shots-spent);
            }
        }
    };
    auto decide_attack_move=[&](uint64_t target_uid){
        if(ctx.move_mode_decided) return;
        auto* actor=s.entity(ctx.actor_uid);
        auto* target=s.entity(target_uid);
        bool adjacent=false;
        if(actor&&target){
            Cell aa=ctx.moves.empty()?actor->anchor:ctx.moves.back().cell;
            for(int ax=0;ax<actor->footprint_w&&!adjacent;++ax)
                for(int ay=0;ay<actor->footprint_h&&!adjacent;++ay)
                    for(int bx=0;bx<target->footprint_w&&!adjacent;++bx)
                        for(int by=0;by<target->footprint_h&&!adjacent;++by)
                            if(std::max(std::abs((aa.x+ax)-(target->anchor.x+bx)),
                                        std::abs((aa.y+ay)-(target->anchor.y+by)))<=1) adjacent=true;
        }
        // Raw-corpus invariant: almost every ordinary ranged/WAIT/DEFEND action still
        // emits mUUUXXYY.  For a shooter damaging a non-adjacent target it is a position
        // marker, not movement. Heroes are also non-board actors in the supported PvE
        // corpus, so their m-record is never applied as a creature relocation.
        const bool ranged_marker=actor && ((actor->is_shooter && !adjacent) || actor->is_hero);
        ctx.move_mode_decided=true;
        ctx.apply_actor_moves=!ranged_marker;
        ctx.active_attack_was_ranged = ranged_marker && actor && actor->is_shooter && !actor->is_hero;
        flush_moves(ctx.apply_actor_moves);
    };

    size_t i=0;
    auto known=[&](size_t n){st.total+=n;st.classified+=n;st.records++;};
    auto semantic=[&](size_t n){st.total+=n;st.classified+=n;st.records++;st.semantic_unresolved++;};
    auto unknown=[&](size_t n){st.total+=n;st.records++;st.unknown++;st.semantic_unresolved++; if(s.recent_unknown.size()<64)s.recent_unknown.emplace_back(text.substr(i,n));};
    while(i<text.size()) {
        if(text[i]==';'){++i;continue;}
        if(text.compare(i,2,"f<")==0 || text.compare(i,5,"f_en<")==0) {
            finalize_decision();
            const auto raw=text.substr(i); known(raw.size()); emit(events,seq,"BATTLE_END",0,0,raw); s.phase=Phase::Finished; st.result=true; break;
        }
        if(text[i]=='M' && i+5<=text.size() && digits(text.substr(i+1,3)) && text[i+4]==':') {
            auto pe=parse_entity(text,i); size_t n=pe.valid?pe.end-i:1;
            if(pe.valid){known(n); if(auto* e=s.entity(pe.entity.uid))*e=pe.entity;else s.entities.push_back(pe.entity); if(!pe.entity.is_hero && !pe.entity.is_warmachine) grow_bounds(s,pe.entity.anchor);emit(events,seq,"SUMMON",pe.entity.uid,0,text.substr(i,n));i+=n;continue;}
        }
        if(text[i]=='S' && i+4<=text.size()) {
            const auto code=text.substr(i+1,3);
            const bool code_ok=std::all_of(code.begin(),code.end(),[](unsigned char c){return std::isalnum(c)||c=='_'||c=='-';});
            if(code_ok){size_t j=i+4;while(j<text.size()&&(std::isdigit((unsigned char)text[j])||text[j]=='.'||text[j]=='+'||text[j]=='-'))++j;size_t n=j-i;uint64_t uid=0;if(j>=i+7&&digits(text.substr(i+4,3)))uid=loose_int(text.substr(i+4,3));
                if(uid==ctx.actor_uid) ctx.saw_active_special=true;
                if(code=="def"){
                    known(n);ctx.saw_defend = ctx.saw_defend || uid==ctx.actor_uid;
                    if(auto*e=s.entity(uid)) e->defending=true;
                    emit(events,seq,"DEFEND",uid,0,text.substr(i,n));
                }
                else if(code=="car" && j==i+19 && digits(text.substr(i+4,15))){
                    // Exact carrier relocation recovered from all 102 records in the new
                    // corpus and cross-checked against the server `carrier` tooltip:
                    // actor3,target3,actor_x2,actor_y2,dest_x2,dest_y2,flag1.
                    const uint64_t target_uid=loose_int(text.substr(i+7,3));
                    const Cell actor_pos{loose_int(text.substr(i+10,2)),loose_int(text.substr(i+12,2))};
                    const Cell dest{loose_int(text.substr(i+14,2)),loose_int(text.substr(i+16,2))};
                    const int flag=loose_int(text.substr(i+18,1));
                    auto* actor=s.entity(uid);auto* target=s.entity(target_uid);
                    const uint32_t carrier_id=stable_id("carrier");
                    const bool has_carrier=actor&&std::find(actor->ability_ids.begin(),actor->ability_ids.end(),carrier_id)!=actor->ability_ids.end();
                    const bool exact=actor&&target&&has_carrier&&actor->anchor==actor_pos&&
                        actor->owner==target->owner&&!target->is_big&&target->count<=2*actor->count&&flag==0;
                    if(exact){
                        known(n);target->anchor=dest;if(!target->is_hero)grow_bounds(s,dest);
                        emit(events,seq,"CARRIER_RELOCATE",uid,target_uid,text.substr(i,n));
                    }else{
                        semantic(n);emit(events,seq,"SPECIAL",uid,target_uid,text.substr(i,n));
                    }
                }
                else if(code=="rn2" && j==i+19 && digits(text.substr(i+4,15))){
                    const auto state12=text.substr(i+7,12);
                    auto* actor=s.entity(uid);
                    const bool clear=state12=="000000000000";
                    const bool exact=actor && actor->rune_speed_available &&
                        (clear ? actor->rune_speed_active : !actor->rune_speed_consumed);
                    if(exact){
                        known(n);
                        if(clear) actor->rune_speed_active=false;
                        else { actor->rune_speed_active=true; actor->rune_speed_consumed=true; }
                        emit(events,seq,clear?"RUNE_SPEED_CLEAR":"RUNE_SPEED_ACTIVATE",uid,0,text.substr(i,n));
                    }else{
                        semantic(n); emit(events,seq,"SPECIAL",uid,0,text.substr(i,n));
                    }
                }
                else if(code=="phm" && j==i+19 && digits(text.substr(i+4,15))){
                    // 250/250 independently recovered records:
                    // caster3,clone_uid3,effective_mana2,source_uid3,trailer4. Trailer is
                    // 0000; the preceding M<clone> is authoritative clone state/position.
                    const uint64_t clone_uid=loose_int(text.substr(i+7,3));
                    const int effective_cost=loose_int(text.substr(i+10,2));
                    const uint64_t source_uid=loose_int(text.substr(i+12,3));
                    const int trailer=loose_int(text.substr(i+15,4));
                    auto* caster=s.entity(uid); auto* source=s.entity(source_uid); auto* clone=s.entity(clone_uid);
                    const SpellSpec* spell=(caster&&source&&clone&&trailer==0)?validated_phantom_forces_spell(*caster,*source,*clone,effective_cost):nullptr;
                    if(spell){
                        known(n); caster->mana=std::max(0,caster->mana-effective_cost);
                        // P<clone><model> is state-neutral in exact Sphm decisions; it was
                        // conservatively counted semantic when encountered before M/Sphm.
                        if(ctx.pending_p_uid==clone_uid && st.semantic_unresolved>0)--st.semantic_unresolved;
                        emit(events,seq,"PHANTOM_FORCES",uid,source_uid,text.substr(i,n));
                    }else{
                        semantic(n); emit(events,seq,"SPECIAL",uid,source_uid,text.substr(i,n));
                    }
                }
                else if(code=="rsd" && j==i+19 && digits(text.substr(i+4,6)) && text[i+10]=='-' &&
                        digits(text.substr(i+11,2)) && digits(text.substr(i+13,6))){
                    // 434/434 supplied raw records independently satisfy:
                    // caster3,target3,-1<effective-mana>,heal6.  The caster's authoritative
                    // spellbook contains exactly one raisedead entry, the target is a damaged
                    // same-owner undead stack, and the final six digits are the HP restored.
                    const uint64_t target_uid=loose_int(text.substr(i+7,3));
                    const int effective_cost=loose_int(text.substr(i+12,1));
                    const int heal=loose_int(text.substr(i+13,6));
                    auto* caster=s.entity(uid); auto* target=s.entity(target_uid);
                    const SpellSpec* spell=(caster&&target)?validated_raise_dead_spell(*caster,*target,effective_cost):nullptr;
                    if(spell){
                        known(n); caster->mana=std::max(0,caster->mana-effective_cost); apply_heal(*target,heal);
                        emit(events,seq,"RAISE_DEAD",uid,target_uid,text.substr(i,n));
                    }else{
                        semantic(n); emit(events,seq,"SPECIAL",uid,target_uid,text.substr(i,n));
                    }
                }
                else if(code=="msl" && j==i+19 && digits(text.substr(i+4,15)) && text.substr(i+7,12)=="000000000000"){
                    const uint64_t slam_uid=loose_int(text.substr(i+4,3));
                    auto* slam_actor=s.entity(slam_uid);
                    const bool exact=slam_actor&&slam_actor->alive&&has_ability(*slam_actor,"mightyslam");
                    if(exact){known(n);upsert_status_effect(*slam_actor,"msl",3,1.0f,text.substr(i,n));emit(events,seq,"MIGHTY_SLAM",slam_uid,0,text.substr(i,n));}
                    else{semantic(n);emit(events,seq,"SPECIAL",slam_uid,0,text.substr(i,n));}
                }
                else if(code=="mfd" && j==i+19 && digits(text.substr(i+4,15)) && text.substr(i+12,7)=="0000000"){
                    // Mana Feed corpus invariant (42/42 observed): actor3,own_hero3,
                    // amount2,0000000. The amount is min(current count,current mana).
                    const uint64_t target_uid=loose_int(text.substr(i+7,3));
                    const int amount=loose_int(text.substr(i+10,2));
                    auto* actor=s.entity(uid); auto* hero=s.entity(target_uid);
                    const int expected=actor?std::min(std::max(0,actor->count),std::max(0,actor->mana)):0;
                    const bool exact=actor&&hero&&actor->alive&&has_ability(*actor,"manafeed")&&hero->is_hero&&
                        actor->owner==hero->owner&&amount>0&&amount==expected;
                    if(exact){known(n);actor->mana-=amount;hero->mana+=amount;emit(events,seq,"MANA_FEED",uid,target_uid,text.substr(i,n));}
                    else{semantic(n);emit(events,seq,"SPECIAL",uid,target_uid,text.substr(i,n));}
                }
                else if(code=="rgl" && j==i+19 && digits(text.substr(i+4,15)) && text.substr(i+4,3)=="000"){
                    // Mana Drain heal record.  New raw-corpus invariant: when the second UID
                    // belongs to a stack carrying `manadrain`, the final 9 digits equal
                    // drained_mana * max_hp_per_unit exactly (e.g. 5*19=95, 27*19=513).
                    const uint64_t source_uid=loose_int(text.substr(i+7,3));
                    const int heal=loose_int(text.substr(i+10,9));
                    auto* source=s.entity(source_uid);
                    const bool exact=source&&has_ability(*source,"manadrain")&&source->max_hp_per_unit>0&&
                        heal>=0&&heal%source->max_hp_per_unit==0;
                    if(exact){known(n);apply_heal(*source,heal);emit(events,seq,"MANA_DRAIN_HEAL",source_uid,0,text.substr(i,n));}
                    else{semantic(n);emit(events,seq,"SPECIAL",uid,0,text.substr(i,n));}
                }
                else if((code=="enr"||code=="blt") && j==i+19 && digits(text.substr(i+4,15)) && text.substr(i+7,9)=="100000000"){
                    // Generic persistent modifier layout actor3 + 100000000 + magnitude3.
                    // Held-out damage validation confirms the final magnitude is the current
                    // Attack bonus for Enraged/Bloodlust (not an increment).
                    auto* actor=s.entity(uid);
                    const bool enr=code=="enr";
                    const bool exact=actor && (enr ? (has_ability(*actor,"enraged")||has_ability(*actor,"packenrage")) : has_ability(*actor,"bloodlust"));
                    const int magnitude=loose_int(text.substr(i+16,3));
                    if(exact){
                        known(n);upsert_status_effect(*actor,code,10000,(float)magnitude,text.substr(i,n));
                        emit(events,seq,enr?"ENRAGED_ATTACK_BONUS":"BLOODLUST_ATTACK_BONUS",uid,0,text.substr(i,n));
                    }else{semantic(n);emit(events,seq,"SPECIAL",uid,0,text.substr(i,n));}
                }
                else if((code=="btt"||code=="tob") && j==i+19 && digits(text.substr(i+4,15)) && text.substr(i+10,9)=="000000000"){
                    // Corpus-authoritative persistent combat counters:
                    //   Sbtt uid3,current_attack_bonus3,zeros9 (0/2/4/.../20)
                    //   Stob uid3,current_absolute_min_damage3,zeros9
                    // Exactness is gated by the matching server-declared ability.
                    auto* actor=s.entity(uid); const int value=loose_int(text.substr(i+7,3));
                    const bool thirst=code=="btt";
                    const bool exact=actor&&has_ability(*actor,thirst?"battlethirst":"tasteofblood")&&
                        (thirst?(value>=0&&value<=20):(value>=0));
                    if(exact){
                        known(n);
                        const float magnitude=thirst?(float)value:std::max(0.0f,(float)value-actor->min_damage);
                        upsert_status_effect(*actor,code,10000,magnitude,text.substr(i,n));
                        emit(events,seq,thirst?"BATTLE_THIRST_BONUS":"TASTE_OF_BLOOD_MIN_DAMAGE",uid,0,text.substr(i,n));
                    }else{semantic(n);emit(events,seq,"SPECIAL",uid,0,text.substr(i,n));}
                }
                else if((code=="sta"||code=="wnd") && j==i+19){
                    // Observed proc-state records, independently recovered from the new raw
                    // corpus. Both layouts begin actor3,target3. The remaining 9 characters
                    // are proc telemetry, not required to reproduce the durable state effect.
                    // Exactness is gated by the server-declared ability on the acting stack.
                    const uint64_t target_uid=loose_int(text.substr(i+7,3));
                    auto* actor=s.entity(uid);auto* target=s.entity(target_uid);
                    const bool stone=code=="sta";
                    const bool exact=actor&&target&&actor->side!=target->side&&
                        has_ability(*actor,stone?"stoning":"cripplingwound");
                    if(exact){
                        known(n);
                        upsert_status_effect(*target,stone?"proc_stone":"proc_cripple",stone?1:2,1.0f,text.substr(i,n));
                        emit(events,seq,stone?"STONING":"CRIPPLING_WOUND",uid,target_uid,text.substr(i,n));
                    }else{semantic(n);emit(events,seq,"SPECIAL",uid,target_uid,text.substr(i,n));}
                }
                else if(code=="tel" && j==i+19 && digits(text.substr(i+4,15))){
                    known(n); const uint64_t target=loose_int(text.substr(i+7,3));
                    Cell c{loose_int(text.substr(i+10,2)),loose_int(text.substr(i+12,2))};
                    if(auto*e=s.entity(target)){e->anchor=c;if(!e->is_hero)grow_bounds(s,c);}
                    emit(events,seq,"TELEPORT",uid,target,text.substr(i,n));
                }else if((code=="fst"||code=="slw"||code=="bls"||code=="crs"||code=="stn"||code=="dfm"||code=="rgm"||code=="cnf")
                         && j==i+19 && digits(text.substr(i+4,15))){
                    // Independently recovered hero status layout from the new raw corpus:
                    // caster3,target3,mana2,duration_x100(4),magnitude3.  The first target
                    // carries the non-zero selected-spell mana cost; mass-followup targets use
                    // zero.  A record is exact only after the non-zero cost matches a spell in
                    // this hero's authoritative embedded spellbook.  This avoids treating
                    // triggered Sxxx result records as selected spells.
                    const uint64_t target=loose_int(text.substr(i+7,3));
                    const int cost=loose_int(text.substr(i+10,2));
                    const int duration_raw=loose_int(text.substr(i+12,4));
                    const int magnitude=loose_int(text.substr(i+16,3));
                    bool exact=false;
                    if(auto* caster=s.entity(uid); caster){
                        if(cost>0){
                            if(status_spell_for_wire_and_cost(*caster,code,cost)){
                                exact=true;ctx.exact_status_wire=std::string(code);
                            }
                        }else if(ctx.exact_status_wire==code) exact=true;
                    }
                    if(exact){
                        known(n);
                        if(cost>0) if(auto* caster=s.entity(uid)) caster->mana=std::max(0,caster->mana-cost);
                        if(auto* target_e=s.entity(target))
                            upsert_status_effect(*target_e,code,std::max(0,(int)std::llround(duration_raw/100.0)),(float)magnitude,text.substr(i,n));
                        emit(events,seq,"STATUS_EFFECT",uid,target,text.substr(i,n));
                    }else{
                        semantic(n);emit(events,seq,"SPECIAL",uid,target,text.substr(i,n));
                    }
                }else if(code=="psc" && j==i+19 && digits(text.substr(i+4,12))){
                    // Corpus-wide Spsc layout: caster3,target3,damage6,mode3. The final
                    // signed mode identifies source/effect family. Mode 062 is independently
                    // verified as the standard single-target hero basic attack: 50/50
                    // observations are one-target enemy hits and damage is exactly
                    // 16 + 4*hero.max_count. Other modes retain semantic uncertainty.
                    const auto mode=text.substr(i+16,3);
                    const bool exact_hero_basic = mode=="062" && s.entity(uid) && s.entity(uid)->is_hero;
                    if(exact_hero_basic) known(n); else semantic(n);
                    const uint64_t target=loose_int(text.substr(i+7,3));
                    const int amount=loose_int(text.substr(i+10,6));
                    if(auto*e=s.entity(target))apply_damage(*e,std::abs(amount));
                    emit(events,seq,exact_hero_basic?"HERO_BASIC_ATTACK":"SPECIAL_PSC_DAMAGE",uid,target,text.substr(i,n));
                }else if(special_direct_damage_code(code) && j==i+19 && digits(text.substr(i+4,15))){
                    semantic(n);
                    const uint64_t target=loose_int(text.substr(i+7,3));
                    const int effective_cost=loose_int(text.substr(i+10,3));
                    const int amount=loose_int(text.substr(i+13,6));
                    // Across all 636 hero direct-damage decisions in the supplied corpus this
                    // field is non-negative and there is exactly one such S-record per action.
                    // It can differ from spellbook base cost (school/talent modifiers), so use
                    // the wire value as the authoritative observed mana delta.
                    if(auto* caster=s.entity(uid);caster&&direct_spell_for_wire_and_cost(*caster,code,effective_cost))
                        caster->mana=std::max(0,caster->mana-effective_cost);
                    if(auto*e=s.entity(target))apply_damage(*e,std::abs(amount));
                    emit(events,seq,"SPECIAL_DAMAGE",uid,target,text.substr(i,n));
                }else{semantic(n);emit(events,seq,"SPECIAL",uid,0,text.substr(i,n));}i=j;continue;}
        }
        if(text[i]=='l'&&i+4<=text.size()&&digits(text.substr(i+1,3))){size_t c=text.find('^',i+4);if(c!=std::string_view::npos){size_t n=c-i+1;known(n);auto code=text.substr(i+4,c-(i+4));emit(events,seq,code=="luck"?"LUCK":(code=="morale"?"MORALE":"PROC"),loose_int(text.substr(i+1,3)),0,text.substr(i,n));i=c+1;continue;}}

        if((text[i]=='&'||text[i]=='o'||text[i]=='p'||text[i]=='k')&&i+4<=text.size()&&digits(text.substr(i+1,3))){
            size_t n=4;const uint64_t uid=loose_int(text.substr(i+1,3));
            const auto* actor=s.entity(ctx.actor_uid);
            const bool shieldbash_marker=text[i]=='o'&&uid==ctx.actor_uid&&actor&&has_ability(*actor,"shieldbash");
            if(shieldbash_marker){known(n);ctx.saw_shieldbash_proc=true;emit(events,seq,"SHIELDBASH_PROC",uid,0,text.substr(i,n));}
            else{semantic(n);emit(events,seq,"OPAQUE_SHORT",uid,0,text.substr(i,n));}
            i+=n;continue;
        }
        if(text[i]=='A'&&i+7<=text.size()&&digits(text.substr(i+1,6))){size_t n=7;semantic(n);emit(events,seq,"OPAQUE_A",loose_int(text.substr(i+1,3)),0,text.substr(i,n));i+=n;continue;}
        if(text[i]=='B'&&i+8<=text.size()&&digits(text.substr(i+1,7))){size_t n=8;known(n);uint64_t uid=loose_int(text.substr(i+1,3));Cell c{loose_int(text.substr(i+4,2)),loose_int(text.substr(i+6,2))};if(auto*e=s.entity(uid)){e->anchor=c;if(!e->is_hero)grow_bounds(s,c);}emit(events,seq,"FORCED_POSITION",uid,0,text.substr(i,n));i+=n;continue;}
        if((text[i]=='b'||text[i]=='r')&&i+8<=text.size()&&digits(text.substr(i+1,7))){size_t n=8;known(n);uint64_t uid=loose_int(text.substr(i+1,3));Cell c{loose_int(text.substr(i+4,2)),loose_int(text.substr(i+6,2))};if(auto*e=s.entity(uid)){e->anchor=c;if(!e->is_hero)grow_bounds(s,c);}emit(events,seq,"FORCED_POSITION",uid,0,text.substr(i,n));i+=n;continue;}
        if(text[i]=='s'&&i+13<=text.size()&&digits(text.substr(i+1,12))){size_t n=13;known(n);uint64_t uid=loose_int(text.substr(i+1,3));int x=loose_int(text.substr(i+4,2)),y=loose_int(text.substr(i+6,2)),count=loose_int(text.substr(i+8,5));if(auto*e=s.entity(uid)){e->anchor={x,y};e->count=std::max(0,count);if(e->count>0&&e->top_unit_hp<=0)e->top_unit_hp=e->max_hp_per_unit;e->alive=e->count>0;if(!e->is_hero)grow_bounds(s,e->anchor);}emit(events,seq,"SPAWN_POSITION",uid,0,text.substr(i,n));i+=n;continue;}

        const bool core_numeric_prefix =
            (text[i]=='m'||text[i]=='d'||text[i]=='i'||text[i]=='w'||text[i]=='h'||text[i]=='u'||text[i]=='z'||text[i]=='x') &&
            i+1<text.size() && std::isdigit(static_cast<unsigned char>(text[i+1]));
        if(std::islower(static_cast<unsigned char>(text[i])) && !core_numeric_prefix && i+4<=text.size()){
            if(i+3<=text.size()){
                const auto code=text.substr(i,3);
                const bool code_ok=std::islower(static_cast<unsigned char>(code[0])) &&
                    (std::islower(static_cast<unsigned char>(code[1]))||std::isdigit(static_cast<unsigned char>(code[1]))) &&
                    (std::islower(static_cast<unsigned char>(code[2]))||std::isdigit(static_cast<unsigned char>(code[2])));
                if(code_ok){
                    size_t j=i+3;
                    if(j<text.size()&&(text[j]=='+'||text[j]=='-'))++j;
                    const size_t num_start=j; bool dot=false;
                    while(j<text.size()){
                        unsigned char ch=static_cast<unsigned char>(text[j]);
                        if(std::isdigit(ch)){++j;continue;}
                        if(text[j]=='.'&&!dot){dot=true;++j;continue;}
                        break;
                    }
                    if(j>num_start){size_t n=j-i;semantic(n);emit(events,seq,"OPAQUE_EFFECT",0,0,text.substr(i,n));i=j;continue;}
                }
            }
        }
        if(text[i]=='m'&&i+8<=text.size()&&digits(text.substr(i+1,7))){
            size_t n=8;known(n);uint64_t uid=loose_int(text.substr(i+1,3));Cell c{loose_int(text.substr(i+4,2)),loose_int(text.substr(i+6,2))};
            if(uid==ctx.actor_uid && uid!=0){
                PendingMove pm{c,std::string(text.substr(i,n))};
                if(ctx.move_mode_decided){
                    if(ctx.apply_actor_moves) apply_one_move(uid,pm);
                    else emit(events,seq,"POSITION_MARKER",uid,0,pm.raw);
                }else ctx.moves.push_back(std::move(pm));
            }else{
                if(auto*e=s.entity(uid)){e->anchor=c;if(!e->is_hero)grow_bounds(s,c);}
                emit(events,seq,"MOVE",uid,0,text.substr(i,n));
            }
            i+=n;continue;
        }
        if(text[i]=='d'&&i+17<=text.size()&&digits(text.substr(i+1,16))){
            size_t n=17;known(n);uint64_t a=loose_int(text.substr(i+1,3)),t=loose_int(text.substr(i+4,3));int amount=loose_int(text.substr(i+7,10));
            if(a==ctx.actor_uid){ctx.saw_active_damage=true;decide_attack_move(t);}
            if(auto*e=s.entity(t)){
                apply_damage(*e,amount);
                if(a==ctx.actor_uid&&ctx.saw_shieldbash_proc&&e->alive&&!has_ability(*e,"mechanical")){
                    const uint32_t id=status_effect_id("proc_shieldbash");
                    auto it=std::find_if(e->effects.begin(),e->effects.end(),[&](const Effect&fx){return fx.id==id;});
                    Effect fx{id,10000,1.0f,"observed:o"};if(it==e->effects.end())e->effects.push_back(std::move(fx));else *it=std::move(fx);
                }
            }
            if(s.active_entity_uid && a!=s.active_entity_uid && t==s.active_entity_uid){
                auto* src=s.entity(a);auto* active=s.entity(t);
                if(src&&active&&src->alive&&src->side!=active->side&&src->side!=Side::Unknown){
                    const bool adjacent=[&](){for(int ax=0;ax<src->footprint_w;++ax)for(int ay=0;ay<src->footprint_h;++ay)for(int bx=0;bx<active->footprint_w;++bx)for(int by=0;by<active->footprint_h;++by)if(std::max(std::abs((src->anchor.x+ax)-(active->anchor.x+bx)),std::abs((src->anchor.y+ay)-(active->anchor.y+by)))<=1)return true;return false;}();
                    if(adjacent&&!src->is_warmachine&&!src->unlimited_retaliation)src->retaliation_available=false;
                }
            }
            emit(events,seq,"DAMAGE",a,t,text.substr(i,n));i+=n;continue;
        }
        if(text[i]=='i'&&i+8<=text.size()&&digits(text.substr(i+1,3))){size_t n=8;known(n);emit(events,seq,"STATE",loose_int(text.substr(i+1,3)),0,text.substr(i,n));i+=n;continue;}
        if(text[i]=='C'&&i+10<=text.size()&&digits(text.substr(i+1,3))){
            size_t n=10;known(n);
            finalize_decision();
            uint64_t uid=loose_int(text.substr(i+1,3));
            if(s.active_entity_uid){
                if(auto*prev=s.entity(s.active_entity_uid)){
                    prev->last_acted_seq=s.decision_seq;
                    // Observed one/two-activation control effects are authoritative once
                    // their S-record occurred. Tick them only after the affected stack has
                    // actually completed an activation; this keeps Stoning active while
                    // the petrified stack is the current actor and expires it afterwards.
                    const uint32_t stone=status_effect_id("proc_stone"),cripple=status_effect_id("proc_cripple"),slam=status_effect_id("msl");
                    for(auto&fx:prev->effects) if((fx.id==stone||fx.id==cripple||fx.id==slam)&&fx.duration>0)--fx.duration;
                    prev->effects.erase(std::remove_if(prev->effects.begin(),prev->effects.end(),[&](const Effect&fx){
                        return (fx.id==stone||fx.id==cripple||fx.id==slam)&&fx.duration<=0;
                    }),prev->effects.end());
                }
            }
            ++s.decision_seq;s.active_entity_uid=uid;
            if(auto*e=s.entity(uid)){s.side_to_act=e->side;e->retaliation_available=true;e->defending=false;
                const uint32_t sid=status_effect_id("proc_shieldbash"),wid=status_effect_id("proc_warding");
                e->effects.erase(std::remove_if(e->effects.begin(),e->effects.end(),[&](const Effect&fx){return fx.id==sid||fx.id==wid;}),e->effects.end());
            }else s.side_to_act=Side::Unknown;
            emit(events,seq,"TURN_START",uid,0,text.substr(i,n));reset_ctx(uid);i+=n;continue;
        }
        if(text[i]=='w'&&i+4<=text.size()&&digits(text.substr(i+1,3))){size_t n=4;known(n);uint64_t uid=loose_int(text.substr(i+1,3));if(uid==ctx.actor_uid)ctx.saw_wait=true;if(auto*e=s.entity(uid))e->waited_this_round=true;emit(events,seq,"WAIT",uid,0,text.substr(i,n));i+=n;continue;}
        if((text[i]=='h'||text[i]=='u')&&i+4<=text.size()&&digits(text.substr(i+1,3))){
            size_t n=4;uint64_t uid=loose_int(text.substr(i+1,3));
            if(text[i]=='h'){
                known(n);
                if(auto*e=s.entity(uid)){e->count=0;e->top_unit_hp=0;e->alive=false;}
                emit(events,seq,"HIDE_OR_DEATH",uid,0,text.substr(i,n));
            }else{
                auto* e=s.entity(uid);
                const uint32_t endurance_id=stable_id("endurance");
                const bool has_endurance=e&&std::find(e->ability_ids.begin(),e->ability_ids.end(),endurance_id)!=e->ability_ids.end();
                const bool exact=has_endurance&&e->speed<8.0f;
                if(exact){known(n);e->speed=std::min(8.0f,e->speed+1.0f);emit(events,seq,"ENDURANCE_SPEED_UP",uid,0,text.substr(i,n));}
                else{semantic(n);emit(events,seq,"U_RECORD",uid,0,text.substr(i,n));}
            }
            i+=n;continue;
        }
        if(text[i]=='P'&&i+7<=text.size()&&digits(text.substr(i+1,6))){size_t n=7;semantic(n);const uint64_t puid=loose_int(text.substr(i+1,3));ctx.pending_p_uid=puid;emit(events,seq,"P_RECORD",puid,0,text.substr(i,n));i+=n;continue;}
        if(text[i]=='T'&&i+7<=text.size()&&digits(text.substr(i+1,6))){
            size_t n=7;const uint64_t actor_uid=loose_int(text.substr(i+1,3)),target_uid=loose_int(text.substr(i+4,3));
            auto* actor=s.entity(actor_uid);auto* target=s.entity(target_uid);
            // Corpus invariant: all 140 T<actor><target> records occur on ranged actions
            // by actors carrying `wardingarrows`; no non-warding ranged action emits T.
            const bool exact=actor&&target&&has_ability(*actor,"wardingarrows")&&actor->side!=target->side;
            if(exact){known(n);upsert_status_effect(*target,"proc_warding",10000,0.2f,text.substr(i,n));emit(events,seq,"WARDING_ARROWS_DELAY",actor_uid,target_uid,text.substr(i,n));}
            else{semantic(n);emit(events,seq,"T_RECORD",actor_uid,target_uid,text.substr(i,n));}
            i+=n;continue;
        }
        if(text[i]=='W'&&i+7<=text.size()&&digits(text.substr(i+1,6))){
            size_t n=7;const uint64_t actor_uid=loose_int(text.substr(i+1,3)),target_uid=loose_int(text.substr(i+4,3));
            auto* actor=s.entity(actor_uid);auto* target=s.entity(target_uid);
            const bool exact=actor&&target&&actor->side!=target->side&&has_ability(*actor,"weakeningstrike");
            if(exact){known(n);target->attack=std::max(0.0f,target->attack-4.0f);if(!has_ability(*target,"armoured"))target->defense=std::max(0.0f,target->defense-4.0f);emit(events,seq,"WEAKENING_STRIKE",actor_uid,target_uid,text.substr(i,n));}
            else{semantic(n);emit(events,seq,"W_RECORD",actor_uid,target_uid,text.substr(i,n));}
            i+=n;continue;
        }
        if(text[i]=='z'&&i+10<=text.size()&&digits(text.substr(i+1,9))){
            const size_t n=10;const uint64_t actor_uid=loose_int(text.substr(i+1,3)),target_uid=loose_int(text.substr(i+4,3));
            const int drained=loose_int(text.substr(i+7,3));auto* actor=s.entity(actor_uid);auto* target=s.entity(target_uid);
            const bool exact=actor&&target&&has_ability(*actor,"manadrain")&&has_ability(*target,"caster")&&
                !target->is_statix&&!target->is_warmachine&&drained>=0&&drained<=std::max(0,target->mana);
            if(exact){known(n);target->mana=std::max(0,target->mana-drained);emit(events,seq,"MANA_DRAIN_MANA",actor_uid,target_uid,text.substr(i,n));}
            else{semantic(n);emit(events,seq,"Z_RECORD",actor_uid,target_uid,text.substr(i,n));}
            i+=n;continue;
        }
        bool fixed=false;
        for(auto spec: {std::pair<char,int>{'I',8},{'T',7},{'R',7},{'V',7},{'F',7},{'Y',10},{'x',10}}){
            if(text[i]==spec.first&&i+(size_t)spec.second<=text.size()&&digits(text.substr(i+1,3))){size_t n=spec.second;semantic(n);emit(events,seq,"RAW_KNOWN",loose_int(text.substr(i+1,3)),0,text.substr(i,n));i+=n;fixed=true;break;}
        }
        if(fixed)continue;
        unknown(1); emit(events,seq,"UNKNOWN",0,0,text.substr(i,1)); ++i;
    }
}

} // namespace

std::vector<std::string> ProtocolDecoder::tokenize(std::string_view p) {
    std::vector<std::string> out; std::string cur;
    auto flush=[&]{if(!cur.empty()){out.push_back(cur);cur.clear();}};
    for(char c:p){if(c=='\n'||c=='\r'||c=='|'||c==';'||c=='^')flush();else cur+=c;} flush(); return out;
}

DecodeResult ProtocolDecoder::decode_initial(std::string_view payload,std::string battle_id) const {
    DecodeResult r; r.raw_hash=hexhash(payload); r.state.battle_id=std::move(battle_id); r.state.protocol_version=2; r.state.state_seq=1; r.state.phase=Phase::Combat; r.state.min_x=1; r.state.min_y=1; r.state.width=13; r.state.height=11;
    if(has_static(payload)) parse_static(r.state,payload,r.warnings);
    if(r.state.entities.empty()) {
        r.warnings.push_back({"INITIAL_STATE_MISSING","Payload has no independently parseable static M entity section; waiting for lastturn=-3 capture."});
        r.state.protocol_ready=false; r.coverage.bytes_total=1; return r;
    }
    // lastturn=-3 contains static initial state plus a current/final turn fragment. Applying that
    // fragment directly would skip turns 1..N-1, so intentionally wait for lastturn=0/full stream.
    r.state.halfturn=0; r.state.stream_contiguous=false; r.state.protocol_ready=false; r.state.recommendation_safe=false; r.state.protocol_unknown_ratio=0.0; r.state.semantic_unresolved_ratio=0.0; r.state.protocol_bytes_total=0; r.state.protocol_bytes_classified=0; r.state.protocol_unknown_records=0; r.state.protocol_records_seen=0; r.state.semantic_unresolved_records=0;
    r.coverage.bytes_total=1; r.coverage.bytes_classified=1; r.coverage.records=r.state.entities.size();
    r.warnings.push_back({"WAITING_FOR_TURN_STREAM","Static state decoded; waiting for full/contiguous turn stream before planning."});
    return r;
}

DecodeResult ProtocolDecoder::decode_update(const BattleState& previous,std::string_view payload) const {
    if(has_static(payload)) return decode_initial(payload,previous.battle_id);
    DecodeResult r; r.raw_hash=hexhash(payload); r.state=previous; r.state.state_seq=previous.state_seq+1; r.state.protocol_version=2;
    auto slices=turn_slices(payload); uint64_t seq=0; CommandStats stats;
    // Continuity is persistent state, not a sticky readiness bit. Once a gap is observed,
    // delta-only updates cannot silently make the chain trustworthy again; SessionStore
    // can recover by replaying a full stream from the retained static baseline.
    bool contiguous = previous.halfturn==0 ? (!slices.empty() && slices.front().turn==1) : previous.stream_contiguous;
    uint32_t expected = previous.halfturn ? previous.halfturn+1 : 1;
    for(const auto& ts:slices){
        if(ts.turn<=previous.halfturn) continue; // full-stream replay received again: idempotent.
        if(ts.turn!=expected) contiguous=false;
        expected=ts.turn+1;
        if(ts.turn==1)stats.saw_turn1=true;
        apply_commands(r.state,ts.body,r.events,stats,seq);
        r.state.halfturn=ts.turn;
    }
    r.coverage.bytes_total=stats.total;
    r.coverage.bytes_classified=stats.classified;
    r.coverage.records=stats.records;
    r.coverage.unknown_records=stats.unknown;
    r.state.protocol_bytes_total = previous.protocol_bytes_total + stats.total;
    r.state.protocol_bytes_classified = previous.protocol_bytes_classified + stats.classified;
    r.state.protocol_unknown_records = previous.protocol_unknown_records + stats.unknown;
    r.state.protocol_unknown_ratio = r.state.protocol_bytes_total ? 1.0-double(r.state.protocol_bytes_classified)/double(r.state.protocol_bytes_total) : 0.0;
    r.state.protocol_records_seen = previous.protocol_records_seen + stats.records;
    r.state.semantic_unresolved_records = previous.semantic_unresolved_records + stats.semantic_unresolved;
    r.state.semantic_unresolved_ratio = r.state.protocol_records_seen ? double(r.state.semantic_unresolved_records)/double(r.state.protocol_records_seen) : 0.0;
    r.state.stream_contiguous = contiguous;
    const auto validation=validate(r.state);
    for(const auto& v:validation)r.warnings.push_back({"STATE_INVARIANT",v});
    const bool any_new_records = stats.total>0;
    const bool coverage_ok = any_new_records && r.coverage.ratio()>=0.98;
    if(!any_new_records) {
        // Full-stream endpoints are often replayed verbatim. If every turn in this payload
        // is already applied, this is an idempotent no-op rather than a readiness failure.
        r.state.stream_contiguous = previous.stream_contiguous;
        r.state.protocol_ready = previous.protocol_ready;
        r.state.recommendation_safe = previous.recommendation_safe;
    } else {
        r.state.protocol_ready = r.state.stream_contiguous && coverage_ok && r.state.protocol_unknown_records==0 && validation.empty();
        r.state.recommendation_safe = r.state.protocol_ready && r.state.semantic_unresolved_ratio <= kDefaultSemanticRiskLimit;
    }
    if(!contiguous) r.warnings.push_back({"TURN_GAP","Turn stream is not contiguous with current state; planning disabled until a full stream from turn 1 is observed."});
    if(stats.total==0) r.warnings.push_back({"NO_TURN_RECORDS","No turn records found in update payload."});
    if(!coverage_ok && stats.total>0) r.warnings.push_back({"LOW_COMMAND_COVERAGE","Known-command byte coverage below 98%; raw unknowns retained."});
    if(r.state.protocol_ready && r.state.semantic_unresolved_records>0)
        r.warnings.push_back({"SEMANTIC_UNCERTAINTY",r.state.recommendation_safe ?
            "Some mechanics remain approximate; planner confidence is risk-adjusted." :
            "Semantic uncertainty exceeds the strict 30% gate; recommendations are blocked unless degraded mode is explicitly enabled."});
    if(r.state.phase!=Phase::Finished && r.state.protocol_ready && r.state.active_entity_uid==0)
        r.warnings.push_back({"ACTIVE_ENTITY_UNKNOWN","State reconstructed but active actor is not yet known."});
    return r;
}

} // namespace hwm
