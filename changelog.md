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

### Gribbomb evidence resumption

- Commit: `b6b27633154f12588071a3e94145308aceb57451` — `test(ability): pin Gribbomb Sbom activation boundary`.
  - Promoted raw carrier `SPECIAL:bom` to the primary evidence discriminator and added strict whole-corpus adjacency/target-set regression gates.
  - Hosted Windows run `31621278975` failed only on a handwritten expected pre-activation HP (`36356` vs replay-derived `36101`); the preceding discriminator and 3/3 adjacent-target assertions passed.
  - No runtime/registry promotion is claimed from the failed package; predictive Earth-damage magnitude remains unresolved.

- Commit: `d04999b03a094e637223ec7925b3071e50e36ecf` — `fix(ability): use replay-derived Gribbomb pre-bomb HP`.
  - Fixed only the incorrect expected pre-activation HP while keeping all strict discriminator, geometry, target-set, and negative-control assertions intact.
  - Hosted Windows run `31621756446`: **PASS**, 86/86 atomic jobs on the exact functional SHA.
  - Validated corpus evidence: 866 battle dirs, 7 carrier battles, 1/1 valid `Sbom`, 3/3 adjacent living targets hit, zero missing/extra targets, and 3 non-`Sbom` carrier deaths externally explained.
  - Runtime self-destruction and predictive Earth-damage magnitude remain intentionally unresolved; no registry promotion is claimed yet.

- Commit: `2e82c969e0da708f5bbda6973c92d662a638aa3c` — `fix(ability): replay Gribbomb Sbom self-destruction`.
  - Validated canonical carrier-sourced `Sbom` as an exact observed replay self-removal transition and added wrong-source/malformed-marker negative controls.
  - The carrier now becomes `alive=false`, `count=0`, `top_hp=0`; adjacent HP changes remain sourced only from raw `DAMAGE` records and no predictive Earth-damage formula was introduced.
  - Hosted Windows run `31625718512`: **PASS, 87/87 atomic jobs** on the exact functional SHA.
  - Gribbomb's carrier-removal boundary is exact observed replay; predictive collateral magnitude remains unresolved, so the next ability-owned step is a bounded registry/risk promotion rather than a fully exact claim.

### Gribbomb bounded registry/risk promotion

- Commit: `e4616a155fdd1e15def28f74c8c7af43391177ba` — `feat(ability): classify Gribbomb partial exact`.
  - Promoted `gribbomb` in the source-of-truth registry builder from `unresolved` to `partial_exact`, giving the canonical `partial_exact` risk weight `0.25` instead of the old unresolved `0.62`.
  - Added a leakage-safe registry/risk regression that synthesizes the old Gribbomb baseline and proves the candidate registry lowers held-out ability risk.
  - The regression also requires Gribbomb to remain outside the predictive collateral model: the exact claim is carrier self-removal, not an inferred Earth-damage formula.
  - Hosted Windows run `31626881854`: **FAIL** only because the new regression encoded a brittle global support-count constant; the Gribbomb classification and semantic assertions themselves passed.

- Commit: `19ba4e6caed9977839eaac8ebb0181ca57a32ede` — `fix(ability): compare Gribbomb registry counts relatively`.
  - Replaced the brittle global registry cardinality assertion with the invariant that the candidate has exactly `+1 partial_exact / -1 unresolved` versus the synthesized pre-promotion baseline.
  - No semantic or risk threshold was weakened.

- Commit: `da7fd216f6b993f7e6a1770371004253b80d35cc` — `fix(ability): trigger registry risk tests in CI`.
  - Closed a workflow path-filter gap by matching `python/tests/test_*_registry_risk.py` for Ability push/PR triggers instead of naming only the older Crippling Wound file.
  - Added an atomic workflow-contract regression so future ability registry-risk tests cannot silently fall outside the hosted validation trigger.
  - Authoritative hosted Windows run `31627726097`: **PASS, 89/89 jobs**, including the Gribbomb registry/risk node, all Gribbomb self-destruction controls, the new workflow-trigger regression, and final `publish_status`.
  - Gribbomb's supported classification ceiling is now `partial_exact`: observed carrier self-removal is exact, while predictive Earth/collateral-damage magnitude remains unresolved.
  - Checked generated registry/report artifacts still require deterministic regeneration from the validated builder before the Gribbomb package is considered repository-consistent and the queue advances to Taunt.

### Gribbomb generated artifact closure

- Commit: `c24cacf060182494092ef3e460301844639388e6` — `chore(ability): regenerate ability registry artifacts`.
  - Deterministically regenerated checked `data/catalog/ability_registry.json` and `.csv` from the validated source-of-truth builder and tracked inputs.
  - The generated output incorporates the Gribbomb `partial_exact` promotion and also corrects the previously stale checked Crippling Wound classification; support totals are `partial_exact = 20`, `unresolved = 77`.

- Commit: `eaca45fc3de060b030ee912c38efea234aa00c1f` — `chore(ability): regenerate current ability reports`.
  - Regenerated `data/reports/ability-registry-current.json` and `data/reports/ability-risk-current.json` from the synchronized checked registry.
  - Held-out ability-risk mean changed `0.22431 -> 0.21744`; p90 changed `0.37538 -> 0.36755`.
  - Stale unresolved Gribbomb risk dropped out of the unfinished top-risk slice, while Crippling Wound is now represented as `partial_exact` with canonical risk `0.25`.
  - Hosted Windows run `31631708571` on exact SHA `eaca45fc...`: workflow **PASS / conclusion `success`**. All test/build/inventory jobs succeeded; final `publish_status` was skipped by workflow condition.
  - Builder, checked registry, and current report artifacts are now repository-consistent. Gribbomb is closed at the strongest evidence-supported `partial_exact` boundary; predictive Earth/collateral magnitude remains explicitly unresolved and disabled.

### Ability queue after Gribbomb closure

- Recomputed from the synchronized current risk report: Taunt is the highest-priority currently actionable unfinished ability after excluding already documented semantic/substrate blockers.
- Taunt development resumes from the existing evidence auditor rather than restarting from scratch. Its current smoke regression must be upgraded to exact whole-corpus counts and raw special-code contexts before any semantic promotion.
- Final-target observations alone are not accepted as Taunt proc evidence; a carrier-specific raw discriminator is required before claiming redirected targeting or proc probability.
