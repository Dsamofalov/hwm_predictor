# MAIN agent TZ — current handoff

**Updated:** 2026-08-13  
**Role:** authoritative short-form addendum for the `main` development agent.  
**Precedence:** read `SPEC.md`, `docs/MAIN_FRONT_STATUS.md`, `TESTS_CANON.md`, `docs/LIVE_VALIDATION.md`, and `changelog.md` first. Where this file contains a newer checkpoint or an explicit next-step instruction, this file is the binding handoff for the main lane until the canonical long-form SPEC/status mirrors are synchronized again.

## Repository / ownership

- Repository: `Dsamofalov/hwm_predictor`.
- Main development branch: `main`.
- Current functional `main` HEAD at handoff: `3b8131692365d250d96be203836bd36192f1ea4a` — `fix: stop final melee lookahead at battle result`.
- Last fully authoritative hosted standard Windows checkpoint before that geometry patch: functional SHA `3c31ed21eb4f1955c397aef48bc62727a3281b5b`, standard run `31680022438` — **Core PASS + Full PASS**.
- Ability work remains independently owned by branch `ability`; do not duplicate or casually rewrite ability-owned semantics in `main`. Use the current ability status/docs and atomic Ability CI as the acceptance source for new ability mechanics.

## What changed after the last fully hosted standard checkpoint

### Geometry / decoder

The generic decoder lane received one more evidence-bounded SPECIAL-free melee correction.

Functional SHA: `3b8131692365d250d96be203836bd36192f1ea4a`.

The patch:

1. keeps the existing radius-1 nearby unique landing resolver strongest;
2. keeps the existing blocked + globally unique radius-2 landing resolver second;
3. only after those fail, permits a stationary fallback when all of the following are true:
   - the decision is SPECIAL-free;
   - the physical attack has exactly one damage target;
   - the raw actor marker is impossible because it collides only with same-owner live board stacks;
   - the actor's current canonical anchor is legal;
   - the actor is already adjacent to the sole damage target;
4. never turns this into a generic SPECIAL, multi-target, forced-movement, or arbitrary blocked-marker heuristic;
5. stops forward damage/SPECIAL lookahead at `f<...` / `f_en<...` battle-result boundaries so terminal result text is not misread as part of the current action.

Permanent exact regressions include:

- train final-overlap case `1625534409`, decision `82`, actor `22`;
- held-out representability case `1632855461`, decision `71`, actor `15`;
- existing radius-1/radius-2 and shooter-marker regressions remain in place and must continue to pass.

The temporary validation/publish branch `agent/stationary-friendly-marker-20260813` is still present. Its final publish workflow run `31684482264` completed successfully and only pushed the functional files to `main` after targeted Python geometry tests, C++ protocol tests, full-corpus structural budget, and Python geometry/overlap non-regression checks passed. Because the functional `main` push was performed with workflow credentials, the normal standard Windows Core/Full workflows did **not** run automatically on SHA `3b813169...`.

### M11 evidence reproducibility

Functional SHA `3c31ed21eb4f1955c397aef48bc62727a3281b5b` canonicalizes selector quantile threshold candidates to the existing 12-decimal evidence boundary before selection. This fixes the exact-evidence long binary64 tail without weakening `verify_m11_evidence.py` or enabling learned dynamics. Standard hosted run `31680022438` is Core/Full PASS. Production learned dynamics remains **disabled**.

## Mandatory first actions for the next main agent

1. **Validate current main on the authoritative Windows pipeline before claiming the new geometry checkpoint.** Run/trigger the standard hosted Windows Core + Full gates on the current main tree containing `3b813169...` (docs-only handoff commits may sit on top; that is fine). Do not treat the successful temporary Ubuntu publish workflow as a substitute for the supported Windows product/CI gate.
2. If Full fails, diagnose the exact failing gate. In particular, decoder-state changes can make committed M11 evidence stale; do not weaken exact verification and do not blindly refresh evidence unless the evaluator deterministically proves that only the committed evidence representation changed.
3. Re-run the exact geometry audits and record the post-`3b813169...` numbers instead of inferring them from the two fixed regressions:
   - C++ final structural-ready / structural-invalid budget;
   - Python final overlap battles/pairs;
   - held-out observed basic-action representability and exact residual count;
   - semantic-safe final count if changed.
4. Only after the current main functional tree is validated and any required evidence-only refresh is complete, **delete temporary branch `agent/stationary-friendly-marker-20260813`**. Before deletion, confirm that all useful functional/evidence changes are already on `main`. Do not delete other `agent/*` branches merely because they look temporary; other agents may own them.
5. Update `SPEC.md`, `HeroesWM_Solver_TZ_Status_0.3.0.md`, `docs/MAIN_FRONT_STATUS.md`, and `changelog.md` with the exact validated metrics and authoritative run IDs after the Windows verdict. This short-form TZ is intentionally conservative and does not invent post-patch corpus totals before that audit.

## Main-lane priorities after cleanup

Continue development autonomously in this order unless new evidence changes the dependency graph:

1. **Production active-battle closed-loop gate.** Transport feasibility is already proven. The remaining product acceptance is the real shipped path: `MV3 passive capture -> daemon -> canonical revision/hash -> recommendation -> manual move -> next semantic revision -> stale cancellation/re-root -> next recommendation`. Exact `t=<digits>` heartbeat frames remain revision-neutral. Network `battle.php` is primary truth; runtime projection is targeted cross-check/fallback only.
2. **Decoder/legal correctness toward >=99.9% held-out observed-action representability.** Use the published exact residual/overlap evidence to select narrow generic geometry classes. Do not absorb SPECIAL/multi-target/forced-movement mechanics into generic fallback logic.
3. **M11 learned dynamics only behind joint accuracy + survival/validity gates.** Do not enable runtime selector/residual/uncertainty paths while current evidence rejects production enablement.
4. **M13 search quality after correctness closure:** stronger explicit opponent/chance branching, calibration, and measured quality/latency improvements without breaking stochastic outcome separation, transpositions, revision cancellation, exact re-root, or structure/hash guards.
5. **Evaluation:** after stable production live acquisition, run live-state cross-validation and hard-PvE human-in-loop quality/win-rate/calibration work.

## Testing contract

`TESTS_CANON.md` is mandatory. Maximize atomic parallelization without sacrificing correctness:

- freeze exact test inventories;
- shard independent cases aggressively;
- preserve exact map/reduce semantics and complete inventory coverage;
- build once / fan out where possible;
- CI waiting must not block unrelated evidence work;
- never claim a pending or unsupported-platform run as authoritative PASS.

Supported product/CI platform remains Windows 10/11 x64 + MSVC; GitHub-hosted `windows-2022` is the permanent standard CI environment.

## Guardrails

- No auto-clicking or game-command automation.
- No extra high-frequency HeroesWM polling in the primary path.
- Old historical parser/state dumps are not ground truth.
- Do not weaken structural invariants to improve a metric.
- Do not hide unknown/semantic uncertainty.
- Do not enable learned dynamics because mean error improved if observed-action survival/validity is worse.
- Do not rewrite closed ability semantics without new raw/server evidence and the ability-owned acceptance path.
