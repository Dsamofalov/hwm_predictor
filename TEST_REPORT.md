# Test report — HeroesWM Solver 0.3.0

**Дата:** 11.08.2026

## Automated build/test snapshot

```text
Supported product/CI platform:                  Windows 10/11 x64 via GitHub-hosted windows-2022
PowerShell syntax preflight:                    PASS
MSVC Debug main-front CTest:                    1/1 PASS (hwm-planner-tests)
Held-out planner validity:                      120/120 PASS; 0 invalid recommendations
Local API pairing/auth integration:             PASS
Stale-search cancellation integration:          PASS
Live recommendation binding contract:           PASS
WebSocket revision streaming:                   PASS
Python pytest:                                  75/75 PASS
TypeScript typecheck:                           PASS
Extension build:                                PASS
MSVC Release main-front CTest:                  1/1 PASS (hwm-planner-tests)
Release planner benchmark (5000 simulations):   PASS
M11 full-corpus diagnostic/evidence suite:      PASS
```

Validated functional-tree reference: `7cd17878174529a40087ce5a78231dd93690851b`, Windows self-hosted Actions run `31431838319`: **Core PASS + Full PASS**. Core compiled all C++ targets under MSVC Debug, executed the main-owned `hwm-planner-tests`, validated 120 held-out planner states from 109 battles with zero invalid recommendations, state-hash mismatches, illegal best/alternative actions or non-finite metrics, passed pairing/auth, stale cancellation, live binding and WebSocket integrations, Python **75/75**, TypeScript typecheck and extension build. Full passed MSVC Release main-front CTest, `planner-demo 5000`, all permanent M11 full-corpus evaluators, committed-evidence verification and the positive-residual temperature experiment.

The ability-owned monolithic `hwm-tests` target is still built but deliberately excluded from the `main` CTest gate until branch `ability` completes its independent MSVC validation. This ownership split is temporary integration debt, not a permanent reduction of the final test contract.

## Closed-loop safety regressions

### Pairing/auth

`scripts/test_local_api_auth.py` starts a real loopback daemon and verifies:

- private API routes reject unauthenticated calls;
- a wrong pairing code is rejected;
- a correct explicit code returns the local bearer token;
- the token is persisted locally;
- the same bearer token remains valid across a daemon restart when the local token file is retained.

### Revision-bound stale cancellation

`scripts/test_stale_cancellation.py` deliberately republishes the **same** demo BattleState while a long search is in progress. The state hash therefore remains equal, but the SessionStore revision advances. The old planner must cooperatively stop and return `stale` rather than consuming the full search budget or presenting an obsolete result.

This proves stale invalidation is not limited to a post-search hash comparison.

### Live recommendation binding contract

`scripts/test_live_binding.py` verifies that an `ok` recommendation is explicitly bound to the same daemon `state_revision`, `state_hash`, and `battle_id` as the observed planning snapshot.

The extension adds defense-in-depth on top of this contract: a newer accepted capture advances the recommendation epoch, and the side panel refuses to render an `ok` result whose state hash no longer matches current daemon status.

## Full 866-battle corpus-check

```json
{"battles":866,"structural_ready":847,"structural_not_ready":19,"semantic_safe":790,"semantic_unsafe":76,"with_unknown":0,"invalid":19,"initial_entities":14819,"coverage_mean":1.0,"coverage_min":1.0,"semantic_unresolved_ratio_mean":0.137432,"semantic_unresolved_ratio_max":0.480769,"semantic_unresolved_records":42576,"protocol_records":291178,"max_turn":297}
```

`invalid=19` corresponds to 21 strict overlap invariant hits. These are not suppressed.

## Shadow replay

Full result is stored in `data/reports/shadow-replay-current.json`. Highlights:

```text
all battles incremental_final_match:       866/866 = 100%
held-out battles:                          174
held-out player non-hero states:           5,476
held-out structural-ready states:          5,351 = 97.72%
held-out strict semantic-safe states:       4,979 = 90.92%
held-out structural-ready with actions:    5,338 / 5,351 = 99.76%
held-out hero states structural-ready:     684 / 712 = 96.07%
held-out supported hero actions:           684 / 684 = 100%
```

## Legal action replay coverage

Latest stored held-out basic-action evaluation (`legal-coverage-v7-endurance.json`):

```text
observed basic actions evaluated:      5,481
representable by current generator:    5,384
coverage:                              98.23%
```

Primary residual failures are `melee_destination_not_reachable`, `target_not_adjacent_after_move` and rare special movement.

## Ability Registry / risk

Rebuilt from current code/models and `generated_v4` catalog:

```text
ability codes:          421
exact_search:           85
exact_targeting:        11
partial_exact:          18
modeled_proc:           9
modeled_collateral:     5
modeled_kill_trigger:   2
unresolved:             78
```

Current counts include exact Life Drain, Regeneration, Mana Feed and Mighty Slam plus hybrid modeled Paw Strike. All **42/42** observed `Smfd` actions pass the exact Mana Feed invariant, all **32/32** observed `Smsl` decisions classify as explicit `ABILITY`, and the observed Paw Strike ATB-reset relation is validated on **174/174** source-matching I-records.

Current held-out risk was recomputed from the same 866-battle corpus after the Paw Strike promotion:

```text
held-out sampled player states: 1748
risk mean:              0.22431
risk p50:               0.21389
risk p90:               0.37538
risk p99:               0.54688
```

`Crippling Wound` remains deliberately non-speculative: its observed `Swnd` debuff transition is decoded, but the current proc-probability models fail the chronological validation gate and therefore are not enabled in search.

`Paw Strike` is deliberately hybrid rather than exact-search: current-corpus distance model Brier 0.20250 beats the train-frequency baseline 0.23788, while the historical HP-ratio formula fails current holdout. Observed `I<target><source>` transitions reset ATB to zero; speculative physical push is conditional on legal placement.

## Policy priors

```text
PLAYER held-out: top-1 70.76%, top-3 93.46%
PvE held-out:    top-1 62.81%, top-3 96.11%
```

## Value model

Battle-level held-out/test metrics:

```text
Test Brier:              0.051761
Constant Brier:          0.118906
Test AUC:                0.988889
Test logloss:            0.159399
```

## Physical / ability damage

```text
Held-out attacks: 6201
Generic median abs-log:                0.35739
Creature residual median abs-log:      0.28122

Rare creature <=20 train attacks:
  creature-only median abs-log:        0.27190
  creature + ability median abs-log:   0.24844
```

Unseen creature IDs deliberately use conservative exact-core fallback rather than an unverified global creature multiplier.

## Next actor

```text
Held-out transitions:      10,202
Top-1:                     32.16%
Top-3:                     65.86%
MRR:                       0.5290
Round-robin top-1:         12.75%
Round-robin top-3:         33.49%
```

## Planner regression / permanent validity gate

The old 20-state Release stability snapshot is retained as historical evidence, but the permanent acceptance gate is now the deterministic chronological 120-state replay suite.

```text
sampled states:                 120
sampled battles:                109
low-budget valid:               120/120
high-budget valid:              120/120
invalid recommendations:        0
state-hash mismatches:           0
illegal best actions:           0
illegal alternatives:           0
non-finite metrics:              0
action-type stability 1 -> 120: 99.17%
exact-action stability 1 -> 120: 85.83%
```

This closes the **replay** half of the >=100-state technical recommendation-validity requirement. It is not a substitute for the real authenticated active-battle smoke or a live win-rate benchmark.

## Not validated in this environment

1. Active authenticated battle capture/replanning in the user's Chromium session. The metadata-only closed-loop trace and `docs/LIVE_VALIDATION.md` are ready for this gate, but the real live exercise has not yet been claimed as complete.
2. Hard-PvE human-in-loop win-rate uplift.
3. Full structured learned dynamics ensemble / ONNX Runtime C++ production path.

## M13 stochastic outcome / persistent re-root verification

Functional commits `d06217fd4aa531aa0e49cf7c8c2495a5ab0ca5e4`, `135826c05d7f9b3d44e165ef6732bb6ede89a4c4`, and `6edec4d8360169060d280cd07a6e63de9c0fda89` add a dedicated `hwm-planner-tests` target covering distinct stochastic outcome nodes/legal sets, equal-hash transpositions, exact persistent root reuse, reachable-subgraph pruning, battle reset, and static-structure mismatch reset. Follow-up hashing work includes scheduler recency (`last_acted_seq`) in canonical identity and excludes provenance-only `Effect.raw` from semantic state identity, preventing unsafe reuse while avoiding false-negative reuse on diagnostic-only raw text.

## M11 multi-step damage-residual ensemble gate

Commit `45581ae7d0f844f67797c590c3ed529390b76f1f` adds five targeted evaluator tests and `data/reports/dynamics-multistep-damage.json`. On 174 chronological held-out battles, the five-member train-only ensemble beats the generic baseline in mean normalized force-L1 at 2/4/8/16 halfturn horizons, while 16-step predicted-invalid-action fraction remains worse (3.58% vs 2.51%); production enablement therefore stays false.

## Current M11 uncertainty / selector / survival / temperature evidence

- Uncertainty calibration: ensemble disagreement is informative for absolute error but not learned-vs-generic underperformance, so runtime uncertainty fallback remains disabled.
- Strict 64/16/20 selector experiment: final test rejects selector enablement because multi-step L1 is slightly worse than the pure ensemble and invalid-action rate remains above generic.
- Stochastic survival-distribution gate: learned force-L1 remains better than generic, but observed-action survival/validity coverage is below generic at longer horizons; production enablement remains false.
- Leakage-safe positive-residual temperature calibration selects scale **0.0** because no candidate clears the joint accuracy/coverage hard gate.
- Committed M11 report JSONs are reproduced and verified by the permanent Full suite.

## Windows self-hosted exhaustive main-front validation — 2026-08-10

Temporary validation PR #5 / Actions run `31417309122` executed the accumulated main-front test debt on the Windows self-hosted runner.

```text
MSVC Debug configure/build:                    PASS
hwm-planner-tests Debug:                       PASS
held-out planner validity:                     120/120 PASS, 0 invalid recommendations
pairing/auth integration:                      PASS
stale cancellation integration:                PASS
live binding integration:                      PASS
WebSocket integration:                         PASS
Python pytest:                                 61/61 PASS
TypeScript typecheck / extension build:        PASS / PASS
MSVC Release build + main-front CTest:          PASS
planner-demo 5000:                             PASS
M11 multistep / uncertainty / selector / survival commands: PASS / PASS / PASS / PASS
```

The main-front C++ claim excludes the ability-owned monolithic `hwm-tests` executable. Windows/MSVC exposed a dangling-pointer Mighty Slam test, a misspelled Frightful Aura ability code, and then a later `0xc0000409` termination; those defects are handed to the independent ability branch rather than patched from main. Permanent main CI reflects this ownership split in `bb8404606621966d8c688f22e93c6ce35dd695ea`.

M11 uncertainty reproducibility was then repaired in `8dc9dc5b81db936089c7764fafb9c22cb79505a3`. Dedicated run `31419316512` passed 7 targeted tests and produced byte-for-meaning identical JSON objects across two independent full-corpus processes. Runtime uncertainty fallback remains disabled.
