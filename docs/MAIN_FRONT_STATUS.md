# Main development front checkpoint

Updated: 2026-08-13

This file tracks main-owned correctness/search/runtime work. Ability mechanics retain separate evidence ownership, while the validated ability snapshot and atomic Ability Windows workflow are already integrated into `main`.


## 2026-08-13 authoritative checkpoint

- Current functional `main` SHA: `49bbe98e00cbee27d437c26cd93b2127a18dc8b8` (`fix: retry live replanning after transport failure`).
- Hosted atomic Windows CI run `31693648818`: **Core PASS + Full PASS** on `windows-2022`; strict aggregate jobs passed after exact C++/pytest inventories, independent runtime cases, planner gates, structural budget and M11 reducer completed.
- Geometry Evidence run `31693648857`: **PASS** on the same SHA.
- Exact full-corpus structural checkpoint: **855/866 structural-ready**, **11 invalid finals**, **798/866 semantic-safe**.
- Exact held-out observed basic-action representability: **5394/5481 = 98.4127%**; residuals **87** = 35 melee-destination-unreachable + 49 target-not-adjacent-after-move + 3 move-unreachable. Python final overlap inventory is **15 battles / 15 pairs**. Only 21 residuals are SPECIAL-free; no safe generic expansion is currently proven for them.
- Live deterministic boundary is stronger than the previous checkpoint: scrubbed production-shape snapshot/heartbeat/incremental traffic now passes through real HTTP `/capture`; exact `t=<digits>` heartbeat is revision-neutral; recommendation binding is checked against canonical state.
- Extension replanning dedupe is keyed by `(battle_id, revision, state_hash)`, preventing daemon-restart numeric-revision collisions. Transport/auth failure releases only its own scheduling claim so reconnect can retry the same canonical state without allowing an obsolete failure to unlock a newer state.
- Numeric revision is monotonic only within one daemon session. It is **not** a global cross-restart identity.
- M11 production learned dynamics remains disabled despite Full/evidence PASS.
- Remaining product blocker: real authenticated shipped MV3 -> daemon -> recommendation -> manual move -> next semantic revision -> stale cancellation/exact re-root -> new recommendation smoke per `docs/LIVE_VALIDATION.md`.

## 2026-08-12 historical checkpoint

- Decoder functional commit `1c5a2b3478e7dacf0ebc714a4fb83246fed3b3f8` conservatively recovers unique nearby **single-target** melee position hints in both Python and C++; multi-target and SPECIAL decisions keep the guarded path.
- Full corpus: **852/866 structural-ready**, **14 invalid finals**, **795/866 semantic-safe**. All 14 final structural failures are `overlap` only (16 pairs total).
- Held-out observed basic-action representability: **5392/5481 = 98.376%**, exact residual inventory **89**; the promoted change removed one held-out failure and added/changed none.
- Generic follow-up probes rejected broader non-colliding melee recovery (downstream regressions) and unreachable-shooter marker expansion (zero delta). Remaining generic MOVE failures have no unambiguous geometry-only correction.
- Residual ownership audit: **66/86** remaining melee representability failures contain SPECIAL records; the two special-free multi-target cases are tied to intrinsic multi-target abilities. Do not absorb those into generic decoder heuristics.
- First standard rerun `31622628256` exposed only stale M11 selector committed evidence after replay-state changed. Evidence-only commit `16998598ce3dc282bef76a9b29b27e83fba8bdf9` refreshed that report on `windows-2022`; follow-up standard run `31624580974` is **Core PASS + Full PASS**. Atomic Ability run `31622630092` is **PASS**.
- Live transport feasibility is now independently proven on authenticated active PvE battle `warid=1672746591`: a passive XHR hook saw a **12,686-byte** `battle.php` semantic payload with `turns=>3` + `s=...`, then after one manual move a **41-byte** incremental `turns=>4:m0080501i0080100C001000000;`; runtime `lastturn` changed **3 -> 4**. The same short capture saw **28** `t=950` heartbeat/no-op responses.
- Existing user-side browser automation provides additional read-only engine evidence: live units are read from `stage.pole.obj` / `stage[war_scr].obj` with `owner`, grid `x/y`, `nownumber`, `nowhealth`, `nowturn`, while `scr_x/scr_y` are render/Pixi coordinates. This is a targeted runtime cross-check/fallback surface, not a reason to replace network protocol truth or import auto-action logic.
- The immediate product blocker is therefore narrower than before: raw live transport is no longer unknown, but the **production** MV3 -> daemon -> canonical revision/hash -> recommendation -> manual move -> next revision -> stale cancellation/re-root -> next recommendation smoke in `docs/LIVE_VALIDATION.md` is still mandatory before M01/M14 can be COMPLETE.


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

### Live engine evidence — 12.08.2026

This evidence was collected outside the project checkout because the project was not installed on the user's battle machine. It therefore closes **protocol feasibility**, not the production extension/daemon gate.

- `war.php?warid=1672746591` issued client XHR `GET /battle.php?warid=1672746591` during the active authenticated fight.
- Passive interception made no extra HeroesWM request and captured a semantic current-state response containing `turns=>3` and `s=M001...M008...`.
- One manual user action was followed by a compact incremental `turns=>4:...` response; client global `lastturn` advanced from 3 to 4.
- Frequent `t=950` responses are transport no-ops/heartbeats. They must be revision-neutral and must not trigger planning/cancellation/replanning.
- Network remains primary truth. A runtime adapter, if needed, should target `stage.pole.obj` / `stage[war_scr].obj` plus minimal turn markers. Grid `x/y` are semantic positions; `scr_x/scr_y` are render-space coordinates useful only for diagnostics/overlay mapping.
- Do not commit the raw user capture as-is: it contains battle chat/tooltips/user-facing metadata. A future regression fixture must be scrubbed down to protocol blocks required for the test.

## CI gate

The standard CI now requires, in addition to C++/Python/TypeScript suites:

1. local pairing/auth integration;
2. stale-search cancellation integration;
3. live recommendation revision/hash binding contract.

CI commit carrying all three gates: `676da42b754ee9d1409cc27e8ad1dfec26d17e6c` — PASS.

## Current main-lane decision gate

### M16 authenticated WebSocket streaming

The local daemon now exposes an authenticated `ws://127.0.0.1:<port>/ws` state stream. The bearer is carried as `Sec-WebSocket-Protocol: hwm-bearer.<token>` rather than in the URL. The daemon pushes canonical status immediately and whenever SessionStore revision changes, plus a 20-second heartbeat. The MV3 service worker consumes this stream, stores the last daemon status, deduplicates replanning by canonical `(battle_id, revision, state_hash)` identity, safely releases the same-key claim after transport/auth failure for reconnect retry, and falls back to HTTP status only when streamed status is stale/unavailable. Numeric revision is session-local and is not treated as a global cross-restart identity.

The next correctness step is a real authenticated **production closed-loop** validation using `docs/LIVE_VALIDATION.md`. The old uncertainty “does active `battle.php` transport exist and is it interceptable?” is closed by the 12.08.2026 live evidence; the remaining gate is whether the shipped extension/daemon pipeline consumes the semantic payload correctly and advances revision/recommendation after a manual move.

Do **not** claim M01/M14 complete before that run. The current code proves the local pipeline and safety contracts against deterministic integration fixtures, while the external live capture proves HeroesWM transport/progression. What is still missing is the same evidence through the actual MV3 -> daemon -> decoder -> planner path.

Primary implementation decision is now explicit:

- keep `battle.php` network payload as authoritative primary source;
- classify pure `t=<digits>` heartbeat/no-op frames as revision-neutral;
- keep the now-permanent scrubbed live-derived `snapshot -> heartbeat -> incremental turn delta` HTTP regression green;
- if a concrete canonical field is missing or disagrees, use a **targeted** runtime projection from `stage.pole.obj`/`nowturn` and report mismatch diagnostically;
- never build a broad runtime scraper speculatively and never use `scr_x/scr_y` as canonical board coordinates.

After stable production live acquisition is proven, main continues with evidence-backed decoder closure, M11 production gating and M13 opponent/chance/search calibration, followed by live/hard-PvE evaluation.

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

Verification: standard CI run `31380236279` PASS on Linux and Windows for the original M13 outcome/re-root/fingerprint set. The scheduler-recency follow-up has a dedicated regression in `hwm-planner-tests`, but draft PR #4 run `31393097068` did not execute any job steps; it is therefore committed but not claimed CI-verified yet. The immediate product gate remains the real authenticated active-battle smoke test; M01/M14 are not promoted to COMPLETE by planner work. The next autonomous main correctness front is attribution of the 15 remaining structural-invalid finals and legal-action representability improvement toward >=99.9%.

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

That self-hosted migration checkpoint is historical. Permanent CI now executes Core and Full on GitHub-hosted `windows-2022`; the custom `hwm-windows` runner label is no longer part of the active contract.

## Executed Windows main-front validation checkpoint

The Windows self-hosted runner is now proven executable rather than merely configured. Temporary exhaustive run `31417309122` passed Debug/Release MSVC main-front C++, the permanent 120-state planner gate (120/120 valid, 0 invalid recommendations), pairing/auth, stale cancellation, live binding, WebSocket, Python 61/61, TypeScript/extension, `planner-demo 5000`, and all four M11 full-corpus evaluator commands.

This run also closes the pending executable verification for the M13 canonical-hash regressions in `hwm-planner-tests`, including scheduler recency and semantic effect-provenance canonicalization.

M11 uncertainty evidence is now reproducible under commit `8dc9dc5b81db936089c7764fafb9c22cb79505a3`: dedicated run `31419316512` passed 7 targeted tests and exact JSON equality across two independent full-corpus processes. The production uncertainty gate remains disabled by evidence.

Permanent main CI commit `bb8404606621966d8c688f22e93c6ce35dd695ea` excludes the independently owned `hwm-tests` executable from the main-front CTest gate while leaving ability validation responsible for its Windows failures. The real authenticated active-PvE browser smoke remains the product-level blocker and is not replaced by replay/integration CI.

## Decoder/legal checkpoint — guarded raw-position handling

- Functional commits: `c22d41678e4054c721f70bd2f1f6abe40830b93c` and `d00c3c73f5c6f618e07d1123a2789c9c1f089016`; synchronized M11 evidence commit: `2843f4e086852688d3188f19b1973306c40ebe7b`.
- `mUUUXXYY` ordinary melee hints are conservatively canonicalized only for physically colliding raw anchors with one unique target-adjacent reachable landing within one Chebyshev cell; ability-owned SPECIAL movement stays excluded.
- Impossible special-free shooter position hints are treated as markers only under guarded stationary-melee or actually-legal ranged conditions (`shots > 0`, no adjacent enemy block).
- Main-owned `hwm-protocol-tests` is now a permanent CTest target separate from ability-owned `hwm-tests`.
- Full-corpus result at the 12.08.2026 checkpoint: **852/866 structural-ready**, **14 invalid finals** (all `overlap`, 16 pairs), **795/866 semantic-safe**; Python replay-final overlap audit remains **17 battles / 17 pairs**.
- Held-out observed basic-action representability: **5392/5481 = 98.376%** (**89** residual failures).
- Full CI permanently enforces `invalid <= 14`; M11 committed evidence was re-synchronized after decoder semantics changed and exact verification passes on run `31624580974`. Production learned dynamics remains disabled.
- Hosted run `31475600960`: **Core PASS + Full PASS**, CTest **2/2**, planner **120/120**, Python **84/84**.
- Next main-owned decoder front: continue corpus-proven discrepancies among the remaining 14 overlap finals and 89 held-out representability residuals; do not absorb SPECIAL/multi-target/forced-movement semantics owned by the ability evidence lane.
