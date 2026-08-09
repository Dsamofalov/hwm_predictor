# HeroesWM Solver — Change Log

This file is the development diary for repository changes performed against the active specification (`SPEC.md` / `HeroesWM_Solver_TZ_Status_0.3.0.md`).

## Working convention

- Functional changes are committed as separate logical change sets.
- After each functional commit, this file is updated with the real commit SHA in a bookkeeping commit.
- Specification/status documents are updated when a requirement is verified or its implementation status changes.
- A bookkeeping commit cannot record its own SHA; entries therefore reference the functional commit they document.

## 2026-08-10

### Repository layout and CI activation

- Commit: `d0daf171bb7c3fdee84a943eabde37e8905a4435`
- Moved the project contents from `heroeswm-solver-github-0.3.0/` directly to the repository root without changing file contents.
- This made `.github/workflows/ci.yml` visible to GitHub Actions.
- Verified workflow run `31337305152`: completed successfully.

### Review focus started

- Started source-vs-spec review with priority on `hwm_battles/`, the two supplied creature HTML snapshots, and creature ability semantics/coverage.
- No implementation claim is marked complete until verified against repository data and tests.

### Changelog initialization

- Commit: `b3c085477c0d55ea8aac6bf2f1be1a8fb36abc5a`
- Added `changelog.md` and established the commit-linked development diary convention.

### Life Drain patch tooling

- Commit: `4b4d18fd8727fe9e9c9fec72edd26eff1cc0cf08`
  - First one-shot workflow staging attempt; GitHub rejected the embedded multiline YAML before creating a job. No functional source change was produced.
- Commit: `539eba4ebf9ff075a420f2da6e01990351f86e55`
  - Moved the large patch logic into a temporary Python script to keep the workflow YAML small and parseable.
- Commit: `66150992861f3641a1cba32ef2c3e089dfb50a0a`
  - Fixed the temporary workflow and reached a real build/test run. C++ build and CTest passed, but an over-broad `git diff --check` rejected intentional Markdown hard-break spaces and generated CRLF CSV, so no functional commit was produced.
- Commit: `73e7cdd743fdf3606b62c5bfddd5aa1316334c31`
  - Narrowed the whitespace gate to C++/Python source files and added cleanup of the first temporary script.
- Commit: `e5fc43c25792f5a66c12931f07d9070c30ccf7b1`
  - Re-ran the verified patch pipeline successfully. The functional commit below deletes all temporary patch infrastructure.

### Exact Life Drain transition

- Commit: `132cb2b35118845acb24c25573a6088b846a58af`
- Implemented `lifedrain` healing from 50% of actually inflicted physical damage, including resurrection up to `max_count`.
- Applied the same rule to normal and concentration/pre-emptive retaliation paths.
- Added a phantom-damage guard so phantom dissipation cannot inflate healing.
- Added C++ regression coverage for primary healing/resurrection, max-count cap, and retaliation healing.
- Promoted `lifedrain` from `learned_damage` to `exact_search`; regenerated Ability Registry to 82 exact-search / 180 learned-damage / 78 unresolved.
- Updated active Markdown specification, implementation report, and test report status.
- C++ Debug build and CTest passed before commit.

### Regeneration patch tooling

- Commit: `9ae958b2bc2aed3382bb05af0578d3db3224b27d`
  - Initial Regeneration staging runner. Production code and registry generation compiled far enough to verify 83/179/78 counts, but the new C++ test did not compile because the project `CHECK` macro returns `false` inside lambdas. No functional commit was produced.
- Commit: `4a4d9947a63ab4246d0a853c148ae6a6cee1ab70`
  - Corrected the regression helper lambdas and the scheduler indentation warning; re-ran the self-removing patch pipeline.
- The temporary workflow and patch scripts were removed by the functional commit below.

### Exact Regeneration turn-start transition

- Commit: `ed108d79169bb21720bc830f846865fcf9c1a9b6`
- Implemented `regeneration` as a start-of-turn transition when the rollout advances to the next actor.
- Uses an exact 30–50 HP integer roll and heals only the current top creature; stack `count` never increases.
- Explicitly excludes Srn2 preparatory same-actor reactivation and terminal states to avoid duplicate/non-turn healing.
- Added C++ regression coverage for 30/40/50 HP rolls, max-HP cap, next-actor timing, and no-resurrection invariant.
- Promoted `regeneration` from `learned_damage` to `exact_search`; regenerated Ability Registry to 83 exact-search / 179 learned-damage / 78 unresolved.
- Updated active Markdown specification, implementation reports, and test report status.
- C++ Debug build and CTest passed before commit.

### Regeneration formula correction

- Commit: `c60b3c9af08e5a88973b86809191f89720aee67a`
  - Staged a self-removing correction after cross-checking the HeroesWM reference formula against the fixed 30–50 implementation.
- Commit: `00dd1074ad6c83d92f43bb90a1fe1dc5083aaadf`
  - Corrected Regeneration from a fixed 30–50 HP roll to `random(3,5) * min(current_count, 10)`.
  - Preserved the already-correct start-of-turn timing, Srn2 exclusion, top-unit-only healing, and no-resurrection invariant from `ed108d79169bb21720bc830f846865fcf9c1a9b6`.
  - Expanded regression coverage for 3-creature 9/12/15 HP healing and the 10-creature 50 HP cap.
  - Updated the active Markdown specification formula. Ability Registry counts remain 83 exact-search / 179 learned-damage / 78 unresolved.
  - C++ Debug build and CTest passed before commit.

### Ability decision corpus probe

- Commit: `0346b7befb70ac3d47540ed60f4d857016c9ddbe`
  - Added `scripts/ability_probe.py`, a read-only analyzer built on the canonical `iter_battle_decisions()` replay stream.
- Commit: `2f8ffc8f7ef92cc531b77e60c7b099af68368203`
  - Ran the probe over the repository `hwm_battles` corpus for `manafeed` and stored `data/reports/manafeed_probe.json`.
  - Matched decisions: **730** across **125** battles; mechanic-like candidates: **243**.
  - The report preserves raw decision records/opcodes and already-decoded mana deltas for evidence-driven wire decoding.
  - Probe parse errors: **0**.

### Exact Mana Feed action

- Commit: `5f01febfbc542f662f99f49acb401201edb18099`
  - Initial verified patch staging. Registry regeneration and the 42-record corpus probe passed, C++ compiled, but CTest exposed a regression-test bug caused by `begin()`/`end()` from two temporary legal-action vectors. No functional commit was produced.
- Commit: `aabf7ed4bbab7df68238370e637fc1562e81bf71`
  - Corrected the regression test to retain one legal-action vector and re-ran the self-removing verified patch.
- Commit: `80ded68159636f3d3b497e00cc86aa422823eefa`
  - Decoded `Smfd` as actor3 + own-hero3 + amount2 + zero trailer and marked it exact only when actor ability, ownership and `amount=min(count,mana)` invariants hold.
  - Added Python and C++ canonical mana transitions: creature mana decreases and own hero mana increases by the same amount.
  - Added exact C++ legal `Ability` generation and simulator execution targeting only the actor's own hero.
  - Reclassified observed Mana Feed decisions as target-bound `ABILITY` actions instead of generic targetless `CAST_OR_ABILITY`.
  - Re-ran the full 866-battle Mana Feed probe: **42/42 `Smfd` records** satisfy the exact action/target/mana-delta invariant.
  - Added Python and C++ regressions, promoted `manafeed` to exact-search and regenerated the registry to 84 exact-search / 178 learned-damage / 78 unresolved.
  - Updated active Markdown specification, implementation reports, test report and `data/reports/manafeed_probe.json`.
  - Targeted C++ build/CTest and Python pytest passed before commit.
