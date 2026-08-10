# Test report — HeroesWM Solver 0.3.0

**Дата:** 10.08.2026

## Automated build/test snapshot

```text
C++ incremental Debug build:            PASS
C++ CTest:                              1/1 PASS (100%)
Local API pairing/auth integration:     PASS
Stale-search cancellation integration:  PASS
Live recommendation binding contract:   PASS
WebSocket revision streaming:            PASS
Windows/MSVC C++ + daemon integrations:     PASS
Python pytest:                          42/42 PASS
TypeScript typecheck:                   PASS
Extension build:                        PASS
```

The snapshot above is enforced by the standard GitHub CI. Pairing/auth, stale cancellation and live binding passed together in `676da42b754ee9d1409cc27e8ad1dfec26d17e6c`; WebSocket streaming is additionally covered by `scripts/test_websocket_stream.py` and is promoted to the standard CI in the follow-up CI wiring commit.

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
representable by current generator:    5,373
coverage:                              98.03%
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

## Planner regression

Latest Release real-state evaluation (`planner-eval-v6-release.json`):

```text
held-out states:           20
low budget:                300 simulations
high budget:               1200 simulations
recommendation success:    20/20 low, 20/20 high
action-type stability:     100%
exact-action stability:    90%
avg low time:              79.4 ms
avg high time:             363.7 ms
```

These numbers are a controlled held-out replay-state regression, not a live win-rate benchmark.

## Not validated in this environment

1. Active authenticated battle capture/replanning in the user's Chromium session. The metadata-only closed-loop trace and `docs/LIVE_VALIDATION.md` are ready for this gate, but the real live exercise has not yet been claimed as complete.
2. Hard-PvE human-in-loop win-rate uplift.
3. Full learned dynamics ensemble / ONNX Runtime C++ production path.

## M13 stochastic outcome / persistent re-root verification

Functional commits `d06217fd4aa531aa0e49cf7c8c2495a5ab0ca5e4`, `135826c05d7f9b3d44e165ef6732bb6ede89a4c4`, and `6edec4d8360169060d280cd07a6e63de9c0fda89` add a dedicated `hwm-planner-tests` target covering distinct stochastic outcome nodes/legal sets, equal-hash transpositions, exact persistent root reuse, reachable-subgraph pruning, battle reset, and static-structure mismatch reset. WebSocket harness commit `33aaea0cac7549972e4be93bf495d0a9dca7f301` handles coalesced handshake/frame bytes without weakening protocol checks. Standard CI run `31380236279`: PASS; Linux CTest 2/2 plus all daemon integrations, Python tests, TypeScript and extension build passed; Windows current-MSVC build/test passed.

