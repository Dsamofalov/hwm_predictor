# HeroesWM Solver — ТЗ для агента по abilities

Версия контракта: 2026-08-11
Рабочая ветка: `ability`
Draft PR: `#1` (`ability` -> `main`)
Целевая product/CI платформа: **Windows 10/11 x64 + MSVC**

## 1. Роль и границы

Ability-agent отвечает только за creature abilities и связанные с ними evidence/tests:

- raw/corpus evidence;
- ability protocol decoding;
- ability-specific simulator/proc/collateral mechanics;
- ability registry/risk evidence;
- C++/Python regression tests;
- merge-ready handoff в Draft PR #1.

Не переключаться на main-owned planner/M11/live/UI/decoder-задачи и не дублировать работу main-agent.

Ability-agent **не merge'ит `ability` в `main` самостоятельно**. Его задача — держать ветку review-ready и совместимой с актуальным `main`; интеграцию выполняет основной front/reviewer.

## 2. Актуальный CI/platform contract

Поддерживаемая product/test платформа — Windows 10/11 x64, MSVC/Visual Studio 2022.

Linux/WSL не являются CI target и не используются как основание для PASS/FAIL продукта.

Репозиторий public. Старые self-hosted runners удаляются и больше не считаются доступными.

### Ability workflow

Ability-specific workflow: `.github/workflows/ability.yml`.

Runner:

```yaml
runs-on: windows-latest
```

Не использовать:

- `[self-hosted, windows, x64, hwm-windows]`;
- `ubuntu-latest`;
- отдельный пользовательский/local runner;
- workflow-секреты для выполнения untrusted fork code.

PR workflow должен быть безопасен для внешних forks:

- обычный `pull_request`, не `pull_request_target` для выполнения PR code;
- минимальные permissions, обычно `contents: read`;
- без `contents: write` / `statuses: write` для untrusted PR job;
- без secrets;
- clean `actions/checkout`;
- `concurrency` + `cancel-in-progress` для устаревших commits.

`workflow_dispatch` разрешён для ручной диагностики текущего HEAD.

### Что проверяет ability CI

Не дублировать main CI. Ability workflow добавляет только:

- MSVC x64 build target `hwm-tests.exe`;
- CTest только `^hwm-tests$`;
- ability-owned Python tests относительно актуального `origin/main`;
- full-corpus/evidence gates по `hwm_battles`.

Entrypoint: `scripts/ci_ability_windows.ps1`.

Main-owned planner replay, daemon auth/live/WebSocket, M11, TypeScript/extension gates в ability workflow не добавлять.

### PASS rule

Не заявлять PASS, пока реальный GitHub-hosted Windows job не запустил steps и не завершился `success`.

При `cancel-in-progress` старые cancelled runs не продолжаются; authority — последний run для текущего функционального HEAD.

## 3. Текущий Windows test priority

Основной ближайший приоритет — довести ability-owned монолитный `hwm-tests` до нормального MSVC состояния на `windows-latest`.

Известные исторические Windows defects считать входом ability-front:

1. dangling/pointer invalidation в Mighty Slam regression после `std::vector<Entity>::push_back`;
2. несогласованность `frightful_aura` / `frightfulaura`;
3. последующий hard termination `0xc0000409` в `hwm-tests`.

Порядок:

1. воспроизвести `hwm-tests` на hosted MSVC;
2. исправлять дефекты последовательно;
3. assertions/invariants не ослаблять;
4. failing tests не исключать без доказанной причины;
5. после каждого исправления снова запускать hosted Windows suite;
6. после зелёного C++ gate продолжать corpus/evidence queue по weighted contribution.

## 4. Evidence ground truth

Ground truth для ability:

1. raw `init.txt` + `turns0.txt` полного доступного corpus;
2. однозначные server-declared ability/spell tags/tooltips/rules;
3. canonical replay только как проверяемая реализация, не источник истины.

Не считать ground truth:

- старый 50-battle parser;
- HTML сам по себе;
- существующий hardcoded runtime/replay effect;
- историческую формулу без проверки на текущем corpus.

## 5. Обязательная структура исследования ability

### 5.1 Corpus discovery

Собирать по всему `hwm_battles`:

- battle/turn ids;
- actor/source/target uid и owner;
- creature ids и server ability sets;
- action type;
- raw opcode sequence;
- DAMAGE/FORCED_POSITION/SPECIAL/I records;
- movement/attack anchor;
- HP/count/mana/ATB/initiative/speed/position deltas;
- effect lifecycle;
- retaliation/additional actions;
- geometry/occupancy;
- positive и negative controls.

### 5.2 Discriminator

Доказать минимальный discriminator, отделяющий механику от других abilities. Проверять co-abilities и collision population. Не вводить новый canonical state field только ради модели.

### 5.3 Observed consequence

Отделять server consequence от trigger probability. Exact consequence требует полной corpus-проверки либо явного server rule и проверенных ограничений.

### 5.4 Trigger/probability

Вероятностные правила проверять на battle-level chronological holdout. Минимум:

- train-frequency baseline;
- candidate Brier;
- improvement;
- AUC/calibration, если осмысленно.

Не включать speculative proc, если candidate не улучшает holdout достаточно устойчиво.

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

Не повышать статус ради registry/risk метрики.

## 6. Приоритет mechanics

После завершённого пакета пересчитать ability-risk и выбирать следующую незакрытую механику по `weighted_contribution`, а не по алфавиту.

Без нового противоречащего evidence не переделывать закрытые:

- Life Drain;
- Regeneration;
- Mana Feed;
- Mighty Slam mechanics;
- Paw Strike.

Power Strike:

- collision population изолирована от Paw Strike;
- observed consequence изучен отдельно;
- probability holdout недостаточен;
- speculative exact proc не добавлять.

Crippling Wound:

- exact marker/consequence закрыты до `partial_exact`;
- speculative probability остаётся недоказанной без устойчивого holdout win.

Подготовленные evidence probes и текущую weighted queue брать из `docs/ability/AGENT_STATUS.md`.

## 7. Ownership

### Ability-owned / разрешено

C++ ability/protocol/simulator:

- `cpp/src/protocol.cpp`;
- `cpp/src/simulator.cpp`;
- `cpp/src/proc_model.cpp`;
- `cpp/src/ability_registry.cpp`;
- `cpp/src/ability_damage_model.cpp`;
- `cpp/src/collateral_model.cpp`;
- `cpp/src/kill_trigger_model.cpp`;
- соответствующие ability headers;
- `cpp/tests/test_main.cpp`.

Python:

- `python/hwm_solver/protocol/replay.py` для ability decoding;
- `python/hwm_solver/knowledge/build_ability_registry.py`;
- `python/hwm_solver/ability/**`;
- ability/proc/collateral evidence/train code;
- соответствующие ability-specific tests в `python/tests/**`.

Evidence/docs:

- ability registry/risk reports;
- `data/reports/abilities/**`;
- `docs/ability/**`;
- `docs/ABILITY_AGENT_TZ.md`.

Ability CI exception:

- `.github/workflows/ability.yml`;
- `scripts/ci_ability_windows.ps1`;
- `python/tests/test_ability_workflow_contract.py`.

`changelog.md` разрешено менять только отдельным bookkeeping commit, фиксирующим уже существующие functional SHA.

### Integration request first

Без доказанной необходимости не менять:

- `cpp/src/state.cpp`;
- `cpp/include/hwm/state.hpp`;
- `CMakeLists.txt`;
- `CMakePresets.json`.

Если ability требует их изменения — сначала записать integration request в `docs/ability/AGENT_STATUS.md`.

### Main-owned / не менять

Кроме минимального разрешения неизбежного merge conflict не менять:

- `cpp/src/planner.cpp`, `cpp/include/hwm/planner.hpp`;
- M11/evaluation main-front;
- session/http/main runtime;
- `extension/**`;
- `.github/workflows/ci.yml`;
- main Windows scripts;
- `schemas/**`;
- общие product/spec/report документы main-front.

## 8. Regression gates

Ability package должен иметь, где применимо:

- positive observed case;
- wrong source/carrier negative case;
- exact consequence;
- blocked/illegal geometry;
- lifecycle/cooldown;
- proc/no-proc branches только если model разрешён;
- retaliation/additional action semantics;
- collision controls.

Windows authority:

```powershell
.\scripts\ci_ability_windows.ps1
```

Expected details:

- Visual Studio 2022 generator, `-A x64`;
- `hwm-tests.exe`;
- `ctest.exe ... -C Debug -R '^hwm-tests$'`;
- Python 3.13 managed venv;
- ability-owned pytest selection relative to `origin/main`;
- complete `hwm_battles` (>=800 battle dirs, включая допустимый nested layout `hwm_battles\battles`).

## 9. Status / handoff

После законченного блока обновить `docs/ability/AGENT_STATUS.md`:

- ability functional HEAD;
- актуальный `main` HEAD только как integration reference;
- Windows hosted workflow run ID/status;
- exact remaining failures;
- corpus support counts;
- exact observed coverage;
- baseline/candidate metrics;
- ability-risk / weighted contribution change;
- exact/modeled boundary;
- integration requests;
- limitations;
- следующую механику.

## 10. Коммиты и changelog

Делать небольшие логические functional commits. Не squash самостоятельно.

После **каждого functional commit** обязательный отдельный bookkeeping commit в `changelog.md`, содержащий реальный SHA функционального коммита.

Bookkeeping commit не обязан ссылаться на собственный SHA.

Не использовать временные self-modifying workflows.

## 11. Review-ready завершение блока

Перед завершением блока:

1. убедиться, что работа остаётся в `ability`;
2. проверить diff против актуального `main` и отсутствие случайных main-owned изменений;
3. прогнать реальный GitHub-hosted `windows-latest` ability workflow;
4. не заявлять PASS без завершившихся steps;
5. обновить `AGENT_STATUS.md` и changelog;
6. держать Draft PR #1 актуальным;
7. **не merge `ability` в `main` самостоятельно**.

Если `main` продвинулся параллельно, это не повод постоянно вливать его в ability во время каждой ability-итерации. Синхронизацию делать только при реальной необходимости для review/integration conflicts, сохраняя main-owned изменения.