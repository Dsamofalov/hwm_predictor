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
