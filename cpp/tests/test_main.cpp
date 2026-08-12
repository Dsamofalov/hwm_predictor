#include "hwm/planner.hpp"
#include "hwm/protocol.hpp"
#include "hwm/session.hpp"

#include <cstdlib>
#include <iostream>
#include <fstream>
#include <filesystem>
#include <string>
#include <vector>

using namespace hwm;

#define CHECK(expr) do { if (!(expr)) { std::cerr << "CHECK failed: " #expr << " at " << __FILE__ << ':' << __LINE__ << '\n'; return false; } } while (0)

static BattleState fixture() {
    BattleState s;
    s.battle_id = "test"; s.state_seq = 1; s.phase = Phase::Combat; s.width = 12; s.height = 10; s.protocol_ready=true;s.recommendation_safe=true;
    Entity a; a.uid=1; a.creature_id=10; a.side=Side::Player; a.anchor={1,1}; a.count=10; a.top_unit_hp=20; a.max_hp_per_unit=20; a.attack=10; a.defense=8; a.min_damage=2; a.max_damage=4; a.speed=4; a.shots=3; a.is_shooter=true;
    Entity b=a; b.uid=2; b.side=Side::Pve; b.anchor={5,1}; b.count=8;
    s.entities={a,b}; s.active_entity_uid=1; s.side_to_act=Side::Player; return s;
}

static std::string mrec(int uid,int owner,int creature,int count,int x,int y,bool hero=false) {
    std::vector<std::string> f={
        owner==1?"000001":"000002",
        creature==53?"000053":"000172",
        "000022","000022","000003","000005","000000","000000",
        "000005","000100","000010","000010","000010",
        x==1?"000001":(x==5?"000005":"000002"),
        y==1?"000001":(y==5?"000005":"000002"),
        "000000","000008","000008","000006","000000","000000","000001","000022","000223"
    };
    f[11]="000010"; f[12]=count==8?"000008":"000010";
    std::string out="M"; if(uid<10)out+="00";else if(uid<100)out+="0";out+=std::to_string(uid);out+=':';
    for(auto&s:f)out+=s;
    out += hero ? "heroani|[1.0]|Hero|alive|hero|~magicfist-5-1-25-5-0-neutral-swarm-5-2-15-3-0-other-^" : "bearani|[1.0]|Bear|alive|big|shooter|~^";
    return out;
}

static std::string static_payload() {
    return "t=000turns=>2:f<result>|#f_en<result>|#i0000000;/" + mrec(1,1,53,10,1,1,true) + ";/" + mrec(2,2,172,8,5,5,false) + ";bm_tooltips=e30<";
}

static bool test_state_and_planner() {
    auto s=fixture(); CHECK(validate(s).empty()); CHECK(state_hash(s)==state_hash(s));
    GenericSimulator sim; auto acts=sim.legal_actions(s); CHECK(!acts.empty());
    bool ranged=false, move_attack=false; for(auto&a:acts) { if(a.type==ActionType::RangedAttack) ranged=true; if(a.type==ActionType::MeleeAttack&&a.destination&&a.target_uid&&*a.target_uid==2) move_attack=true; } CHECK(ranged); CHECK(move_attack);
    Planner p({1000,6,8,1.2,42,0}); auto r=p.plan(s); CHECK(r.status=="ok"&&r.simulations==1000);
    CHECK(!r.pv.empty()); CHECK(r.best.visits > 0); return true;
}

static bool test_decoder() {
    ProtocolDecoder d;
    auto initial=d.decode_initial(static_payload(),"x");
    CHECK(initial.state.entities.size()==2); CHECK(initial.state.halfturn==0); CHECK(!initial.state.protocol_ready);
    CHECK(initial.state.entity(1) && initial.state.entity(1)->side==Side::Player); CHECK(initial.state.entity(1)->spells.size()==2); CHECK(initial.state.entity(1)->spells[0].mana_cost==5);
    CHECK(initial.state.entity(2) && initial.state.entity(2)->side==Side::Pve);
    auto update=d.decode_update(initial.state,"t=000turns=>1:C001000000;>2:m0010202d0010020000000022i0010100C002-00001");
    CHECK(update.state.halfturn==2); CHECK(update.state.protocol_ready); CHECK(update.state.recommendation_safe); CHECK(update.coverage.ratio()>0.99);
    // UID1 is a hero in this static fixture. Raw hero m-records are position markers,
    // not creature relocation; keep the canonical hero anchor unchanged.
    Cell expected{1,1}; CHECK(update.state.entity(1)->anchor==expected); CHECK(update.state.entity(2)->count==7);
    CHECK(update.state.active_entity_uid==2); CHECK(update.state.side_to_act==Side::Pve);
    // Idempotence: replaying the full stream must not apply damage a second time.
    auto again=d.decode_update(update.state,"t=000turns=>1:C001000000;>2:m0010202d0010020000000022i0010100C002-00001");
    CHECK(again.state.entity(2)->count==7); CHECK(again.state.halfturn==2); CHECK(again.state.protocol_ready); CHECK(again.state.stream_contiguous);

    // A real turn gap must not heal merely because the next delta is locally consecutive.
    auto gap=d.decode_update(initial.state,"t=000turns=>2:C001000000");
    CHECK(!gap.state.protocol_ready); CHECK(!gap.state.stream_contiguous);
    auto after_gap=d.decode_update(gap.state,"t=000turns=>3:C002000000");
    CHECK(!after_gap.state.protocol_ready); CHECK(!after_gap.state.stream_contiguous);

    // Structurally known opaque records must not tank live protocol confidence.
    auto opaque=d.decode_update(initial.state,
        "t=000turns=>1:C001000000;>2:&001o002p003k004A001002B0010203b0010203r0020304"
        "s003040500006bld0000slw737.81crs439.05i0010100C002-00001");
    CHECK(opaque.coverage.ratio()>0.99);
    CHECK(opaque.coverage.unknown_records==0);
    CHECK(opaque.state.protocol_ready);
    CHECK(!opaque.state.recommendation_safe);
    CHECK(opaque.state.semantic_unresolved_records>0);
    Planner strict_planner({20,3,4,1.2,42,0});
    auto strict_rec=strict_planner.plan(opaque.state);
    CHECK(strict_rec.status=="not_ready");
    return true;
}


static bool test_contextual_move_markers() {
    ProtocolDecoder d;

    // Ranged actions can emit mUUUXXYY even though the shooter never left its cell.
    // A non-adjacent damage target makes this a position marker, not a MOVE.
    {
        BattleState s=fixture(); s.halfturn=0; s.stream_contiguous=false; s.protocol_ready=false;
        auto r=d.decode_update(s,"t=000turns=>1:C001000000m0010202d0010020000000005i0010100C002000000");
        CHECK((r.state.entity(1)->anchor==Cell{1,1}));
        CHECK(std::any_of(r.events.begin(),r.events.end(),[](const BattleEvent&e){return e.type=="POSITION_MARKER"&&e.actor_uid==1;}));
    }

    // WAIT and DEFEND also carry a current-position m marker in real replays.
    for(const std::string body: {
            std::string("t=000turns=>1:C001000000m0010202w001i0010100C002000000"),
            std::string("t=000turns=>1:C001000000m0010202Sdef001100000000030i0010100C002000000")}) {
        BattleState s=fixture(); s.halfturn=0; s.stream_contiguous=false; s.protocol_ready=false;
        auto r=d.decode_update(s,body);
        CHECK((r.state.entity(1)->anchor==Cell{1,1}));
    }

    // Melee move+attack: the first m is the attack landing cell and must be applied
    // before damage. A later m in the same decision is strike-and-return movement.
    {
        BattleState s=fixture(); s.halfturn=0; s.stream_contiguous=false; s.protocol_ready=false;
        auto* actor=s.entity(1); auto* target=s.entity(2); CHECK(actor&&target);
        actor->is_shooter=false; actor->shots=0; actor->anchor={1,1}; target->anchor={3,1};
        auto melee=d.decode_update(s,"t=000turns=>1:C001000000m0010201d0010020000000005i0010100C002000000");
        CHECK((melee.state.entity(1)->anchor==Cell{2,1}));
        CHECK(std::any_of(melee.events.begin(),melee.events.end(),[](const BattleEvent&e){return e.type=="MOVE"&&e.actor_uid==1;}));

        auto ret=d.decode_update(s,"t=000turns=>1:C001000000m0010201d0010020000000005m0010101i0010100C002000000");
        CHECK((ret.state.entity(1)->anchor==Cell{1,1}));
    }
    return true;
}

static bool test_session_lifecycle() {
    SessionStore store;
    // Turn stream may arrive before static state; it must be buffered and replayed later.
    RawEnvelope turns; turns.battle_id="100"; turns.captured_at_ms=10000; turns.sequence_hint=1; turns.body="t=000turns=>1:C001000000;>2:m0010202d0010020000000022i0010100C002-00001";
    auto first=store.capture(turns); CHECK(first.accepted && !first.duplicate && !first.out_of_order);
    auto duplicate=store.capture(turns); CHECK(duplicate.accepted && duplicate.duplicate);
    RawEnvelope init; init.battle_id="100"; init.captured_at_ms=10100; init.sequence_hint=2; init.body=static_payload();
    auto second=store.capture(init); CHECK(second.accepted && second.canonical_state_updated);
    auto s=store.state(); CHECK(s && s->protocol_ready && s->halfturn==2);
    RawEnvelope old=turns; old.body="t=000turns=>3:C001000000"; old.captured_at_ms=5000; old.sequence_hint=0;
    auto stale=store.capture(old); CHECK(!stale.accepted && stale.out_of_order);
    RawEnvelope other=init; other.battle_id="200"; other.body=static_payload(); other.captured_at_ms=11000;
    auto reset=store.capture(other); CHECK(reset.accepted && reset.session_reset);
    const auto status=store.status_json(); CHECK(status.find("\"battle_id\":\"200\"")!=std::string::npos);
    CHECK(status.find("\"duplicate_captures\":1")!=std::string::npos);
    CHECK(status.find("\"out_of_order_captures\":1")!=std::string::npos);
    return true;
}



static bool test_exact_shooter_flags() {
    BattleState s=fixture();
    auto* actor=s.entity(1); auto* enemy=s.entity(2);
    CHECK(actor && enemy);
    actor->anchor={1,1}; enemy->anchor={2,1}; actor->speed=0;

    GenericSimulator sim;
    // shootonly is an exact server trait: no melee attack candidates.
    actor->shoot_only=true;
    auto acts=sim.legal_actions(s);
    CHECK(std::none_of(acts.begin(),acts.end(),[](const Action&a){return a.type==ActionType::MeleeAttack;}));

    // Ordinary shooters are blocked by an adjacent enemy.
    CHECK(std::none_of(acts.begin(),acts.end(),[](const Action&a){return a.type==ActionType::RangedAttack;}));

    // Server tooltip for warmachine explicitly exempts it from adjacent blocking.
    actor->is_warmachine=true;
    acts=sim.legal_actions(s);
    CHECK(std::any_of(acts.begin(),acts.end(),[](const Action&a){return a.type==ActionType::RangedAttack;}));
    return true;
}

static bool test_dynamic_geometry() {
    BattleState s; s.battle_id="geom"; s.state_seq=1; s.phase=Phase::Combat; s.protocol_ready=true;s.recommendation_safe=true;
    s.min_x=5; s.min_y=7; s.width=11; s.height=13; // x=5..10, y=7..12
    Entity flyer; flyer.uid=10; flyer.side=Side::Player; flyer.anchor={5,7}; flyer.count=3; flyer.max_hp_per_unit=10; flyer.top_unit_hp=10; flyer.speed=3; flyer.is_flyer=true;
    Entity blocker=flyer; blocker.uid=11; blocker.side=Side::Pve; blocker.anchor={6,7}; blocker.is_flyer=false;
    Entity big=blocker; big.uid=12; big.anchor={8,9}; big.is_big=true; big.footprint_w=2; big.footprint_h=2;
    s.entities={flyer,blocker,big}; s.active_entity_uid=10; s.side_to_act=Side::Player;
    CHECK(validate(s).empty());
    GenericSimulator sim; auto acts=sim.legal_actions(s);
    bool fly_over=false, lands_on_big=false;
    for(const auto&a:acts)if(a.type==ActionType::Move&&a.destination){if(a.destination->x==7&&a.destination->y==7)fly_over=true;if(a.destination->x==8&&a.destination->y==9)lands_on_big=true;}
    CHECK(fly_over); CHECK(!lands_on_big);

    // On-board mechanisms/objects occupy their cells even though they cannot walk.
    Entity machine=blocker; machine.uid=13; machine.anchor={7,10}; machine.is_warmachine=true; machine.is_big=false; machine.footprint_w=1; machine.footprint_h=1;
    s.entities.push_back(machine);
    acts=sim.legal_actions(s);
    CHECK(std::none_of(acts.begin(),acts.end(),[](const Action&a){return a.type==ActionType::Move&&a.destination&&*a.destination==Cell{7,10};}));
    return true;
}


static bool test_defend_and_ammo_core_mechanics() {
    BattleState s=fixture();
    auto* actor=s.entity(1); auto* target=s.entity(2); CHECK(actor&&target);
    actor->anchor={1,1}; target->anchor={5,1}; actor->shots=2; actor->is_shooter=true; actor->double_shoot=true;
    GenericSimulator sim;
    auto acts=sim.legal_actions(s);
    auto rit=std::find_if(acts.begin(),acts.end(),[](const Action&a){return a.type==ActionType::RangedAttack;});
    CHECK(rit!=acts.end());
    auto shot=sim.apply(s,*rit,0.5); CHECK(shot.valid); CHECK(shot.state.entity(1)->shots==0);

    // DEFEND is +30% defence until this stack acts again.
    s=fixture(); actor=s.entity(1); target=s.entity(2); CHECK(actor&&target);
    auto dacts=sim.legal_actions(s);
    auto dit=std::find_if(dacts.begin(),dacts.end(),[](const Action&a){return a.type==ActionType::Defend;});
    CHECK(dit!=dacts.end()); auto defended=sim.apply(s,*dit,0.5); CHECK(defended.valid); CHECK(defended.state.entity(1)->defending);
    BattleState attack_state=defended.state; attack_state.active_entity_uid=2; attack_state.side_to_act=Side::Pve;
    auto before_hp=attack_state.entity(1)->count*attack_state.entity(1)->max_hp_per_unit;
    auto melee_actions=sim.legal_actions(attack_state);
    // Move target next to defender to ensure a melee action exists.
    attack_state.entity(2)->anchor={2,1}; attack_state.entity(2)->speed=0; melee_actions=sim.legal_actions(attack_state);
    auto mit=std::find_if(melee_actions.begin(),melee_actions.end(),[](const Action&a){return a.type==ActionType::MeleeAttack&&a.target_uid&&*a.target_uid==1;});
    CHECK(mit!=melee_actions.end()); auto defended_hit=sim.apply(attack_state,*mit,0.5); CHECK(defended_hit.valid);
    BattleState plain=attack_state; plain.entity(1)->defending=false; auto plain_hit=sim.apply(plain,*mit,0.5); CHECK(plain_hit.valid);
    auto hp_after=[](const Entity&e){return e.alive?(e.count-1)*std::max(1,e.max_hp_per_unit)+e.top_unit_hp:0;};
    CHECK(hp_after(*defended_hit.state.entity(1))>=hp_after(*plain_hit.state.entity(1)));
    (void)before_hp;
    return true;
}

static bool test_retaliation_cycle() {
    GenericSimulator sim;
    BattleState s=fixture(); auto* a=s.entity(1);auto* t=s.entity(2);CHECK(a&&t);
    a->anchor={1,1};t->anchor={2,1};a->speed=0;t->speed=0;a->is_shooter=false;a->shots=0;
    auto acts=sim.legal_actions(s);auto it=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2;});CHECK(it!=acts.end());
    auto hp=[](const Entity&e){return e.alive?(e.count-1)*std::max(1,e.max_hp_per_unit)+e.top_unit_hp:0;};
    const int before=hp(*a);auto with_ret=sim.apply(s,*it,0.5);CHECK(with_ret.valid);CHECK(hp(*with_ret.state.entity(1))<before);
    BattleState nr=s;nr.entity(1)->no_retaliation=true;auto without_ret=sim.apply(nr,*it,0.5);CHECK(without_ret.valid);CHECK(hp(*without_ret.state.entity(1))==before);

    ProtocolDecoder d;auto initial=d.decode_initial(static_payload(),"r");
    auto upd=d.decode_update(initial.state,"t=000turns=>1:C001000000;>2:m0010404d0010020000000001d0020010000000001i0010100C002000000");
    CHECK(upd.state.entity(2));CHECK(upd.state.entity(2)->retaliation_available); // C002 starts its turn and resets response.
    return true;
}

static bool test_protocol_defend_and_recovery() {
    ProtocolDecoder d;
    auto initial=d.decode_initial(static_payload(),"def");
    CHECK(initial.state.entity(2));

    // Independently established corpus record: Sdef...030 is standard DEFEND.
    auto defended=d.decode_update(initial.state,"t=000turns=>1:C002000000m0020505Sdef002100000000030i0020100");
    CHECK(defended.state.protocol_ready);
    CHECK(defended.state.entity(2)->defending);
    CHECK(std::any_of(defended.events.begin(),defended.events.end(),[](const BattleEvent&e){return e.type=="DEFEND"&&e.actor_uid==2;}));

    // Stel is exact corpus-derived teleport: caster3,target3,x2,y2,param5.
    auto teleported=d.decode_update(initial.state,"t=000turns=>1:C001000000Stel001002030400000i0010100");
    CHECK(teleported.state.protocol_ready);
    CHECK((teleported.state.entity(2)->anchor==Cell{3,4}));
    CHECK(std::any_of(teleported.events.begin(),teleported.events.end(),[](const BattleEvent&e){return e.type=="TELEPORT"&&e.actor_uid==1&&e.target_uid==2;}));

    // The stance ends when that stack receives its next activation.
    auto reactivated=d.decode_update(defended.state,"t=000turns=>2:C002000000");
    CHECK(!reactivated.state.entity(2)->defending);

    // SessionStore must recover after a missing turn when a fresh full stream arrives.
    SessionStore store;
    RawEnvelope init; init.battle_id="300"; init.captured_at_ms=1000; init.sequence_hint=1; init.body=static_payload();
    auto a=store.capture(init); CHECK(a.accepted && a.canonical_state_updated);
    RawEnvelope gap; gap.battle_id="300"; gap.captured_at_ms=2000; gap.sequence_hint=2; gap.body="t=000turns=>2:C002000000";
    auto b=store.capture(gap); CHECK(b.accepted); auto gap_state=store.state(); CHECK(gap_state && !gap_state->protocol_ready && !gap_state->stream_contiguous);
    RawEnvelope full; full.battle_id="300"; full.captured_at_ms=3000; full.sequence_hint=3; full.body="t=000turns=>1:C001000000;>2:C002000000";
    auto c=store.capture(full); CHECK(c.accepted && c.canonical_state_updated);
    auto recovered=store.state(); CHECK(recovered && recovered->protocol_ready && recovered->stream_contiguous && recovered->halfturn==2);
    CHECK(recovered->active_entity_uid==2);
    return true;
}

static bool test_warmachine_never_retaliates() {
    GenericSimulator sim;
    BattleState s=fixture(); auto* a=s.entity(1); auto* t=s.entity(2); CHECK(a&&t);
    a->anchor={1,1}; t->anchor={2,1}; a->speed=0; t->speed=0; a->is_shooter=false; a->shots=0;
    t->is_warmachine=true; t->shoot_only=false; t->retaliation_available=true;
    auto actions=sim.legal_actions(s);
    auto it=std::find_if(actions.begin(),actions.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2;});
    CHECK(it!=actions.end());
    auto hp=[](const Entity&e){return e.alive?(e.count-1)*std::max(1,e.max_hp_per_unit)+e.top_unit_hp:0;};
    const int before=hp(*a); auto result=sim.apply(s,*it,0.5); CHECK(result.valid);
    CHECK(hp(*result.state.entity(1))==before);
    return true;
}


static bool test_semantic_safety_and_state_hash() {
    BattleState s=fixture();
    s.protocol_ready=true; s.semantic_unresolved_records=0; s.semantic_unresolved_ratio=0.0; s.recommendation_safe=true;
    CHECK(std::string(semantic_safety_tier(s))=="exact_core");
    s.semantic_unresolved_records=1; s.semantic_unresolved_ratio=0.05; CHECK(std::string(semantic_safety_tier(s))=="guarded");
    s.semantic_unresolved_ratio=0.20; CHECK(std::string(semantic_safety_tier(s))=="degraded");
    s.semantic_unresolved_ratio=0.40; s.recommendation_safe=false; CHECK(std::string(semantic_safety_tier(s))=="semantic_blocked");
    s.protocol_ready=false; CHECK(std::string(semantic_safety_tier(s))=="structural_blocked");

    BattleState a=fixture(), b=a;
    CHECK(state_hash(a)==state_hash(b));
    b.entity(1)->shots--; CHECK(state_hash(a)!=state_hash(b));
    b=a; b.entity(1)->mana++; CHECK(state_hash(a)!=state_hash(b));
    b=a; b.entity(1)->defending=true; CHECK(state_hash(a)!=state_hash(b));
    b=a; b.entity(1)->retaliation_available=false; CHECK(state_hash(a)!=state_hash(b));
    return true;
}

static bool test_runtime_probe_status() {
    SessionStore store;
    CHECK(!store.capture_runtime_probe(""));
    CHECK(store.capture_runtime_probe("{\"schema\":\"hwm-runtime-structure-v1\",\"candidates\":[]}"));
    const auto status=store.status_json();
    CHECK(status.find("\"runtime_probe_count\":1")!=std::string::npos);
    CHECK(status.find("\"runtime_probe_bytes\":")!=std::string::npos);
    return true;
}

static bool test_policy_prior_defend_is_distinct() {
    const auto path=std::filesystem::temp_directory_path()/"hwm_policy_prior_test.csv";
    {
        std::ofstream f(path);
        f << "side,creature_id,count,MOVE,MELEE_ATTACK,RANGED_ATTACK,WAIT,DEFEND,HERO_ACTION,CAST_OR_ABILITY,ABILITY,ATTACK\n";
        f << "PLAYER,10,100,0.01,0.02,0.03,0.04,0.70,0.05,0.06,0.07,0.02\n";
    }
    PolicyPriorTable p(path.string()); CHECK(p.loaded());
    BattleState s=fixture();
    CHECK(p.type_probability(s,ActionType::Defend)>p.type_probability(s,ActionType::MeleeAttack));
    CHECK(p.type_probability(s,ActionType::Defend)>0.6);
    return true;
}



static bool test_hero_direct_spell_path() {
    BattleState s=fixture();
    auto* hero=s.entity(1); auto* enemy=s.entity(2); CHECK(hero&&enemy);
    hero->is_hero=true; hero->creature_id=622; hero->mana=10; hero->anchor={0,2};
    hero->spells={{2077100434u,"magicfist","mfs",5,true}};
    s.active_entity_uid=hero->uid; s.side_to_act=Side::Player;
    GenericSimulator sim;
    auto actions=sim.legal_actions(s);
    auto it=std::find_if(actions.begin(),actions.end(),[](const Action&a){return a.type==ActionType::Cast&&a.target_uid&&*a.target_uid==2&&a.ability_id&&*a.ability_id==2077100434u;});
    CHECK(it!=actions.end());
    CHECK(to_json(*it).find("\"ability_id\":2077100434")!=std::string::npos);
    const int before=(enemy->count-1)*enemy->max_hp_per_unit+enemy->top_unit_hp;
    auto tr=sim.apply(s,*it,0.5); CHECK(tr.valid); CHECK(tr.state.entity(1)->mana==5);
    const auto* after_enemy=tr.state.entity(2); CHECK(after_enemy);
    const int after=after_enemy->alive?(after_enemy->count-1)*after_enemy->max_hp_per_unit+after_enemy->top_unit_hp:0;
    CHECK(after<before);
    // Organic Armor is an exact 80% resistance to Magic Fist and must apply even
    // when the spell model has a target-conditioned row for this creature ID.
    BattleState organic=s; organic.entity(2)->ability_ids.push_back(stable_ability_id("organicarmor"));
    auto oacts=sim.legal_actions(organic);
    auto oit=std::find_if(oacts.begin(),oacts.end(),[](const Action&a){return a.type==ActionType::Cast&&a.target_uid&&*a.target_uid==2&&a.ability_id&&*a.ability_id==2077100434u;});
    CHECK(oit!=oacts.end()); auto otr=sim.apply(organic,*oit,0.5); CHECK(otr.valid);
    const auto* organic_enemy=otr.state.entity(2); CHECK(organic_enemy);
    const int organic_after=organic_enemy->alive?(organic_enemy->count-1)*organic_enemy->max_hp_per_unit+organic_enemy->top_unit_hp:0;
    CHECK(before-organic_after < (before-after)*0.35);
    Planner p({100,4,8,1.2,42,0}); auto rec=p.plan(s); CHECK(rec.status=="ok");
    CHECK(rec.best.action.type==ActionType::Cast || rec.best.action.type==ActionType::HeroAction ||
          rec.best.action.type==ActionType::Wait || rec.best.action.type==ActionType::Defend);
    return true;
}

static bool test_hero_basic_attack_path() {
    BattleState s=fixture();
    auto* hero=s.entity(1); auto* enemy=s.entity(2); CHECK(hero&&enemy);
    hero->is_hero=true; hero->creature_id=427; hero->max_count=8; hero->mana=0; hero->anchor={13,2};
    hero->spells.clear();
    s.active_entity_uid=hero->uid; s.side_to_act=Side::Player;
    GenericSimulator sim;
    auto actions=sim.legal_actions(s);
    auto hit=std::find_if(actions.begin(),actions.end(),[](const Action&a){return a.type==ActionType::HeroAction&&a.target_uid&&*a.target_uid==2;});
    CHECK(hit!=actions.end());
    CHECK(hit->source=="raw-corpus-hero-basic-attack");
    CHECK(std::any_of(actions.begin(),actions.end(),[](const Action&a){return a.type==ActionType::Wait;}));
    CHECK(std::any_of(actions.begin(),actions.end(),[](const Action&a){return a.type==ActionType::Defend;}));
    const int before=(enemy->count-1)*enemy->max_hp_per_unit+enemy->top_unit_hp;
    auto tr=sim.apply(s,*hit,0.0); CHECK(tr.valid);
    const auto* after_enemy=tr.state.entity(2); CHECK(after_enemy);
    const int after=after_enemy->alive?(after_enemy->count-1)*after_enemy->max_hp_per_unit+after_enemy->top_unit_hp:0;
    // Raw Spsc mode 062 invariant: damage = 16 + 4*max_count = 48 here.
    CHECK(before-after==48);
    return true;
}


static bool test_status_spellbook_and_effect_mechanics() {
    ProtocolDecoder d;
    std::string payload=static_payload();
    const std::string old_magic="magicfist-5-1-25-5-0-neutral-swarm-5-2-15-3-0-other-";
    const std::string new_magic="fast-4-1-40-0-0-light-mfast-8-3-40-0-0-light-slow-4-1-40-0-0-dark-"
                                "bless-4-1-100-0-0-light-curse-4-1-100-0-0-dark-stoneskin-4-1-12-0-0-light-"
                                "deflect_missile-4-1-70-0-0-light-righteous_might-4-1-12-0-0-light-confusion-4-1-70-0-0-dark-";
    auto pos=payload.find(old_magic); CHECK(pos!=std::string::npos); payload.replace(pos,old_magic.size(),new_magic);
    auto initial=d.decode_initial(payload,"status-spells");
    auto* hero=initial.state.entity(1); CHECK(hero); CHECK(hero->is_hero); hero->mana=20;
    CHECK(std::any_of(hero->spells.begin(),hero->spells.end(),[](const SpellSpec&sp){return sp.name=="fast"&&sp.wire_code=="fst"&&!sp.mass&&sp.mana_cost==4&&sp.effect_kind==SpellEffectKind::Fast&&sp.target==SpellTarget::Friendly;}));
    CHECK(std::any_of(hero->spells.begin(),hero->spells.end(),[](const SpellSpec&sp){return sp.name=="mfast"&&sp.wire_code=="fst"&&sp.mass&&sp.mana_cost==8;}));

    // Exact observed single Fast: caster=001,target=002,cost=04,duration=1000,magnitude=040.
    // The fixture target is PvE, so this record proves wire decoding only; selected spell is
    // still exact because the authoritative spellbook+mana cost match. Target-side legality is
    // enforced by speculative action generation, not by replay decoding.
    auto observed=d.decode_update(initial.state,"t=000turns=>1:C001000000Sfst001002041000040i0010100C002000000");
    const auto* target=observed.state.entity(2); CHECK(target);
    CHECK(effect_magnitude(*target,"fst")==40.0f);
    CHECK(observed.state.entity(1)->mana==16);
    CHECK(observed.state.semantic_unresolved_records==0);

    // Mass Fast: first result carries mana cost, subsequent result has cost 00 in same decision.
    BattleState mass_state=initial.state;
    Entity ally=*mass_state.entity(2); ally.uid=3; ally.side=Side::Player; ally.anchor={8,5}; mass_state.entities.push_back(ally);
    auto mass=d.decode_update(mass_state,"t=000turns=>1:C001000000Sfst001003081000040Sfst001002001000040i0010100C002000000");
    CHECK(effect_magnitude(*mass.state.entity(3),"fst")==40.0f);
    CHECK(effect_magnitude(*mass.state.entity(2),"fst")==40.0f);
    CHECK(mass.state.entity(1)->mana==12);

    Entity e; e.initiative=10; e.attack=20; e.defense=15; e.min_damage=10; e.max_damage=20;
    e.effects={{status_effect_id("fst"),2,40,""},{status_effect_id("slw"),2,30,""}};
    CHECK(std::abs(effective_initiative(e)-11.0f)<0.001f);
    e.effects.push_back({status_effect_id("rgm"),2,12,""});
    e.effects.push_back({status_effect_id("stn"),2,8,""});
    CHECK(std::abs(effective_attack(e)-32.0f)<0.001f); CHECK(std::abs(effective_defense(e)-23.0f)<0.001f);
    e.effects.push_back({status_effect_id("bls"),2,50,""});
    CHECK(std::abs(effective_min_damage(e)-15.0f)<0.001f);
    e.effects.push_back({status_effect_id("crs"),2,25,""});
    CHECK(std::abs(effective_min_damage(e)-12.5f)<0.001f);
    Entity attacker=e, defender=e; attacker.effects={{status_effect_id("cnf"),2,70,""}}; defender.effects={{status_effect_id("dfm"),2,70,""}};
    CHECK(std::abs(ranged_damage_multiplier(attacker,defender)-0.09f)<0.001f);
    CHECK(std::abs(retaliation_damage_multiplier(attacker)-0.30f)<0.001f);

    // Speculative single + mass status spell actions and duration expiry.
    BattleState s=fixture(); auto* h=s.entity(1); CHECK(h); h->is_hero=true; h->mana=20; h->max_count=3; h->side=Side::Player;
    Entity friend_stack=*s.entity(2); friend_stack.uid=3; friend_stack.side=Side::Player; friend_stack.anchor={8,2}; s.entities.push_back(friend_stack);
    h=s.entity(1); CHECK(h);
    h->spells={
        {status_effect_id("fast"),"fast","fst",4,false,false,SpellEffectKind::Fast,SpellTarget::Friendly,40},
        {status_effect_id("mfast"),"mfast","fst",8,false,true,SpellEffectKind::Fast,SpellTarget::Friendly,40},
        {status_effect_id("slow"),"slow","slw",4,false,false,SpellEffectKind::Slow,SpellTarget::Enemy,40},
    };
    GenericSimulator sim; auto acts=sim.legal_actions(s);
    auto fast=std::find_if(acts.begin(),acts.end(),[](const Action&a){return a.type==ActionType::Cast&&a.target_uid&&*a.target_uid==3;}); CHECK(fast!=acts.end());
    auto tr=sim.apply(s,*fast,0.5); CHECK(tr.valid); CHECK(tr.state.entity(1)->mana==16); CHECK(effect_magnitude(*tr.state.entity(3),"fst")==40.0f);
    // Target has not acted yet, so duration is unchanged at caster action end.
    auto fx=std::find_if(tr.state.entity(3)->effects.begin(),tr.state.entity(3)->effects.end(),[](const Effect&f){return f.id==status_effect_id("fst");}); CHECK(fx!=tr.state.entity(3)->effects.end()); CHECK(fx->duration==3);

    // Force affected stack active, make it WAIT twice; effect counts down after each own action.
    tr.state.active_entity_uid=3; tr.state.side_to_act=Side::Player;
    auto wa=sim.legal_actions(tr.state); auto wit=std::find_if(wa.begin(),wa.end(),[](const Action&a){return a.type==ActionType::Wait;}); CHECK(wit!=wa.end());
    auto tr2=sim.apply(tr.state,*wit,0.5); CHECK(tr2.valid); CHECK(tr2.state.entity(3)->effects.front().duration==2);
    tr2.state.active_entity_uid=3; tr2.state.side_to_act=Side::Player;
    auto wa2=sim.legal_actions(tr2.state); auto wit2=std::find_if(wa2.begin(),wa2.end(),[](const Action&a){return a.type==ActionType::Wait;}); CHECK(wit2!=wa2.end());
    auto tr3=sim.apply(tr2.state,*wit2,0.5); CHECK(tr3.valid); CHECK(tr3.state.entity(3)->effects.front().duration==1);
    tr3.state.active_entity_uid=3; tr3.state.side_to_act=Side::Player;
    auto wa3=sim.legal_actions(tr3.state); auto wit3=std::find_if(wa3.begin(),wa3.end(),[](const Action&a){return a.type==ActionType::Wait;}); CHECK(wit3!=wa3.end());
    auto tr4=sim.apply(tr3.state,*wit3,0.5); CHECK(tr4.valid); CHECK(effect_magnitude(*tr4.state.entity(3),"fst")==0.0f);

    auto mass_acts=sim.legal_actions(s); auto mit=std::find_if(mass_acts.begin(),mass_acts.end(),[&](const Action&a){return a.type==ActionType::Cast&&!a.target_uid&&a.ability_id&&*a.ability_id==status_effect_id("mfast");}); CHECK(mit!=mass_acts.end());
    auto mt=sim.apply(s,*mit,0.5); CHECK(mt.valid); CHECK(effect_magnitude(*mt.state.entity(3),"fst")==40.0f);
    return true;
}

static bool test_special_damage_state_mutation() {
    ProtocolDecoder d;
    auto initial=d.decode_initial(static_payload(),"spell-dmg");
    auto* target=initial.state.entity(2); CHECK(target);
    const int before=(target->count-1)*target->max_hp_per_unit+target->top_unit_hp;
    // Smfs = corpus-verified caster3,target3,param3,damage6 layout.
    auto hit=d.decode_update(initial.state,"t=000turns=>1:C001000000Smfs001002005000030i0010100");
    target=hit.state.entity(2); CHECK(target);
    const int after=target->alive ? (target->count-1)*target->max_hp_per_unit+target->top_unit_hp : 0;
    CHECK(before-after==30);
    CHECK(std::any_of(hit.events.begin(),hit.events.end(),[](const BattleEvent&e){return e.type=="SPECIAL_DAMAGE"&&e.actor_uid==1&&e.target_uid==2;}));
    // We apply the known HP delta but still retain semantic uncertainty for possible
    // secondary spell mechanics.
    CHECK(hit.state.semantic_unresolved_records>0);
    return true;
}




static bool test_raise_dead_observed_path() {
    ProtocolDecoder d;
    std::string payload = "t=000turns=>0:f<result>|#f_en<result>|#i0000000;/" +
        mrec(1,1,53,10,1,1,true) + ";/" + mrec(2,1,172,8,5,5,false) + ";bm_tooltips=e30<";
    // Make the authoritative spellbook/target ability explicit in the raw M records.
    auto hero_magic = std::string("magicfist-5-1-25-5-0-neutral-swarm-5-2-15-3-0-other-");
    auto pos = payload.find(hero_magic);
    CHECK(pos != std::string::npos);
    payload.replace(pos, hero_magic.size(), "raisedead-9-2-136-17-0-neutral-" + hero_magic);
    auto bear = std::string("alive|big|shooter|");
    pos = payload.find(bear, pos + 1);
    CHECK(pos != std::string::npos);
    payload.replace(pos, bear.size(), "alive|undead|");

    auto initial=d.decode_initial(payload,"raise");
    auto* caster=initial.state.entity(1); auto* target=initial.state.entity(2); CHECK(caster&&target);
    caster->mana=20; caster->owner=1; target->owner=1;
    target->count=0; target->top_unit_hp=0; target->alive=false; target->max_count=10;
    auto raised=d.decode_update(initial.state,"t=000turns=>1:C001000000Srsd001002-19000136i0010100C002000000");
    caster=raised.state.entity(1); target=raised.state.entity(2); CHECK(caster&&target);
    CHECK(caster->mana==11); CHECK(target->alive); CHECK(target->count==7); CHECK(target->top_unit_hp==4);
    CHECK(std::any_of(raised.events.begin(),raised.events.end(),[](const BattleEvent&e){return e.type=="RAISE_DEAD"&&e.actor_uid==1&&e.target_uid==2;}));

    // The same spell becomes a speculative planner action from the authoritative spellbook.
    BattleState sim_state=initial.state; caster=sim_state.entity(1);target=sim_state.entity(2);CHECK(caster&&target);
    caster->mana=20;caster->owner=1;target->owner=1;target->count=0;target->top_unit_hp=0;target->alive=false;target->max_count=10;
    sim_state.active_entity_uid=1;sim_state.side_to_act=Side::Player;sim_state.protocol_ready=true;sim_state.recommendation_safe=true;
    GenericSimulator sim;auto actions=sim.legal_actions(sim_state);
    auto it=std::find_if(actions.begin(),actions.end(),[](const Action&a){return a.type==ActionType::Cast&&a.target_uid&&*a.target_uid==2;});CHECK(it!=actions.end());
    auto tr=sim.apply(sim_state,*it,0.5);CHECK(tr.valid);CHECK(tr.state.entity(2)->alive);CHECK(tr.state.entity(2)->count>0);CHECK(tr.state.entity(1)->mana==11);
    return true;
}


static bool test_phantom_forces_observed_exact() {
    ProtocolDecoder d;
    std::string hero=mrec(1,1,53,10,1,1,true);
    const std::string old_magic="swarm-5-2-15-3-0-other-^";
    const auto mp=hero.find(old_magic); CHECK(mp!=std::string::npos);
    hero.replace(mp,old_magic.size(),"swarm-5-2-15-3-0-other-phantom_forces-18-3-5-0-1-neutral-^");
    // M fixed field 6 is current mana.
    hero.replace(5+6*6,6,"000030");
    const std::string source=mrec(2,1,172,8,5,5,false);
    std::string payload="t=000turns=>1:f<result>|#f_en<result>|#i0000000;/"+hero+";/"+source+";bm_tooltips=e30<";
    auto initial=d.decode_initial(payload,"phm");
    const auto* caster=initial.state.entity(1); CHECK(caster); CHECK(caster->mana==30);
    CHECK(std::any_of(caster->spells.begin(),caster->spells.end(),[](const SpellSpec&sp){return sp.effect_kind==SpellEffectKind::PhantomForces&&sp.wire_code=="phm"&&sp.mana_cost==18;}));

    std::string clone=mrec(3,1,172,8,2,2,false);
    const auto marker=clone.find("~^"); CHECK(marker!=std::string::npos);
    clone.replace(marker,2,"~^phm100000000001");
    auto r=d.decode_update(initial.state,"t=000turns=>1:C001000000P003999"+clone+"Sphm001003180020000i0010100C002000000");
    const auto* ph=r.state.entity(3); CHECK(ph); CHECK(ph->is_phantom); CHECK(ph->creature_id==r.state.entity(2)->creature_id);
    CHECK(r.state.entity(1)->mana==12);
    CHECK(r.state.semantic_unresolved_records==0);
    CHECK(std::any_of(r.events.begin(),r.events.end(),[](const BattleEvent&e){return e.type=="PHANTOM_FORCES"&&e.actor_uid==1&&e.target_uid==2;}));

    // Speculative planner action does not expose a destination: the server chooses the
    // adjacent clone cell. The simulator samples that chance outcome from the train-only
    // placement model and copies the source stack without temporary effects/spellbook.
    BattleState sim_state=initial.state;sim_state.protocol_ready=true;sim_state.recommendation_safe=true;
    sim_state.stream_contiguous=true;sim_state.active_entity_uid=1;sim_state.side_to_act=Side::Player;
    GenericSimulator sim;auto acts=sim.legal_actions(sim_state);
    auto it=std::find_if(acts.begin(),acts.end(),[](const Action&a){return a.type==ActionType::Cast&&a.target_uid&&*a.target_uid==2&&a.ability_id.has_value();});
    CHECK(it!=acts.end());auto tr=sim.apply(sim_state,*it,0.5);CHECK(tr.valid);CHECK(tr.state.entity(1)->mana==12);
    const Entity* speculative=nullptr;for(const auto&e:tr.state.entities)if(e.uid!=2&&e.uid!=1&&e.is_phantom)speculative=&e;
    CHECK(speculative);CHECK(speculative->creature_id==sim_state.entity(2)->creature_id);CHECK(speculative->count==sim_state.entity(2)->count);
    CHECK(speculative->spells.empty());CHECK(std::max(std::abs(speculative->anchor.x-sim_state.entity(2)->anchor.x),std::abs(speculative->anchor.y-sim_state.entity(2)->anchor.y))<=2);
    return true;
}

static bool test_phantom_damage_dissipation() {
    ProtocolDecoder d;
    // Every Sphm-created clone carries a post-^ phm modifier in the new raw corpus.
    const std::string clone =
        "M017:0000010000720000140000140000050000080000000000000000060000460013.4000042000042000001000009000006000013000052000029000005000001000001000014000003"
        "hunterelfani|[1.4-34.29b25c]|Grandmaster bowmen|alive|shooter|doubleshoot|wardingarrows|~^sum100000000001phm100000000001";
    BattleState s=fixture(); s.halfturn=0; s.stream_contiguous=false; s.protocol_ready=false;
    auto spawned=d.decode_update(s,"t=000turns=>1:"+clone+"C001000000");
    const auto* ph=spawned.state.entity(17); CHECK(ph); CHECK(ph->is_phantom); CHECK(ph->alive); CHECK(ph->count==42);

    // 1 point is deeply sub-lethal under normal HP, but positive damage dissipates a phantom.
    auto hit=d.decode_update(spawned.state,"t=000turns=>2:d0010170000000001i0010100C002000000");
    ph=hit.state.entity(17); CHECK(ph); CHECK(!ph->alive); CHECK(ph->count==0); CHECK(ph->top_unit_hp==0);

    // The same rule must hold in speculative rollouts, not only observed replay decoding.
    BattleState sim_state=fixture(); auto* target=sim_state.entity(2); CHECK(target);
    target->is_phantom=true; target->anchor={2,1}; target->count=8; target->top_unit_hp=20;
    auto* actor=sim_state.entity(1); CHECK(actor); actor->is_shooter=false; actor->shots=0; actor->anchor={1,1};
    GenericSimulator sim; auto acts=sim.legal_actions(sim_state);
    auto it=std::find_if(acts.begin(),acts.end(),[](const Action&a){return a.type==ActionType::MeleeAttack&&a.target_uid&&*a.target_uid==2;});
    CHECK(it!=acts.end()); auto tr=sim.apply(sim_state,*it,0.0); CHECK(tr.valid); CHECK(!tr.state.entity(2)->alive);
    return true;
}


static bool test_psc_damage_delta() {
    ProtocolDecoder d;
    BattleState s=fixture(); s.halfturn=0; s.stream_contiguous=false; s.protocol_ready=false;
    auto* target=s.entity(2); CHECK(target); target->is_phantom=true; target->count=8; target->top_unit_hp=20;
    auto r=d.decode_update(s,"t=000turns=>1:C001000000Spsc001002000016062i0010100C002000000");
    target=r.state.entity(2); CHECK(target); CHECK(!target->alive); CHECK(target->count==0);
    CHECK(std::any_of(r.events.begin(),r.events.end(),[](const BattleEvent&e){return e.type=="SPECIAL_PSC_DAMAGE"&&e.target_uid==2;}));
    // The mode field is not fully decoded, so this remains semantic uncertainty despite
    // applying the independently verified HP delta.
    CHECK(r.state.semantic_unresolved_records>0);
    return true;
}



static bool test_endurance_u_record_exact_speed_increment() {
    hwm::BattleState st; st.battle_id="endurance"; st.min_x=1; st.min_y=1; st.width=12; st.height=10; st.phase=hwm::Phase::Combat; st.stream_contiguous=true;
    hwm::Entity e; e.uid=18; e.creature_id=920; e.owner=2; e.side=hwm::Side::Pve; e.anchor={10,1}; e.alive=true; e.count=1; e.max_count=1; e.max_hp_per_unit=100; e.top_unit_hp=100; e.speed=4.0f;
    uint32_t h=2166136261u; for(unsigned char c:std::string("endurance")){h^=c;h*=16777619u;} e.ability_ids.push_back(h); st.entities.push_back(e);
    hwm::ProtocolDecoder dec;
    auto d1=dec.decode_update(st,"t=001turns=>1:u018");
    CHECK(d1.state.entity(18)); CHECK(std::abs(d1.state.entity(18)->speed-5.0f)<1e-5f); CHECK(d1.state.semantic_unresolved_records==0);
    auto d2=dec.decode_update(d1.state,"t=002turns=>2:u018u018u018");
    CHECK(std::abs(d2.state.entity(18)->speed-8.0f)<1e-5f); CHECK(d2.state.semantic_unresolved_records==0);
    auto d3=dec.decode_update(d2.state,"t=003turns=>3:u018");
    CHECK(std::abs(d3.state.entity(18)->speed-8.0f)<1e-5f); CHECK(d3.state.semantic_unresolved_records==1);
    return true;
}

static bool test_rune_speed_exact_path() {
    // Speculative path: server-declared run modifier exposes one preparatory ABILITY,
    // keeps the same actor active, doubles the next movement budget, then consumes it.
    BattleState s=fixture();
    auto* actor=s.entity(1); auto* enemy=s.entity(2); CHECK(actor&&enemy);
    actor->is_hero=false;actor->is_shooter=false;actor->shots=0;actor->anchor={1,1};actor->speed=3;
    actor->rune_speed_available=true;actor->run_modifier="100000000001";
    enemy->anchor={8,1};s.active_entity_uid=1;s.side_to_act=Side::Player;s.protocol_ready=true;s.recommendation_safe=true;
    GenericSimulator sim;
    auto actions=sim.legal_actions(s);
    auto rune=std::find_if(actions.begin(),actions.end(),[](const Action&a){return a.type==ActionType::Ability&&a.ability_id.has_value()&&a.source.find("Srn2")!=std::string::npos;});
    CHECK(rune!=actions.end());
    auto armed=sim.apply(s,*rune,0.5);CHECK(armed.valid);CHECK(armed.state.active_entity_uid==1);
    CHECK(armed.state.entity(1)->rune_speed_active);CHECK(armed.state.entity(1)->rune_speed_consumed);
    auto boosted=sim.legal_actions(armed.state);
    auto hit=std::find_if(boosted.begin(),boosted.end(),[](const Action&a){return a.type==ActionType::MeleeAttack&&a.target_uid&&*a.target_uid==2&&a.destination&&a.destination->x==7&&a.destination->y==1;});
    CHECK(hit!=boosted.end());
    auto after=sim.apply(armed.state,*hit,0.5);CHECK(after.valid);CHECK(!after.state.entity(1)->rune_speed_active);CHECK(after.state.entity(1)->rune_speed_consumed);
    auto later=sim.legal_actions(after.state);
    CHECK(std::none_of(later.begin(),later.end(),[](const Action&a){return a.type==ActionType::Ability&&a.source.find("Srn2")!=std::string::npos;}));

    // Observed path: Srn2 non-zero and zero records are exact semantic transitions.
    ProtocolDecoder d; BattleState obs=s;obs.halfturn=0;obs.stream_contiguous=false;obs.protocol_ready=false;obs.recommendation_safe=false;
    auto decoded=d.decode_update(obs,
        "t=000turns=>1:C001000000Srn2001001100200000C001000000;>2:m0010701d0010020000000005Srn2001000000000000i0010100C002000000");
    const auto* oe=decoded.state.entity(1);CHECK(oe);CHECK(oe->rune_speed_consumed);CHECK(!oe->rune_speed_active);
    CHECK((oe->anchor==Cell{7,1}));CHECK(decoded.coverage.unknown_records==0);CHECK(decoded.state.semantic_unresolved_records==0);
    CHECK(std::any_of(decoded.events.begin(),decoded.events.end(),[](const BattleEvent&e){return e.type=="RUNE_SPEED_ACTIVATE";}));
    CHECK(std::any_of(decoded.events.begin(),decoded.events.end(),[](const BattleEvent&e){return e.type=="RUNE_SPEED_CLEAR";}));
    return true;
}

static bool test_statix_cell_overlay_validation() {
    BattleState s=fixture();
    auto* a=s.entity(1); auto* b=s.entity(2); CHECK(a&&b);
    a->is_shooter=false; a->is_big=true; a->footprint_w=a->footprint_h=2; a->anchor={3,3};
    b->creature_id=760; b->is_statix=true; b->is_big=true; b->footprint_w=b->footprint_h=2; b->anchor={3,3};
    CHECK(validate(s).empty());
    // The exception is intentionally specific: an arbitrary overlapping statix-like
    // combatant must not silently make geometry valid.
    b->creature_id=999; CHECK(!validate(s).empty());
    return true;
}


static void add_tag(Entity& e,const char* code){ e.ability_ids.push_back(stable_ability_id(code)); }

static int entity_total_hp(const Entity& e){ return e.alive&&e.count>0?(e.count-1)*std::max(1,e.max_hp_per_unit)+std::max(0,e.top_unit_hp):0; }



static bool test_collateral_model_application() {
    const auto path=std::filesystem::temp_directory_path()/"hwm_collateral_test.csv";
    {
        std::ofstream f(path);
        f << "ability_code,action_type,zone,max_secondary,enabled,train_decisions,candidate_hit_probability,train_recall,heldout_decisions,heldout_precision,heldout_recall,heldout_exact_set_rate\n";
        f << "spray,MELEE_ATTACK,actor_adjacent,2,1,100,1.0,1.0,50,1.0,1.0,1.0\n";
    }
    BattleState s=fixture();auto*a=s.entity(1);auto*t=s.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};t->retaliation_available=false;add_tag(*a,"spray");
    Entity secondary=*t;secondary.uid=3;secondary.anchor={1,2};secondary.count=8;secondary.top_unit_hp=20;s.entities.push_back(secondary);
    GenericSimulator sim;CHECK(sim.load_collateral_model(path.string()));
    auto acts=sim.legal_actions(s);auto it=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(it!=acts.end());
    const int before=entity_total_hp(*s.entity(3));auto tr=sim.apply(s,*it,0.5);CHECK(tr.valid);CHECK(entity_total_hp(*tr.state.entity(3))<before);
    std::filesystem::remove(path);return true;
}

static bool test_ability_registry_and_transfer_models() {
    const auto tmp=std::filesystem::temp_directory_path()/"hwm_ability_registry_test.csv";
    {
        std::ofstream f(tmp);
        f << "ability_id,code,support,risk_weight,categories,observed_entity_tags,name\n";
        f << stable_ability_id("shooter") << ",shooter,exact_search,0.0,ranged,100,shooter\n";
        f << stable_ability_id("mystery_proc") << ",mystery_proc,unresolved,0.8,control,10,mystery\n";
    }
    AbilityRegistry reg(tmp.string()); CHECK(reg.loaded()); CHECK(reg.risk_for(stable_ability_id("shooter"))==0.0); CHECK(reg.risk_for(stable_ability_id("mystery_proc"))>0.79);
    BattleState st=fixture(); add_tag(*st.entity(1),"shooter"); CHECK(reg.state_risk(st)<0.01); add_tag(*st.entity(2),"mystery_proc"); CHECK(reg.state_risk(st)>0.10);
    std::filesystem::remove(tmp);

    const auto dm=std::filesystem::temp_directory_path()/"hwm_ability_damage_test.csv";
    {
        std::ofstream f(dm);
        f << "action_type,role,ability_code,samples,log_coefficient,multiplier\n";
        f << "MELEE_ATTACK,actor,mystery_proc,30,0.200000000,1.221402758\n";
        f << "MELEE_ATTACK,target,shielded,30,-0.100000000,0.904837418\n";
    }
    AbilityDamageModel model(dm.string());CHECK(model.loaded()); Entity a,t;add_tag(a,"mystery_proc");add_tag(t,"shielded");double m=model.multiplier(a,t,ActionType::MeleeAttack);CHECK(m>1.10&&m<1.11);
    std::filesystem::remove(dm);
    return true;
}


static bool test_spell_immunity_targeting_and_dynamic_caster_risk() {
    GenericSimulator sim;

    // Direct spell immunities are target legality, not a post-hoc damage modifier.
    {
        BattleState s=fixture(); auto* hero=s.entity(1); auto* enemy=s.entity(2); CHECK(hero&&enemy);
        hero->is_hero=true; hero->mana=30; hero->spells={
            {stable_ability_id("lighting"),"lighting","ltn",5,true,false,SpellEffectKind::DirectDamage,SpellTarget::Enemy,0},
            {stable_ability_id("icebolt"),"icebolt","ice",5,true,false,SpellEffectKind::DirectDamage,SpellTarget::Enemy,0},
            {stable_ability_id("slow"),"slow","slw",4,false,false,SpellEffectKind::Slow,SpellTarget::Enemy,40},
        };
        add_tag(*enemy,"ilighting"); add_tag(*enemy,"icold"); add_tag(*enemy,"islow");
        s.active_entity_uid=hero->uid; s.side_to_act=Side::Player;
        auto acts=sim.legal_actions(s);
        for(const auto&a:acts){
            if(a.type!=ActionType::Cast||!a.target_uid||*a.target_uid!=enemy->uid||!a.ability_id)continue;
            CHECK(*a.ability_id!=stable_ability_id("lighting"));
            CHECK(*a.ability_id!=stable_ability_id("icebolt"));
            CHECK(*a.ability_id!=stable_ability_id("slow"));
        }
        Action invalid; invalid.action_id=99; invalid.actor_uid=hero->uid; invalid.type=ActionType::Cast;
        invalid.target_uid=enemy->uid; invalid.ability_id=stable_ability_id("lighting");
        auto tr=sim.apply(s,invalid,0.5); CHECK(!tr.valid); CHECK(tr.warning=="illegal_action"||tr.warning=="spell_target_invalid_or_immune");

        BattleState full=s;auto* fe=full.entity(2);CHECK(fe);fe->ability_ids.clear();add_tag(*fe,"immunity");
        auto full_acts=sim.legal_actions(full);CHECK(std::none_of(full_acts.begin(),full_acts.end(),[&](const Action&x){return x.type==ActionType::Cast&&x.target_uid&&*x.target_uid==2;}));
        BattleState mind=s;auto* mh=mind.entity(1);auto* mt=mind.entity(2);CHECK(mh&&mt);mt->ability_ids.clear();add_tag(*mt,"imind");
        mh->spells={{stable_ability_id("confusion"),"confusion","cnf",5,false,false,SpellEffectKind::Confusion,SpellTarget::Enemy,50}};
        auto mind_acts=sim.legal_actions(mind);CHECK(std::none_of(mind_acts.begin(),mind_acts.end(),[&](const Action&x){return x.type==ActionType::Cast&&x.target_uid&&*x.target_uid==2;}));
    }

    // For unseen target creature IDs, all-magic resistance is applied to SA/S fallback
    // rather than being double-counted on target-conditioned SAT/ST observations.
    {
        BattleState base=fixture();auto*hero=base.entity(1);auto*enemy=base.entity(2);CHECK(hero&&enemy);hero->is_hero=true;hero->mana=30;enemy->creature_id=999999;enemy->max_count=100;enemy->count=100;enemy->top_unit_hp=20;
        hero->spells={{stable_ability_id("lighting"),"lighting","ltn",5,true,false,SpellEffectKind::DirectDamage,SpellTarget::Enemy,0}};
        base.active_entity_uid=1;base.side_to_act=Side::Player;
        auto acts=sim.legal_actions(base);auto cast=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::Cast&&x.ability_id&&*x.ability_id==stable_ability_id("lighting");});CHECK(cast!=acts.end());int hp=entity_total_hp(*enemy);auto normal=sim.apply(base,*cast,0.5);int dn=hp-entity_total_hp(*normal.state.entity(2));CHECK(dn>0);
        BattleState resistant=base;add_tag(*resistant.entity(2),"magicproof50");auto ra=sim.legal_actions(resistant);auto rc=std::find_if(ra.begin(),ra.end(),[](const Action&x){return x.type==ActionType::Cast&&x.ability_id&&*x.ability_id==stable_ability_id("lighting");});CHECK(rc!=ra.end());auto rr=sim.apply(resistant,*rc,0.5);int dr=hp-entity_total_hp(*rr.state.entity(2));CHECK(dr<dn*0.65&&dr>dn*0.35);
    }

    // Dynamic spell modifiers must be applied even when the learned spell table is
    // target-conditioned: position/status is not encoded by creature ID.
    {
        BattleState base=fixture();auto*hero=base.entity(1);auto*enemy=base.entity(2);CHECK(hero&&enemy);
        hero->is_hero=true;hero->mana=30;hero->spells={{stable_ability_id("lighting"),"lighting","ltn",5,true,false,SpellEffectKind::DirectDamage,SpellTarget::Enemy,0}};
        enemy->max_count=1000;enemy->count=1000;enemy->top_unit_hp=20;enemy->anchor={6,5};
        base.active_entity_uid=1;base.side_to_act=Side::Player;
        auto find_cast=[](const std::vector<Action>&acts){return std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::Cast&&x.ability_id&&*x.ability_id==stable_ability_id("lighting");});};
        auto ba=sim.legal_actions(base);auto bc=find_cast(ba);CHECK(bc!=ba.end());int hp=entity_total_hp(*enemy);auto normal=sim.apply(base,*bc,0.5);int dn=hp-entity_total_hp(*normal.state.entity(2));CHECK(dn>4);

        BattleState resist=base;add_tag(*resist.entity(2),"auraofres");auto ra=sim.legal_actions(resist);auto rc=find_cast(ra);CHECK(rc!=ra.end());auto rr=sim.apply(resist,*rc,0.5);int dr=hp-entity_total_hp(*rr.state.entity(2));CHECK(dr<dn*0.80&&dr>dn*0.58);

        BattleState vulnerable=base;Entity aura=*vulnerable.entity(1);aura.uid=3;aura.is_hero=false;aura.spells.clear();aura.anchor={5,5};aura.side=Side::Player;aura.owner=1;aura.ability_ids.clear();add_tag(aura,"auraofairvul");vulnerable.entities.push_back(aura);
        auto va=sim.legal_actions(vulnerable);auto vc=find_cast(va);CHECK(vc!=va.end());auto vr=sim.apply(vulnerable,*vc,0.5);int dv=hp-entity_total_hp(*vr.state.entity(2));CHECK(dv>dn*1.35&&dv<dn*1.65);

        BattleState stone=base;stone.entity(2)->effects.push_back({status_effect_id("proc_stone"),1,1.0f,"test"});auto sa=sim.legal_actions(stone);auto sc=find_cast(sa);CHECK(sc!=sa.end());auto sr=sim.apply(stone,*sc,0.5);int ds=hp-entity_total_hp(*sr.state.entity(2));CHECK(ds<dn*0.60&&ds>dn*0.40);
    }

    // `caster` uncertainty comes from the authoritative spellbook. A caster whose
    // entire spellbook is supported must be substantially lower-risk than one whose
    // listed spell is not modeled by non-hero rollouts.
    const auto tmp=std::filesystem::temp_directory_path()/"hwm_dynamic_caster_registry.csv";
    {
        std::ofstream f(tmp);
        f << "ability_id,code,support,risk_weight,categories,observed_entity_tags,name\n";
        f << stable_ability_id("caster") << ",caster,dynamic_spellbook,0.1,casting,100,caster\n";
    }
    AbilityRegistry reg(tmp.string()); CHECK(reg.loaded());
    BattleState supported=fixture(); auto* c=supported.entity(2); CHECK(c); c->ability_ids.clear(); add_tag(*c,"caster");
    c->spells={{stable_ability_id("magicfist"),"magicfist","mfs",5,true,false,SpellEffectKind::DirectDamage,SpellTarget::Enemy,0}};
    const double r_supported=reg.state_risk(supported);
    BattleState unknown=supported; auto* cu=unknown.entity(2); CHECK(cu);
    cu->spells={{stable_ability_id("mystery_spell"),"mystery_spell","zzz",5,false,false,SpellEffectKind::None,SpellTarget::Enemy,0}};
    const double r_unknown=reg.state_risk(unknown);
    CHECK(r_supported<0.10); CHECK(r_unknown>r_supported+0.15);
    std::filesystem::remove(tmp);
    return true;
}


static bool test_proc_model_stateful_mechanics() {
    const auto path=std::filesystem::temp_directory_path()/"hwm_proc_model_test.csv";
    {
        std::ofstream f(path);
        f << "ability_code,action_types,effect,signal,train_n,train_hits,train_probability,heldout_n,heldout_hits,heldout_probability,abs_drift,enabled\n";
        f << "entroots,MELEE_ATTACK,root,ent,100,100,1.0,50,50,1.0,0.0,1\n";
        f << "ferociouswound,MELEE_ATTACK,ferocious_wound,fdc,100,100,1.0,50,50,1.0,0.0,1\n";
        f << "blinding_attack,MELEE_ATTACK|RANGED_ATTACK,blind,bld,100,100,1.0,50,50,1.0,0.0,1\n";
        f << "torpor,MELEE_ATTACK,torpor,tor,100,100,1.0,50,50,1.0,0.0,1\n";
        f << "stoning,MELEE_ATTACK,stone,sta,100,100,1.0,50,50,1.0,0.0,1\n";
        f << "wardingarrows,RANGED_ATTACK,atb_delay,T_RECORD,100,100,1.0,50,50,1.0,0.0,1\n";
        // Conditional Shield Bash row: intercept=10 and zero coefficients makes the
        // non-mechanical proc effectively certain while exercising logistic CSV loading.
        f << "shieldbash,MELEE_ATTACK,stun_delay,o<actor>,100,50,0.5,50,25,0.5,0.0,1,logistic,10,"
             "0|0|0|0|0|0|0|0|0,1|1|1|1|1|1|1|1|1,0|0|0|0|0|0|0|0|0,,,\n";
    }
    GenericSimulator sim; CHECK(sim.load_proc_model(path.string()));

    // Roots: attack roots target; while source remains in place the target has no MOVE.
    {
        BattleState s=fixture();auto*a=s.entity(1);auto*t=s.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};t->retaliation_available=false;add_tag(*a,"entroots");
        auto acts=sim.legal_actions(s);auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=acts.end());
        auto tr=sim.apply(s,*hit,0.0);CHECK(tr.valid);CHECK(effect_magnitude(*tr.state.entity(2),"proc_root")>0);
        tr.state.active_entity_uid=2;tr.state.side_to_act=Side::Pve;auto rooted=sim.legal_actions(tr.state);CHECK(std::none_of(rooted.begin(),rooted.end(),[](const Action&x){return x.type==ActionType::Move;}));
        // Moving the root source clears its old roots.
        tr.state.active_entity_uid=1;tr.state.side_to_act=Side::Player;auto source_acts=sim.legal_actions(tr.state);auto mv=std::find_if(source_acts.begin(),source_acts.end(),[](const Action&x){return x.type==ActionType::Move&&x.destination.has_value();});CHECK(mv!=source_acts.end());
        auto moved=sim.apply(tr.state,*mv,0.5);CHECK(moved.valid);CHECK(effect_magnitude(*moved.state.entity(2),"proc_root")==0.0f);
    }

    // Ferocious wound: -3 speed plus a two-turn DoT derived from the triggering hit.
    {
        BattleState s=fixture();auto*a=s.entity(1);auto*t=s.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};t->retaliation_available=false;add_tag(*a,"ferociouswound");const float speed=t->speed;
        auto acts=sim.legal_actions(s);auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=acts.end());auto tr=sim.apply(s,*hit,0.0);CHECK(tr.valid);CHECK(std::abs(effective_speed(*tr.state.entity(2))-(speed-3.0f))<0.01f);
        const int before_dot=entity_total_hp(*tr.state.entity(2));tr.state.active_entity_uid=2;tr.state.side_to_act=Side::Pve;auto ta=sim.legal_actions(tr.state);auto wait=std::find_if(ta.begin(),ta.end(),[](const Action&x){return x.type==ActionType::Wait;});CHECK(wait!=ta.end());auto tick=sim.apply(tr.state,*wait,0.5);CHECK(tick.valid);CHECK(entity_total_hp(*tick.state.entity(2))<before_dot);
    }

    // Shield Bash: modeled proc suppresses the immediate retaliation but does not
    // invent a whole forced skipped action. Mechanical targets are immune.
    {
        BattleState s=fixture();auto*a=s.entity(1);auto*t=s.entity(2);CHECK(a&&t);
        a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};t->retaliation_available=true;add_tag(*a,"shieldbash");
        const int actor_hp=entity_total_hp(*a);
        auto acts=sim.legal_actions(s);auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=acts.end());
        auto tr=sim.apply(s,*hit,0.0);CHECK(tr.valid);CHECK(entity_total_hp(*tr.state.entity(1))==actor_hp);
        BattleState immune=s;add_tag(*immune.entity(2),"mechanical");auto ia=sim.legal_actions(immune);auto ih=std::find_if(ia.begin(),ia.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(ih!=ia.end());
        auto itr=sim.apply(immune,*ih,0.0);CHECK(itr.valid);CHECK(entity_total_hp(*itr.state.entity(1))<actor_hp);
    }

    // Blind is a modeled forced-skip proc and does not apply to immune identity classes.
    {
        BattleState s=fixture();auto*a=s.entity(1);auto*t=s.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};t->retaliation_available=true;add_tag(*a,"blinding_attack");
        auto acts=sim.legal_actions(s);auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=acts.end());auto tr=sim.apply(s,*hit,0.0);CHECK(tr.valid);CHECK(effect_magnitude(*tr.state.entity(2),"proc_blind")>0);CHECK(tr.state.entity(2)->retaliation_available);
        tr.state.active_entity_uid=2;tr.state.side_to_act=Side::Pve;auto blind=sim.legal_actions(tr.state);CHECK(blind.size()==1&&blind[0].type==ActionType::Wait);
        BattleState immune=s;add_tag(*immune.entity(2),"undead");auto ia=sim.legal_actions(immune);auto ih=std::find_if(ia.begin(),ia.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(ih!=ia.end());auto itr=sim.apply(immune,*ih,0.0);CHECK(effect_magnitude(*itr.state.entity(2),"proc_blind")==0.0f);
        BattleState explicit_immune=s;add_tag(*explicit_immune.entity(2),"iblind");auto ea=sim.legal_actions(explicit_immune);auto eh=std::find_if(ea.begin(),ea.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(eh!=ea.end());auto etr=sim.apply(explicit_immune,*eh,0.0);CHECK(effect_magnitude(*etr.state.entity(2),"proc_blind")==0.0f);
    }

    // Stoning: one skipped activation and 50% incoming damage while petrified.
    {
        BattleState s=fixture();auto*a=s.entity(1);auto*t=s.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};t->retaliation_available=true;add_tag(*a,"stoning");
        auto acts=sim.legal_actions(s);auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=acts.end());
        auto tr=sim.apply(s,*hit,0.0);CHECK(tr.valid);CHECK(effect_magnitude(*tr.state.entity(2),"proc_stone")>0);CHECK(entity_total_hp(*tr.state.entity(1))==entity_total_hp(*s.entity(1)));
        tr.state.active_entity_uid=2;tr.state.side_to_act=Side::Pve;auto stoned=sim.legal_actions(tr.state);CHECK(stoned.size()==1&&stoned[0].type==ActionType::Wait);
        auto wake=sim.apply(tr.state,stoned[0],0.5);CHECK(wake.valid);CHECK(effect_magnitude(*wake.state.entity(2),"proc_stone")==0.0f);
    }

    // Warding Arrows: learned chance creates an explicit scheduler-delay marker; it does
    // not invent a forced skip or suppress melee retaliation.
    {
        BattleState s=fixture();auto*a=s.entity(1);auto*t=s.entity(2);CHECK(a&&t);a->anchor={1,1};t->anchor={8,1};a->is_shooter=true;a->shots=5;add_tag(*a,"wardingarrows");
        auto acts=sim.legal_actions(s);auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::RangedAttack&&x.target_uid&&*x.target_uid==2;});CHECK(hit!=acts.end());
        auto tr=sim.apply(s,*hit,0.0);CHECK(tr.valid);CHECK(effect_magnitude(*tr.state.entity(2),"proc_warding")>0.19f);
    }
    std::filesystem::remove(path);return true;
}


static bool test_festering_aura_exact_position_effect() {
    GenericSimulator sim;
    BattleState s=fixture();
    auto* a=s.entity(1); auto* t=s.entity(2); CHECK(a&&t);
    a->is_shooter=false; a->shots=0; a->anchor={1,1}; a->attack=20; a->defense=20; a->morale=3;
    t->anchor={2,1}; t->attack=18; t->defense=18; t->morale=4; t->retaliation_available=false; add_tag(*t,"festeringaura");
    CHECK(std::abs(effective_attack(s,*a)-16.0f)<0.01f);
    CHECK(std::abs(effective_defense(s,*a)-16.0f)<0.01f);
    CHECK(std::abs(effective_morale(s,*a)-1.0f)<0.01f);
    // Aura affects allies as well. Add a friendly adjacent victim.
    Entity ally=*t; ally.uid=3; ally.side=Side::Pve; ally.anchor={3,1}; ally.attack=14; ally.defense=13; ally.morale=2; ally.ability_ids.clear(); s.entities.push_back(ally);
    CHECK(std::abs(effective_attack(s,*s.entity(3))-10.0f)<0.01f);
    CHECK(std::abs(effective_defense(s,*s.entity(3))-9.0f)<0.01f);
    CHECK(std::abs(effective_morale(s,*s.entity(3))-0.0f)<0.01f);
    // Undead is explicitly immune according to the supplied ability description.
    add_tag(*s.entity(1),"undead");
    CHECK(std::abs(effective_attack(s,*s.entity(1))-20.0f)<0.01f);
    CHECK(std::abs(effective_defense(s,*s.entity(1))-20.0f)<0.01f);
    CHECK(std::abs(effective_morale(s,*s.entity(1))-3.0f)<0.01f);
    // Moving away immediately removes the positional modifier; no stale status is stored.
    s.entity(1)->ability_ids.erase(std::remove(s.entity(1)->ability_ids.begin(),s.entity(1)->ability_ids.end(),stable_ability_id("undead")),s.entity(1)->ability_ids.end());
    s.entity(1)->anchor={7,7};
    CHECK(std::abs(effective_attack(s,*s.entity(1))-20.0f)<0.01f);
    // 2x2 footprint adjacency is edge based, not anchor-distance based.
    BattleState big=s; big.entity(1)->anchor={1,1}; big.entity(1)->footprint_w=2;big.entity(1)->footprint_h=2; big.entity(2)->anchor={3,2};
    CHECK(std::abs(effective_attack(big,*big.entity(1))-16.0f)<0.01f);
    BattleState fear=fixture();auto*fa=fear.entity(1);auto*fv=fear.entity(2);CHECK(fa&&fv);fa->anchor={1,1};fv->anchor={2,1};fa->morale=2;fv->morale=4;add_tag(*fa,"frightfulaura");
    CHECK(std::abs(effective_morale(fear,*fv)-1.0f)<0.01f);CHECK(std::abs(effective_morale(fear,*fa)-2.0f)<0.01f);fv->anchor={8,8};CHECK(std::abs(effective_morale(fear,*fv)-4.0f)<0.01f);
    BattleState brave=fixture();auto*bs=brave.entity(1);CHECK(bs);bs->anchor={1,1};bs->morale=-2;add_tag(*bs,"auraofbravery");Entity brave_ally=*bs;brave_ally.uid=3;brave_ally.anchor={2,1};brave_ally.morale=-1;brave_ally.ability_ids.clear();brave.entities.push_back(brave_ally);CHECK(effective_morale(brave,*brave.entity(1))>=3.0f);CHECK(effective_morale(brave,*brave.entity(3))>=3.0f);brave.entity(3)->anchor={8,8};CHECK(std::abs(effective_morale(brave,*brave.entity(3))+1.0f)<0.01f);
    return true;
}

static bool test_exact_reference_ability_mechanics() {
    GenericSimulator sim;

    // Double shot must be two physical hits and spend two shots.
    {
        BattleState base=fixture(); auto* a=base.entity(1); auto* t=base.entity(2); CHECK(a&&t);
        a->anchor={1,1};t->anchor={8,1};a->shots=4;a->double_shoot=false;
        auto acts=sim.legal_actions(base);auto it=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::RangedAttack&&x.target_uid&&*x.target_uid==2;});CHECK(it!=acts.end());
        int before=entity_total_hp(*t);auto one=sim.apply(base,*it,0.5);CHECK(one.valid);int one_damage=before-entity_total_hp(*one.state.entity(2));CHECK(one.state.entity(1)->shots==3);
        BattleState dbl=base;auto* da=dbl.entity(1);CHECK(da);add_tag(*da,"doubleshoot");da->double_shoot=true;
        auto dactions=sim.legal_actions(dbl);auto dit=std::find_if(dactions.begin(),dactions.end(),[](const Action&x){return x.type==ActionType::RangedAttack&&x.target_uid&&*x.target_uid==2;});CHECK(dit!=dactions.end());
        int dbefore=entity_total_hp(*dbl.entity(2));auto two=sim.apply(dbl,*dit,0.5);CHECK(two.valid);int two_damage=dbefore-entity_total_hp(*two.state.entity(2));CHECK(two.state.entity(1)->shots==2);CHECK(two_damage>one_damage*1.7);
    }

    // Impervious to Pain blocks all speculative damage until the target has acted once.
    {
        BattleState s=fixture();auto*a=s.entity(1);auto*t=s.entity(2);CHECK(a&&t);
        a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};t->retaliation_available=false;t->last_acted_seq=0;add_tag(*t,"impervioustopain");
        auto acts=sim.legal_actions(s);auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=acts.end());
        const int hp=entity_total_hp(*t);auto protected_hit=sim.apply(s,*hit,0.5);CHECK(protected_hit.valid);CHECK(entity_total_hp(*protected_hit.state.entity(2))==hp);
        BattleState after=s;after.entity(2)->last_acted_seq=1;auto aacts=sim.legal_actions(after);auto ahit=std::find_if(aacts.begin(),aacts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(ahit!=aacts.end());auto damaged=sim.apply(after,*ahit,0.5);CHECK(damaged.valid);CHECK(entity_total_hp(*damaged.state.entity(2))<hp);
    }

    // Swift Attack: a target under Slow cannot retaliate.  The Slow effect is
    // already decoded from the authoritative server spell record; this perk only
    // changes the retaliation branch of the tree.
    {
        BattleState base=fixture();auto* a=base.entity(1);auto* t=base.entity(2);CHECK(a&&t);
        a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};t->retaliation_available=true;
        auto acts=sim.legal_actions(base);auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=acts.end());
        const int actor_hp=entity_total_hp(*a);auto normal=sim.apply(base,*hit,0.5);CHECK(normal.valid);CHECK(entity_total_hp(*normal.state.entity(1))<actor_hp);
        BattleState swift=base;add_tag(*swift.entity(1),"swiftattack");swift.entity(2)->effects.push_back({status_effect_id("slw"),2,20.0f,"test slow"});
        auto sacts=sim.legal_actions(swift);auto shit=std::find_if(sacts.begin(),sacts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(shit!=sacts.end());
        auto no_ret=sim.apply(swift,*shit,0.5);CHECK(no_ret.valid);CHECK(entity_total_hp(*no_ret.state.entity(1))==actor_hp);
    }

    // Double/triple melee strike performs extra hits; retaliation only occurs after hit #1.
    {
        BattleState base=fixture();auto* a=base.entity(1);auto* t=base.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};t->retaliation_available=false;
        auto act=sim.legal_actions(base);auto hit=std::find_if(act.begin(),act.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=act.end());
        int hp0=entity_total_hp(*t);auto one=sim.apply(base,*hit,0.5);int d1=hp0-entity_total_hp(*one.state.entity(2));
        BattleState ds=base;add_tag(*ds.entity(1),"doublestrike");auto da=sim.legal_actions(ds);auto dh=std::find_if(da.begin(),da.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(dh!=da.end());auto two=sim.apply(ds,*dh,0.5);int d2=hp0-entity_total_hp(*two.state.entity(2));CHECK(d2>d1*1.7);
        BattleState ts=base;add_tag(*ts.entity(1),"triplestrike");auto ta=sim.legal_actions(ts);auto th=std::find_if(ta.begin(),ta.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(th!=ta.end());auto three=sim.apply(ts,*th,0.5);int d3=hp0-entity_total_hp(*three.state.entity(2));CHECK(d3>d2*1.3);
    }

    // Strike-and-return ends on the original anchor after a move+attack.
    {
        BattleState s=fixture();auto* a=s.entity(1);auto* t=s.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->anchor={1,1};a->speed=4;t->anchor={4,1};add_tag(*a,"strikeandreturn");
        auto acts=sim.legal_actions(s);auto it=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&x.destination.has_value();});CHECK(it!=acts.end());Cell origin=a->anchor;auto tr=sim.apply(s,*it,0.5);CHECK(tr.valid);CHECK(tr.state.entity(1)->anchor==origin);
    }

    // Take Roots: DEFEND is +50% Defence and retaliation is not consumed until
    // the stack's next activation.  The hero-talent +100% variant is intentionally
    // not modeled until a reliable talent flag is present in canonical state.
    {
        BattleState s=fixture();auto*a=s.entity(1);auto*t=s.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};add_tag(*t,"takeroots");
        s.active_entity_uid=2;s.side_to_act=t->side;auto ta=sim.legal_actions(s);auto def=std::find_if(ta.begin(),ta.end(),[](const Action&x){return x.type==ActionType::Defend;});CHECK(def!=ta.end());auto rooted=sim.apply(s,*def,0.5);CHECK(rooted.valid);CHECK(rooted.state.entity(2)->defending);
        BattleState attack=rooted.state;attack.active_entity_uid=1;attack.side_to_act=Side::Player;attack.entity(2)->retaliation_available=true;auto aa=sim.legal_actions(attack);auto hit=std::find_if(aa.begin(),aa.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=aa.end());auto tr=sim.apply(attack,*hit,0.5);CHECK(tr.valid);CHECK(tr.state.entity(2)->retaliation_available);
        BattleState normal=attack;normal.entity(2)->ability_ids.clear();auto na=sim.legal_actions(normal);auto nh=std::find_if(na.begin(),na.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(nh!=na.end());const int hp=entity_total_hp(*attack.entity(2));const int rooted_d=hp-entity_total_hp(*tr.state.entity(2));const int normal_d=hp-entity_total_hp(*sim.apply(normal,*nh,0.5).state.entity(2));CHECK(rooted_d<normal_d);
    }

    // Numeric passive pack from the supplied creature catalog.
    {
        BattleState base=fixture();auto*a=base.entity(1);auto*t=base.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->speed=8;a->anchor={1,1};t->anchor={5,1};t->retaliation_available=false;
        auto acts=sim.legal_actions(base);auto moved=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&x.destination;});CHECK(moved!=acts.end());const int hp=entity_total_hp(*t);const int plain=hp-entity_total_hp(*sim.apply(base,*moved,0.5).state.entity(2));
        BattleState agile=base;add_tag(*agile.entity(1),"agilesteed");auto aa=sim.legal_actions(agile);auto ah=std::find_if(aa.begin(),aa.end(),[&](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&x.destination==moved->destination;});const int agile_d=hp-entity_total_hp(*sim.apply(agile,*ah,0.5).state.entity(2));CHECK(agile_d<plain);
        BattleState blind=base;add_tag(*blind.entity(1),"blindingcharge");auto ba=sim.legal_actions(blind);auto bh=std::find_if(ba.begin(),ba.end(),[&](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&x.destination==moved->destination;});const int blind_d=hp-entity_total_hp(*sim.apply(blind,*bh,0.5).state.entity(2));CHECK(blind_d>plain);
        BattleState brittle=base;add_tag(*brittle.entity(2),"brittle");auto bra=sim.legal_actions(brittle);auto brh=std::find_if(bra.begin(),bra.end(),[&](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&x.destination==moved->destination;});CHECK(hp-entity_total_hp(*sim.apply(brittle,*brh,0.5).state.entity(2))>plain);
        for(const char* code:{"deadflesh","lifeguardmembrane","pleasureinpain","raptureinagony"}){BattleState r=base;add_tag(*r.entity(2),code);auto ra=sim.legal_actions(r);auto rh=std::find_if(ra.begin(),ra.end(),[&](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&x.destination==moved->destination;});CHECK(hp-entity_total_hp(*sim.apply(r,*rh,0.5).state.entity(2))<plain);}
    }

    // Fire Attack is an elemental side component: +5 fire damage per creature,
    // reduced by fire resistance and not folded into physical damage.
    {
        BattleState s=fixture();auto*a=s.entity(1);auto*t=s.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};t->retaliation_available=false;a->count=5;a->max_count=5;
        auto acts=sim.legal_actions(s);auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=acts.end());const int hp=entity_total_hp(*t);const int plain=hp-entity_total_hp(*sim.apply(s,*hit,0.5).state.entity(2));
        BattleState fire=s;add_tag(*fire.entity(1),"fireattack");auto fa=sim.legal_actions(fire);auto fh=std::find_if(fa.begin(),fa.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});const int fd=hp-entity_total_hp(*sim.apply(fire,*fh,0.5).state.entity(2));CHECK(fd>=plain+24);
        BattleState skin=fire;add_tag(*skin.entity(2),"fireprskin");auto sa=sim.legal_actions(skin);auto sh=std::find_if(sa.begin(),sa.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});const int sd=hp-entity_total_hp(*sim.apply(skin,*sh,0.5).state.entity(2));CHECK(sd<fd);
    }

    // Attentive overrides an attacker's no-retaliation flag; Blinding Charge suppresses
    // retaliation only when the attacker actually moved before the hit.
    {
        BattleState s=fixture();auto*a=s.entity(1);auto*t=s.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};t->retaliation_available=true;a->no_retaliation=true;add_tag(*t,"attentive");
        auto acts=sim.legal_actions(s);auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=acts.end());const int hp=entity_total_hp(*a);auto tr=sim.apply(s,*hit,0.5);CHECK(tr.valid);CHECK(entity_total_hp(*tr.state.entity(1))<hp);
        BattleState c=fixture();auto*ca=c.entity(1);auto*ct=c.entity(2);CHECK(ca&&ct);ca->is_shooter=false;ca->shots=0;ca->speed=8;ca->anchor={1,1};ct->anchor={5,1};ct->retaliation_available=true;add_tag(*ca,"blindingcharge");auto cas=sim.legal_actions(c);auto ch=std::find_if(cas.begin(),cas.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&x.destination;});CHECK(ch!=cas.end());const int chp=entity_total_hp(*ca);auto ctr=sim.apply(c,*ch,0.5);CHECK(ctr.valid);CHECK(entity_total_hp(*ctr.state.entity(1))==chp);
    }

    // Fierce retaliation doubles retaliation damage.
    {
        BattleState s=fixture();auto*a=s.entity(1);auto*t=s.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};t->retaliation_available=true;auto acts=sim.legal_actions(s);auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=acts.end());const int hp=entity_total_hp(*a);const int normal=hp-entity_total_hp(*sim.apply(s,*hit,0.5).state.entity(1));BattleState f=s;add_tag(*f.entity(2),"fierceretaliation");auto fa=sim.legal_actions(f);auto fh=std::find_if(fa.begin(),fa.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});const int fierce=hp-entity_total_hp(*sim.apply(f,*fh,0.5).state.entity(1));CHECK(fierce>normal*1.7);
    }

    // Ignore-defence and ignore-attack are not cosmetic: they alter physical damage.
    {
        BattleState s=fixture();auto* a=s.entity(1);auto* t=s.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};a->attack=10;t->defense=40;t->retaliation_available=false;
        auto acts=sim.legal_actions(s);auto it=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(it!=acts.end());int hp=entity_total_hp(*t);auto normal=sim.apply(s,*it,0.5);int dn=hp-entity_total_hp(*normal.state.entity(2));
        BattleState pen=s;add_tag(*pen.entity(1),"ignoredefence40");auto pa=sim.legal_actions(pen);auto ph=std::find_if(pa.begin(),pa.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});auto ptr=sim.apply(pen,*ph,0.5);int dp=hp-entity_total_hp(*ptr.state.entity(2));CHECK(dp>dn);
        BattleState resist=s;add_tag(*resist.entity(2),"ignoreattack40");auto ra=sim.legal_actions(resist);auto rh=std::find_if(ra.begin(),ra.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});auto rtr=sim.apply(resist,*rh,0.5);int dr=hp-entity_total_hp(*rtr.state.entity(2));CHECK(dr<dn);
    }

    // Blood Frenzy is conditional exact damage: +30% only while Ferocious Wound is active.
    {
        BattleState base=fixture();auto*a=base.entity(1);auto*t=base.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};t->retaliation_available=false;
        auto acts=sim.legal_actions(base);auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=acts.end());const int hp=entity_total_hp(*t);const int plain=hp-entity_total_hp(*sim.apply(base,*hit,0.5).state.entity(2));
        BattleState frenzy=base;add_tag(*frenzy.entity(1),"bloodfrenzy");frenzy.entity(2)->effects.push_back({status_effect_id("proc_ferocious_speed"),2,1.0f,"test"});auto fa=sim.legal_actions(frenzy);auto fh=std::find_if(fa.begin(),fa.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(fh!=fa.end());const int boosted=hp-entity_total_hp(*sim.apply(frenzy,*fh,0.5).state.entity(2));CHECK(boosted>plain*1.20);
    }

    // Shield Other is a positional ranged aura. One adjacent guard reduces ranged damage
    // by 25%; Big Shield on the target supersedes it so the aura does not stack again.
    {
        BattleState base=fixture();auto*a=base.entity(1);auto*t=base.entity(2);CHECK(a&&t);a->anchor={1,1};a->shots=4;a->no_range_penalty=true;t->anchor={6,1};
        auto acts=sim.legal_actions(base);auto shot=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::RangedAttack&&x.target_uid&&*x.target_uid==2;});CHECK(shot!=acts.end());const int hp=entity_total_hp(*t);const int plain=hp-entity_total_hp(*sim.apply(base,*shot,0.5).state.entity(2));
        BattleState guarded=base;Entity guard=*guarded.entity(2);guard.uid=3;guard.anchor={6,2};guard.side=Side::Pve;guard.ability_ids.clear();add_tag(guard,"shieldother");guarded.entities.push_back(guard);auto ga=sim.legal_actions(guarded);auto gh=std::find_if(ga.begin(),ga.end(),[](const Action&x){return x.type==ActionType::RangedAttack&&x.target_uid&&*x.target_uid==2;});CHECK(gh!=ga.end());const int reduced=hp-entity_total_hp(*sim.apply(guarded,*gh,0.5).state.entity(2));CHECK(reduced<plain*0.85&&reduced>plain*0.65);
        BattleState bigshield=guarded;add_tag(*bigshield.entity(2),"lshield");auto ba=sim.legal_actions(bigshield);auto bh=std::find_if(ba.begin(),ba.end(),[](const Action&x){return x.type==ActionType::RangedAttack&&x.target_uid&&*x.target_uid==2;});CHECK(bh!=ba.end());const int with_guard=hp-entity_total_hp(*sim.apply(bigshield,*bh,0.5).state.entity(2));BattleState alone=base;add_tag(*alone.entity(2),"lshield");auto aa=sim.legal_actions(alone);auto ah=std::find_if(aa.begin(),aa.end(),[](const Action&x){return x.type==ActionType::RangedAttack&&x.target_uid&&*x.target_uid==2;});CHECK(ah!=aa.end());const int no_guard=hp-entity_total_hp(*sim.apply(alone,*ah,0.5).state.entity(2));CHECK(std::abs(with_guard-no_guard)<=1);
    }

    // Permanent ranged penalty and Diamond armor stack multiplicatively.
    {
        BattleState s=fixture();auto* a=s.entity(1);auto* t=s.entity(2);CHECK(a&&t);a->anchor={1,1};t->anchor={4,1};a->shots=4;a->no_range_penalty=true;
        auto acts=sim.legal_actions(s);auto it=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::RangedAttack&&x.target_uid&&*x.target_uid==2;});CHECK(it!=acts.end());int hp=entity_total_hp(*t);auto normal=sim.apply(s,*it,0.5);int dn=hp-entity_total_hp(*normal.state.entity(2));
        BattleState rp=s;add_tag(*rp.entity(1),"rangepenalty");auto rpa=sim.legal_actions(rp);auto rph=std::find_if(rpa.begin(),rpa.end(),[](const Action&x){return x.type==ActionType::RangedAttack&&x.target_uid&&*x.target_uid==2;});auto rptr=sim.apply(rp,*rph,0.5);int dr=hp-entity_total_hp(*rptr.state.entity(2));CHECK(dr<dn*0.7);
        BattleState dia=s;add_tag(*dia.entity(2),"diamondarmor");auto diaa=sim.legal_actions(dia);auto diah=std::find_if(diaa.begin(),diaa.end(),[](const Action&x){return x.type==ActionType::RangedAttack&&x.target_uid&&*x.target_uid==2;});auto diatr=sim.apply(dia,*diah,0.5);int dd=hp-entity_total_hp(*diatr.state.entity(2));CHECK(dd<dn*0.25);
    }

    // Reliable position and Shield wall use the actual pre-hit movement distance.
    {
        BattleState s=fixture();auto*a=s.entity(1);auto*t=s.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->speed=5;a->anchor={1,1};t->anchor={2,1};t->retaliation_available=false;
        auto acts=sim.legal_actions(s);auto stationary=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(stationary!=acts.end());int hp=entity_total_hp(*t);auto normal=sim.apply(s,*stationary,0.5);int dn=hp-entity_total_hp(*normal.state.entity(2));
        BattleState safe=s;add_tag(*safe.entity(1),"safeposition");auto sa=sim.legal_actions(safe);auto sh=std::find_if(sa.begin(),sa.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});auto str=sim.apply(safe,*sh,0.5);int ds=hp-entity_total_hp(*str.state.entity(2));CHECK(ds>dn*1.35);

        BattleState wall=fixture();auto*wa=wall.entity(1);auto*wt=wall.entity(2);CHECK(wa&&wt);wa->is_shooter=false;wa->shots=0;wa->speed=6;wa->anchor={1,1};wt->anchor={5,1};wt->retaliation_available=false;add_tag(*wt,"shieldwall");
        auto wacts=sim.legal_actions(wall);auto moved=std::find_if(wacts.begin(),wacts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&x.destination.has_value();});CHECK(moved!=wacts.end());int whp=entity_total_hp(*wt);auto wtr=sim.apply(wall,*moved,0.5);int wd=whp-entity_total_hp(*wtr.state.entity(2));
        BattleState no_wall=wall;no_wall.entity(2)->ability_ids.clear();auto nwacts=sim.legal_actions(no_wall);auto nwm=std::find_if(nwacts.begin(),nwacts.end(),[&](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&x.destination==moved->destination;});CHECK(nwm!=nwacts.end());auto nwtr=sim.apply(no_wall,*nwm,0.5);int nwd=whp-entity_total_hp(*nwtr.state.entity(2));CHECK(wd<nwd);
    }

    // Weakening Strike applies after primary damage and before retaliation; Armoured blocks only Defence loss.
    {
        BattleState s=fixture();auto*a=s.entity(1);auto*t=s.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};a->attack=20;t->attack=20;t->defense=20;t->retaliation_available=false;add_tag(*a,"weakeningstrike");
        auto acts=sim.legal_actions(s);auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=acts.end());auto tr=sim.apply(s,*hit,0.5);CHECK(tr.valid);CHECK(tr.state.entity(2)->attack==16);CHECK(tr.state.entity(2)->defense==16);
        BattleState arm=s;add_tag(*arm.entity(2),"armoured");auto aa=sim.legal_actions(arm);auto ah=std::find_if(aa.begin(),aa.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});auto atr=sim.apply(arm,*ah,0.5);CHECK(atr.state.entity(2)->attack==16);CHECK(atr.state.entity(2)->defense==20);
        BattleState organic=s;add_tag(*organic.entity(2),"organicarmor");auto oa=sim.legal_actions(organic);auto oh=std::find_if(oa.begin(),oa.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});auto otr=sim.apply(organic,*oh,0.5);CHECK(otr.state.entity(2)->attack==16);CHECK(otr.state.entity(2)->defense==20);
    }

    // Death Strike guarantees at least one unit kill below the 400-HP threshold.
    {
        BattleState s=fixture();auto*a=s.entity(1);auto*t=s.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};a->count=1;a->min_damage=a->max_damage=1;a->attack=0;t->defense=100;t->max_hp_per_unit=399;t->max_count=3;t->count=3;t->top_unit_hp=399;t->retaliation_available=false;add_tag(*a,"deathstrike");
        auto acts=sim.legal_actions(s);auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=acts.end());auto tr=sim.apply(s,*hit,0.5);CHECK(tr.valid);CHECK(tr.state.entity(2)->count<=2);
        BattleState immune=s;immune.entity(2)->max_hp_per_unit=400;immune.entity(2)->top_unit_hp=400;auto ia=sim.legal_actions(immune);auto ih=std::find_if(ia.begin(),ia.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});auto itr=sim.apply(immune,*ih,0.5);CHECK(itr.state.entity(2)->count==3);
    }

    // Fire Shield reflects 20% of actual melee damage; fire-immune attackers take none.
    {
        BattleState s=fixture();auto*a=s.entity(1);auto*t=s.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};t->retaliation_available=false;add_tag(*t,"fireshield");int ahp=entity_total_hp(*a);
        auto acts=sim.legal_actions(s);auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=acts.end());auto tr=sim.apply(s,*hit,0.5);CHECK(tr.valid);CHECK(entity_total_hp(*tr.state.entity(1))<ahp);
        BattleState fire=s;add_tag(*fire.entity(1),"ifire");auto fa=sim.legal_actions(fire);auto fh=std::find_if(fa.begin(),fa.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});auto ftr=sim.apply(fire,*fh,0.5);CHECK(entity_total_hp(*ftr.state.entity(1))==ahp);
    }

    // Lizard Bite is an assist attack from a different allied stack adjacent to
    // the primary melee target. It deals half ordinary damage and never redirects
    // retaliation to the helper.
    {
        BattleState base=fixture();auto*a=base.entity(1);auto*t=base.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};t->retaliation_available=false;
        auto acts=sim.legal_actions(base);auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=acts.end());const int hp=entity_total_hp(*t);const int plain=hp-entity_total_hp(*sim.apply(base,*hit,0.5).state.entity(2));
        BattleState assist=base;Entity liz=*assist.entity(1);liz.uid=3;liz.anchor={2,2};liz.side=Side::Player;liz.owner=1;liz.is_shooter=false;liz.shots=0;liz.ability_ids.clear();add_tag(liz,"lizardbite");assist.entities.push_back(liz);auto aa=sim.legal_actions(assist);auto ah=std::find_if(aa.begin(),aa.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(ah!=aa.end());const int helper_hp=entity_total_hp(*assist.entity(3));auto atr=sim.apply(assist,*ah,0.5);CHECK(atr.valid);const int combined=hp-entity_total_hp(*atr.state.entity(2));CHECK(combined>plain);CHECK(entity_total_hp(*atr.state.entity(3))==helper_hp);
    }

    // Predator Reflexes (`concentration`) is a true pre-emptive retaliation: it
    // strikes before the attacker and works even against no-retaliation attackers.
    {
        BattleState plain=fixture();auto*a=plain.entity(1);auto*t=plain.entity(2);CHECK(a&&t);
        a->is_shooter=false;a->shots=0;a->anchor={1,1};a->count=1;a->max_count=1;a->max_hp_per_unit=5;a->top_unit_hp=5;a->min_damage=a->max_damage=50;a->attack=100;a->no_retaliation=true;
        t->anchor={2,1};t->count=8;t->min_damage=t->max_damage=10;t->attack=30;t->retaliation_available=true;
        auto pa=sim.legal_actions(plain);auto ph=std::find_if(pa.begin(),pa.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(ph!=pa.end());const int target_hp=entity_total_hp(*t);auto ptr=sim.apply(plain,*ph,0.5);CHECK(ptr.valid);CHECK(entity_total_hp(*ptr.state.entity(2))<target_hp);CHECK(ptr.state.entity(1)->alive);
        BattleState reflex=plain;add_tag(*reflex.entity(2),"concentration");auto ra=sim.legal_actions(reflex);auto rh=std::find_if(ra.begin(),ra.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(rh!=ra.end());auto rtr=sim.apply(reflex,*rh,0.5);CHECK(rtr.valid);CHECK(!rtr.state.entity(1)->alive);CHECK(entity_total_hp(*rtr.state.entity(2))==target_hp);
    }

    // Incorporeal is a stochastic physical miss, not a 0.5 average-damage multiplier.
    // A miss can still provoke retaliation, exactly as observed in the raw corpus.
    {
        BattleState s=fixture();auto*a=s.entity(1);auto*t=s.entity(2);CHECK(a&&t);a->is_shooter=false;a->shots=0;a->anchor={1,1};t->anchor={2,1};t->retaliation_available=true;add_tag(*t,"incorporeal");
        auto acts=sim.legal_actions(s);auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=acts.end());
        bool saw_hit=false,saw_miss=false,saw_retaliation_on_miss=false;int target_hp=entity_total_hp(*t),actor_hp=entity_total_hp(*a);
        for(int i=0;i<=20;++i){auto tr=sim.apply(s,*hit,i/20.0);CHECK(tr.valid);int td=target_hp-entity_total_hp(*tr.state.entity(2));int ad=actor_hp-entity_total_hp(*tr.state.entity(1));if(td>0)saw_hit=true;else{saw_miss=true;if(ad>0)saw_retaliation_on_miss=true;}}
        CHECK(saw_hit&&saw_miss&&saw_retaliation_on_miss);
    }
    return true;
}


static bool test_observed_stoning_and_crippling_lifecycle() {
    ProtocolDecoder dec;
    BattleState s=fixture();
    auto* actor=s.entity(1); auto* target=s.entity(2); CHECK(actor&&target);
    actor->is_shooter=false; actor->shots=0; actor->ability_ids.push_back(stable_ability_id("stoning"));
    s.active_entity_uid=1; s.side_to_act=Side::Player;
    auto stone=dec.decode_update(s,"t=000turns=>1:Ssta001002000000098i0010100C002000000");
    CHECK(stone.state.semantic_unresolved_records==0);
    CHECK(effect_magnitude(*stone.state.entity(2),"proc_stone")>0.0f);
    GenericSimulator sim; auto blocked=sim.legal_actions(stone.state);
    CHECK(blocked.size()==1 && blocked[0].type==ActionType::Wait);
    auto after=dec.decode_update(stone.state,"t=000turns=>2:i0020100C001000000");
    CHECK(effect_magnitude(*after.state.entity(2),"proc_stone")==0.0f);

    BattleState c=fixture();
    auto* ca=c.entity(1); auto* ct=c.entity(2); CHECK(ca&&ct);
    ca->is_shooter=false; ca->shots=0; ca->ability_ids.push_back(stable_ability_id("cripplingwound"));
    c.active_entity_uid=1; c.side_to_act=Side::Player;
    const float base_speed=ct->speed, base_init=ct->initiative;
    auto wound=dec.decode_update(c,"t=000turns=>1:Swnd001002000000000i0010100C002000000");
    CHECK(wound.state.semantic_unresolved_records==0);
    CHECK(std::abs(effective_speed(*wound.state.entity(2))-base_speed*0.5f)<1e-5f);
    CHECK(std::abs(effective_initiative(*wound.state.entity(2))-base_init*0.7f)<1e-5f);
    auto one=dec.decode_update(wound.state,"t=000turns=>2:i0020100C001000000");
    CHECK(effect_magnitude(*one.state.entity(2),"proc_cripple")>0.0f);
    auto two=dec.decode_update(one.state,"t=000turns=>3:i0010100C002000000;>4:i0020100C001000000");
    CHECK(effect_magnitude(*two.state.entity(2),"proc_cripple")==0.0f);
    CHECK(std::abs(effective_speed(*two.state.entity(2))-base_speed)<1e-5f);
    CHECK(std::abs(effective_initiative(*two.state.entity(2))-base_init)<1e-5f);
    return true;
}




static bool test_entrenchment_lifecycle_and_resistance() {
    BattleState s=fixture(); auto* a=s.entity(1); CHECK(a); a->is_shooter=false;a->shots=0;add_tag(*a,"entrenchment");
    GenericSimulator sim; auto acts=sim.legal_actions(s);auto defend=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::Defend;});CHECK(defend!=acts.end());
    auto entrenched=sim.apply(s,*defend,0.5);CHECK(entrenched.valid);CHECK(effect_magnitude(*entrenched.state.entity(1),"proc_entrenchment")>0.0f);
    BattleState move_state=entrenched.state;move_state.active_entity_uid=1;move_state.side_to_act=Side::Player;auto moves=sim.legal_actions(move_state);auto mv=std::find_if(moves.begin(),moves.end(),[](const Action&x){return x.type==ActionType::Move&&x.destination;});CHECK(mv!=moves.end());auto moved=sim.apply(move_state,*mv,0.5);CHECK(moved.valid);CHECK(effect_magnitude(*moved.state.entity(1),"proc_entrenchment")==0.0f);

    BattleState base=fixture();auto* ba=base.entity(1);auto* bt=base.entity(2);CHECK(ba&&bt);ba->is_shooter=false;ba->shots=0;ba->anchor={1,1};bt->anchor={2,1};bt->retaliation_available=false;
    auto bacts=sim.legal_actions(base);auto hit=std::find_if(bacts.begin(),bacts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=bacts.end());const int hp=entity_total_hp(*bt);const int normal=hp-entity_total_hp(*sim.apply(base,*hit,0.5).state.entity(2));
    BattleState res=base;res.entity(2)->effects.push_back({status_effect_id("proc_entrenchment"),10000,0.5f,"test"});auto racts=sim.legal_actions(res);auto rh=std::find_if(racts.begin(),racts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});const int reduced=hp-entity_total_hp(*sim.apply(res,*rh,0.5).state.entity(2));CHECK(reduced<=normal/2+1);
    return true;
}

static bool test_pawstrike_modeled_proc_exact_consequence() {
    GenericSimulator sim;
    BattleState s=fixture();s.width=14;s.height=10;
    auto* actor=s.entity(1);auto* target=s.entity(2);CHECK(actor&&target);
    actor->owner=1;actor->side=Side::Player;actor->is_shooter=false;actor->shots=0;
    actor->anchor={1,1};actor->speed=12;actor->count=10;actor->max_count=10;
    actor->min_damage=actor->max_damage=2;actor->attack=8;actor->ability_ids.push_back(stable_ability_id("pawstrike"));
    target->owner=2;target->side=Side::Pve;target->is_shooter=false;target->shots=0;
    target->anchor={12,1};target->count=20;target->max_count=20;target->max_hp_per_unit=50;target->top_unit_hp=50;
    target->min_damage=target->max_damage=8;target->attack=10;target->retaliation_available=true;target->atb=5000;

    auto acts=sim.legal_actions(s);
    auto charge=std::find_if(acts.begin(),acts.end(),[](const Action&a){
        return a.type==ActionType::MeleeAttack&&a.target_uid&&*a.target_uid==2&&a.destination&&*a.destination==Cell{11,1};
    });
    CHECK(charge!=acts.end()); // moved_cells=10 => modeled p=1.0
    const int actor_hp=entity_total_hp(*actor);
    auto open=sim.apply(s,*charge,0.37);CHECK(open.valid);
    CHECK(open.state.entity(2)->atb==0.0f);
    const Cell expected_open_push{13,1};CHECK(open.state.entity(2)->anchor==expected_open_push);
    CHECK(entity_total_hp(*open.state.entity(1))==actor_hp); // pushed out of retaliation adjacency

    BattleState blocked=s;Entity wall=*target;wall.uid=3;wall.anchor={13,1};wall.owner=2;wall.side=Side::Pve;
    blocked.entities.push_back(wall);
    auto bacts=sim.legal_actions(blocked);
    auto bcharge=std::find_if(bacts.begin(),bacts.end(),[](const Action&a){return a.type==ActionType::MeleeAttack&&a.target_uid&&*a.target_uid==2&&a.destination&&*a.destination==Cell{11,1};});
    CHECK(bcharge!=bacts.end());
    auto stuck=sim.apply(blocked,*bcharge,0.37);CHECK(stuck.valid);
    CHECK(stuck.state.entity(2)->atb==0.0f);const Cell expected_blocked_anchor{12,1};CHECK(stuck.state.entity(2)->anchor==expected_blocked_anchor);
    CHECK(entity_total_hp(*stuck.state.entity(1))<actor_hp); // still adjacent: normal retaliation remains possible

    BattleState stationary=s;stationary.entity(1)->anchor={11,1};stationary.entity(1)->speed=1;stationary.entity(2)->anchor={12,1};stationary.entity(2)->atb=4321;
    auto sacts=sim.legal_actions(stationary);auto hit=std::find_if(sacts.begin(),sacts.end(),[](const Action&a){return a.type==ActionType::MeleeAttack&&a.target_uid&&*a.target_uid==2&&!a.destination;});CHECK(hit!=sacts.end());
    auto nocharge=sim.apply(stationary,*hit,0.0);CHECK(nocharge.valid);CHECK(nocharge.state.entity(2)->atb==4321);

    BattleState p=fixture();auto*pa=p.entity(1);auto*pt=p.entity(2);CHECK(pa&&pt);pa->owner=1;pt->owner=2;pa->ability_ids.push_back(stable_ability_id("pawstrike"));pt->atb=7777;p.active_entity_uid=1;
    ProtocolDecoder decoder;auto decoded=decoder.decode_update(p,"t=000turns=>1:I0020001i0010100C002000000");
    CHECK(decoded.state.entity(2)->atb==0.0f);CHECK(decoded.state.semantic_unresolved_records==0);
    CHECK(std::any_of(decoded.events.begin(),decoded.events.end(),[](const BattleEvent&e){return e.type=="PAW_STRIKE_ATB_RESET"&&e.actor_uid==1&&e.target_uid==2;}));
    return true;
}


static bool test_mighty_slam_exact_action_splash_knockback_cooldown() {
    GenericSimulator sim;
    BattleState s=fixture(); auto* actor=s.entity(1); auto* primary=s.entity(2); CHECK(actor&&primary);
    actor->owner=1;actor->side=Side::Player;actor->anchor={1,1};actor->count=8;actor->max_count=8;
    actor->max_hp_per_unit=100;actor->top_unit_hp=100;actor->attack=25;actor->min_damage=actor->max_damage=10;
    actor->ability_ids.push_back(stable_ability_id("mightyslam"));
    primary->owner=2;primary->side=Side::Pve;primary->anchor={2,1};primary->count=20;primary->max_count=20;
    primary->max_hp_per_unit=50;primary->top_unit_hp=50;primary->retaliation_available=true;primary->min_damage=primary->max_damage=100;
    Entity secondary=*primary;secondary.uid=3;secondary.anchor={2,2};secondary.count=20;secondary.max_count=20;secondary.top_unit_hp=50;
    Entity friendly=secondary;friendly.uid=4;friendly.owner=1;friendly.side=Side::Player;friendly.anchor={1,2};
    Entity far=secondary;far.uid=5;far.anchor={8,8};
    Entity big=secondary;big.uid=6;big.anchor={3,2};big.is_big=true;big.footprint_w=2;big.footprint_h=1;
    s.entities.push_back(secondary);s.entities.push_back(friendly);s.entities.push_back(far);s.entities.push_back(big);
    actor=s.entity(1);primary=s.entity(2);CHECK(actor&&primary);

    auto acts=sim.legal_actions(s);
    auto slam=std::find_if(acts.begin(),acts.end(),[](const Action&a){return a.type==ActionType::Ability&&a.target_uid&&*a.target_uid==2&&a.ability_id&&*a.ability_id==stable_ability_id("msl")&&!a.destination;});
    CHECK(slam!=acts.end());
    const int actor_hp=entity_total_hp(*actor), p_hp=entity_total_hp(*primary), sec_hp=entity_total_hp(*s.entity(3));
    const int friend_hp=entity_total_hp(*s.entity(4)), far_hp=entity_total_hp(*s.entity(5)), big_hp=entity_total_hp(*s.entity(6));
    const Cell p0=primary->anchor, sec0=s.entity(3)->anchor, big0=s.entity(6)->anchor;
    auto tr=sim.apply(s,*slam,0.5); CHECK(tr.valid); CHECK(tr.warning=="exact_mighty_slam");
    CHECK(entity_total_hp(*tr.state.entity(2))<p_hp); CHECK(entity_total_hp(*tr.state.entity(3))<sec_hp);
    CHECK(entity_total_hp(*tr.state.entity(4))==friend_hp); CHECK(entity_total_hp(*tr.state.entity(5))==far_hp);
    CHECK(entity_total_hp(*tr.state.entity(6))<big_hp); // adjacent enemy big stack is splashed
    CHECK(entity_total_hp(*tr.state.entity(1))==actor_hp); // no ordinary retaliation
    CHECK(tr.state.entity(2)->anchor!=p0); CHECK(tr.state.entity(3)->anchor!=sec0);
    CHECK(tr.state.entity(6)->anchor==big0); // big creature never knocked back
    CHECK(effect_magnitude(*tr.state.entity(1),"msl")>0.0f);

    BattleState cd=tr.state;cd.active_entity_uid=1;cd.side_to_act=Side::Player;
    auto blocked1=sim.legal_actions(cd);CHECK(std::none_of(blocked1.begin(),blocked1.end(),[](const Action&a){return a.ability_id&&*a.ability_id==stable_ability_id("msl");}));
    auto w1=std::find_if(blocked1.begin(),blocked1.end(),[](const Action&a){return a.type==ActionType::Wait;});CHECK(w1!=blocked1.end());
    auto t1=sim.apply(cd,*w1,0.5);CHECK(t1.valid);t1.state.active_entity_uid=1;t1.state.side_to_act=Side::Player;
    auto blocked2=sim.legal_actions(t1.state);CHECK(std::none_of(blocked2.begin(),blocked2.end(),[](const Action&a){return a.ability_id&&*a.ability_id==stable_ability_id("msl");}));
    auto w2=std::find_if(blocked2.begin(),blocked2.end(),[](const Action&a){return a.type==ActionType::Wait;});CHECK(w2!=blocked2.end());
    auto t2=sim.apply(t1.state,*w2,0.5);CHECK(t2.valid);t2.state.active_entity_uid=1;t2.state.side_to_act=Side::Player;
    auto ready=sim.legal_actions(t2.state);CHECK(std::any_of(ready.begin(),ready.end(),[](const Action&a){return a.ability_id&&*a.ability_id==stable_ability_id("msl");}));

    // Observed protocol marker becomes semantic-safe and stores the same cooldown.
    BattleState p=s;p.stream_contiguous=false;p.protocol_ready=false;p.recommendation_safe=false;p.active_entity_uid=1;
    ProtocolDecoder decoder;
    auto decoded=decoder.decode_update(p,"t=000turns=>1:C001000000Smsl001000000000000d0010020000000010i0010100C002000000");
    CHECK(std::any_of(decoded.events.begin(),decoded.events.end(),[](const BattleEvent&e){return e.type=="MIGHTY_SLAM"&&e.actor_uid==1;}));
    CHECK(effect_magnitude(*decoded.state.entity(1),"msl")>0.0f);CHECK(decoded.state.semantic_unresolved_records==0);
    return true;
}


static bool test_mana_feed_exact_action_and_protocol() {
    GenericSimulator sim;
    BattleState s=fixture(); auto* actor=s.entity(1); CHECK(actor);
    actor->owner=1; actor->count=5; actor->max_count=20; actor->mana=15;
    actor->ability_ids.push_back(stable_ability_id("manafeed"));
    Entity hero; hero.uid=3; hero.owner=1; hero.side=Side::Player; hero.is_hero=true; hero.alive=true; hero.mana=10;
    Entity enemy_hero=hero; enemy_hero.uid=4; enemy_hero.owner=2; enemy_hero.side=Side::Pve; enemy_hero.mana=7;
    s.entities.push_back(hero); s.entities.push_back(enemy_hero);

    auto acts=sim.legal_actions(s);
    auto feed=std::find_if(acts.begin(),acts.end(),[](const Action&a){
        return a.type==ActionType::Ability&&a.target_uid&&*a.target_uid==3&&a.ability_id&&*a.ability_id==stable_ability_id("mfd");
    });
    CHECK(feed!=acts.end());
    CHECK(std::none_of(acts.begin(),acts.end(),[](const Action&a){return a.type==ActionType::Ability&&a.target_uid&&*a.target_uid==4&&a.ability_id&&*a.ability_id==stable_ability_id("mfd");}));
    auto tr=sim.apply(s,*feed,0.5); CHECK(tr.valid); CHECK(tr.warning=="exact_mana_feed");
    CHECK(tr.state.entity(1)->mana==10); CHECK(tr.state.entity(3)->mana==15); CHECK(tr.state.entity(4)->mana==7);

    BattleState limited=s; limited.entity(1)->count=20; limited.entity(1)->mana=3;
    auto limited_acts=sim.legal_actions(limited);
    auto limited_feed=std::find_if(limited_acts.begin(),limited_acts.end(),[](const Action&a){return a.type==ActionType::Ability&&a.target_uid&&*a.target_uid==3&&a.ability_id&&*a.ability_id==stable_ability_id("mfd");});
    CHECK(limited_feed!=limited_acts.end());
    auto limited_tr=sim.apply(limited,*limited_feed,0.5); CHECK(limited_tr.valid);
    CHECK(limited_tr.state.entity(1)->mana==0); CHECK(limited_tr.state.entity(3)->mana==13);
    BattleState empty=limited; empty.entity(1)->mana=0;
    const auto empty_acts=sim.legal_actions(empty);
    CHECK(std::none_of(empty_acts.begin(),empty_acts.end(),[](const Action&a){return a.type==ActionType::Ability&&a.ability_id&&*a.ability_id==stable_ability_id("mfd");}));

    // Live protocol decoder must apply the same exact transition and clear semantic risk.
    BattleState p=s; p.halfturn=0; p.stream_contiguous=false; p.protocol_ready=false; p.recommendation_safe=false;
    p.entity(1)->mana=15; p.entity(1)->count=5; p.entity(3)->mana=10; p.active_entity_uid=0;
    ProtocolDecoder decoder;
    auto decoded=decoder.decode_update(p,"t=000turns=>1:C001000000Smfd001003050000000i0010100C002000000");
    CHECK(decoded.state.entity(1)->mana==10); CHECK(decoded.state.entity(3)->mana==15);
    CHECK(std::any_of(decoded.events.begin(),decoded.events.end(),[](const BattleEvent&e){return e.type=="MANA_FEED"&&e.actor_uid==1&&e.target_uid==3;}));
    CHECK(decoded.state.semantic_unresolved_records==0); CHECK(decoded.state.recommendation_safe);
    return true;
}


static bool test_mana_drain_and_reference_damage_perks() {
    BattleState s=fixture();
    auto* a=s.entity(1); auto* t=s.entity(2); CHECK(a&&t);
    a->owner=1; a->is_shooter=false; a->shots=0; a->anchor={1,1};
    a->max_count=10; a->count=5; a->max_hp_per_unit=20; a->top_unit_hp=10;
    a->min_damage=a->max_damage=5; a->attack=20; add_tag(*a,"manadrain");
    t->owner=2; t->anchor={2,1}; t->mana=3; t->retaliation_available=false; add_tag(*t,"caster");
    GenericSimulator sim; auto acts=sim.legal_actions(s);
    auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});CHECK(hit!=acts.end());
    auto tr=sim.apply(s,*hit,0.5); CHECK(tr.valid); CHECK(tr.state.entity(2)->mana==0);
    CHECK(entity_total_hp(*tr.state.entity(1))==150); // 90 + 3 full creatures * 20 HP

    BattleState j=s; auto* ja=j.entity(1); auto* jt=j.entity(2);CHECK(ja&&jt);
    ja->ability_ids.clear();add_tag(*ja,"jousting");ja->anchor={1,1};ja->speed=8;jt->anchor={5,1};jt->mana=0;jt->ability_ids.clear();jt->retaliation_available=false;
    auto jaa=sim.legal_actions(j);auto moved=std::find_if(jaa.begin(),jaa.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&x.destination;});CHECK(moved!=jaa.end());
    BattleState plain=j;plain.entity(1)->ability_ids.clear();auto pa=sim.legal_actions(plain);auto ph=std::find_if(pa.begin(),pa.end(),[&](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&x.destination==moved->destination;});CHECK(ph!=pa.end());
    const int hp=entity_total_hp(*jt);const int jd=hp-entity_total_hp(*sim.apply(j,*moved,0.5).state.entity(2));const int pd=hp-entity_total_hp(*sim.apply(plain,*ph,0.5).state.entity(2));CHECK(jd>pd);
    return true;
}


static bool test_battle_thirst_and_taste_of_blood_exact_state() {
    // Authoritative observed wire counters.
    BattleState observed=fixture();
    add_tag(*observed.entity(1),"battlethirst");
    add_tag(*observed.entity(2),"tasteofblood");
    ProtocolDecoder dec;
    auto upd=dec.decode_update(observed,
        "t=000turns=>1:Sbtt001004000000000Stob002007000000000i0010100C002000000");
    CHECK(upd.coverage.unknown_records==0);
    CHECK(upd.state.semantic_unresolved_records==0);
    CHECK(std::abs(effect_magnitude(*upd.state.entity(1),"btt")-4.0f)<1e-5f);
    CHECK(std::abs(effective_attack(*upd.state.entity(1))-14.0f)<1e-5f);
    CHECK(std::abs(effect_magnitude(*upd.state.entity(2),"tob")-5.0f)<1e-5f);
    CHECK(std::abs(effective_min_damage(*upd.state.entity(2))-7.0f)<1e-5f);

    // Speculative Battle Thirst lifecycle: non-attack +2, attack reset.
    GenericSimulator sim;
    BattleState thirst=fixture(); auto* a=thirst.entity(1); auto* t=thirst.entity(2); CHECK(a&&t);
    add_tag(*a,"battlethirst"); a->is_shooter=false; a->shots=0; a->anchor={1,1}; t->anchor={2,1}; t->retaliation_available=false;
    auto acts=sim.legal_actions(thirst);
    auto defend=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::Defend;});
    CHECK(defend!=acts.end());
    auto after_def=sim.apply(thirst,*defend,0.5); CHECK(after_def.valid);
    CHECK(std::abs(effect_magnitude(*after_def.state.entity(1),"btt")-2.0f)<1e-5f);
    after_def.state.active_entity_uid=1; after_def.state.side_to_act=Side::Player;
    auto attacks=sim.legal_actions(after_def.state);
    auto melee=std::find_if(attacks.begin(),attacks.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2;});
    CHECK(melee!=attacks.end());
    auto after_hit=sim.apply(after_def.state,*melee,0.5); CHECK(after_hit.valid);
    CHECK(effect_magnitude(*after_hit.state.entity(1),"btt")==0.0f);

    // Taste of Blood: every actual received damage event increases minimum damage by 1.
    BattleState taste=fixture(); auto* ta=taste.entity(1); auto* tt=taste.entity(2); CHECK(ta&&tt);
    ta->is_shooter=false; ta->shots=0; ta->anchor={1,1}; tt->anchor={2,1}; tt->retaliation_available=false;
    add_tag(*tt,"tasteofblood");
    const float min_before=effective_min_damage(*tt);
    auto taste_acts=sim.legal_actions(taste);
    auto taste_hit=std::find_if(taste_acts.begin(),taste_acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2;});
    CHECK(taste_hit!=taste_acts.end());
    auto taste_after=sim.apply(taste,*taste_hit,0.5); CHECK(taste_after.valid);
    CHECK(std::abs(effective_min_damage(*taste_after.state.entity(2))-(min_before+1.0f))<1e-5f);
    return true;
}

static bool test_regeneration_exact_turn_start_no_resurrection() {
    GenericSimulator sim;

    auto make_state=[](int top_hp,int count=3)->BattleState{
        BattleState s=fixture();
        auto* actor=s.entity(1); auto* regen=s.entity(2);
        if(!actor||!regen)return {};
        s.decision_seq=10;
        actor->last_acted_seq=9; actor->initiative=1; actor->atb=0;
        regen->max_count=20; regen->count=count; regen->max_hp_per_unit=125;
        regen->top_unit_hp=top_hp; regen->initiative=100; regen->atb=10000;
        regen->last_acted_seq=0; add_tag(*regen,"regeneration");
        return s;
    };

    auto apply_wait=[&](BattleState s,double roll)->Transition{
        auto acts=sim.legal_actions(s);
        auto it=std::find_if(acts.begin(),acts.end(),[](const Action&a){return a.type==ActionType::Wait;});
        if(it==acts.end()){Transition bad;bad.valid=false;bad.warning="wait_missing";return bad;}
        return sim.apply(s,*it,roll);
    };

    auto low=apply_wait(make_state(20),0.0); CHECK(low.valid); CHECK(!low.terminal); CHECK(low.state.active_entity_uid==2); CHECK(low.state.entity(2));
    CHECK(low.state.entity(2)->top_unit_hp==29);  // 3 HP * 3 creatures = +9
    CHECK(low.state.entity(2)->count==3);

    auto mid=apply_wait(make_state(20),0.5); CHECK(mid.valid); CHECK(!mid.terminal); CHECK(mid.state.active_entity_uid==2); CHECK(mid.state.entity(2));
    CHECK(mid.state.entity(2)->top_unit_hp==32);  // 4 HP * 3 creatures = +12
    CHECK(mid.state.entity(2)->count==3);

    auto high=apply_wait(make_state(20),1.0); CHECK(high.valid); CHECK(!high.terminal); CHECK(high.state.active_entity_uid==2); CHECK(high.state.entity(2));
    CHECK(high.state.entity(2)->top_unit_hp==35); // 5 HP * 3 creatures = +15
    CHECK(high.state.entity(2)->count==3);

    auto full_stack=apply_wait(make_state(20,10),1.0); CHECK(full_stack.valid); CHECK(full_stack.state.entity(2));
    CHECK(full_stack.state.entity(2)->top_unit_hp==70); // cap: 5 * min(10,10) = +50
    CHECK(full_stack.state.entity(2)->count==10);

    auto capped=apply_wait(make_state(120),1.0); CHECK(capped.valid); CHECK(!capped.terminal); CHECK(capped.state.active_entity_uid==2); CHECK(capped.state.entity(2));
    CHECK(capped.state.entity(2)->top_unit_hp==125);
    CHECK(capped.state.entity(2)->count==3); // no resurrection / count increase
    return true;
}


static bool test_life_drain_exact_heal_resurrection_and_retaliation() {
    GenericSimulator sim;

    // Primary attack: 50% of actually inflicted damage heals the attacker and may
    // resurrect previously lost creatures, but never beyond max_count.
    BattleState s=fixture(); auto* a=s.entity(1); auto* t=s.entity(2); CHECK(a&&t);
    a->owner=1; a->is_shooter=false; a->shots=0; a->anchor={1,1}; a->max_count=10;
    a->count=5; a->max_hp_per_unit=20; a->top_unit_hp=10; a->attack=30;
    a->min_damage=a->max_damage=8; add_tag(*a,"lifedrain");
    t->owner=2; t->anchor={2,1}; t->max_count=50; t->count=50;
    t->max_hp_per_unit=20; t->top_unit_hp=20; t->retaliation_available=false;
    auto acts=sim.legal_actions(s);
    auto hit=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});
    CHECK(hit!=acts.end());
    const int attacker_before=entity_total_hp(*a), target_before=entity_total_hp(*t);
    auto tr=sim.apply(s,*hit,0.5); CHECK(tr.valid);
    const int dealt=target_before-entity_total_hp(*tr.state.entity(2)); CHECK(dealt>0);
    CHECK(entity_total_hp(*tr.state.entity(1))==std::min(200,attacker_before+dealt/2));
    CHECK(tr.state.entity(1)->count>5);

    BattleState full=s; auto* fa=full.entity(1); CHECK(fa); fa->count=10; fa->top_unit_hp=20;
    auto facts=sim.legal_actions(full);
    auto fhit=std::find_if(facts.begin(),facts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});
    CHECK(fhit!=facts.end());
    auto capped=sim.apply(full,*fhit,0.5); CHECK(capped.valid);
    CHECK(entity_total_hp(*capped.state.entity(1))==200);

    // Retaliation uses the same rule. Compare against an otherwise identical branch
    // where retaliation is disabled to isolate target HP after the primary hit.
    BattleState r=fixture(); auto* ra=r.entity(1); auto* rt=r.entity(2); CHECK(ra&&rt);
    ra->is_shooter=false; ra->shots=0; ra->anchor={1,1}; ra->max_count=20; ra->count=20;
    ra->max_hp_per_unit=30; ra->top_unit_hp=30; ra->min_damage=ra->max_damage=1; ra->attack=1;
    rt->anchor={2,1}; rt->max_count=10; rt->count=5; rt->max_hp_per_unit=20; rt->top_unit_hp=10;
    rt->min_damage=rt->max_damage=10; rt->attack=30; rt->retaliation_available=true; add_tag(*rt,"lifedrain");
    auto racts=sim.legal_actions(r);
    auto rhit=std::find_if(racts.begin(),racts.end(),[](const Action&x){return x.type==ActionType::MeleeAttack&&x.target_uid&&*x.target_uid==2&&!x.destination;});
    CHECK(rhit!=racts.end());
    BattleState no_ret=r; no_ret.entity(2)->retaliation_available=false;
    auto primary_only=sim.apply(no_ret,*rhit,0.5); CHECK(primary_only.valid);
    const int target_after_primary=entity_total_hp(*primary_only.state.entity(2));
    const int retaliation_target_before=entity_total_hp(*r.entity(1));
    auto with_ret=sim.apply(r,*rhit,0.5); CHECK(with_ret.valid);
    const int retaliation_dealt=retaliation_target_before-entity_total_hp(*with_ret.state.entity(1));
    CHECK(retaliation_dealt>0);
    CHECK(entity_total_hp(*with_ret.state.entity(2))==std::min(200,target_after_primary+retaliation_dealt/2));
    return true;
}


static bool test_kill_trigger_enraged_gate() {
    const auto path=std::filesystem::temp_directory_path()/"hwm_kill_trigger_test.csv";
    {
        std::ofstream f(path);
        f << "ability_code,event,train_n,train_hits,train_probability,heldout_n,heldout_hits,heldout_probability,abs_drift,increment,enabled,train_delta_median,heldout_delta_median\n";
        f << "enraged,friendly_stack_death,1000,1000,1.0,200,200,1.0,0.0,1,1,1,1\n";
        f << "bloodlust,enemy_stack_death_by_our_side,1000,1000,1.0,200,200,1.0,0.0,1,0,1,1\n";
    }
    BattleState s=fixture();
    auto* actor=s.entity(1); auto* victim=s.entity(2); CHECK(actor&&victim);
    actor->owner=1; actor->is_shooter=true; actor->shots=3; actor->attack=100; actor->count=50; actor->min_damage=actor->max_damage=50;
    victim->owner=2; victim->count=1; victim->max_count=1; victim->max_hp_per_unit=10; victim->top_unit_hp=10; victim->anchor={5,1};
    Entity rage=*victim; rage.uid=3; rage.creature_id=999; rage.owner=2; rage.anchor={8,1}; rage.count=5; rage.max_count=5; rage.top_unit_hp=20; rage.max_hp_per_unit=20; rage.attack=7; rage.ability_ids.clear(); rage.ability_ids.push_back(stable_ability_id("enraged"));
    Entity blood=rage; blood.uid=4; blood.anchor={9,3}; blood.attack=9; blood.ability_ids.clear(); blood.ability_ids.push_back(stable_ability_id("bloodlust"));
    s.entities.push_back(rage); s.entities.push_back(blood);
    GenericSimulator sim; CHECK(sim.load_kill_trigger_model(path.string())); CHECK(sim.kill_trigger_model_loaded());
    const auto acts=sim.legal_actions(s); auto shot=std::find_if(acts.begin(),acts.end(),[](const Action&x){return x.type==ActionType::RangedAttack&&x.target_uid&&*x.target_uid==2;}); CHECK(shot!=acts.end());
    const float before_rage=effective_attack(*s.entity(3)); const float before_blood=effective_attack(*s.entity(4));
    auto tr=sim.apply(s,*shot,0.25); CHECK(tr.valid); CHECK(!tr.state.entity(2)->alive);
    CHECK(std::abs(effective_attack(*tr.state.entity(3))-(before_rage+1.0f))<1e-5f);
    CHECK(std::abs(effective_attack(*tr.state.entity(4))-before_blood)<1e-5f);
    std::filesystem::remove(path);
    return true;
}

int main() {
    if (!test_state_and_planner()) return EXIT_FAILURE;
    if (!test_decoder()) return EXIT_FAILURE;
    if (!test_contextual_move_markers()) return EXIT_FAILURE;
    if (!test_session_lifecycle()) return EXIT_FAILURE;
    if (!test_dynamic_geometry()) return EXIT_FAILURE;
    if (!test_statix_cell_overlay_validation()) return EXIT_FAILURE;
    if (!test_exact_shooter_flags()) return EXIT_FAILURE;
    if (!test_collateral_model_application()) return EXIT_FAILURE;
    if (!test_ability_registry_and_transfer_models()) return EXIT_FAILURE;
    if (!test_spell_immunity_targeting_and_dynamic_caster_risk()) return EXIT_FAILURE;
    if (!test_proc_model_stateful_mechanics()) return EXIT_FAILURE;
    if (!test_battle_thirst_and_taste_of_blood_exact_state()) return EXIT_FAILURE;
    if (!test_regeneration_exact_turn_start_no_resurrection()) return EXIT_FAILURE;
    if (!test_life_drain_exact_heal_resurrection_and_retaliation()) return EXIT_FAILURE;
    if (!test_kill_trigger_enraged_gate()) return EXIT_FAILURE;
    if (!test_pawstrike_modeled_proc_exact_consequence()) return EXIT_FAILURE;
    if (!test_mighty_slam_exact_action_splash_knockback_cooldown()) return EXIT_FAILURE;
    if (!test_mana_feed_exact_action_and_protocol()) return EXIT_FAILURE;
    if (!test_mana_drain_and_reference_damage_perks()) return EXIT_FAILURE;
    if (!test_entrenchment_lifecycle_and_resistance()) return EXIT_FAILURE;
    if (!test_observed_stoning_and_crippling_lifecycle()) return EXIT_FAILURE;
    if (!test_festering_aura_exact_position_effect()) return EXIT_FAILURE;
    if (!test_exact_reference_ability_mechanics()) return EXIT_FAILURE;
    if (!test_defend_and_ammo_core_mechanics()) return EXIT_FAILURE;
    if (!test_retaliation_cycle()) return EXIT_FAILURE;
    if (!test_protocol_defend_and_recovery()) return EXIT_FAILURE;
    if (!test_warmachine_never_retaliates()) return EXIT_FAILURE;
    if (!test_semantic_safety_and_state_hash()) return EXIT_FAILURE;
    if (!test_runtime_probe_status()) return EXIT_FAILURE;
    if (!test_policy_prior_defend_is_distinct()) return EXIT_FAILURE;
    if (!test_hero_direct_spell_path()) return EXIT_FAILURE;
    if (!test_hero_basic_attack_path()) return EXIT_FAILURE;
    if (!test_status_spellbook_and_effect_mechanics()) return EXIT_FAILURE;
    if (!test_special_damage_state_mutation()) return EXIT_FAILURE;
    if (!test_raise_dead_observed_path()) return EXIT_FAILURE;
    if (!test_phantom_forces_observed_exact()) return EXIT_FAILURE;
    if (!test_phantom_damage_dissipation()) return EXIT_FAILURE;
    if (!test_endurance_u_record_exact_speed_increment()) return EXIT_FAILURE;
    if (!test_rune_speed_exact_path()) return EXIT_FAILURE;
    if (!test_psc_damage_delta()) return EXIT_FAILURE;
    std::cout << "all tests passed\n";
    return EXIT_SUCCESS;
}
