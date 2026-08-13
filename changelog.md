# HeroesWM Solver — Change Log

Historical entries through **2026-08-11** remain in [`docs/changelog_archive_through_2026-08-11.md`](docs/changelog_archive_through_2026-08-11.md). On 2026-08-13 that archive received only a governance banner clarifying that its old branch/lane instructions are historical; the archived development entries themselves remain unchanged.

## Working convention

- Functional changes are committed as separate logical change sets.
- After functional changes, this file records the real commit SHA(s) in a bookkeeping commit.
- Specification/status documents are updated when a requirement is verified or its implementation status changes.
- A bookkeeping commit cannot record its own SHA; entries therefore reference the functional commits they document.

## 2026-08-13

### Ability development governance unified on `main`

- Ability is now a logical module/ownership boundary, not a dedicated Git development lane. All future ability implementation, evidence, tests, registry/risk updates and docs are committed directly to `main`.
- Ability-specific status/evidence and atomic Windows CI remain separate module surfaces; branch isolation is replaced by scope discipline and exact-SHA cross-module validation for shared substrate.
- `ABILITY_MERGE_CANON.md` is retired as an active procedure. The historical `ability` ref is archive/provenance only and is not source of truth, handoff destination, or normal merge source.
- Earlier changelog/archive references to an `ability` branch, Draft PR or ability-to-main integration describe historical repository organization and are superseded by this governance checkpoint.

### Ability integration: validated ability state merged into current main

- Ability source: `2ae1046c48e99c94da3481a8b3ed81285b9125ab`; source Ability Windows run `31697180629`, check-suite `85986692434` — **PASS / completed with conclusion `success`**.
- Main source before integration: `2d6c985fbc4a6725e64871f12b127d68f86f1000`.
- Real two-parent integration merge: `e69592eaa9461825e231cc73656d1e58b9ac4ffd`, with current-main source as first parent and the validated ability source as second parent. No squash/cherry-pick reconstruction and no force-push were used.
- Promoted and tested functional main checkpoint: `3df0d5ee4434d3cc401dba1b765a4dca068c15c1`.
  - Ability Windows integration run `31700597609`, check-suite `85996170989` — **PASS** on that exact SHA.
  - Main Windows CI run `31700599112`, check-suite `85996175100` — **Core PASS + Full PASS** on that exact SHA.
  - Strict `full-m11-evidence-reducer` job `94449755943` passed `M11Verify`; strict Full aggregate job `94452449852` passed.
- Shared `python/hwm_solver/protocol/replay.py` was integrated semantically rather than replaced wholesale. The merged delta is limited to the independently evidenced shared `ray -> dray` status-family decode plus the validated Gribbomb `bom` semantic gate/self-removal path; newer main geometry/runtime changes were preserved.
- Four generated M11 evidence reports were regenerated on the merged replay semantics after the first integration candidate correctly exposed stale numeric snapshots. The final independent strict verifier passed without loosening assertions or tolerances.
- Final negative-diff audit from `2d6c985...` to `3df0d5ee...` found only ability-owned/integration files, the audited shared replay delta, and the four regenerated M11 reports; there were no unexplained main-owned changes and no deletions. `SPEC.md`, `docs/MAIN_FRONT_STATUS.md`, `docs/LIVE_VALIDATION.md`, production live/front/search code and main geometry were not replaced by ability versions.
- Semantic ceilings remain explicit: Child of the Light school discrimination is unresolved; Taunt remains unresolved; Spider/`Sent` is not promoted to a Spider-specific mechanic; Hexing gains no speculative proc probability/rule; Gribbomb remains `partial_exact` with predictive collateral/Earth magnitude unresolved.
- The historical `ability` ref is retained only as archive/provenance. It is no longer an active development branch and no future ability work should target or merge from it.

### Authoritative main stabilization / production replanning safety

- Commit: `58138613956951271c921914c76b6802fdf5f83a` — `fix: bind live replanning dedupe to canonical state`.
  - Replaced revision-only extension replanning dedupe with canonical `(battle_id, revision, state_hash)` identity so daemon restart/revision reset cannot suppress a genuinely new state.
  - Extended the live-binding integration through real HTTP `/capture` using the scrubbed production-shape snapshot -> exact `t=<digits>` heartbeat -> incremental sequence; heartbeat remains revision-neutral even when MV3 `sequenceHint` restarts.
  - Hosted run `31692504639` passed Core + Full; targeted live-binding log proved both HTTP capture progression and recommendation binding.
- Commit: `49bbe98e00cbee27d437c26cd93b2127a18dc8b8` — `fix: retry live replanning after transport failure`.
  - Made recommendation scheduling retry-safe after transport/auth failure: only the same claimed canonical key may be released, while a late old-state failure cannot unlock a newer state; auth lifecycle reset clears the guard deliberately.
  - `not_ready`, `finished`, and `stale` remain semantic non-results rather than automatic retry triggers.
  - Final hosted atomic Windows CI run `31693648818` is **Core PASS + Full PASS** on `windows-2022`; final Geometry Evidence run `31693648857` is **PASS** on the same SHA.
  - Exact final corpus checkpoint: **855/866 structural-ready**, **11 invalid**, **798/866 semantic-safe**; held-out observed basic-action representability **5394/5481 = 98.4127%**, residuals **87** (35/49/3); Python final overlaps **15 battles / 15 pairs**.
  - The remaining M01/M14 blocker is the real authenticated shipped MV3 -> daemon -> recommendation -> manual move -> next recommendation smoke; deterministic CI does not promote that product gate to COMPLETE.

### Main atomic Windows CI checkpoint

- Permanent main CI now follows `TESTS_CANON.md`: exact C++/pytest inventories are frozen before fan-out, Debug/Release C++ are build-once, independent runtime/planner/Full gates run separately, and strict aggregate jobs publish `HWM / Core` and `HWM / Full` only when every mandatory surface succeeds.
- Final functional run `31693648818` materialized the atomic graph and passed both strict aggregates. Do not return to historical monolithic Core/Full execution.


### Evidence-backed blocked melee recovery

- Commit: `8bd394edb26e6f17fb5fe1dc4cd05736250ef2e9` — `fix: recover local unique blocked melee landing`.
  - Narrowed SPECIAL-free blocked melee-marker recovery to the evidence-backed local-unique landing class identified by the corpus diagnostics, with matching Python and C++ protocol regressions.
  - Kept SPECIAL-owned decisions outside the generic repair path and preserved the existing conservative ambiguity handling; hosted full-corpus non-regression remains an external validation gate rather than an assumption.
- Commit: `3367e802d9448bb008418e78f7a44f42ab99186c` — `test: isolate stationary friendly-marker geometry class`.
  - Refined the corpus evidence for the next blocked-melee correction into an exact residual class: all raw-marker blockers must be same-owner, the attack must have exactly one physical damage target, the actor's current anchor must already be legal and target-adjacent, and neither the existing radius-1 nor radius-2 unique landing resolver may apply.
  - The diagnostic additionally requires the current decoder to resolve away from the stationary anchor and the observed action to remain unrepresentable, preventing already-fixed shooter/unique-landing cases from being reclassified. Decoder/simulator semantics and all acceptance gates remain unchanged.
- Commit: `3b8131692365d250d96be203836bd36192f1ea4a` — `fix: stop final melee lookahead at battle result`.
  - Promoted the exact stationary friendly-blocked marker class into both C++ and Python only after the existing radius-1 and radius-2 unique-landing rules: SPECIAL-free, exactly one physical damage target, every raw-marker blocker same-owner, and the actor's current anchor legal + already adjacent to the target.
  - Added exact regressions for train final-overlap battle `1625534409` decision 82 / actor 22 and held-out representability battle `1632855461` decision 71 / actor 15; existing shooter and unique-landing regressions remain mandatory controls.
  - Stopped forward SPECIAL/other-damage lookahead at terminal `f<...>` / `f_en<...` result boundaries so result text cannot leak into current-action classification.
  - Temporary branch `agent/stationary-friendly-marker-20260813` publish run `31684482264` completed successfully after targeted Python geometry tests, C++ protocol tests, a full-corpus structural budget, and Python geometry/overlap non-regression checks. The functional push to `main` came from workflow credentials, so normal standard Windows Core/Full did not auto-trigger on this SHA; authoritative Windows validation and exact post-patch corpus totals remain the next-agent gate before the branch is deleted.

### M11 selector threshold canonicalization

- Commit: `3c31ed21eb4f1955c397aef48bc62727a3281b5b` — `fix: canonicalize M11 selector threshold`.
  - Diagnosed Full run `31644212192`: all C++ main-front tests, `invalid <= 14`, planner benchmark, M11 multistep, uncertainty, selector, survival, and temperature gates passed; only exact committed selector evidence failed because quantile interpolation reintroduced a long binary64 threshold tail (`0.5365153371341599`).
  - Canonicalized quantile threshold candidates to the existing 12-decimal selector policy/evidence boundary **before** threshold selection, so calibration metrics and the selected runtime/evidence policy use the same deterministic threshold values.
  - Added a focused regression proving `choose_threshold()` cannot return a longer-than-canonical interpolation tail. Exact evidence verification is not weakened and M11 production learned dynamics remains disabled.
  - Follow-up hosted standard run `31680022438` on this functional checkpoint is **Core PASS + Full PASS**. This is the last fully authoritative standard Windows checkpoint before `3b813169...`.

### Main-agent handoff TZ

- Commit: `5b6e78975f11e9457703e0d73352afffce438b3e` — `docs: add current main-agent handoff TZ [skip ci]`.
  - Added `docs/MAIN_AGENT_TZ.md` as the short-form binding handoff over the long `SPEC.md` for the current main lane.
  - The next agent must first run authoritative Windows validation for the current main functional tree, measure exact post-geometry corpus totals, resolve only evidence-proven stale M11 data if necessary, then delete `agent/stationary-friendly-marker-20260813` after confirming all useful changes are already in `main`.
  - Historical note for that checkpoint: other `agent/*` branches were not deleted merely by name because they could contain concurrent evidence work. This no longer defines ability governance; current ability development is `main`-only.

### Production live heartbeat-neutral ingestion

- Commit: `c3d07e81770681c9b0daae8ef1a19874ad98efa1` — `fix: keep live heartbeats revision-neutral`.
  - Added exact numeric-only `battle.php` heartbeat classification in the MAIN-world network hook before sequence allocation and forwarding; semantic network responses remain the primary capture truth.
  - Removed the periodic broad runtime-global structure scraper from the MAIN-world hook instead of expanding it into canonical state acquisition. Narrow runtime cross-check/fallback remains a separate, non-primary surface.
  - Added daemon defense-in-depth before session reset, raw hash/dedup, capture-time ordering, decoder publication, and revision bookkeeping, so a heartbeat cannot reset a battle, replace the last meaningful envelope, publish a canonical revision, or invalidate search.
  - Added a scrubbed `fixtures/live_closed_loop` snapshot/heartbeat/incremental-update regression and an independent `hwm-live-ingestion-tests` CTest asserting monotonic revision/hash behavior.
  - Extended the existing stale-cancellation integration to inject a heartbeat during an in-flight long search, assert unchanged revision/hash, then verify that the following real canonical publication still cancels the stale search.
- Commit: `6066a4ca1e6051cb0949115737512d5321647857` — `fix: classify observed t= heartbeat frames`.
  - Corrected the live fixture and stale-cancellation integration to the authenticated observed `t=<digits>` `battle.php` heartbeat shape instead of the earlier numeric-only surrogate.
- Commit: `a0fc9119b2e257a08c3eeff1bbc446cf66248ce1` — `fix: keep heartbeat classifier evidence-strict`.
  - Narrowed both MAIN-world and daemon heartbeat classification to exactly trimmed `t=<digits>` on `battle.php`/`battle_update`; bare numeric or otherwise unknown network payloads are no longer guessed away.
  - Added a negative ingestion regression proving a bare numeric payload reaches normal capture and is retained as the last envelope rather than being classified as a heartbeat.
  - Preserved the established snapshot -> heartbeat -> incremental regression, monotonic revision/hash assertions, and stale-search cancellation semantics without decoder/protocol changes.

### Exact decoder residual evidence

- Commit: `9f8597edc99a310226a5e6c272c4a8b8acfacc6b` — `test: publish exact decoder residual taxonomy`.
  - Extended `decoder_geometry_audit.py` without changing decoder behavior: every current held-out failure is now emitted with battle/decision identity, ownership (`special_free`, semantically resolved SPECIAL, or unresolved SPECIAL), special codes, unresolved opcodes, actor metadata, damage targets, and exact target-relative landing cardinality near the observed destination.
  - Added an independent `Geometry Evidence` workflow that runs the full chronological corpus audit on every functional `main` push, publishes the exact JSON artifact, and ignores changelog/docs-only pushes. The workflow is diagnostic/evidence-only and does not weaken or replace Core/Full/Ability gates.
- Commit: `1b4d8f4c6ae0564c0b19b99c269d028bb40e4c21` — `test: trace overlap introduction lineage`.
  - Added an exact replay lineage audit that records every newly introduced overlap with battle/decision identity, actor/action, raw decision payload, SPECIAL ownership markers, and the colliding entities after the decision.
  - Extended the existing Geometry Evidence artifact with `overlap-lineage-audit.json`, including the latest introduction event responsible for every final overlap pair. This changes no decoder or simulator semantics and is intended to drive the next narrow evidence-backed geometry correction.
- Commit: `8b384270e1bcda5a4d06e2bb90ee4007e8ebb18a` — `test: expose pre-overlap repair evidence`.
  - Extended overlap lineage evidence with the colliding pair and actor state before each introduction, the first physical damage target, raw-destination blockers, and whether the actor's prior canonical anchor was already melee-adjacent to that target.
  - The added fields are diagnostic only: decoder/simulator semantics and acceptance gates are unchanged. They distinguish invariant-preserving marker suppression from cases that require a separately proven landing or SPECIAL-specific mechanic.
- Commit: `a654e4a04c9d618a1640706edc92af00f3610618` — `test: fix overlap adjacency evidence`.
  - Corrected the pre-overlap adjacency diagnostic by retaining `alive`, hero, and hidden flags in summarized pre-state entities; the previous diagnostic boolean falsely treated every summarized entity as non-participating.
  - No decoder/simulator semantics or acceptance gates changed. The corrected Geometry Evidence rerun is the evidence source for subsequent invariant-preserving repair decisions.
- Commit: `2988acfc9ad504b26dad49fe142175cb9e616078` — `test: classify blocked melee marker evidence`.
  - Added a corpus-wide diagnostic class for SPECIAL-free melee decisions whose raw attack-position marker is blocked while the actor's prior canonical anchor is still legal and adjacent to the first physical damage target.
  - Each candidate now records raw blockers and ownership, all reachable target-adjacent landings, nearby-to-raw landings, damage-target cardinality, unresolved non-SPECIAL opcodes, resolved destination, overlap introduction/final lineage, and baseline observed-action representability.
  - This is evidence-only and intentionally follows rejection of a broader blocked-marker fallback that created new held-out failures; decoder and simulator semantics remain unchanged until the candidate classes provide a non-regressing discriminator.

## 2026-08-12

### Live active-battle engine evidence / TZ correction

- Commit: `2c042fb8fa9c6f737c5165c945b4ac58720f31d0` — `docs: record live battle transport evidence [skip ci]`.
  - Updated canonical `SPEC.md`, its active status mirror `HeroesWM_Solver_TZ_Status_0.3.0.md`, and `docs/MAIN_FRONT_STATUS.md` from evidence captured on authenticated active battle `warid=1672746591`.
  - Phase 0 state-acquisition feasibility is now closed: passive client XHR to `battle.php` produced a semantic `turns=>3` + `s=...` snapshot/update and, after one manual move, a compact `turns=>4:...` incremental update; client `lastturn` advanced `3 -> 4`.
  - Pure `t=<digits>` responses are specified as transport heartbeat/no-op frames: they are revision-neutral and must not cancel search or trigger replanning.
  - Network `battle.php` remains primary truth. `stage.pole.obj` / `stage[war_scr].obj` plus `nowturn` are documented only as a targeted read-only cross-check/fallback; grid `x/y` are semantic coordinates, while `scr_x/scr_y` are render-space and must not become canonical board state.
  - M01/M14 remain open until the same semantic progression passes through the actual MV3 extension -> daemon -> decoder -> planner -> revision-bound replan path. The raw user capture is not committed unsanitized because it contains user-facing battle metadata/chat/tooltips; only a scrubbed minimal regression fixture is acceptable.

### M11 exact-evidence float canonicalization

- Commit: `342cbac80606969af97ea75cfa99339e48c01dc9` — `fix: canonicalize M11 selector floats`.
  - Diagnosed standard Windows run `31627888832`: Core, planner/protocol regressions, the `invalid <= 14` corpus gate, M11 multistep/calibration/selector/survival gates, and the Release planner benchmark all passed; Full failed only because exact committed selector evidence differed by final binary64 bits in fitted coefficients.
  - Added an explicit 12-decimal canonical precision boundary for fitted selector coefficients and selector probabilities before they become exact evidence or policy decisions, removing irrelevant BLAS/reduction last-bit variation without loosening `verify_m11_evidence.py` or any acceptance threshold.
  - The M11 selector remains production-disabled; this change only makes its evidence representation reproducible across equivalent hosted Windows runners.
- Commit: `a71a249343dce0e2ebc34ecb4107695c49e896e2` — `test: lock selector evidence precision`.
  - Added focused Python regressions that require fitted selector weights and probabilities to stay on the canonical precision boundary and verify that adjacent binary64 tail values collapse to the same exact evidence value.
- Commit: `96499e4d242d1c4d1af1d6579cc21af5a0155679` — `data: canonicalize M11 selector evidence`.
  - Refreshed only `data/reports/dynamics-selector-gate.json` to the new canonical selector representation: fitted weights and the selected threshold are stored at the same 12-decimal evidence boundary used by the evaluator.
  - Accuracy, invalid-action, split, and production-enable gates are unchanged; exact committed-evidence verification remains strict equality rather than a tolerance-based comparison.

### CI parallel-work canon

- Commit: `4beff4847cfd0c17fccc27809131854628e6ea30` — `docs: add non-blocking CI work rule [skip ci]`.
  - Extended `TESTS_CANON.md` with the explicit rule that hosted CI is a verification source, not a global development barrier.
  - While a candidate SHA is still running in CI, useful independent work must continue in parallel when its correctness does not depend on the pending verdict.
  - Waiting is reserved for genuinely dependent decisions such as declaring a checkpoint validated, diagnosing a failure on the same surface, or avoiding ambiguous attribution between dependent changes.
  - Parallel work must still preserve atomic commits, identifiable candidate SHAs, and the prohibition on claiming a pending CI result as passed.

### M13 opponent probability-mass expansion

- Commit: `1bdc948f5572cf72bc3bd8749f341d73e4e16de0` — `feat: expand opponent search by policy mass`.
  - Split opponent expansion policy from player `self_top_k`: opponent nodes now cover configurable cumulative policy mass (`0.98` by default) subject to an independent configurable cap (`32` by default), while progressive widening remains intact.
  - Opponent detection is perspective-aware instead of being hard-coded to `Side::Pve`; the default player perspective preserves existing product behavior while non-player planner perspectives no longer invert self/opponent treatment.
  - Preserved existing `PlannerConfig` aggregate-initializer field order by appending the new parameters, so existing positional initializers keep their previous semantics.
  - Added targeted `hwm-planner-tests` coverage for cumulative-mass thresholds, caps, zero-target handling, and zero-prior fallback. Chance outcomes remain sampled and separated by canonical `state_hash`; transposition, persistent re-root, revision cancellation, and structure guards are unchanged.

### Single-target melee position-hint recovery

- Commit: `1c5a2b3478e7dacf0ebc714a4fb83246fed3b3f8` — `fix: recover single-target melee position hints`.
  - Extended special-free melee recovery to non-colliding raw position hints only when the actor damages exactly one target; multi-target decisions retain the conservative existing path so first-hit inference cannot corrupt later replay state.
  - Added three exact corpus regressions (two chronological-train, one held-out) where one legal/reachable target-adjacent landing exists within one Chebyshev cell of the raw hint.
  - Held-out basic-action representability improved from `5391/5481` to `5392/5481` (`98.3762%`), with exact failure inventory `90 -> 89`, no added or changed held-out failures, and unchanged Python final-overlap evidence at `17` battles / `17` pairs.
  - C++ protocol regression and the full-corpus structural-invalid budget (`14`) passed before promotion to `main`; the candidate also improved train representability by two actions without a partition regression.

### Post-decoder evidence and hosted validation

- Commit: `16998598ce3dc282bef76a9b29b27e83fba8bdf9` — `data: refresh M11 selector evidence`.
  - The first standard Windows run after the decoder change (`31622628256`) passed Core and all functional Full gates but correctly failed committed-evidence verification because `dynamics-selector-gate.json` was stale after the replay-state shift.
  - Regenerated exactly that selector evidence file on `windows-2022`; no other production or report file changed in the refresh commit.
  - Follow-up standard hosted run `31624580974` on `16998598ce3dc282bef76a9b29b27e83fba8bdf9`: **Core PASS + Full PASS**, including the `invalid <= 14` full-corpus structural budget and exact M11 committed-evidence verification.
  - Atomic Ability run `31622630092`: **PASS** on the same functional decoder checkpoint before the selector-only evidence refresh.
- Commit: `7e646024cda8d4439420462d479e1a3ca007be85` — `docs: sync validated 2026-08-12 checkpoint [skip ci]`.
  - Synchronized `SPEC.md`, its active status mirror, and `docs/MAIN_FRONT_STATUS.md` to the verified metrics: **852/866 structural-ready**, **795/866 semantic-safe**, **5392/5481 held-out representable**, and **14 final structural-invalid battles**.
  - Final-only inventory confirms all 14 remaining structural failures are `overlap` only, with 16 C++ overlap pairs total; broader blocked-anchor and non-colliding fallback experiments were rejected because they worsened semantic representability or produced no gain.

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
