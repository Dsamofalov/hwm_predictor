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
