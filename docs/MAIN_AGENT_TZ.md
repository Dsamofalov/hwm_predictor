# MAIN agent TZ — current handoff

**Updated:** 2026-08-13  
**Role:** binding short-form handoff for the `main` development lane.  
**Precedence:** read `SPEC.md`, `docs/MAIN_FRONT_STATUS.md`, `TESTS_CANON.md`, `docs/LIVE_VALIDATION.md`, and `changelog.md`. Ability mechanics remain independently owned by `ability`.

## Authoritative repository checkpoint

- Repository: `Dsamofalov/hwm_predictor`.
- Branch: `main`.
- Current validated functional SHA: `49bbe98e00cbee27d437c26cd93b2127a18dc8b8` — `fix: retry live replanning after transport failure`.
- Hosted atomic Windows CI: run `31693648818` — **Core PASS + Full PASS**.
- Geometry Evidence: run `31693648857` — **PASS** on the same SHA.
- Supported product/CI platform: Windows 10/11 x64 + MSVC; permanent hosted validation runs on `windows-2022`.

## Exact current decoder / corpus checkpoint

- C++ full corpus: **855/866 structural-ready**, **11 structural-invalid**, **798/866 semantic-safe**, low-level `with_unknown = 0`.
- Python final overlaps: **15 battles / 15 pairs**.
- Held-out observed basic-action representability: **5394/5481 = 98.4127%**.
- Exact residuals: **87** = 35 `melee_destination_not_reachable` + 49 `target_not_adjacent_after_move` + 3 `move_not_reachable`.
- Ownership audit: **21 special-free**, 1 semantically resolved SPECIAL, 65 unresolved SPECIAL. The special-free set has no currently proven safe generic expansion; do not trade invariants for the percentage target.
- Generic melee resolution order remains: radius-1 unique landing -> blocked globally-unique radius-2 landing -> evidence-bounded stationary fallback only for SPECIAL-free, one physical target, same-owner blockers, legal current anchor already adjacent to target. No generic SPECIAL/multi-target/forced-movement fallback.
- Forward action lookahead stops at `f<...>` / `f_en<...>` battle-result boundaries.

## Live closed-loop state

Transport feasibility is proven on authenticated battle `warid=1672746591`: passive official `battle.php` XHR exposed `turns=>3 + s=...`; after one manual move an incremental `turns=>4...` arrived; frequent exact `t=<digits>` frames are heartbeat/no-op.

Current shipped-path contracts are now permanently regression-tested:

1. production-shape `snapshot -> heartbeat -> incremental` passes real HTTP `/capture`;
2. heartbeat does not publish a canonical revision or cancel/replan search;
3. recommendation is bound to `battle_id`, `state_revision` and `state_hash`;
4. service-worker replanning identity is `(battle_id, revision, state_hash)`, not revision alone;
5. daemon restart may reuse a numeric revision without suppressing a different canonical state;
6. transport/auth `/recommend` failure releases only the same claimed key so reconnect may retry it; an obsolete failure cannot unlock a newer claimed state;
7. `not_ready`, `finished` and `stale` are safe semantic non-results, not transport retry triggers.

**Still open:** the real authenticated active-PvE smoke through the actually loaded MV3 extension and daemon. M01/M14 are not COMPLETE until `docs/LIVE_VALIDATION.md` shows capture -> recommendation -> manual move -> newer semantic capture -> stale cancellation/exact re-root -> new recommendation. Revision is monotonic only inside one daemon session; cross-restart identity is composite.

Network `battle.php` remains primary truth. Runtime `stage.pole.obj` / `nowturn` is targeted cross-check/fallback only for a concretely missing field. No broad runtime scraper and no gameplay automation.

## Mandatory next work order

1. Execute and retain metadata-safe evidence for the real authenticated production closed-loop smoke.
2. Continue decoder/legal closure toward **>=99.9%** from the exact 87-residual inventory, only with evidence-backed generic corrections. Do not duplicate ability-owned mechanics.
3. Keep M11 learned dynamics production-disabled until joint multi-step accuracy + observed-action survival/validity gates pass.
4. Continue M13 opponent/chance/search calibration only after correctness closure, preserving stochastic outcomes, transpositions, revision cancellation, exact re-root and hash/structure guards.
5. After stable live acquisition, run live-state and hard-PvE human-in-loop evaluation/calibration.

## Testing contract

`TESTS_CANON.md` is mandatory and already reflected by the permanent main workflow: freeze exact inventories, build once/fan out, run independent meaningful units in parallel, preserve exact map/reduce semantics, and use strict aggregate failure. Do not reintroduce monolithic Core/Full execution merely for historical compatibility. CI waiting does not block independent useful work, but no pending run may be called PASS.

## Guardrails

- No autoclicking, game-command automation, or extra high-frequency HeroesWM polling.
- Do not weaken structural invariants or semantic safety gates to improve metrics.
- Do not enable learned dynamics from mean-error improvement alone.
- Do not rewrite ability-owned semantics without new raw/server evidence and ability-owned acceptance.
