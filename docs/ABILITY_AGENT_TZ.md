# HeroesWM Solver — ТЗ для агента по abilities

Версия контракта: 2026-08-13 — unified-main governance
Рабочая ветка: **`main`**
Модуль: **ability** — отдельный logical ownership boundary, не отдельная Git lane
Legacy ref `ability`: только historical/archive provenance; не source of truth и не handoff/merge destination
Целевая product/CI платформа: **Windows 10/11 x64 + Visual Studio 2022 / MSVC**

## 0. Текущий обязательный checkpoint

Текущий проверенный интегрированный functional checkpoint:

- **`3df0d5ee4434d3cc401dba1b765a4dca068c15c1`** — validated functional `main` после последней ability integration;
- Ability Windows CI **`31700597609` — PASS / conclusion `success`**, check-suite `85996170989`;
- Main Windows CI **`31700599112` — Core PASS + Full PASS**, check-suite `85996175100`;
- historical pre-unification ability source `2ae1046c48e99c94da3481a8b3ed81285b9125ab` / run `31697180629` остаётся только provenance.

Перед новой functional ability-работой агент обязан сверить фактический HEAD `main`, этот документ, `docs/ability/AGENT_STATUS.md`, `docs/ability/ability_changelog.md`, root `changelog.md` и `TESTS_CANON.md`. Никакой синхронизации с legacy веткой `ability` не требуется и не разрешается считать её актуальным состоянием проекта.

### Закрытые на текущей доказуемой границе mechanics

Без нового противоречащего evidence **не переделывать**:

- Life Drain;
- Regeneration;
- Mana Feed;
- Mighty Slam;
- Paw Strike;
- Crippling Wound (`partial_exact`, probability не доказана);
- Power Strike (predictive proc остаётся learned/unresolved);
- Gribbomb (`partial_exact`, exact observed self-removal; predictive Earth/collateral magnitude не доказана);
- Taunt (`unresolved`, закрыт precise blocker'ом: нет carrier-specific redirect discriminator и numeric probability);
- Spider (`unresolved`, raw `Sent` не Spider-specific и не Entroots-exclusive; отдельный Spider runtime effect запрещён);
- Child of the Light (`unresolved`, нет независимого per-spell Light-school discriminator; hardcoded Light taxonomy запрещена).

### Последний закрытый evidence-front: Hexing Attack / shared `ray`

Pre-unification Hexing work завершил общий parser-substrate package: evidence-backed `ray -> dray` structural/status-family decoding вошёл в integrated `main`, при этом standalone zero-cost Hexing-like rows остаются semantic-unresolved.

Зафиксированная граница:

- shared `crs/slw/sff/ray` wire families имеют independent normal-cast controls;
- `ray` структурно декодируется через shared status substrate;
- Hexing не получает отдельный runtime effect только из tooltip/mnemonic;
- `15/115` и другие observed frequencies **не** являются proc probability;
- Child/Taunt/Spider/Gribbomb ceilings ниже остаются в силе.

Следующая ability не hardcode'ится этим governance checkpoint. Перед новым functional package пересчитать текущий `data/reports/ability-risk-current.json` на HEAD `main` и выбрать следующую actionable unfinished ability по canonical weighted queue.

## 1. КРИТИЧЕСКОЕ ПРАВИЛО: ability changelog обязателен

Ability-agent ведёт канонический журнал разработки: `docs/ability/ability_changelog.md`.

После **каждого functional ability commit** обязательно:

1. получить validation именно для реального functional SHA;
2. authority — GitHub-hosted Windows/MSVC Ability CI;
3. отдельным bookkeeping commit обновить:
   - `docs/ability/ability_changelog.md`;
   - `docs/ability/AGENT_STATUS.md`;
   - корневой `changelog.md`;
4. записать functional SHA, semantic boundary/result и authoritative Windows run/check-suite;
5. не переписывать старые changelog entries; исправления оформлять новыми correction entries.

Bookkeeping/docs-only commit сам по себе не требует нового Ability CI, если не меняет executable behavior/tests/registry/tooling.

## 2. Роль и границы

Ability-agent — модульный агент внутри единой ветки `main`. Он отвечает за creature abilities и связанные evidence/tests:

- raw/corpus evidence;
- ability protocol decoding;
- ability-specific replay/simulator/proc/collateral mechanics;
- ability registry/risk evidence;
- C++/Python regressions;
- актуальный module status/changelog.

Все functional и bookkeeping commits делаются непосредственно в `main`. Dedicated `ability` branch, Draft PR #1 и отдельный ability-to-main merge/handoff больше не являются частью workflow.

Не переключаться на planner/M11/live/UI/extension/daemon задачи без прямой доказанной зависимости ability package. Если ability требует shared substrate, сделать минимальное изменение в `main` и прогнать все затронутые main + Ability validation surfaces.

## 3. CI/platform contract

Единственная PASS/FAIL authority для ability functional work:

- Windows 10/11 x64;
- Visual Studio 2022 / MSVC;
- GitHub-hosted `windows-latest`;
- workflow `.github/workflows/ability.yml`;
- entrypoint `scripts/ci_ability_windows.ps1`.

Linux/WSL не нужен и не является PASS/FAIL authority. Локальные результаты могут быть только diagnostic.

Ability CI должен сохранять atomic model из `TESTS_CANON.md`:

- MSVC x64 build once;
- exact frozen C++ inventory;
- one named C++ case per matrix job;
- exact frozen ability-owned pytest node inventory;
- one exact pytest node per matrix job;
- full-corpus/evidence gates по `hwm_battles`;
- aggregate success только если прошли все обязательные surfaces.

Не заявлять PASS до `completed + success` на exact functional SHA.

## 4. Evidence ground truth

Ground truth для abilities, по убыванию силы:

1. raw `init.txt` + `turns0.txt` полного доступного corpus;
2. однозначные server-declared ability/spell tags/tooltips/rules;
3. canonical replay как проверяемая implementation, но не как источник истины.

Не считать ground truth:

- старый 50-battle parser;
- HTML сам по себе;
- существующий hardcoded runtime effect;
- мнемонику raw opcode;
- observed frequency без доказанного trigger label;
- историческую формулу без проверки на текущем corpus.

## 5. Обязательная структура исследования ability

### 5.1 Corpus discovery

По всему `hwm_battles` собирать, где применимо:

- battle/turn/decision ids;
- actor/source/target uid и owner;
- creature IDs и server ability sets;
- action type;
- raw opcode sequence;
- DAMAGE/FORCED_POSITION/SPECIAL/I records;
- movement/attack/cast anchor;
- HP/count/mana/ATB/initiative/speed/position deltas;
- effect lifecycle;
- retaliation/additional actions;
- geometry/occupancy;
- positive и negative controls;
- source/spellbook/collision populations.

### 5.2 Discriminator

Доказать минимальный discriminator, который отличает механику от co-abilities и generic protocol substrate.

Обязательны collision controls. Совпадение кода, final target, tooltip wording или мнемоники не является достаточным discriminator само по себе.

Не вводить новый canonical state field только ради модели.

### 5.3 Observed consequence

Отделять server consequence от trigger probability. Exact consequence требует corpus evidence либо однозначного server rule с проверенными ограничениями.

### 5.4 Trigger/probability

Probability разрешено моделировать только после доказанного per-event trigger label/discriminator.

Если probability действительно моделируется, использовать battle-level chronological holdout и минимум:

- train-frequency baseline;
- candidate Brier;
- improvement;
- AUC/calibration, когда осмысленно.

Не включать speculative proc, если candidate не улучшает holdout устойчиво.

### 5.5 Runtime classification

Использовать минимально достаточный статус:

- `exact_search`;
- `exact_targeting`;
- `partial_exact`;
- `modeled_proc`;
- `modeled_collateral`;
- `modeled_kill_trigger`;
- `learned_damage`;
- `unresolved`.

Не повышать статус ради registry/risk metric.

## 6. Текущие доказанные blockers, которые нельзя обходить эвристиками

### Gribbomb

`gribbomb = partial_exact`, canonical risk `0.25`. Exact observed carrier self-removal по canonical carrier-sourced `Sbom` реализован. Predictive Earth/collateral magnitude остаётся unresolved/disabled.

### Taunt

Exact tooltip/geometry/opportunity population pin'нуты. `ra2/ral` collide между carrier-target и adjacent-ally controls. Final DAMAGE destination нельзя использовать для восстановления original intended target. Numeric redirect probability отсутствует.

### Spider / `Sent`

Strict locked facts:

- 866 battle dirs;
- 182 `ent` battles;
- 806 `Sent` records;
- 315 zero-source, 491 nonzero-source;
- nonzero-source split `405 Entroots-without-Spider / 84 Spider+Entroots / 2 neither`;
- payload `source3 + target3 + 000000000`;
- second UID state-resolvable 806/806;
- current parser intentionally leaves `target_uid=None` for this package.

`Sent` не Spider-specific. Два Netshooter controls не позволяют объявить его Entroots-exclusive. Второй Spider runtime effect запрещён без нового evidence.

### Child of the Light

Strict locked facts:

- 866 battle dirs;
- 108 carrier battles;
- 137 carriers;
- server spellbook в carrier battles: 651 actors / 2031 entries;
- raw school tokens: `neutral 1405`, `air 275`, `earth 144`, `cold 141`, `other 31`, `fire 18`, `nt 17`;
- literal `light` token отсутствует;
- `neutral/nt` смешивают несовместимые game-school semantics;
- decoded `bm_tooltips` в 108/108 carrier battles имеет только `abil_desc`, `abil_names`, `perk_hints`;
- exact mapping-key overlap с same-battle spellbook names = 0;
- `child_light_text_hits = 216`;
- `non_child_light_text_hits = 92`;
- `school_text_hits = 112`;
- decisive independent discriminator: `non_child_school_light_hits = 0`.

Следствие: Child закрыт `unresolved` на missing per-spell Light-school discriminator. Hardcoded Light spell taxonomy/runtime copy rule запрещены.

## 7. Weighted queue

После каждого законченного package пересчитать `data/reports/ability-risk-current.json` и выбирать следующую **actionable unfinished** ability по `weighted_contribution`, исключая уже закрытые precise blockers.

Не выбирать следующую механику по алфавиту и не искусственно менять registry weights ради удобной очереди.

Текущий active lead на этом checkpoint — **Hexing Attack**.

## 8. Ownership

### Ability-module scope / normal changes on `main`

C++ ability/protocol/simulator:

- `cpp/src/protocol.cpp`;
- `cpp/src/simulator.cpp`;
- `cpp/src/proc_model.cpp`;
- `cpp/src/ability_registry.cpp`;
- `cpp/src/ability_damage_model.cpp`;
- `cpp/src/collateral_model.cpp`;
- `cpp/src/kill_trigger_model.cpp`;
- соответствующие ability headers/tests.

Python:

- `python/hwm_solver/protocol/replay.py` для evidence-backed ability/shared-wire decoding;
- `python/hwm_solver/knowledge/build_ability_registry.py`;
- `python/hwm_solver/ability/**`;
- ability/proc/collateral evidence/train code;
- соответствующие ability-specific tests.

Evidence/docs/CI:

- ability registry/risk reports и `data/reports/abilities/**`;
- `docs/ability/**`, `docs/ABILITY_AGENT_TZ.md`, bookkeeping в root `changelog.md`;
- `.github/workflows/ability.yml`, `scripts/ci_ability_windows.ps1`, `python/tests/test_ability_workflow_contract.py` при необходимости поддерживать сам validation surface.

### Shared substrate

`cpp/src/state.cpp`, `cpp/include/hwm/state.hpp`, CMake, protocol/replay, simulator и shared reports могут влиять на другие модули. Ability-agent может менять их прямо в `main` только при доказанной необходимости текущего package, минимальным diff и с cross-module regressions/CI. Перед широким shared change записать impact в `docs/ability/AGENT_STATUS.md`.

### Outside module scope

Без прямой ability dependency не менять planner/search, M11/evaluation, session/http/runtime, extension/UI, schemas и unrelated product docs. Это scope rule, а не branch ownership rule; merge conflicts между `main` и ability больше не являются нормальной стадией разработки.

## 9. Regression gates

Ability package должен иметь, где применимо:

- positive observed case;
- wrong source/carrier negative case;
- collision population;
- exact consequence;
- blocked/illegal geometry;
- lifecycle/cooldown;
- proc/no-proc branches только если model разрешён;
- retaliation/additional action semantics;
- source/spellbook normal-cast controls для ambiguous status wires.

Windows authority:

```powershell
.\scripts\ci_ability_windows.ps1
```

Expected platform details:

- Visual Studio 2022 generator, `-A x64`;
- `hwm-tests.exe`;
- CTest только `^hwm-tests$`;
- Python 3.13 managed venv;
- ability-owned pytest selection relative to `origin/main`;
- complete `hwm_battles` (>=800 battle dirs, включая допустимый nested layout `hwm_battles\battles`).

## 10. Status / handoff

После законченного functional блока обновить `docs/ability/AGENT_STATUS.md`:

- current `main` HEAD;
- validated functional SHA;
- hosted Windows Ability run/check-suite/status;
- затронутые Main validation surfaces и их run/status, если менялся shared substrate;
- exact remaining failures/blockers и corpus support counts;
- observed coverage / model metrics, если применимо;
- ability-risk / weighted contribution change;
- exact/modeled/unresolved boundary;
- следующую actionable ability либо явный blocker.

Handoff всегда указывает на `main`. Legacy `ability` ref не обновляется как часть нормальной разработки.

## 11. Коммиты

Делать небольшие логические functional commits.

Каждый functional commit обязан получить hosted Windows validation на exact SHA до semantic claim и до bookkeeping.

После этого — отдельный bookkeeping commit с `ability_changelog.md`, `AGENT_STATUS.md`, `changelog.md`.

Не использовать temporary self-modifying workflows. Не ослаблять assertions ради green CI. Evidence-fail, который опровергает гипотезу, фиксировать как evidence, а не маскировать rerun'ом.

## 12. Завершение ability-блока на `main`

Перед handoff следующему диалогу:

1. весь functional код находится в `main`;
2. нет случайных unrelated-module изменений;
3. exact functional SHA имеет `completed + success` hosted Windows Ability CI;
4. shared-substrate change имеет все необходимые Main validation results на том же exact SHA;
5. evidence claims соответствуют strict corpus tests;
6. `AGENT_STATUS.md`, ability changelog и root changelog актуальны;
7. handoff указывает на текущий `main` HEAD и следующий module task — без Draft PR и без ability-to-main merge шага.

Если `main` изменился до завершения проверки и functional tree изменился, старый PASS не переносится: валидировать новый exact SHA. Legacy ветку `ability` не синхронизировать и не использовать как промежуточную рабочую копию.
