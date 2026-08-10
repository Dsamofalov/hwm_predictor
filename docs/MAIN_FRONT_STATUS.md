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
- Standard CI now includes WebSocket streaming and a Windows/MSVC job. CI commit `7353e1ddcf17f27e981cac52f2b1e38f5545881e`: **PASS** on both Linux and Windows; Windows executes C++ build/CTest plus pairing, stale cancellation, live binding and WebSocket daemon integrations.
- Next main-planner correctness issue identified during audit: `planner.cpp` currently gives each action edge one child while `sim_.apply(..., roll)` is stochastic. Before persistent tree reuse, split sampled outcomes by `state_hash`, share equal states via a transposition table, and regression-test that different sampled outcomes do not reuse a node initialized from the first outcome's legal actions.
- Stop point for this agent: do not begin that M13 patch in this checkpoint; hand off from here.

## M13 stochastic search correctness and persistent re-root

Functional commits:

- `d06217fd4aa531aa0e49cf7c8c2495a5ab0ca5e4` — per-action stochastic outcomes keyed by canonical state hash + per-search transpositions.
- `135826c05d7f9b3d44e165ef6732bb6ede89a4c4` — persistent planner graph and exact observed-state re-root with reachable-subgraph pruning.
- `6edec4d8360169060d280cd07a6e63de9c0fda89` — conservative static structure fingerprint guard for safe reuse.
- `33aaea0cac7549972e4be93bf495d0a9dca7f301` — RFC6455 integration harness buffering fix exposed by the new verification run.

Current behavior: a stochastic action may retain multiple canonical outcome children; equal canonical outcome hashes share one node. Across observed revisions, reuse occurs only for an exact predicted hash in the same non-empty battle/perspective and matching board/static-structure fingerprint. Otherwise search starts fresh. Revision change still cancels stale in-flight search.

Verification: standard CI run `31380236279` PASS on Linux and Windows. The immediate product gate remains the real authenticated active-battle smoke test; M01/M14 are not promoted to COMPLETE by planner work. The next autonomous main correctness front is attribution of the 19 structural-invalid finals and legal-action representability improvement toward >=99.9%.

