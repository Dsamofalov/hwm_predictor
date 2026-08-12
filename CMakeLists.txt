cmake_minimum_required(VERSION 3.25)
project(heroeswm_solver VERSION 0.3.0 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
option(HWM_BUILD_TESTS "Build tests" ON)

add_library(hwm_core
  cpp/src/state.cpp
  cpp/src/protocol.cpp
  cpp/src/simulator.cpp
  cpp/src/planner.cpp
  cpp/src/policy_prior.cpp
  cpp/src/value_model.cpp
  cpp/src/next_actor_model.cpp
  cpp/src/damage_model.cpp
  cpp/src/ability_damage_model.cpp
  cpp/src/ability_registry.cpp
  cpp/src/collateral_model.cpp
  cpp/src/proc_model.cpp
  cpp/src/kill_trigger_model.cpp
  cpp/src/hero_spell_model.cpp
  cpp/src/raise_dead_model.cpp
  cpp/src/phantom_forces_model.cpp
  cpp/src/session.cpp
  cpp/src/http_server.cpp
)
target_include_directories(hwm_core PUBLIC cpp/include)
target_compile_definitions(hwm_core PRIVATE HWM_PROJECT_ROOT="${CMAKE_SOURCE_DIR}")
if(WIN32)
  target_link_libraries(hwm_core PUBLIC ws2_32)
endif()
if(MSVC)
  target_compile_options(hwm_core PRIVATE /W4 /permissive-)
else()
  target_compile_options(hwm_core PRIVATE -Wall -Wextra -Wpedantic)
endif()

add_executable(solver-daemon cpp/src/main.cpp)
target_link_libraries(solver-daemon PRIVATE hwm_core)
add_executable(replay-inspect cpp/src/replay_inspect.cpp)
target_link_libraries(replay-inspect PRIVATE hwm_core)
add_executable(planner-demo cpp/src/planner_demo.cpp)
target_link_libraries(planner-demo PRIVATE hwm_core)
add_executable(corpus-check cpp/src/corpus_check.cpp)
target_link_libraries(corpus-check PRIVATE hwm_core)
add_executable(shadow-replay cpp/src/shadow_replay.cpp)
target_link_libraries(shadow-replay PRIVATE hwm_core)
add_executable(planner-eval cpp/src/planner_eval.cpp)
target_link_libraries(planner-eval PRIVATE hwm_core)
add_executable(overlap-diagnose cpp/src/overlap_diagnose.cpp)
target_link_libraries(overlap-diagnose PRIVATE hwm_core)

if(HWM_BUILD_TESTS)
  enable_testing()
  add_executable(hwm-tests cpp/tests/test_main.cpp)
  target_link_libraries(hwm-tests PRIVATE hwm_core)
  add_test(NAME hwm-tests COMMAND hwm-tests)

  # Ability validation executes the exact hwm-tests function inventory one case per
  # CI job.  The case runner is intentionally not registered in CTest so main-front
  # CTest ownership stays unchanged.
  add_executable(hwm-ability-case-tests cpp/tests/test_ability_cases.cpp)
  target_link_libraries(hwm-ability-case-tests PRIVATE hwm_core)

  # Kept separate from test_main.cpp because creature-ability work owns that file on
  # the parallel ability branch.  This target is the main-lane M13 planner regression.
  add_executable(hwm-planner-tests cpp/tests/test_planner_tree.cpp)
  target_link_libraries(hwm-planner-tests PRIVATE hwm_core)
  add_test(NAME hwm-planner-tests COMMAND hwm-planner-tests)

  # Main-owned protocol/decoder regressions stay separate from ability-owned test_main.cpp.
  add_executable(hwm-protocol-tests cpp/tests/test_protocol_geometry.cpp)
  target_link_libraries(hwm-protocol-tests PRIVATE hwm_core)
  target_compile_definitions(hwm-protocol-tests PRIVATE HWM_PROJECT_ROOT="${CMAKE_SOURCE_DIR}")
  add_test(NAME hwm-protocol-tests COMMAND hwm-protocol-tests)

  # Production closed-loop ingestion regression: semantic snapshot -> heartbeat -> delta.
  add_executable(hwm-live-ingestion-tests cpp/tests/test_live_ingestion.cpp)
  target_link_libraries(hwm-live-ingestion-tests PRIVATE hwm_core)
  target_compile_definitions(hwm-live-ingestion-tests PRIVATE HWM_PROJECT_ROOT="${CMAKE_SOURCE_DIR}")
  add_test(NAME hwm-live-ingestion-tests COMMAND hwm-live-ingestion-tests)
endif()
