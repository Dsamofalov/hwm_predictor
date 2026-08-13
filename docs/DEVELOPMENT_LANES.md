# Development modules and ownership

Current governance: **2026-08-13**
Compatibility note: this filename is retained because older handoffs link to it; the old multi-branch lane model is retired.

## One development branch

Normal project development, including creature abilities, happens on **`main`**.

Ability is a separate logical module/ownership boundary, not a Git branch. Do not create or use a dedicated `ability` branch as the normal source of ability work, and do not plan a later ability-to-main merge as part of the development cycle.

The historical Git ref named `ability` is archive/provenance only. It is not authoritative project state and must not be used as a handoff destination or merge source for new work.

## Ability module

Canonical contract: `docs/ABILITY_AGENT_TZ.md`.

Normal module scope includes:

- ability protocol/evidence work;
- ability-specific replay/simulator/proc/collateral mechanics;
- Ability Registry and risk evidence;
- `python/hwm_solver/ability/**` and corresponding tests;
- ability-specific C++/Python regressions;
- `docs/ability/**` status/history;
- `.github/workflows/ability.yml` and its contract tests when the validation surface itself needs maintenance.

All such changes are committed directly on `main`.

## Other project modules

Planner/search, live extension/daemon, session/API, M11/evaluation, UI and release infrastructure remain distinct ownership areas for task decomposition, but they share the same `main` history.

An ability-focused agent should not modify unrelated project modules merely because they are available in the same branch. Scope discipline replaces branch isolation.

## Shared substrate

Files including `python/hwm_solver/protocol/replay.py`, protocol/simulator code, state structures, CMake configuration and shared reports can affect multiple modules.

When an ability change requires shared substrate:

1. make the smallest evidence-backed change directly in `main`;
2. preserve generic parser/state/runtime invariants;
3. add positive and negative regressions at the correct ownership boundary;
4. run Ability validation and every affected main validation surface on the exact functional SHA;
5. record cross-module impact in `docs/ability/AGENT_STATUS.md` and the changelogs.

There is no integration-request/merge-conflict ceremony merely because the change is ability-related.

## Validation and handoff

`TESTS_CANON.md` remains mandatory. Ability-specific atomic CI is a validation surface inside unified `main` development, not evidence of a separate lane.

A completed ability block ends with a validated `main` functional SHA plus bookkeeping/status updates. It does not end with a dedicated branch, draft PR, or merge-back handoff.
