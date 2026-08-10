# Development lanes

Active since: 2026-08-10

## `ability` lane

Branch: `ability`
Draft PR: #1
Detailed contract: `docs/ABILITY_AGENT_TZ.md` on branch `ability`.

While the ability branch is active, main development must avoid modifying the following reserved files unless an integration blocker makes it unavoidable:

- `cpp/src/protocol.cpp`
- `cpp/src/simulator.cpp`
- `cpp/src/proc_model.cpp`
- `cpp/src/ability_registry.cpp`
- `cpp/src/ability_damage_model.cpp`
- `cpp/src/collateral_model.cpp`
- `cpp/src/kill_trigger_model.cpp`
- matching ability/proc/collateral/kill-trigger headers under `cpp/include/hwm/`
- `cpp/tests/test_main.cpp`
- `python/hwm_solver/protocol/replay.py`
- `python/hwm_solver/knowledge/build_ability_registry.py`
- ability/proc/collateral research/train scripts under `python/hwm_solver/`
- `python/tests/test_replay_parser.py`
- `python/tests/test_ability_probe.py`
- ability-specific new Python tests
- `data/catalog/ability_registry.json`
- `data/catalog/ability_registry.csv`
- ability reports/evidence/model artifacts

The ability agent must not modify planner/runtime/UI/CI/shared project reports and must never push to `main`.

## `main` lane

Until PR #1 is ready for review, main development focuses on areas that do not overlap the reserved ability files:

1. live browser-extension <-> daemon end-to-end path;
2. pairing/authentication and loopback security;
3. stale recommendation cancellation/state-hash binding/session correctness;
4. planner tree reuse/transpositions/opponent branching where changes stay inside planner/runtime ownership;
5. live diagnostics and reproducible human-in-loop validation tooling;
6. CI/build/release infrastructure outside ability-owned files.

Primary main-owned files include:

- `cpp/src/planner.cpp`
- `cpp/include/hwm/planner.hpp`
- `cpp/src/session.cpp`
- `cpp/include/hwm/session.hpp`
- `cpp/src/http_server.cpp`
- `cpp/include/hwm/http_server.hpp`
- `cpp/src/main.cpp`
- `extension/**`
- `.github/**`
- shared project documentation and release files.

`cpp/src/state.cpp`, `cpp/include/hwm/state.hpp`, `CMakeLists.txt` and `CMakePresets.json` are integration-sensitive. The ability agent should request changes to them rather than modifying them directly; main may change them only when needed for non-ability work.

## Merge policy

The ability agent stops at branch/PR delivery. Main reviews `main...ability`, corpus evidence, risk changes and CI, resolves any integration requests, and only then merges.
