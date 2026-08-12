# HeroesWM Solver — Change Log

Historical entries through **2026-08-11** are preserved verbatim in [`docs/changelog_archive_through_2026-08-11.md`](docs/changelog_archive_through_2026-08-11.md). The archive is the exact previous `changelog.md` blob; no historical entry was rewritten or dropped during this rollover.

## Working convention

- Functional changes are committed as separate logical change sets.
- After functional changes, this file records the real commit SHA(s) in a bookkeeping commit.
- Specification/status documents are updated when a requirement is verified or its implementation status changes.
- A bookkeeping commit cannot record its own SHA; entries therefore reference the functional commits they document.

## 2026-08-12

### Atomic test execution canon

- Commit: `d4424f5bc861f8eae58b0c6c723f99b8b3b58341` — `docs: define atomic test execution canon`.
  - Added `TESTS_CANON.md` to `main` as the canonical testing policy.
  - Atomicity, independence, deterministic execution, exact inventory coverage, no duplicate/omitted cases, and exact aggregation are correctness requirements.
  - Shard count, worker count, matrix width, and `max-parallel` are explicitly implementation details rather than fixed correctness contracts.

### Ability snapshot integration without divergent-history merge

- Commit: `f98ea913be9331ca393c49df82b2025303956f92` — `feat: integrate ability evidence snapshot with atomic CI`.
  - Recreated the final ability-owned state directly on top of current `main` instead of merging the divergent raw `ability` history.
  - Imported `python/hwm_solver/ability/**`, matching evidence regressions, ability ownership/status documentation, and the evidence-backed `cripplingwound -> partial_exact` registry classification.
  - Preserved current main-owned planner, M11/evaluation, daemon/runtime, extension, general CI, specification, and report files rather than taking their divergent ability-branch versions.
  - Imported the ability-owned C++ test state with the Windows/MSVC test-only fixes: Mighty Slam pointers are reacquired after `vector::push_back`, the canonical `frightfulaura` tag is used, and temporary files use `std::filesystem::temp_directory_path()`.
  - Added a minimal CMake target for an ability case runner and a dedicated hosted-Windows atomic ability workflow.
  - C++ builds once, freezes the exact `hwm-tests` function inventory, then executes one named function per matrix job.
  - Python freezes exact pytest node IDs from the explicit ability test manifest and executes one node per matrix job.
  - No ability correctness regression requires a particular shard count, worker count, matrix width, or `max-parallel` value.

- Commit: `53a2e08b9eb2d8185f9d72f8ebf03b5b77b1a886` — `fix: delimit PowerShell case labels`.
  - Corrected PowerShell variable interpolation exposed by real hosted run `31607100702`; both C++ and Python syntax preflights then passed.

- Commit: `03d2fbe138e0dad929037315dce46d38256be8f3` — `fix: preserve C++ inventory JSON for matrix`.
  - Preserved the case runner's JSON array verbatim for GitHub matrix expansion after run `31607254689` exposed an accidental single `Object` matrix value.
  - Authoritative integration run `31607886774`: **PASS**, expanding to **85 jobs** with independent C++ function jobs, independent pytest node jobs, inventory gates, and aggregate status publication.

- Commit: `a9dab68a0e6720f415571cad2bc4865b50a5f4f0` — `docs: record validated ability snapshot integration`.
  - Replaced the stale outage-era ability status with the validated snapshot handoff, preserved semantic boundaries, and documented the new atomic CI ownership model.
  - `main` was advanced to this commit by a normal non-forced fast-forward; the raw 134-commit divergent `ability` history was not merged.
  - Post-merge atomic Ability run `31609098962`: **PASS**.
  - Post-merge standard Windows run `31609098960`: **PASS** — Core and Full both completed successfully on the same functional SHA.

### Ability semantic boundary after integration

- `cripplingwound` is `partial_exact`: observed consequence is represented, while speculative proc probability remains disabled.
- `powerstrike` trigger prediction remains unresolved/learned rather than being promoted to an exact speculative proc.
- Evidence-only Aura of Fire Vulnerability and the remaining ability queue remain evidence-only until executable semantics satisfy their own gates.
- Existing closed Life Drain, Regeneration, Mana Feed, Mighty Slam, and Paw Strike mechanics were not reworked by this integration.
