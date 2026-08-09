# Test report — HeroesWM Solver 0.3.0

**Дата:** 09.08.2026

## Automated build/test snapshot

```text
C++ incremental Debug build: PASS
C++ CTest:                  1/1 PASS (100%)
Python pytest:              39/39 PASS
TypeScript typecheck:       PASS
Extension build:            PASS
```

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
exact_search:           81
exact_targeting:        11
partial_exact:          18
modeled_proc:           8
modeled_collateral:     5
modeled_kill_trigger:   2
unresolved:             78

held-out sampled player states: 1748
risk mean:              0.23886
risk p50:               0.22799
risk p90:               0.39780
risk p99:               0.54688
```

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

1. Active authenticated battle capture/replanning in the user's Chromium session.
2. Windows MSVC execution (source/tasks/scripts supplied; current validation environment is Linux).
3. Hard-PvE human-in-loop win-rate uplift.
4. Full learned dynamics ensemble / ONNX Runtime C++ production path.
