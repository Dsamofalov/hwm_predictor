# Implementation report — HeroesWM Solver 0.3.0

**Дата checkpoint:** 10.08.2026  
**Источник данных:** независимо декодированный raw corpus `init.txt + turns0.txt`; старый 50-бойный parser не используется как ground truth.

## 1. Короткий итог

Проект перешёл от инфраструктурного scaffold к работающему research solver: собран реальный corpus 866 боёв, реализован independent protocol decoder, canonical state, hybrid simulator, ability registry, train-only baseline models и PUCT planner. Offline replay/shadow pipeline детерминирован и проверяется на полном корпусе.

За текущий main-front pass закрыты важные части live plumbing из оригинального ТЗ: explicit local pairing/bearer auth, revision-bound cooperative stale-search cancellation и metadata-only closed-loop trace с binding `capture/recommendation -> revision/state_hash`.

Главный оставшийся продуктовый gate — выполнить подготовленный smoke-test на **реальном активном авторизованном бою**. Полноценный runtime-object fallback должен добавляться только если этот live trace докажет, что network payload не покрывает необходимое состояние/legal actions.

Ability-механики развиваются как отдельный логический модуль внутри `main`: module ownership и Ability CI сохраняются, но отдельная Git-ветка/PR/merge-back workflow больше не используется.

## 2. Текущие метрики

| Метрика | Результат |
|---|---:|
| Raw battles | 866/866 |
| Protocol low-level coverage | 100% |
| Incremental == one-shot final state | 866/866 |
| Final structural-ready | 847/866 |
| Final semantic-safe | 790/866 |
| Held-out non-hero player states structural-ready | 5351/5476 = 97.72% |
| Held-out strict semantic-safe | 4979/5476 = 90.92% |
| Basic action availability when structural-ready | 5338/5351 = 99.76% |
| Held-out observed basic-action representability | 5373/5481 = 98.03% |
| Dataset accepted decisions | 52,357 |
| Creature IDs | 644 |
| Ability codes | 421 |
| Ability Registry exact-search | 85 |
| Ability Registry modeled-proc | 9 |
| Ability Registry unresolved | 78 |
| Held-out ability risk mean / p90 | 0.22431 / 0.37538 |
| Player prior top-1 / top-3 | 70.76% / 93.46% |
| PvE prior top-1 / top-3 | 62.81% / 96.11% |
| Value test Brier / AUC | 0.05176 / 0.9889 |
| Constant value Brier | 0.11891 |
| Damage median abs-log generic -> learned | 0.3574 -> 0.2812 |
| Rare-creature ability transfer | 0.2719 -> 0.2484 |
| Next actor top-1 / top-3 | 32.16% / 65.86% |
| Round-robin next actor top-1 / top-3 | 12.75% / 33.49% |
| Planner real-state regression | 20/20 recommendations |
| Planner action-type stability | 100% |
| Planner exact-action stability | 90% |

Current standard CI additionally enforces three local closed-loop integration contracts: pairing/authentication, cooperative stale-search cancellation and live recommendation revision/hash binding.

## 3. M01–M19

| Module | Status | Что реально есть | Что не закрыто |
|---|---|---|---|
| M01 Browser Bridge | MOSTLY COMPLETE | MV3 passive fetch/XHR capture, content/service-worker bridge, authenticated localhost forwarding, auto replan, bounded metadata-only live trace | real active-battle validation, full runtime-object fallback if network path proves insufficient |
| M02 Protocol Decoder | ADVANCED PARTIAL | independent C++/Python decoder, 100% record coverage, 866/866 shadow determinism | 19 rare structural-invalid finals, unresolved semantics |
| M03 Session | MOSTLY COMPLETE | reset/dedupe/out-of-order, immutable observed state, hash + monotonic revision, atomic snapshots, cooperative stale-search cancellation | persistent search-tree re-rooting by predicted/observed child |
| M04 Knowledge | ADVANCED PARTIAL | 644 creatures, 421 abilities, reference HTML ingestion, explicit Ability Registry support levels | remaining unresolved/high-impact ability semantics; active work continues in the ability module on `main` |
| M05 Corpus | COMPLETE CURRENT DATA | 866/866 raw init+turns, metadata/collector/HAR path | corpus itself intentionally external to GitHub |
| M06 Dataset | MOSTLY COMPLETE | 52,357 accepted decisions, temporal battle split, real features/labels | production learned-dynamics targets/gates |
| M07 Legal Actions | ADVANCED PARTIAL | basic + hero/spell/ability subset, move+attack, large/flyer/shooter mechanics | rare special action families; observed representability still 98.03% vs higher target |
| M08 Opponent Policy | BASELINE COMPLETE | creature-conditioned PvE action-type prior | full candidate-action neural policy |
| M09 Player Prior | BASELINE COMPLETE | real player action-type prior | search distillation/full candidate ranking |
| M10 Value/Risk | ADVANCED BASELINE | battle-balanced P(win), ability-risk integration | quantiles/CVaR production heads |
| M11 Dynamics | PARTIAL | exact transitions + residual/proc/collateral components | full learned world ensemble/multi-step gate |
| M12 Hybrid Simulator | ADVANCED PARTIAL | broad exact mechanics + stochastic models | complete ability/mechanic coverage |
| M13 Search | ADVANCED PARTIAL | PUCT, priors/value/risk, real-state regression, cooperative cancellation | transpositions/tree reuse/full chance modeling |
| M14 Orchestrator | MOSTLY COMPLETE OFFLINE | authenticated capture/session/decode/plan/revision/hash/replan with stale guards | real live active-battle E2E |
| M15 Inference Runtime | PARTIAL | C++ CSV/JSON model loaders, Python/ONNX export scaffold | ONNX Runtime batching/manifest |
| M16 Local API | COMPLETE CURRENT API | loopback HTTP, persistent bearer pairing, authenticated WebSocket revision/status stream, capture/state/status/plan/debug, origin guard, auth/stale/live/WS CI contracts | — |
| M17 UI | PARTIAL/USABLE | side panel, pairing, recommendation/alternatives, auto refresh, stale hash guard, live trace | rich overlay/PV/explanation/live UX QA |
| M18 Training | ADVANCED PARTIAL | real pipelines for policy/value/damage/spell/next-actor/proc/collateral/kill-trigger | unified production NN dynamics/distillation |
| M19 Evaluation | ADVANCED PARTIAL | full corpus check, shadow, legal coverage, model metrics, planner stability, local closed-loop integration gates | real live shadow + hard-PvE human trial suite |

## 4. Ability system

Ability handling is not a flat creature-value heuristic. It is split into:

1. **Exact mechanics** — change legal actions / transition / retaliation / resistances / state lifecycle.
2. **Modeled proc/collateral/kill-trigger** — probability is train-only/held-out gated or otherwise explicitly modeled.
3. **Ability-conditioned damage residual** — used especially for low-support creature IDs.
4. **Ability risk** — unresolved mechanics increase search uncertainty weighted by stack strength.

Latest Ability Registry support counts at this report checkpoint:

```json
{
  "exact_search": 85,
  "exact_targeting": 11,
  "partial_exact": 18,
  "modeled_proc": 9,
  "modeled_collateral": 5,
  "modeled_kill_trigger": 2,
  "dynamic_spellbook": 1,
  "learned_damage": 176,
  "reference_only": 32,
  "identity": 4,
  "unresolved": 78
}
```

Examples already handled include core movement/shooter/large/flyer/retaliation rules; multi-hit; defense penetration/resistances/immunities; Defend/Take Roots/Entrenchment; Stone/Warding/Crippling observed state; Enraged/Pack Enrage; Battle Thirst/Taste of Blood; Mana Drain; Mana Feed; Life Drain; Regeneration; Mighty Slam; modeled Paw Strike ATB/knockback; Blood Frenzy; Organic Armor; Shield Other; Swift Attack; Impervious to Pain; Concentration; Lizard Bite; direct hero spells and several status spells.

Life Drain, Regeneration, Mana Feed and Mighty Slam are `exact_search`; Mana Feed is validated on all 42 observed `Smfd` actions, Mighty Slam on all 32 observed `Smsl` decisions, and Paw Strike has 174/174 observed source-matching I-record ATB-reset evidence while remaining hybrid `modeled_proc` for speculative trigger probability.

Further ability work follows `docs/ABILITY_AGENT_TZ.md` as module-scoped work committed directly to `main`; Ability CI validates the module, with no dedicated ability branch or later merge-back step.

## 5. Current closed-loop safety implementation

### Local pairing

Functional commit `a1012a73146fc9c832a31b7d48cc38464ddc8a76`:

- daemon prints an explicit per-process pairing code;
- private local API requires a persistent bearer token;
- extension stores that bearer locally and clears it on 401;
- wrong codes are rate-limited/locked after repeated failures;
- normal CI starts a real daemon and verifies the contract across restart.

### Stale recommendation prevention

Functional commit `ed20ee1f1bdb88200c65f74f13e60dc25a47f1b7`:

- every canonical publication has a monotonic SessionStore revision;
- planning is bound to an atomic state+revision snapshot;
- planner cooperatively cancels when revision changes;
- extension has an independent recommendation epoch guard;
- side panel checks current state hash before rendering an `ok` result.

The regression deliberately republishes an identical state (same state hash) while search runs, proving revision cancellation is stronger than hash-only post-checking.

### Live trace / binding

Functional commit `21927bdc6b528a06018bad95e63540c9ce02d9fd`:

- capture results expose canonical revision/hash;
- successful recommendations expose state revision/hash and battle ID;
- extension keeps at most 80 metadata-only trace events for capture/planning/runtime-probe stages;
- raw battle payloads, full URLs and bearer tokens are not stored in that trace;
- `scripts/test_live_binding.py` verifies a successful recommendation is bound to current daemon revision/hash.

Manual real-battle procedure and pass criteria are recorded in `docs/LIVE_VALIDATION.md`.

## 6. What is intentionally not claimed

- This is not yet a verified live production advisor: an authenticated active battle has not yet been exercised in the user's Chromium session after the new live instrumentation.
- 847/866 final structural-ready is not 100%; validator remains strict rather than hiding overlaps.
- 98.03% observed basic-action representability is below the stronger legal-action acceptance target.
- A 421-code catalog does not mean 421 exact mechanics; support level is explicit per ability.
- No hard-PvE win-rate uplift is claimed without live human-in-loop trials.
- Full runtime-object fallback is not guessed from offline data; it will be implemented only if live evidence identifies a missing canonical/legal-action field.

## 7. Next gates

1. Execute `docs/LIVE_VALIDATION.md` against a real authenticated PvE battle and preserve the metadata-only trace/status evidence.
2. If network capture is incomplete, implement the smallest evidence-driven runtime-object fallback adapter; otherwise keep network payload as primary truth.
3. Continue high-impact ability work as a dedicated module directly on `main`, preserving corpus/evidence gates and the Ability atomic-CI surface.
4. After stable live acquisition is proven, continue main-only original-TZ work: persistent tree re-root/transpositions/opponent branching.
5. Continue structural/legal-action correctness toward the acceptance targets without weakening strict invariants.
6. Add full learned dynamics ensemble + multi-step divergence gate when the acquisition/correctness prerequisites are satisfied.
7. Run hard-PvE human-in-loop benchmark: win rate, attempts-to-win, invalid action rate and calibration.

## M13 persistent stochastic search update — 2026-08-10

The historical single-child stochastic edge is removed. Action edges retain outcome bindings keyed by canonical state hash, a per-search transposition graph shares equal states, and the daemon now keeps one mutex-protected Planner whose search graph can be re-rooted on an exactly predicted observed state. Reuse is conservative: same non-empty battle id, perspective, canonical root hash and static structure fingerprint are all required; otherwise the graph resets. Unreachable pre-root nodes are pruned. Revision-bound stale cancellation remains authoritative. Functional SHAs: `d06217fd4aa531aa0e49cf7c8c2495a5ab0ca5e4`, `135826c05d7f9b3d44e165ef6732bb6ede89a4c4`, `6edec4d8360169060d280cd07a6e63de9c0fda89`. CI run `31380236279`: PASS.

