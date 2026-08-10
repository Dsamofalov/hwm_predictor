# Main development front checkpoint

Updated: 2026-08-10

This file tracks the non-ability lane while creature abilities are developed independently on branch `ability` / draft PR #1.

## Completed in the current main-front pass

### M16 local pairing/authentication

Functional commit: `a1012a73146fc9c832a31b7d48cc38464ddc8a76`

- persistent 256-bit local bearer token;
- explicit per-process six-digit pairing code;
- private API requires `Authorization: Bearer ...`;
- public surface limited to health/version/preflight/pairing;
- pairing failure lock after ten invalid codes per process;
- extension stores bearer token in `chrome.storage.local` and clears it on 401;
- token remains valid across daemon restart when the same local token file is used;
- permanent CI regression: `scripts/test_local_api_auth.py`.

### M03/M14 revision-bound stale-search cancellation

Functional commit: `ed20ee1f1bdb88200c65f74f13e60dc25a47f1b7`

- monotonic `SessionStore` revision;
- atomic state + revision snapshot for planning;
- planner cooperative cancellation callback polled between simulations;
- `/recommend` returns structured `stale` response when a newer observed revision appears;
- revision invalidation is stronger than hash-only invalidation and is regression-tested with an identical republished state;
- extension recommendation epoch prevents an older in-flight result from overwriting a newer one;
- side panel verifies recommendation `state_hash` against current daemon state before rendering;
- permanent CI regression: `scripts/test_stale_cancellation.py`.

### M01/M14 live closed-loop trace and binding

Functional commit: `21927bdc6b528a06018bad95e63540c9ce02d9fd`

- capture response exposes canonical `revision` and `state_hash`;
- successful recommendation exposes `state_revision`, `state_hash` and `battle_id`;
- bounded metadata-only extension trace for capture/planning/runtime-probe stages;
- raw payloads, full URLs and bearer tokens are excluded from trace storage;
- side panel exposes the latest trace for active-battle debugging;
- permanent CI regression: `scripts/test_live_binding.py`;
- active-battle execution procedure and pass criteria: `docs/LIVE_VALIDATION.md`.

## CI gate

The standard CI now requires, in addition to C++/Python/TypeScript suites:

1. local pairing/auth integration;
2. stale-search cancellation integration;
3. live recommendation revision/hash binding contract.

CI commit carrying all three gates: `676da42b754ee9d1409cc27e8ad1dfec26d17e6c` — PASS.

## Current main-lane decision gate

### M16 authenticated WebSocket streaming

The local daemon now exposes an authenticated `ws://127.0.0.1:<port>/ws` state stream. The bearer is carried as `Sec-WebSocket-Protocol: hwm-bearer.<token>` rather than in the URL. The daemon pushes canonical status immediately and whenever SessionStore revision changes, plus a 20-second heartbeat. The MV3 service worker consumes this stream, stores the last daemon status, deduplicates replanning by revision and falls back to HTTP status only when streamed status is stale/unavailable.

The next correctness step is a real authenticated active-battle smoke validation using `docs/LIVE_VALIDATION.md`.

Do **not** claim M01/M14 complete before that run. The current code proves the local pipeline and safety contracts against deterministic integration fixtures, not HeroesWM's live authenticated client.

If the real battle trace shows network capture is sufficient, keep network payload as the primary path. If it proves a missing canonical/legal-action field, use the existing metadata-only runtime structure probe to identify the smallest explicit runtime-object adapter. Do not implement a broad runtime scraper speculatively.

After stable live acquisition is proven, main may continue with the next original-TZ gates that do not conflict with `ability`, notably WebSocket streaming, persistent tree re-root/transpositions/opponent branching, and later live/hard-PvE evaluation.

## 2026-08-10 final handoff update

- Authenticated WebSocket functional commit: `68345f0afc89ed0e17884042592fb08b6edd83be`.
- Historical CI checkpoint: commit `7353e1ddcf17f27e981cac52f2b1e38f5545881e` passed both Linux and Windows/MSVC. This is retained only as historical verification; Linux is no longer a supported CI/product platform after the Windows-only migration below.
- Next main-planner correctness issue identified during audit: `planner.cpp` currently gives each action edge one child while `sim_.apply(..., roll)` is stochastic. Before persistent tree reuse, split sampled outcomes by `state_hash`, share equal states via a transposition table, and regression-test that different sampled outcomes do not reuse a node initialized from the first outcome's legal actions.
- Stop point for this agent: do not begin that M13 patch in this checkpoint; hand off from here.

## M13 stochastic search correctness and persistent re-root

Functional commits:

- `d06217fd4aa531aa0e49cf7c8c2495a5ab0ca5e4` — per-action stochastic outcomes keyed by canonical state hash + per-search transpositions.
- `135826c05d7f9b3d44e165ef6732bb6ede89a4c4` — persistent planner graph and exact observed-state re-root with reachable-subgraph pruning.
- `6edec4d8360169060d280cd07a6e63de9c0fda89` — conservative static structure fingerprint guard for safe reuse.
- `33aaea0cac7549972e4be93bf495d0a9dca7f301` — RFC6455 integration harness buffering fix exposed by the new verification run.
- `56190d72d133d325cf5a71f369339b82ba2f3aa1` — canonical hash now includes scheduler recency (`last_acted_seq`) so transition-semantically different next-actor histories cannot collide in the transposition table.

Current behavior: a stochastic action may retain multiple canonical outcome children; equal canonical outcome hashes share one node. Across observed revisions, reuse occurs only for an exact predicted hash in the same non-empty battle/perspective and matching board/static-structure fingerprint. Otherwise search starts fresh. Revision change still cancels stale in-flight search. `NextActorModel` recency is now part of canonical transposition identity; decoder and simulator both stamp the completed actor before incrementing `decision_seq`, so observed and predicted scheduler histories use the same counter convention.

Verification: standard CI run `31380236279` PASS on Linux and Windows for the original M13 outcome/re-root/fingerprint set. The scheduler-recency follow-up has a dedicated regression in `hwm-planner-tests`, but draft PR #4 run `31393097068` did not execute any job steps; it is therefore committed but not claimed CI-verified yet. The immediate product gate remains the real authenticated active-battle smoke test; M01/M14 are not promoted to COMPLETE by planner work. The next autonomous main correctness front is attribution of the 19 structural-invalid finals and legal-action representability improvement toward >=99.9%.

## M11 multi-step damage-residual gate

Functional evidence commit: `45581ae7d0f844f67797c590c3ed529390b76f1f`. The existing damage residual now has a reproducible five-member ensemble evaluation at 2/4/8/16 held-out halfturn horizons. Mean force-L1 beats the generic baseline at all horizons, but long-horizon invalid-action drift is worse, so runtime learned-world enablement remains disabled. M11 stays PARTIAL / EXPERIMENTAL.

## Current M11 / evaluation checkpoint

M11 evidence commits `45581ae7d0f844f67797c590c3ed529390b76f1f`, `ef35d28aca6a044019896e3ecf6c4d4b52113d6f`, `7c5a4634da26b99ee5b74f824f98fe5dcce4dc5b` and `70c7b3a61058ca9e3cfc883cb826ac2b1ef15f4b` now cover deterministic multi-step ensemble drift, uncertainty calibration, a strict 64/16/20 fallback-selector test, and a distributional survival gate aligned with the simulator's stochastic physical-damage roll. Mean HP/force drift improves strongly, while valid-observed-action coverage remains modestly below generic and the gap grows with horizon; production learned dynamics therefore remain disabled and M11 stays PARTIAL / EXPERIMENTAL.

The stochastic survival gate uses 692 train / 174 chronological held-out battles. Learned vs generic mean force-L1 is **0.01149 vs 0.01697** at 2 steps and **0.05028 vs 0.08178** at 16 steps. Learned vs generic valid-observed-action coverage is **98.789% vs 98.919%** at 2 steps and **96.349% vs 97.493%** at 16 steps. This replaces the earlier deterministic member-count interpretation as the primary survival/validity diagnostic; the next calibrated experiment targets only positive log-residual corrections so negative damage corrections are preserved.

Planner replay gate commit `cde38a5a89684ff2691c80eeb3583195ffa31758` permanently checks 120 safe heldout states across 109 battles and records 0 invalid recommendations. It has now been moved from Linux CI into the Windows self-hosted CI job. Replay acceptance is closed; the real authenticated active-battle smoke in `docs/LIVE_VALIDATION.md` remains mandatory before the live product loop is declared complete.

## Windows-only product and CI platform

Platform migration commits:

- `31c25740d4f6cbf27d802ad4e478993b7571f54f` — collapsed the previous Linux-full + Windows-partial matrix into one Windows self-hosted job while preserving every standard gate.
- `6bd81ce9fabc6fa29fb0e3f9694c988ea69e7b8c` — finalized runner labels `self-hosted, windows, x64, hwm-windows`, added manual `workflow_dispatch`, same-branch stale-run cancellation, and blocked external-fork PR execution on the self-hosted machine.
- `09237be777671fa3697da05b1813b57e5fc19f78` — updated the public development instructions to declare Windows 10/11 x64 as the sole supported product/CI platform and converted active examples to PowerShell/Windows paths.

Current standard CI executes C++/CTest, the 120-state planner replay gate, all four daemon integration gates, Python pytest, TypeScript typecheck and extension build on Windows/MSVC. Historical Linux PASS records above remain evidence for older trees only; they are not a continuing support commitment.

The new workflow is intentionally queued until a repository-level Windows x64 self-hosted runner carrying the custom `hwm-windows` label is registered and online. No PASS claim is made for the migration commits until that runner executes the workflow.
