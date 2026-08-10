# Implementation report — HeroesWM Solver 0.3.0

**Дата checkpoint:** 09.08.2026  
**Источник данных:** независимо декодированный raw corpus `init.txt + turns0.txt`; старый 50-бойный parser не используется как ground truth.

## 1. Короткий итог

Проект перешёл от инфраструктурного scaffold к работающему research solver: собран реальный corpus 866 боёв, реализован independent protocol decoder, canonical state, hybrid simulator, ability registry, train-only baseline models и PUCT planner. Offline replay/shadow pipeline детерминирован и проверяется на полном корпусе.

Главный оставшийся продуктовый gate — live validation на **активном** бою + дальнейшее закрытие rare/high-impact mechanics.

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
| Ability Registry unresolved | 78 |
| Held-out ability risk mean / p90 | 0.2389 / 0.3978 |
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

## 3. M01–M19

| Module | Status | Что реально есть | Что не закрыто |
|---|---|---|---|
| M01 Browser Bridge | MOSTLY COMPLETE | MV3 passive fetch/XHR capture, localhost bridge, side panel, auto replan | live active-battle validation, runtime-object fallback |
| M02 Protocol Decoder | ADVANCED PARTIAL | independent C++/Python decoder, 100% record coverage, 866/866 shadow determinism | 19 rare structural-invalid finals, unresolved semantics |
| M03 Session | MOSTLY COMPLETE | reset/dedupe/out-of-order/hash/stale protection/incremental state | full persistent tree re-root |
| M04 Knowledge | ADVANCED PARTIAL | 644 creatures, 421 abilities, reference HTML ingestion, Ability Registry | remaining unresolved/high-impact ability semantics |
| M05 Corpus | COMPLETE CURRENT DATA | 866/866 raw init+turns, metadata/collector/HAR path | corpus itself intentionally external to GitHub |
| M06 Dataset | MOSTLY COMPLETE | 52,357 accepted decisions, temporal battle split, real features/labels | production learned-dynamics targets/gates |
| M07 Legal Actions | ADVANCED PARTIAL | basic + hero/spell/ability subset, move+attack, large/flyer/shooter mechanics | rare special action families |
| M08 Opponent Policy | BASELINE COMPLETE | creature-conditioned PvE action-type prior | full candidate-action neural policy |
| M09 Player Prior | BASELINE COMPLETE | real player action-type prior | search distillation/full candidate ranking |
| M10 Value/Risk | ADVANCED BASELINE | calibrated-ish battle-balanced linear P(win), ability risk | quantiles/CVaR production heads |
| M11 Dynamics | PARTIAL | exact transitions + residual/proc/collateral components | full learned world ensemble/multi-step gate |
| M12 Hybrid Simulator | ADVANCED PARTIAL | broad exact mechanics + stochastic models | complete ability/mechanic coverage |
| M13 Search | ADVANCED PARTIAL | PUCT, priors/value/risk, real-state regression | transpositions/tree reuse/full chance modeling |
| M14 Orchestrator | MOSTLY COMPLETE OFFLINE | capture/session/decode/plan/hash/replan | live active battle E2E |
| M15 Inference Runtime | PARTIAL | C++ CSV/JSON model loaders, Python/ONNX export scaffold | ONNX Runtime batching/manifest |
| M16 Local API | MOSTLY COMPLETE | loopback HTTP, capture/state/status/plan/debug, origin guard | pairing token/WebSocket |
| M17 UI | PARTIAL/USABLE | extension side panel/recommendation/alternatives/auto refresh | rich overlay/PV/explanation/live UX QA |
| M18 Training | ADVANCED PARTIAL | real pipelines for policy/value/damage/spell/next-actor/proc/collateral/kill-trigger | unified production NN dynamics/distillation |
| M19 Evaluation | ADVANCED PARTIAL | full corpus check, shadow, legal coverage, model metrics, planner stability | live shadow + hard-PvE human trial suite |

## 4. Ability system

Ability handling is not a flat creature-value heuristic. It is split into:

1. **Exact mechanics** — change legal actions / transition / retaliation / resistances / state lifecycle.
2. **Modeled proc/collateral/kill-trigger** — probability is learned train-only and held-out gated.
3. **Ability-conditioned damage residual** — used especially for low-support creature IDs.
4. **Ability risk** — unresolved mechanics increase search uncertainty weighted by stack strength.

Latest Ability Registry support counts:

```json
{
  "exact_search": 85,
  "exact_targeting": 11,
  "partial_exact": 18,
  "modeled_proc": 8,
  "modeled_collateral": 5,
  "modeled_kill_trigger": 2,
  "dynamic_spellbook": 1,
  "learned_damage": 177,
  "reference_only": 32,
  "identity": 4,
  "unresolved": 78
}
```

Examples already handled in runtime include core movement/shooter/large/flyer/retaliation rules; multi-hit; defense penetration/resistances/immunities; Defend/Take Roots/Entrenchment; Stone/Warding/Crippling observed state; Enraged/Pack Enrage; Battle Thirst/Taste of Blood; Mana Drain; Mana Feed; Life Drain; Regeneration; Mighty Slam; Blood Frenzy; Organic Armor; Shield Other; Swift Attack; Impervious to Pain; Concentration; Lizard Bite; direct hero spells and several status spells.

**Current research frontier:** remaining assist/counter/summon/control abilities. Life Drain, Regeneration, Mana Feed and Mighty Slam are `exact_search`; Mana Feed is additionally validated on all 42 observed `Smfd` actions in the 866-battle corpus.

## 5. What is intentionally not claimed

- This is not yet a verified live production advisor.
- 847/866 final structural-ready is not 100%; validator remains strict rather than hiding overlaps.
- A 421-code catalog does not mean 421 exact mechanics; support level is explicit per ability.
- No claim of hard-PvE win-rate uplift has been made without live human-in-loop trials.
- Old historical `states_by_turn.json` is not used as truth/label.

## 6. Next gates

1. Continue high-impact unresolved abilities after the completed Life Drain, Regeneration, Mana Feed and Mighty Slam transitions.
2. Resolve remaining structural-invalid replay families.
3. Add full learned dynamics ensemble + multi-step divergence gate.
4. Improve tree reuse/transposition/opponent branching.
5. Live active-battle browser validation.
6. Hard-PvE benchmark: win rate, attempts-to-win, invalid action rate, calibration.
