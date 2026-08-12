#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <string>
#include <string_view>
#include <vector>

#define main hwm_tests_monolithic_main
#include "test_main.cpp"
#undef main

namespace {
struct TestCase {
    const char* name;
    bool (*run)();
};

const std::vector<TestCase>& test_cases() {
    static const std::vector<TestCase> tests = {
        {"test_state_and_planner", &test_state_and_planner},
        {"test_decoder", &test_decoder},
        {"test_contextual_move_markers", &test_contextual_move_markers},
        {"test_session_lifecycle", &test_session_lifecycle},
        {"test_dynamic_geometry", &test_dynamic_geometry},
        {"test_statix_cell_overlay_validation", &test_statix_cell_overlay_validation},
        {"test_exact_shooter_flags", &test_exact_shooter_flags},
        {"test_collateral_model_application", &test_collateral_model_application},
        {"test_ability_registry_and_transfer_models", &test_ability_registry_and_transfer_models},
        {"test_spell_immunity_targeting_and_dynamic_caster_risk", &test_spell_immunity_targeting_and_dynamic_caster_risk},
        {"test_proc_model_stateful_mechanics", &test_proc_model_stateful_mechanics},
        {"test_battle_thirst_and_taste_of_blood_exact_state", &test_battle_thirst_and_taste_of_blood_exact_state},
        {"test_regeneration_exact_turn_start_no_resurrection", &test_regeneration_exact_turn_start_no_resurrection},
        {"test_life_drain_exact_heal_resurrection_and_retaliation", &test_life_drain_exact_heal_resurrection_and_retaliation},
        {"test_kill_trigger_enraged_gate", &test_kill_trigger_enraged_gate},
        {"test_pawstrike_modeled_proc_exact_consequence", &test_pawstrike_modeled_proc_exact_consequence},
        {"test_mighty_slam_exact_action_splash_knockback_cooldown", &test_mighty_slam_exact_action_splash_knockback_cooldown},
        {"test_mana_feed_exact_action_and_protocol", &test_mana_feed_exact_action_and_protocol},
        {"test_mana_drain_and_reference_damage_perks", &test_mana_drain_and_reference_damage_perks},
        {"test_entrenchment_lifecycle_and_resistance", &test_entrenchment_lifecycle_and_resistance},
        {"test_observed_stoning_and_crippling_lifecycle", &test_observed_stoning_and_crippling_lifecycle},
        {"test_festering_aura_exact_position_effect", &test_festering_aura_exact_position_effect},
        {"test_exact_reference_ability_mechanics", &test_exact_reference_ability_mechanics},
        {"test_defend_and_ammo_core_mechanics", &test_defend_and_ammo_core_mechanics},
        {"test_retaliation_cycle", &test_retaliation_cycle},
        {"test_protocol_defend_and_recovery", &test_protocol_defend_and_recovery},
        {"test_warmachine_never_retaliates", &test_warmachine_never_retaliates},
        {"test_semantic_safety_and_state_hash", &test_semantic_safety_and_state_hash},
        {"test_runtime_probe_status", &test_runtime_probe_status},
        {"test_policy_prior_defend_is_distinct", &test_policy_prior_defend_is_distinct},
        {"test_hero_direct_spell_path", &test_hero_direct_spell_path},
        {"test_hero_basic_attack_path", &test_hero_basic_attack_path},
        {"test_status_spellbook_and_effect_mechanics", &test_status_spellbook_and_effect_mechanics},
        {"test_special_damage_state_mutation", &test_special_damage_state_mutation},
        {"test_raise_dead_observed_path", &test_raise_dead_observed_path},
        {"test_phantom_forces_observed_exact", &test_phantom_forces_observed_exact},
        {"test_phantom_damage_dissipation", &test_phantom_damage_dissipation},
        {"test_endurance_u_record_exact_speed_increment", &test_endurance_u_record_exact_speed_increment},
        {"test_rune_speed_exact_path", &test_rune_speed_exact_path},
        {"test_psc_damage_delta", &test_psc_damage_delta},
    };
    return tests;
}

int list_json() {
    const auto& tests = test_cases();
    std::cout << '[';
    for (std::size_t i = 0; i < tests.size(); ++i) {
        if (i != 0) std::cout << ',';
        std::cout << '"' << tests[i].name << '"';
    }
    std::cout << "]\n";
    return EXIT_SUCCESS;
}

int run_case(std::string_view requested) {
    const auto& tests = test_cases();
    const auto it = std::find_if(tests.begin(), tests.end(), [&](const TestCase& test) {
        return requested == test.name;
    });
    if (it == tests.end()) {
        std::cerr << "unknown ability C++ test case: " << requested << '\n';
        return EXIT_FAILURE;
    }

    std::cout << "[RUN] " << it->name << std::endl;
    if (!it->run()) {
        std::cerr << "[FAIL] " << it->name << '\n';
        return EXIT_FAILURE;
    }
    std::cout << "[PASS] " << it->name << std::endl;
    return EXIT_SUCCESS;
}
}  // namespace

int main(int argc, char** argv) {
    if (argc == 2 && std::string_view(argv[1]) == "--list-json") {
        return list_json();
    }
    if (argc == 3 && std::string_view(argv[1]) == "--case") {
        return run_case(argv[2]);
    }
    std::cerr << "usage: hwm-ability-case-tests --list-json | --case <test-name>\n";
    return EXIT_FAILURE;
}
