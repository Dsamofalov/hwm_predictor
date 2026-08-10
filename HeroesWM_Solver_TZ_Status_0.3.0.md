# Техническое задание: HeroesWM PvE Battle Solver / Advisor

**Версия:** 1.1 / implementation checkpoint 0.3.0  
**Дата:** 09.08.2026  
**Статус:** Active implementation specification; checkpoint 0.3.0  
**Последнее обновление реализации:** 10.08.2026 — Life Drain, Regeneration, Mana Feed и Mighty Slam переведены в exact-search.  
**Целевая роль документа:** входной документ для coding/agentic-разработчика, который должен начать реализацию без дополнительных продуктовых вопросов.

---

## 0.3. Статус реализации на checkpoint 0.3.0 (09.08.2026)

Этот раздел является частью ТЗ и фиксирует фактическое состояние реализации. Исходные требования ниже **не удалены**: напротив каждого крупного модуля и фазы добавлен статус checkpoint 0.3.0.

**Легенда:** `COMPLETE` — требования текущего этапа закрыты; `MOSTLY COMPLETE` — основной путь реализован, остаётся ограниченная интеграционная проверка; `ADVANCED PARTIAL` — большая часть функциональности работает, но acceptance исходного ТЗ ещё не выполнен полностью; `PARTIAL` — рабочий поднабор; `IN PROGRESS` — активная разработка; `NOT COMPLETE` — этап ещё не закрыт.

### Проверяемые метрики текущего checkpoint

- Raw corpus: **866/866** боёв с `init.txt` + `turns0.txt`.
- Low-level protocol coverage: **100%**, unknown record families в текущем tokenizer: **0**.
- Final structural-ready: **847/866**; semantic-safe final states: **790/866**.
- Incremental replay == one-shot replay: **866/866**.
- Held-out player non-hero states: structural-ready **5351/5476 = 97.72%**; strict semantic-safe **4979/5476 = 90.92%**.
- При structural-ready состоянии basic action generator имеет хотя бы один action в **5338/5351 = 99.76%** held-out states.
- Held-out observed basic-action representability: **5373/5481 = 98.03%**.
- Dataset: **52,357** accepted decisions из **52,375** observed; 644 creature ID.
- Ability catalog: **421** ability code; registry: **85 exact-search**, 11 exact-targeting, 18 partial-exact, 9 modeled-proc, 5 modeled-collateral, 2 modeled-kill-trigger, dynamic spellbook; **78 unresolved**. `Mighty Slam` теперь имеет отдельный exact `ABILITY` path: выбранная цель + соседние вражеские стеки, knockback только small при валидной клетке, без retaliation, cooldown по минимальному наблюдаемому gap=3; `Paw Strike` переведён из `learned_damage` в `modeled_proc`: вероятность `min(1, 0.10 * travelled_cells)` прошла chronological holdout лучше constant baseline, а observed `I<target><source>` даёт exact ATB=0 transition 174/174; physical push применяется только при валидной клетке; `Life Drain` моделируется точным transition-правилом лечения/воскрешения от 50% фактически нанесённого физического урона; `Regeneration` — точным start-of-turn лечением `random(3,5) * min(current_count, 10)` HP только текущего верхнего существа, без увеличения `count`; `Mana Feed` — exact `Smfd` action на собственного героя с передачей `min(current_count, current_mana)` маны.
- Ability-risk на held-out sample: mean **0.2389**, p90 **0.3978**.
- Player action-type prior: held-out top-1 **70.76%**, top-3 **93.46%**. PvE prior: top-1 **62.81%**, top-3 **96.11%**.
- Value: test battle-level Brier **0.05176** против **0.11891** constant baseline; AUC **0.9889**.
- Physical damage: median abs-log error **0.3574 -> 0.2812** после learned creature residual; для rare creatures ability transfer **0.2719 -> 0.2484**.
- Next actor: held-out top-1 **32.16%**, top-3 **65.86%** против round-robin top-1 **12.75%**, top-3 **33.49%**.
- Planner real-state regression (Release, 20 states): recommendation **20/20**, action-type stability **100%**, exact-action stability **90%** при budget 300 -> 1200.
- Automated tests: C++ CTest **100%**, Python **39/39**, TypeScript typecheck/build **PASS**.

### Текущий незавершённый фронт разработки

1. Закрытие high-impact unresolved creature abilities; `Life Drain`, `Regeneration`, `Mana Feed` и `Mighty Slam` закрыты 10.08.2026; `Paw Strike` переведён в validated hybrid modeled-proc 10.08.2026, текущая точка исследования — remaining assist/counter/summon/control abilities.
2. Устранение 19 финальных structural-invalid replay (в основном geometry/rare mechanics) без ослабления invariants.
3. Full learned dynamics ensemble и multi-step validation gate.
4. Tree reuse/transposition и дальнейшее улучшение opponent branching.
5. Live validation расширения на **активном** бою и затем hard-PvE human-in-loop benchmark.

### Правило источников механик

Старый 50-бойный parser **не используется как ground truth**. Источник истины для текущего состояния/способностей — новый raw-корпус (`init.txt`/`turns0.txt`) и server-declared ability/spell tags. Два предоставленных HTML используются только как reference metadata (названия, описания, coverage), а exact mechanics переводятся в production только после независимой проверки по raw replay или однозначного серверного правила.


## 0. Резюме задачи

Нужно разработать локальную систему-советник для PvE-боёв HeroesWM. Пользователь открывает или передаёт системе ссылку на только что начавшийся бой (например, `warlog.php?warid=...`). Система автоматически получает фактическое текущее состояние боя, анализирует его и выдаёт рекомендуемый следующий ход. Пользователь выполняет ход вручную в официальном клиенте. После изменения боя система автоматически подхватывает новое фактическое состояние и повторно рассчитывает оптимальное действие. Цикл продолжается до победы или окончания боя.

Основная оптимизационная цель: **максимизировать вероятность победы**. Вторичные цели применяются только как tie-breaker между стратегиями с близкой вероятностью победы: сохранить больше армии, снизить риск катастрофического исхода, сохранить ресурсы, уменьшить число ходов.

Система не должна строиться вокруг предположения, что можно в начале боя вычислить одну неизменную последовательность действий до конца. Из-за ответов PvE, случайного урона, инициативы, удачи, боевого духа и вероятностных способностей корректный продукт — **замкнутый контур replanning**. В UI можно показывать прогнозируемую основную линию на несколько ходов вперёд, но исполняемым результатом является только следующий ход, рассчитанный по последнему подтверждённому состоянию.

### 0.1. Ключевой пользовательский сценарий

1. Пользователь открывает бой HeroesWM или вставляет его URL/`warid` в интерфейс советника.
2. Browser Bridge получает состояние боя **без управления персонажем и без генерации лишних игровых действий**.
3. Decoder переводит данные клиента/протокола в канонический `BattleState`.
4. Solver получает `BattleState`, строит допустимые действия и оценивает ветви с учётом PvE-ответов и случайных исходов.
5. UI показывает:
   - лучший следующий ход;
   - вероятность победы/оценку уверенности;
   - 2–5 альтернатив;
   - короткое объяснение;
   - прогнозируемую principal variation (необязательная цепочка следующих ходов).
6. Пользователь делает ход вручную.
7. Browser Bridge фиксирует новое фактическое состояние.
8. Старый план инвалидируется, выполняется replanning.
9. Цикл продолжается до завершения боя.

### 0.2. Жёсткие продуктовые ограничения

- Никаких автокликов, эмуляции присутствия игрока, автоматического управления боем или отправки игровых команд.
- По умолчанию никакого активного высокочастотного polling серверов HeroesWM. Предпочтительный способ — пассивно перехватывать/клонировать уже получаемые официальным клиентом ответы.
- Любой режим дополнительного HTTP-сбора реплеев должен быть выключен по умолчанию и иметь rate limit; его использование должно быть отдельно сверено с правилами HeroesWM.
- Система должна работать локально на обычном ПК и не требовать облачного сервера для online inference.
- Архитектура должна выдерживать бои с полным разнообразием существ и способностей; нельзя строить продукт вокруг ограниченного списка из 20–30 существ.
- Все знания о конкретном текущем протоколе HeroesWM должны быть изолированы за адаптером, чтобы изменение клиентского JS/формата не ломало solver.

---

# 1. Ревью предыдущего обсуждения и скорректированные выводы

## 1.1. Что было верно

1. Поле имеет небольшое дискретное состояние: порядок величины — до 14 основных стеков плюс герой, призывы, препятствия и эффекты.
2. На одном полуходе действует один активный стек/герой, поэтому локальное число действий существенно меньше полного количества комбинаций всех юнитов.
3. Полный brute-force по горизонту 10+ полуходов невозможен из-за экспоненциального роста дерева.
4. PvE-ответы необходимо моделировать вероятностно, а не считать противника идеальным minimax-игроком.
5. Основная сложность проекта не в размере нейросети, а в качестве состояния, данных, динамики боя и поискового алгоритма.
6. PixiJS/canvas — это слой отрисовки. Для ML не нужно распознавать поле по картинке, если удаётся получить исходные данные клиента/протокола.
7. Для runtime-производительности разумно использовать C++ core, а Python оставить для ML/training/analytics.

## 1.2. Что уточнено настоящим ТЗ

### Исправление A — «последовательность ходов»

Нельзя гарантированно выдать фиксированную цепочку на весь бой в момент старта. Система должна выдавать **policy в замкнутом контуре**, а не статический script:

`observe -> plan -> recommend -> human move -> observe actual result -> replan`.

### Исправление B — «все существа и способности»

Цель не в том, чтобы вручную реализовать каждую способность до первого полезного результата. Цель — solver, который способен обрабатывать произвольные сущности. Поэтому целевая архитектура гибридная:

- структурированный `BattleState`;
- learned models для PvE policy, value и dynamics;
- точные правила для универсальных механик;
- расширяемые exact rule plugins для тех механик, где learned dynamics не проходит качество;
- автоматическая регрессия по реальным реплеям.

### Исправление C — глубина 70 полуходов

70 полуходов боя не означает search depth = 70 на каждом решении. Используется receding horizon: например, поиск на 8–20 полуходов + value на листе, после чего фактическое состояние снова считывается и поиск запускается заново.

### Исправление D — цель search

Основная функция — не средний урон и не средний остаток армии, а `P(win)`, дополненная risk-sensitive оценкой. Solver должен уметь предпочитать стратегию с чуть худшими средними потерями, если она заметно снижает вероятность поражения.

---

# 2. Зафиксированные допущения

Эти допущения считаются решениями продукта и не требуют вопроса пользователю при старте реализации.

1. Основная платформа online-использования: Windows 10/11 x64, Chromium-браузер.
2. Training pipeline обязан работать на Windows и Linux; тяжёлое обучение предпочтительно на Linux, но это не требование.
3. Поле: 12 x 10 клеток; схема должна оставаться конфигурируемой.
4. Обычно до 7 базовых стеков на сторону, но data model не должен иметь жёсткий лимит 7 из-за summon/clones/objects.
5. Типичный длинный бой: порядка 70 полуходов; архитектура не должна предполагать фиксированную длину.
6. Пользователь вручную делает рекомендованные ходы.
7. Система может использовать GPU, но должна иметь CPU fallback.
8. Данные боёв используются для обучения только в объёме и способом, который не создаёт запрещённую нагрузку; предпочтительны пользовательские архивы/пассивный capture/разрешённый сбор.
9. Победа имеет абсолютный приоритет над минимизацией потерь, если отдельно не настроено иное.
10. Система может показывать probability/confidence, но не должна заявлять «гарантированная победа», если существует стохастика или модельная неопределённость.

---

# 3. Проверенные внешние факты и неизвестности

## 3.1. Проверено

- Страница приведённого боя `warlog.php?warid=1671960831` загружает полноценный интерфейс боя и содержит боевые элементы/характеристики, то есть ссылка является подходящей точкой входа для browser adapter.
- Официальные правила HeroesWM на дату документа запрещают ПО, эмулирующее присутствие игрока, и отдельно предупреждают об автоматических/полуавтоматических скриптах, выполняющих запросы к игровым механизмам/БД и создающих нагрузку. Это причина сделать продукт строго read-only и пассивным по умолчанию.
- Старый/текущий доступный endpoint вида `battle.php?lastturn=-3&warid=...` возвращает компактный текстовый боевой payload для завершённых боёв; его использование исторически фигурирует на форуме HeroesWM.
- Chrome Manifest V3 позволяет выполнять расширению скрипт в `MAIN` execution world, то есть технически возможно поставить read-only wrapper вокруг `fetch`/XHR в контексте страницы и через `window.postMessage` передать копию уже полученного ответа в extension.
- PyTorch имеет официальный C++ frontend; ONNX Runtime имеет официальный C++ API; CMake поддерживает C++23. Это позволяет держать training в Python и inference/search в C++.

## 3.2. НЕ считать проверенным до Phase 0

Следующие пункты являются гипотезами и должны быть подтверждены экспериментом:

1. Тот же `battle.php` endpoint доступен/полезен во время активного боя.
2. Официальный клиент действительно обновляет бой через `fetch`, XHR или другой перехватываемый текстовый transport.
3. Полный текущий `BattleState` может быть реконструирован только из network payload без чтения client-side runtime objects.
4. Серверный payload содержит достаточно информации для точного восстановления позиций, эффектов, очереди ATB и истории random events.
5. Из клиента можно получить полный legal-action set текущего активного юнита.
6. Формат стабильный между PvE-режимами.

Если какая-либо гипотеза не подтверждается, используется предусмотренный fallback-адаптер, описанный ниже.

---

# 4. Высокоуровневая архитектура

```text
┌─────────────────────────────────────────────────────────────────────┐
│                         Chromium / HeroesWM                         │
│                                                                     │
│  Official game JS/PixiJS                                           │
│          │                                                          │
│          ├── existing network responses                            │
│          │                                                          │
│          ▼                                                          │
│  [Browser Bridge, read-only, MV3]                                  │
└──────────────┬──────────────────────────────────────────────────────┘
               │ localhost WebSocket / HTTP
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Local Solver Service                         │
│                                                                     │
│  Protocol Adapter -> Decoder -> Canonical BattleState -> StateStore │
│                                      │                              │
│                                      ├-> Legal Action Provider      │
│                                      ├-> PvE Policy Model           │
│                                      ├-> World/Dynamics Model       │
│                                      ├-> Value/Risk Model           │
│                                      └-> Exact Rules Plugins        │
│                                                  │                  │
│                                                  ▼                  │
│                                      Search Planner (PUCT/MCTS)     │
│                                                  │                  │
│                                                  ▼                  │
│                                         Recommendation API          │
└──────────────┬──────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│             Extension Side Panel / Local Diagnostic UI              │
│  best move | alternatives | P(win) | confidence | PV | diagnostics │
└─────────────────────────────────────────────────────────────────────┘

Training path:
Captured replays -> Corpus -> Normalizer -> Dataset -> PyTorch training
-> validation/calibration -> ONNX export -> model registry -> C++ runtime
```

---

# 5. Репозиторий и разделение ответственности

Использовать monorepo.

```text
heroeswm-solver/
├─ README.md
├─ LICENSE
├─ CMakeLists.txt
├─ CMakePresets.json
├─ vcpkg.json
├─ pyproject.toml
├─ uv.lock
├─ package.json
├─ pnpm-lock.yaml
├─ docs/
│  ├─ architecture.md
│  ├─ protocol-notes.md
│  ├─ state-schema.md
│  ├─ model-card.md
│  ├─ risk-register.md
│  └─ adr/
├─ schemas/
│  ├─ battle.proto
│  ├─ recommendation.proto
│  └─ replay.proto
├─ extension/
│  ├─ manifest.json
│  ├─ src/main_world/
│  ├─ src/content/
│  ├─ src/service_worker/
│  ├─ src/sidepanel/
│  └─ tests/
├─ cpp/
│  ├─ protocol/
│  ├─ state/
│  ├─ rules/
│  ├─ actions/
│  ├─ inference/
│  ├─ planner/
│  ├─ service/
│  ├─ common/
│  └─ tests/
├─ python/
│  ├─ corpus/
│  ├─ dataset/
│  ├─ models/
│  ├─ training/
│  ├─ evaluation/
│  ├─ export/
│  └─ notebooks/
├─ fixtures/
│  ├─ raw_payloads/
│  ├─ decoded_replays/
│  ├─ golden_states/
│  └─ planner_cases/
├─ models/
│  ├─ manifests/
│  └─ README.md
├─ tools/
│  ├─ capture/
│  ├─ benchmark/
│  └─ dataset_inspector/
└─ .github/workflows/
```

Правило зависимостей: Browser Bridge ничего не знает про ML; ML ничего не знает про browser DOM; planner работает только с canonical schemas/interfaces; protocol-specific код не должен протекать в `planner/`.

---

# 6. Стек разработки

## 6.1. Runtime core

**Язык:** C++23  
**Причина:** минимальный overhead для миллионов state transitions/search nodes; удобная интеграция с ONNX Runtime, SIMD, профилировщиками, многопоточностью и нативным сервисом.

**Build:** CMake + Ninja + CMake Presets.  
**Пакетный менеджер:** vcpkg manifest mode.  
**Компиляторы:** Clang/LLVM как основной dev compiler; MSVC поддерживать на Windows; GCC — CI compatibility.  
**Сериализация:** Protocol Buffers.  
**RPC локально:** gRPC для типизированных внутренних API или простой WebSocket/HTTP слой поверх Boost.Beast/uWebSockets. Для MVP рекомендуется WebSocket JSON/Protobuf между extension и daemon, без отдельной распределённой инфраструктуры.  
**ML inference:** ONNX Runtime C++ API. DirectML и CUDA execution providers — опционально; CPU provider обязателен.  
**Tests:** Catch2.  
**Microbenchmarks:** Google Benchmark.  
**Logging:** spdlog + structured JSON logs.  
**Profiling:** Tracy + Windows Performance Recorder/Perf; sanitizers в Linux CI.

## 6.2. ML / data

**Язык:** Python 3.12+ с фиксацией конкретной версии в `.python-version`.  
**Dependency manager:** `uv`.  
**Framework:** PyTorch.  
**DataFrame/ETL:** Polars + PyArrow.  
**Storage:** Parquet datasets; DuckDB для локальных аналитических запросов.  
**Experiment tracking:** MLflow локально или минимальный собственный registry JSON+TensorBoard; для первого этапа предпочтительно MLflow.  
**Export:** ONNX.  
**Metrics:** torchmetrics + собственные calibration/search metrics.

## 6.3. Browser integration/UI

**Язык:** TypeScript.  
**Platform:** Chrome/Chromium Manifest V3 extension.  
**Bundler:** Vite.  
**Package manager:** pnpm.  
**UI:** React + TypeScript для side panel; не нужен большой UI framework.  
**Communication:** `window.postMessage` main-world -> isolated content script -> extension service worker -> localhost WebSocket.

## 6.4. IDE

Рекомендуемый основной IDE: **CLion** для C++/CMake.  
Python-модули можно вести в PyCharm или в том же JetBrains IDE при наличии поддержки Python.  
TypeScript-extension удобно вести в WebStorm или VS Code.  
Наличие конкретной IDE не должно быть build dependency: весь проект обязан собираться из CLI.

---

# 7. Канонические модели данных

## 7.1. BattleState

`BattleState` — единственный источник истины внутри solver. Никаких raw Pixi/DOM объектов за пределами protocol adapter.

Минимальная схема:

```proto
message BattleState {
  string battle_id = 1;
  uint64 state_seq = 2;
  uint32 protocol_version = 3;
  uint32 ruleset_version = 4;

  Board board = 10;
  repeated Entity entities = 11;
  repeated Hero heroes = 12;
  InitiativeState initiative = 13;
  repeated Effect global_effects = 14;

  uint64 active_entity_uid = 20;
  Side side_to_act = 21;
  BattlePhase phase = 22;
  uint32 round = 23;
  uint32 halfturn = 24;

  repeated BattleEvent recent_events = 30;
  RandomContext random_context = 31;
  SourceMetadata source = 40;
}
```

## 7.2. Entity

Не использовать отдельный class на каждое существо.

```proto
message Entity {
  uint64 uid = 1;
  uint32 creature_id = 2;
  Side side = 3;
  EntityKind kind = 4;

  Cell anchor = 10;
  repeated Cell footprint = 11;
  bool alive = 12;

  int32 count = 20;
  int32 top_unit_hp = 21;
  int32 max_hp_per_unit = 22;

  float attack = 30;
  float defense = 31;
  float min_damage = 32;
  float max_damage = 33;
  float speed = 34;
  float initiative = 35;
  int32 shots = 36;
  int32 mana = 37;

  repeated uint32 ability_ids = 40;
  repeated Effect effects = 41;
  repeated Counter counters = 42;

  bool retaliation_available = 50;
  bool waited_this_round = 51;
}
```

## 7.3. Action

Все planner/model components используют одну схему:

```proto
message Action {
  uint64 action_id = 1;
  uint64 actor_uid = 2;
  ActionType type = 3;

  optional uint64 target_uid = 10;
  optional Cell destination = 11;
  optional uint32 ability_id = 12;
  optional uint32 spell_id = 13;
  optional uint32 direction = 14;
  repeated Cell area = 15;

  ActionSource source = 20; // client/legal-generator/model
}
```

`ActionType`: `MOVE`, `MELEE_ATTACK`, `RANGED_ATTACK`, `WAIT`, `DEFEND`, `CAST`, `ABILITY`, `HERO_ACTION`, `SPECIAL`, `PASS`.

## 7.4. BattleEvent

Event sourcing нужен для:

- проверки decoder;
- learned dynamics;
- explainability;
- поиска скрытых зависимостей random mechanics;
- regression tests.

События: `TURN_START`, `MOVE`, `ATTACK_START`, `DAMAGE`, `HEAL`, `COUNT_CHANGED`, `RETALIATION`, `EFFECT_ADD`, `EFFECT_REMOVE`, `EFFECT_TICK`, `ATB_CHANGE`, `MORALE`, `LUCK`, `PROC`, `SUMMON`, `DEATH`, `RESURRECT`, `CAST`, `TURN_END`, `BATTLE_END`, `UNKNOWN`.

`UNKNOWN` обязателен: новый тип события не должен silently теряться.

---

# 8. Модуль M01 — Browser Bridge

> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE.** MV3 MAIN-world fetch/XHR passive capture, content/service-worker bridge, side panel, localhost forwarding и auto-replan реализованы. Не закрыто: проверка на реальном активном авторизованном бою и fallback через runtime objects.

## Назначение

Получать фактические изменения активного боя из официального клиента и отправлять их локальному daemon без управления игрой.

## Основной подход

Manifest V3 extension инжектит небольшой script в `MAIN` world. Script ставит безопасные read-only wrappers на `window.fetch` и `XMLHttpRequest`, клонирует ответы, которые соответствуют whitelist боевых endpoint'ов, и отправляет копию через `window.postMessage` в isolated content script. Исходный ответ должен возвращаться игре без изменения.

Если network transport не даёт полного состояния, разрешён fallback `Client Runtime Adapter`: чтение строго необходимых доступных runtime objects/DOM/Pixi model через main-world script. Это fallback, а не первая реализация.

## Вход

- текущая вкладка `heroeswm.ru`;
- URL боя;
- уже выполняемые клиентом network requests.

## Выход

`RawBattleEnvelope`:

```json
{
  "battleId": "1671960831",
  "capturedAt": 1786270000000,
  "source": "fetch|xhr|runtime",
  "urlKind": "battle_update",
  "sequenceHint": 123,
  "body": "...raw payload..."
}
```

## Требования безопасности

- wrapper не меняет URL, headers, body, response status или timing intentional behavior;
- capture только exact allowlist endpoints;
- не передавать cookies/auth tokens локальному сервису;
- raw responses хранить только если включён debug/data-capture mode;
- localhost transport проверяет одноразовый extension token;
- никаких auto-click/event dispatch.

## Fallback A

Если невозможно перехватить payload, extension отправляет snapshot нужных client state objects. Adapter должен быть отдельным versioned модулем.

## Fallback B

Ручной import `HAR`/raw payload для разработки protocol decoder.

## Тесты

- fetch wrapper возвращает byte-identical response consumer'у;
- XHR wrapper не ломает readyState/events;
- 1000 последовательных responses без leak;
- отсутствие capture на небоевых страницах;
- extension работает при отключённом local daemon без ошибок игры.

## Acceptance

После фактического изменения состояния в клиенте raw envelope должен появляться в daemon обычно менее чем за 250 мс без дополнительных запросов к HeroesWM.

---

# 9. Модуль M02 — Battle Protocol Adapter / Decoder

> **Статус checkpoint 0.3.0 — ADVANCED PARTIAL.** Независимый C++/Python decoder построен по raw init.txt+turns0.txt. 866/866 incremental replay совпадают с one-shot; low-level coverage 100%; 847/866 финальных состояний structural-ready, held-out player-state structural-ready 97.72%. Остаются 19 боёв с geometry overlap и semantic-unresolved mechanics.

## Назначение

Перевести нестабильный внешний протокол HeroesWM в стабильные внутренние события/состояния.

## Правило архитектуры

Весь reverse-engineered protocol код находится здесь. Ни `planner`, ни `models`, ни UI не должны знать, что означает строка вроде `t=000turns=>...`.

## Этапы decoder

1. framing/tokenization;
2. определение protocol/ruleset version;
3. parsing raw records;
4. нормализация IDs;
5. reconstruction battle events;
6. reconstruction/update `BattleState`;
7. validation/invariants;
8. emit canonical delta + snapshot hash.

## API

```cpp
DecodeResult decode_initial(std::string_view payload);
DecodeResult decode_update(const BattleState& previous,
                           std::string_view payload);
```

`DecodeResult`:

- `BattleState state`;
- `vector<BattleEvent> events`;
- `vector<DecodeWarning>`;
- `RawCoverage coverage`;
- `StateHash state_hash`.

## Обязательные invariants

- ни один живой entity не занимает невозможное количество клеток;
- count >= 0;
- top_unit_hp находится в допустимом диапазоне, если max HP известен;
- active UID существует или фаза не требует active entity;
- two solid entities не занимают одну клетку без явно разрешённого правила;
- sequence монотонен;
- неизвестный token сохраняется в diagnostics.

## Golden fixtures

Каждый подтверждённый формат payload сохраняется как fixture:

`raw -> expected events -> expected state hash`.

Изменение decoder, меняющее старый state hash, требует ADR/explicit migration.

## Acceptance

- 100% golden fixtures проходят;
- неизвестные поля не silently drop;
- decoder restart может восстановить состояние из full snapshot/replay без скрытого mutable singleton state.

---

# 10. Модуль M03 — State Store / Battle Session

> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE.** Thread-safe session, battle reset, duplicate/out-of-order handling, immutable observed state, state hash, stale-plan invalidation и incremental decode реализованы. Persistent search-tree re-rooting по predicted child ещё не завершён.

## Назначение

Держать подтверждённое фактическое состояние и отделять его от speculative search states.

## Сущности

- `ObservedState`: пришёл из клиента, immutable.
- `SpeculativeState`: создан planner/world model.
- `BattleSession`: lifecycle одного `battle_id`.
- `StateRevision`: `(battle_id, seq, hash)`.

## Главное правило

Никогда не продолжать старое дерево search после прихода наблюдаемого state, если его hash не соответствует ожидаемому child state. При любом отличии выполнять re-root или полный reset.

## API

```cpp
SessionUpdate ingest_observed(BattleState state);
std::shared_ptr<const BattleState> current_observed() const;
```

## Acceptance

- out-of-order updates игнорируются/буферизуются;
- duplicate update idempotent;
- battle reload не создаёт вторую session;
- завершившийся battle автоматически закрывает planner.

---

# 11. Модуль M04 — Game Knowledge / Entity Catalog

> **Статус checkpoint 0.3.0 — ADVANCED PARTIAL.** Из raw-корпуса: 644 creature ID и 421 ability code. Внешний reference catalog извлечён из двух HTML-источников. Ability Registry: 85 exact-search, 11 exact-targeting, 18 partial-exact, 9 modeled-proc, 5 modeled-collateral, 2 modeled-kill-trigger, dynamic spellbook; 78 abilities остаются unresolved.

## Назначение

Хранить versioned metadata по существам, способностям, заклинаниям и известным правилам.

Это **не означает**, что весь simulator должен быть вручную запрограммирован. Catalog нужен, чтобы модели видели стабильные IDs и known static attributes.

## Хранить

- creature ID/name/faction/tier;
- base stats;
- ability IDs;
- textual/structured ability descriptors, когда доступны;
- spell IDs;
- dimensions/footprint;
- ranged/melee flags;
- timestamps/ruleset version;
- source URL/hash;
- optional exact-rule implementation ID.

## Storage

Git-versioned YAML/JSON для небольших tables + generated Protobuf binary для runtime. Не использовать production SQL БД ради нескольких тысяч сущностей.

## Update strategy

`catalog_version` должен входить в dataset manifest и model manifest. Нельзя обучать модель на одном catalog и silently inference на другом.

---

# 12. Модуль M05 — Replay Corpus Builder

> **Статус checkpoint 0.3.0 — COMPLETE FOR CURRENT CORPUS.** 866/866 боёв имеют init.txt и turns0.txt; URL normalization, dedup, resumable collector, metadata/manifest и HAR fallback реализованы. Raw corpus не включается в GitHub snapshot из-за объёма.

## Назначение

Получить большой корпус исторических траекторий для обучения и regression testing.

## Источники в порядке предпочтения

1. passive capture собственных просмотренных/сыгранных боёв;
2. пользовательские экспортированные URLs/warids + ручной/разрешённый batch import;
3. заранее скачанные raw battle payloads;
4. controlled remote collector — только после отдельной проверки допустимости.

## Необходимые данные на бой

```text
BattleMetadata
InitialState
Event[0..N]
ObservedState[0..N]
ChosenAction[0..N]
ActingSide
Outcome
Optional reward/remaining_army/score
ProtocolVersion
RulesetVersion
RawPayloadHash
```

## Deduplication

Ключ: `battle_id + canonical payload hash`.

## Split

Нельзя делать random split только по отдельным transitions. Train/val/test делятся **по battle_id**, а дополнительно желательно по времени, чтобы test проверял generalization к более новым боям.

## Leakage prevention

Бои одного и того же exact scenario/seed/duplicate replay не должны попадать одновременно в train и test.

---

# 13. Модуль M06 — Dataset Builder

> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE.** Independent raw replay builder формирует 52,357 accepted policy rows из 52,375 observed decisions, unknown low-level commands = 0; chronological battle-level 80/10/10 split, no battle leakage. Полный learned-dynamics target pipeline ещё не является production-ready.

## Назначение

Преобразовать replay corpus в наборы задач.

## Dataset A — Opponent Policy

`(state_t, legal_actions_t) -> action_enemy_t`

## Dataset B — Player Behaviour Warm Start

`(state_t, legal_actions_t) -> action_human_t`

Не считать human action оптимальным; использовать только как initialization/action prior.

## Dataset C — Outcome / Value

`state_t -> battle outcome` + auxiliary targets:

- win/loss;
- remaining force fraction;
- remaining HP-equivalent;
- turns to terminal;
- optional event score.

## Dataset D — Dynamics

`(state_t, action_t) -> event_delta + state_{t+1}`.

Для stochastic transitions допускается distributional target; одинаковые близкие состояния группировать нельзя без контроля hidden history.

## Dataset E — Legal Action / Action Proposal

Если клиент отдаёт legal actions: `(state -> legal actions)`. Если нет — положительные actions из реплеев + generated negatives для обучения proposal/legal scorer.

## Feature policy

- IDs представлены embeddings, а не one-hot огромной длины;
- scalar stats нормализуются robust transforms;
- координаты подаются как `(x,y)` + relative geometry;
- эффекты/abilities — set/sequence embeddings;
- последние N событий (начать N=16) передаются как context;
- side canonicalization: для модели текущая действующая сторона может всегда преобразовываться в `SELF`, чтобы увеличить sample efficiency.

---

# 14. Модуль M07 — Legal Action Provider

> **Статус checkpoint 0.3.0 — ADVANCED PARTIAL.** MOVE/MELEE/RANGED/WAIT/DEFEND, move+attack, large/flyer/shooter rules, hero actions и subset spells/abilities реализованы. Held-out observed basic-action representability ~98.03%; remaining failures mostly special movement/ability mechanics.

## Назначение

Предоставлять planner набор candidate actions.

## Три источника

### Source 1 — Client legal actions (лучший для текущего observed state)

Если Phase 0 показывает, что официальный client уже вычисляет reachable cells/targets, adapter читает их read-only. Это authoritative legal set только для текущего реального состояния.

### Source 2 — Exact generic generator

Точные общие действия:

- wait/defend;
- movement geometry/pathfinding;
- базовые melee/ranged цели;
- известные spells/abilities plugins.

### Source 3 — Learned action proposal

Для speculative states, где full exact legality неизвестна, model предлагает top-K действий + probability of legality. World model умеет возвращать `INVALID_ACTION` penalty.

## Contract

Planner никогда не должен считать отсутствие learned proposal доказательством нелегальности. Для критичных состояний action coverage должен измеряться.

## Metrics

- `legal_recall@K` — доля реально выбранных действий, присутствующих в candidates;
- target: >= 99.9% на held-out replay для разумного K;
- current observed state при client legal source: 100% относительно клиента.

---

# 15. Модуль M08 — Opponent Policy Model

> **Статус checkpoint 0.3.0 — BASELINE COMPLETE / FULL MODEL PARTIAL.** Production fallback использует train-only creature-conditioned action-type prior: held-out PvE top-1 62.81%, top-3 96.11%. Neural candidate-action ranker остаётся experimental из-за неполного authoritative legal-action set.

## Назначение

Оценить распределение поведения PvE:

`π_enemy(a | state)`.

Это важно: search должен учитывать наиболее вероятные ответы реального PvE, а не абстрактного идеального противника.

## Архитектура v1

Entity Transformer:

- entity tokens: 14–32+;
- effect/ability embeddings агрегируются per entity;
- board positional encoding;
- global token;
- recent event tokens;
- action encoder;
- score head `Q_policy(state, candidate_action)`.

Рекомендуемый старт:

- hidden 256;
- 6 transformer blocks;
- 8 heads;
- FFN 1024;
- порядка 10–25M params.

Модель не должна иметь fixed output size вида 120 cells + N abilities. Использовать **candidate-action ranking**: state encoder + action encoder -> logit для каждого предложенного action. Это автоматически поддерживает variable action space.

## Training

Cross entropy по legal candidates + label smoothing минимально/по эксперименту. Hard negative mining — действия, которые похожи по геометрии/целям на выбранное.

## Metrics

- top-1 accuracy;
- top-3/top-5 recall;
- negative log likelihood;
- expected calibration error;
- accuracy по PvE mode, creature, ability, battle stage;
- entropy distribution.

## Acceptance Gate

Planner integration разрешается, когда top-K coverage стабильно высока на held-out battles и probability calibration приемлема. Абсолютный target определить после baseline, но ориентир для top-3 — >95% на хорошо покрытых режимах.

---

# 16. Модуль M09 — Player Policy / Action Prior

> **Статус checkpoint 0.3.0 — BASELINE COMPLETE / FULL MODEL PARTIAL.** Train-only player action-type prior работает на real corpus: held-out top-1 70.76%, top-3 93.46%. Полная candidate-action policy/distillation from search не завершена.

## Назначение

Быстро отсекать очевидно слабые действия пользователя при поиске.

## Источники обучения

1. human actions — только warm start;
2. search-improved actions после появления planner;
3. successful trajectory reweighting;
4. optional offline RL позже.

## Важное ограничение

Модель не должна стать потолком search. PUCT обязан иметь exploration и периодически исследовать low-prior candidates.

---

# 17. Модуль M10 — Value & Risk Model

> **Статус checkpoint 0.3.0 — ADVANCED BASELINE.** Battle-balanced P(win) model обучен на raw corpus: test Brier 0.05176 против 0.11891 у constant baseline, AUC 0.9889. Ability uncertainty/risk layer работает; quantile/CVaR outcome heads и полноценная calibration suite ещё частично.

## Назначение

Оценить долгосрочную привлекательность позиции без досчёта боя до terminal.

## Выходы

Минимум:

```text
P(win)
P(loss)
Expected remaining force
Quantiles of remaining force: q10/q50/q90
Expected turns_to_terminal
Model uncertainty
```

Предпочтительно distributional value, а не один scalar.

## Основная utility

По умолчанию:

`U = P(win) - lambda_risk * downside_risk + tiny_secondary_terms`

где downside risk можно реализовать через нижний quantile/CVaR по outcome distribution.

Важное правило: secondary objective не должен менять выбор с явно большей `P(win)`, если разница превышает configurable epsilon.

## Calibration

`P(win)=0.8` должна примерно означать 80% wins на калибровочном bucket. Использовать Brier score, reliability plots, temperature/isotonic calibration.

---

# 18. Модуль M11 — Learned World / Dynamics Model

> **Статус checkpoint 0.3.0 — PARTIAL / EXPERIMENTAL.** Есть structured dynamics scaffold и несколько learned residual/proc/collateral models, но полноценный multi-step learned world ensemble с 2/4/8/16-step divergence gate не доведён до production. Основной rollout сейчас hybrid exact + learned residual.

## Назначение

Предсказывать последствия гипотетического действия там, где exact simulator отсутствует:

`P(state_{t+1}, events | state_t, action_t)`.

Это ключевой компонент, позволяющий не ждать ручной реализации всех существ/абилок.

## Рекомендуемый подход v1

Не пытаться генерировать весь state как плоский vector. Предсказывать structured delta:

1. event type sequence;
2. affected entity IDs;
3. position delta;
4. count/top HP delta;
5. ATB/initiative delta;
6. added/removed effects;
7. spawned/dead entities;
8. stochastic branch probabilities;
9. terminal flag.

После prediction delta применяется к immutable state через общий state transition layer.

## Uncertainty

Обязательна. Реализовать минимум одним из:

- ensemble 3–5 моделей;
- dropout/MC dropout на evaluation path;
- explicit uncertainty head.

Предпочтительно ensemble для dynamics v1.

## Multi-step validation

One-step accuracy недостаточна. Считать rollout divergence на 2, 4, 8, 16 полуходах по replay, принудительно подставляя реальные actions.

## Decision Gate: learned vs exact

Для каждой family mechanic/ability считать error buckets. Если механика систематически превышает threshold:

- пометить `requires_exact_rule=true`;
- реализовать plugin в M12;
- dynamics model получает exact result или учится только residual.

Это делает покрытие всех существ постепенным, но не ограничивает продукт subset'ом.

---

# 19. Модуль M12 — Exact Rules / Hybrid Simulator

> **Статус checkpoint 0.3.0 — ADVANCED PARTIAL.** C++ simulator поддерживает generic mechanics и широкий Ability Registry. 85 ability имеют exact-search support; реализованы retaliation variants, multi-hit, resistances/immunities, status lifecycle, hero spells, modeled procs/collateral и ability-conditioned damage. Сложные summon/control/active abilities ещё расширяются.

## Назначение

Точная часть dynamics для общих и критичных механик.

## Обязательный baseline exact core

Независимо от learned model точно реализовать:

- board occupancy/geometry;
- movement/path constraints, которые подтверждены;
- basic state mutations;
- death/removal;
- generic turn lifecycle;
- known deterministic counters;
- schema-level effect add/remove;
- terminal condition;
- ability plugin dispatch framework.

## Plugin interface

```cpp
class RulePlugin {
public:
  virtual bool applies(const BattleState&, const Action&) const = 0;
  virtual TransitionResult apply(const BattleState&,
                                 const Action&,
                                 RngContext&) const = 0;
};
```

## Priority

`Exact plugin > exact generic rule > learned dynamics`.

## Regression

Каждый plugin добавляется только вместе с replay fixtures, которые раньше ломали learned/generic transition.

---

# 20. Модуль M13 — Search Planner

> **Статус checkpoint 0.3.0 — ADVANCED PARTIAL.** Open-loop PUCT/search использует policy priors, value, next-actor model, stochastic damage/proc/collateral и ability-risk. На real held-out regression 20/20 states получили recommendation; action-type stability 100%, exact-action stability 90% при 300→1200 simulations. Нет полноценной transposition/tree-reuse системы.

## Назначение

Найти действие с максимальной risk-adjusted вероятностью победы.

## Алгоритм

Основной: **PUCT/MCTS с stochastic/opponent nodes**.

Типы узлов:

1. `SELF_DECISION` — выбирает search policy;
2. `ENEMY_DECISION` — ветви взвешиваются `π_enemy`;
3. `CHANCE` — random outcomes dynamics;
4. `LEAF` — value model;
5. `TERMINAL` — exact win/loss.

## Почему не plain minimax

PvE не обязательно оптимален. Использовать реальную learned policy противника повышает полезность search.

## Expansion

- self: top-K player policy + progressive widening;
- enemy: top probability mass до cumulative threshold, например 0.98, с cap;
- chance: explicit exact outcomes, если мало; иначе sampling.

## PUCT

Использовать стандартную форму приоритета, но параметры конфигурируемы. Node statistics:

- visits `N`;
- total value `W`;
- mean `Q`;
- prior `P`;
- uncertainty;
- virtual loss для parallel search.

## Search horizon

Не фиксировать «10». Использовать termination по одному из условий:

- terminal;
- max depth;
- uncertainty слишком высокая;
- budget exhausted;
- value confidence достаточна.

Default profiles:

- FAST: 10k simulations, depth cap 8–12;
- NORMAL: 50k–100k, depth cap 12–20;
- DEEP: 500k+, depth cap 20–40;
- ANALYSIS: time budget 1–5 min.

Числа являются стартовыми профилями, затем корректируются benchmark'ами.

## Tree reuse

После пользовательского хода и фактического ответа PvE попытаться re-root на matching observed child state hash. Если mismatch — discard tree.

## Transposition table

Использовать Zobrist/strong canonical hash + checksum. Один и тот же state, достигнутый разным порядком, должен делить value statistics, если history-dependent mechanics полностью представлены в state.

## Output

`Recommendation`:

```json
{
  "battleId": "...",
  "stateHash": "...",
  "bestAction": {...},
  "winProbability": 0.973,
  "confidence": 0.86,
  "alternatives": [...],
  "principalVariation": [...],
  "simulations": 81422,
  "elapsedMs": 4280,
  "warnings": []
}
```

---

# 21. Модуль M14 — Orchestrator / Replanning Loop

> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE OFFLINE.** capture -> session -> decode -> plan -> state-hash validation -> auto-replan реализовано. Incremental decoder детерминирован 866/866 replay. Полный active-battle closed loop ещё требует проверки в пользовательском Chromium на живом бою.

## Назначение

Склеить online систему.

## State machine

```text
IDLE
 -> ATTACHED
 -> WAITING_FOR_STATE
 -> PLANNING
 -> RECOMMENDATION_READY
 -> WAITING_FOR_USER_MOVE
 -> OBSERVING_RESULT
 -> PLANNING ...
 -> TERMINAL
```

## Правила

- только один active planning job на battle revision;
- приход нового observed state отменяет старый job;
- UI никогда не показывает recommendation, рассчитанный для старого state hash;
- cancellation cooperative и быстрый;
- если decoder сообщает uncertainty/partial state, planner не должен молча выдавать «точный» ход — UI показывает degraded mode.

---

# 22. Модуль M15 — Inference Runtime

> **Статус checkpoint 0.3.0 — PARTIAL.** Основные production baseline-модели загружаются C++ из CSV/JSON (policy/value/damage/ability/proc/collateral/next-actor/spells). PyTorch/ONNX export path есть, но ONNX Runtime C++ batching/manifest subsystem из исходного ТЗ не завершён.

## Назначение

Эффективно выполнять policy/value/dynamics модели из C++.

## ONNX sessions

- отдельные session objects для policy/value/dynamics или multi-head model;
- preallocated tensors;
- batching queue;
- CPU provider default;
- CUDA/DirectML optional;
- model warmup при старте daemon.

## Dynamic batching

Search генерирует много leaf states. Не вызывать GPU на каждом node. Использовать queue:

1. MCTS workers ставят inference requests;
2. batcher собирает до `B` или `max_wait_us`;
3. один batched inference;
4. futures возвращают результат workers.

Стартовые значения: batch 64–512; max wait 0.2–1.0 ms. Оптимизировать benchmark'ом.

## Model manifest

Каждый ONNX обязан иметь manifest:

```yaml
model_id: opponent_policy_2026_08_09_001
schema_version: 3
catalog_version: 17
ruleset_range: [2026-07-01, 2026-08-09]
training_data_hash: ...
metrics:
  top1: ...
  ece: ...
```

Несовместимая модель не загружается.

---

# 23. Модуль M16 — Local Service API

> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE.** Loopback C++ HTTP daemon, health/status/state/capture/recommend/debug endpoints, origin filtering, capture persistence и concurrency реализованы. Pairing token и WebSocket streaming остаются незакрыты.

## Назначение

Связать extension, solver и debug tools.

## Endpoints

```text
GET  /health
GET  /version
POST /session/attach
POST /session/raw-envelope
GET  /session/{id}/state
POST /session/{id}/plan
GET  /session/{id}/recommendation
WS   /session/{id}/stream
GET  /models
POST /debug/import-replay
```

Production build должен слушать только `127.0.0.1` по умолчанию.

## Authentication

Extension и daemon обмениваются local random token при pairing. Не открывать unauthenticated command API на LAN.

---

# 24. Модуль M17 — User Interface

> **Статус checkpoint 0.3.0 — PARTIAL / USABLE.** Chromium side panel показывает daemon/session/recommendation/alternatives и автоматически обновляется после capture. Полноценная battle overlay/PV visualization, rich creature/ability explanation и live usability QA ещё не завершены.

## Основной UI

Chrome Side Panel.

Показывать:

### Верхняя строка
- battle ID;
- state sequence;
- connection status;
- model/ruleset compatibility.

### Главная рекомендация
- тип действия;
- actor;
- цель;
- клетка назначения;
- способность;
- визуальная текстовая форма, например: `Стек #4 -> MOVE (7,5)` или `Стек #2 -> ATTACK enemy #6 from (8,4)`;
- `P(win)`;
- confidence.

### Альтернативы
2–5 actions с `P(win)`/search visits.

### Principal variation
До 6–12 прогнозируемых полуходов с пометкой, что линия условная.

### Diagnostics
- search time;
- simulations;
- tree nodes;
- model uncertainty;
- warnings: unknown ability/protocol token/partial state.

## Optional overlay

Можно добавить read-only подсветку рекомендуемой клетки поверх игрового canvas, но **не в MVP**. Если добавляется, overlay не должен генерировать события мыши и должен иметь `pointer-events:none`.

---

# 25. Модуль M18 — Training Pipeline

> **Статус checkpoint 0.3.0 — ADVANCED PARTIAL.** Реальные train-only/held-out pipelines построены для policy priors, P(win), physical damage residual, ability residual, hero spell damage, next actor, proc/collateral/kill-trigger и Raise Dead/Phantom experiments. End-to-end production neural training/dynamics/distillation pipeline ещё частично.

## Команды

```bash
python -m corpus.import ...
python -m dataset.build --config configs/dataset.yaml
python -m training.train_opponent --config ...
python -m training.train_value --config ...
python -m training.train_dynamics --config ...
python -m evaluation.full_suite --model ...
python -m export.onnx --checkpoint ...
```

## Reproducibility

Сохранять:

- git commit;
- dataset manifest/hash;
- random seed;
- package lock;
- CUDA/PyTorch version;
- model config;
- metrics;
- catalog/ruleset version.

## Checkpoint policy

Не выбирать «best» только по training loss. Для policy — NLL + calibration + top-K; для dynamics — multi-step rollout; для value — Brier/calibration; итоговый model set — по planner benchmark.

---

# 26. Модуль M19 — Evaluation Harness

> **Статус checkpoint 0.3.0 — ADVANCED PARTIAL.** Есть C++/Python regression, corpus-check, 866-battle shadow replay, held-out legal coverage, policy/value/damage metrics, planner stability и ability-risk attribution. Нет Level 4 live shadow на активном бою и Level 5 human-in-loop hard-PvE win-rate suite.

Это критический модуль. Без него проект легко будет казаться работающим, но советовать плохие ходы.

## Level 1 — Decoder

- golden payload parsing;
- exact event sequences;
- state hashes.

## Level 2 — Models

### Opponent
- top-k;
- NLL;
- calibration.

### Value
- Brier;
- ROC/AUC secondary;
- calibration curve;
- error by battle stage.

### Dynamics
- one-step structured exact match;
- numeric deltas;
- effect set F1;
- 2/4/8/16-step rollout divergence.

## Level 3 — Planner offline

Replay re-decision benchmark:

На каждом state из held-out successful/failed battles запустить planner без просмотра future и записать recommendation. Нельзя автоматически считать отличие от человеческого action ошибкой. Метрики:

- value of recommended action по available learned/exact rollouts;
- agreement with strong successful trajectories;
- stability при увеличении budget;
- action flip rate;
- risk reduction.

## Level 4 — Shadow Mode online

Система наблюдает реальные бои, но пользователь играет сам. Сравнивать recommendation и фактический outcome. Никакого влияния на игру.

## Level 5 — Human-in-the-loop trials

Пользователь вручную исполняет рекомендации. Считать:

- win rate по difficulty bucket;
- baseline human win rate;
- average attempts to win;
- calibration фактического P(win);
- fraction recommendations invalid/unexecutable = должно быть 0 для observed state.

---

# 27. Производительность и ресурсные бюджеты

## 27.1. Целевой локальный ПК

### Минимально полезный
- CPU: 6–8 современных ядер;
- RAM: 16 GB;
- GPU: не обязателен;
- storage: 20–50 GB свободно для dataset subset/models/logs.

### Рекомендуемый
- CPU: 8–16 производительных ядер;
- RAM: 32 GB;
- GPU: NVIDIA 8–16 GB VRAM или эквивалентный DirectML-capable GPU;
- NVMe: 100+ GB свободно для corpus/training.

### Для комфортного обучения
- GPU: 16–24 GB VRAM;
- RAM: 32–64 GB;
- NVMe: 200+ GB при большом corpus.

## 27.2. Размер моделей

Ориентиры, не жёсткие лимиты:

- opponent policy: 10–30M params;
- value/risk: 10–30M;
- dynamics: 20–80M;
- общий ONNX footprint FP16: обычно сотни MB, не гигабайты.

Не увеличивать модель без доказанного bottleneck по metrics.

## 27.3. Search memory

Планировать node размер <= 192 bytes без полного копирования `BattleState` в каждом node. Хранить state delta / arena allocations / shared immutable state.

- 100k nodes: десятки MB плюс caches;
- 1M nodes: порядка сотен MB, общий process budget с model/caches ориентировочно 1–4 GB.

## 27.4. Runtime latency targets

- state ingestion: <250 ms после client update;
- decoder: <10 ms common case;
- recommendation FAST: <2 s на recommended desktop;
- NORMAL: 2–10 s;
- DEEP: user-configured 30–120 s;
- UI update после завершения plan: <100 ms.

Это target gates; agent обязан сделать benchmark, а не подгонять фиктивные цифры.

## 27.5. Simulator/search throughput target

Для exact/generic C++ transitions целиться минимум в 100k transitions/s на одном современном core и масштабирование на несколько workers. Для learned dynamics основное ускорение достигается batching на GPU.

Главный критерий — не raw transitions/s, а `win-rate improvement per second of planning`.

---

# 28. Как считать длинный бой порядка 70 полуходов

Система не решает полное дерево 70 уровней.

Пример NORMAL режима:

1. На каждом пользовательском decision point — 50k search simulations.
2. Средняя speculative depth — 12–16 полуходов.
3. Leaf оценивает value network.
4. После фактического хода tree re-root/replan.

Если в бою около 35 пользовательских decision points и на один план уходит 3–8 секунд, полный бой будет сопровождаться примерно 2–5 минутами суммарных вычислений, распределёнными между ходами. Это acceptable для трудного PvE, поскольку пользователь всё равно действует пошагово.

DEEP mode может тратить десятки секунд на критичный ход. Не считать это дефектом, если quality noticeably improves.

---

# 29. Работа со стохастикой

## Источники случайности

Система обязана предполагать наличие random outcomes даже если конкретная механика неизвестна.

## Представление

Dynamics возвращает distribution/branches:

```text
TransitionDistribution
  outcome_1: p=0.70
  outcome_2: p=0.25
  outcome_3: p=0.05
```

Если точный набор исходов велик, использовать sampling.

## Risk mode

Default objective — conservative:

1. сначала `P(win)`;
2. затем downside risk;
3. затем remaining force.

Добавить профили:

- `SAFE` — сильнее штрафует tail risk;
- `BALANCED` — default;
- `GREEDY` — больше secondary reward, но не default.

---

# 30. Action explanation

Объяснение не должно строиться LLM в критическом loop. Формировать детерминированно из search stats:

```text
Рекомендуется WAIT стеком #3.
P(win): 96.8% (альтернатива ATTACK: 91.2%).
Основная причина: WAIT сохраняет стек вне ответного удара до следующего ATB окна.
Search: 82k simulations, confidence 0.84.
```

Для «причины» использовать feature attribution/search comparisons, а не фантазировать текст.

---

# 31. Versioning и защита от патчей игры

Каждый observed battle получает:

- `protocol_version`;
- `catalog_version`;
- inferred `ruleset_version/date`;
- client asset fingerprint при возможности.

Если fingerprint изменился:

1. отметить protocol as unverified;
2. прогнать smoke fixtures/live capture;
3. запретить high-confidence recommendation при decoder warnings;
4. не смешивать новые данные в старый dataset без manifest.

Создать `compatibility matrix`:

```text
client fingerprint -> decoder version -> catalog -> model set
```

---

# 32. Error handling / degraded modes

## E1. Local daemon недоступен
Extension показывает offline; игра работает как обычно.

## E2. Decoder partial
UI: `STATE PARTIAL`; planner может работать только если missing fields не критичны; иначе no recommendation.

## E3. Unknown token/ability
Сохранить raw; dynamics uncertainty повышается; recommendation помечается low confidence.

## E4. Model incompatible
Fallback CPU/older compatible model или no recommendation; никогда не silently load mismatched schema.

## E5. Search time exceeded
Вернуть best-so-far только если привязан к текущему state hash.

## E6. Новое состояние во время search
Cancel old search, begin new search.

## E7. Recommendation invalid по клиенту
Считать Severity-1 bug. Логировать полный state/action/model/search snapshot для regression fixture.

---

# 33. Security / privacy

- bind daemon на loopback;
- pair extension token;
- не хранить auth cookie/password;
- raw HTML/network payload может содержать user identifiers — debug capture должен иметь clear setting и retention policy;
- logs не должны содержать session cookies/authorization headers;
- модели и datasets локальны по умолчанию;
- никаких remote telemetry без explicit opt-in.

---

# 34. Compliance boundary

Официальные правила HeroesWM на дату ТЗ запрещают ПО, эмулирующее присутствие игрока, и предупреждают об автоматических/полуавтоматических запросах, создающих нагрузку. Поэтому implementation scope:

**Разрешённый по ТЗ функционал:** read-only observation, локальный анализ, рекомендация пользователю, ручное исполнение пользователем.

**Не реализовывать:** auto-click, auto-cast, автоматический выбор клетки, отправка команд боя, анти-AFK, имитация user input, высокочастотный массовый scraper по умолчанию.

Если позднее пользователь захочет автоматическое управление, это отдельный продуктовый/правовой decision и не входит в данное ТЗ.

---

# 35. План реализации по фазам

## Phase 0 — Protocol feasibility spike

> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE.** Historical raw transport подтверждён и собран на 866 боях; grammar reverse engineering и client resource analysis выполнены. Не закрыта только проверка live active-battle transport в пользовательском браузере.

**Цель:** снять самые большие неизвестности до ML.

### Tasks

P0-01. Создать пустой monorepo/build.  
P0-02. Сделать MV3 extension, которая логирует URL/типы боевых network responses без body.  
P0-03. На тестовом бою включить capture body только allowlisted response.  
P0-04. Сохранить 5–20 raw payloads одного боя по мере ходов.  
P0-05. Проверить fetch/XHR/runtime источник.  
P0-06. Проверить, можно ли восстановить active entity, позиции, counts, ATB, effects.  
P0-07. Сопоставить `battle.php?lastturn=-3` completed payload с warlog client data.  
P0-08. Документировать protocol-notes и unknowns.

### Exit Criteria

- доказан автоматический read-only capture состояния;
- получен минимум один бой `raw update -> parsed state progression`;
- нет дополнительных запросов к серверу в primary path;
- определён формат `RawBattleEnvelope`.

**Если Phase 0 не выполнена — не начинать обучение.**

---

## Phase 1 — Canonical State + Decoder MVP

> **Статус checkpoint 0.3.0 — ADVANCED PARTIAL.** Canonical state и independent decoder работают; 100% record coverage, 847/866 final structural-ready, held-out player-state ready 97.72%. Остаток — редкая geometry/semantic mechanics.

P1-01. Protobuf schemas.  
P1-02. Parser/tokenizer.  
P1-03. BattleState reducer.  
P1-04. Golden fixtures.  
P1-05. State inspector CLI.  
P1-06. Hash/versioning.

Exit: один полный replay проходит end-to-end и визуально/логически совпадает с клиентом по ключевым состояниям.

---

## Phase 2 — Closed-loop plumbing без AI

> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE.** Local capture/session/API/auto-replan/stale invalidation реализованы и replay-tested. Нужна live-browser validation.

P2-01. Local C++ daemon.  
P2-02. WebSocket extension connection.  
P2-03. Session state machine.  
P2-04. Side panel.  
P2-05. Dummy recommendation, привязанный к state hash.  
P2-06. Automatic update after user move.

Exit: пользователь делает ход -> UI автоматически видит новую revision и обновляется без refresh/ручной команды.

---

## Phase 3 — Corpus + dataset

> **Статус checkpoint 0.3.0 — COMPLETE FOR CURRENT DATA.** 866 raw battles, 52,357 accepted decisions, battle-level temporal split и corpus reports построены.

P3-01. Replay importer.  
P3-02. Parquet writer.  
P3-03. Dedup/splits.  
P3-04. Dataset inspector.  
P3-05. 1k+ battle pilot dataset.  
P3-06. Data quality report.

Exit: reproducible dataset manifest; transitions можно воспроизвести из raw.

---

## Phase 4 — Baseline models

> **Статус checkpoint 0.3.0 — COMPLETE AS BASELINE.** Policy priors, P(win), physical/ability damage, hero direct-spell damage и next-actor baseline обучены на real corpus и имеют held-out metrics.

P4-01. Opponent policy baseline.  
P4-02. Value baseline.  
P4-03. Human action prior.  
P4-04. Calibration.  
P4-05. ONNX export/inference benchmark.

Exit: model metrics > naive baselines; C++ ONNX outputs numerically совпадают с Python within tolerance.

---

## Phase 5 — Dynamics v1

> **Статус checkpoint 0.3.0 — PARTIAL.** Вместо полного learned dynamics production использует hybrid exact simulator + learned residual/proc/collateral. Full ensemble/multi-step gate ещё не закрыт.

P5-01. Structured transition target.  
P5-02. Model.  
P5-03. One-step eval.  
P5-04. Multi-step forced-action rollout.  
P5-05. Error buckets by ability/mechanic.  
P5-06. Uncertainty ensemble.

Exit: определено, где learned dynamics достаточно точна и где нужны exact plugins.

---

## Phase 6 — Search v1

> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE.** PUCT/search на real states работает и проходит stability regression. Tree reuse/transpositions и более сильная stochastic opponent branching ещё в развитии.

P6-01. Immutable/speculative state layer.  
P6-02. PUCT single-thread.  
P6-03. Enemy/chance nodes.  
P6-04. Value leaves.  
P6-05. Progressive widening.  
P6-06. Tree reuse.  
P6-07. Search benchmarks.

Exit: planner стабильно возвращает action на synthetic/golden tactical cases и улучшается с budget.

---

## Phase 7 — Hybrid exact rules

> **Статус checkpoint 0.3.0 — IN PROGRESS / ADVANCED.** Ability Registry 421 codes; 85 exact-search abilities плюс partial/proc/collateral/kill-trigger layers. Работа продолжается по high-impact unresolved abilities.

P7-01. Generic board lifecycle.  
P7-02. Ability plugin API.  
P7-03. Автоматический error report dynamics -> top failing mechanics.  
P7-04. Реализовывать exact plugins в порядке impact.  
P7-05. Regression fixtures.

Exit: multi-step divergence заметно снижена на реальных боях.

---

## Phase 8 — Online advisor MVP

> **Статус checkpoint 0.3.0 — PARTIAL.** Daemon+extension+sidepanel и API готовы; отсутствует только подтверждённый active-battle end-to-end run на пользовательской машине и UI polish.

P8-01. Подключить planner к live session.  
P8-02. FAST/NORMAL/DEEP profiles.  
P8-03. Recommendation UI.  
P8-04. Principal variation.  
P8-05. Cancellation/replanning.  
P8-06. Shadow mode logging.

Exit: ссылка/открытый бой -> рекомендация -> ручной ход -> автоматическая новая рекомендация.

---

## Phase 9 — Search improvement loop

> **Статус checkpoint 0.3.0 — IN PROGRESS.** Planner held-out stability, ability risk, next-actor, damage/value baselines и mechanic attribution уже используются. Дальнейшее улучшение mechanics/search продолжается.

P9-01. Сохранять search policy targets.  
P9-02. Train player policy на MCTS distribution.  
P9-03. Re-train value на search-enhanced targets.  
P9-04. Повторять offline evaluation.  
P9-05. Не допускать self-training collapse: mix original data and holdout untouched.

---

## Phase 10 — Hard PvE quality program

> **Статус checkpoint 0.3.0 — NOT COMPLETE.** Нет live hard-PvE benchmark с attempts-to-win/win-rate uplift. Это следующий продуктовый этап после live validation и дальнейшего ability coverage.

P10-01. Собрать curated набор самых трудных боёв.  
P10-02. Для каждого хранить initial state, human outcomes, attempts, known winning trajectories.  
P10-03. Запускать planner budgets от 1k до 1M.  
P10-04. Строить compute-vs-win-quality curve.  
P10-05. Находить failure categories.  
P10-06. Добавлять data/rules/model capacity только по evidence.

---

# 36. Definition of Done для MVP

MVP считается готовым, если одновременно выполнено:

1. Пользователь открывает поддерживаемый PvE бой.
2. Extension автоматически определяет battle ID и получает первое состояние.
3. Daemon декодирует его без ручного ввода.
4. Solver выдаёт recommendation, привязанный к state hash.
5. UI показывает action в однозначной форме.
6. Пользователь вручную делает ход.
7. Новое observed state автоматически обнаруживается.
8. Старый plan invalidated/re-rooted.
9. Новый action появляется автоматически.
10. На наборе минимум 100 held-out live/replay states рекомендация ни разу не является технически невозможной для observed state.
11. Opponent/value models имеют сохранённые reproducible metrics.
12. NORMAL mode работает локально без cloud dependency.
13. Весь проект поднимается из чистого checkout по README.
14. CI проходит unit/integration tests.

Это functional MVP, а не обещание высокой win rate. Боевой quality milestone определяется отдельно.

---

# 37. Definition of Done для «полезного solver»

После MVP считать систему практически полезной только при достижении:

- measurable win-rate uplift относительно выбранного human/baseline на curated hard-PvE suite;
- calibrated P(win);
- invalid recommendation rate = 0 на observed-state legal actions;
- protocol drift обнаруживается автоматически;
- planner quality монотонно/почти монотонно улучшается при увеличении search budget;
- нет систематической категории популярных abilities с неконтролируемой dynamics error;
- типичный NORMAL planning укладывается в 2–10 секунд на recommended PC.

---

# 38. Тестовая стратегия

## Unit

- geometry;
- hashing;
- protobuf conversion;
- parser tokens;
- state reducer;
- PUCT formulas;
- risk utility;
- model manifest validation.

## Property-based

- apply delta не создаёт negative counts;
- serialize/deserialize roundtrip;
- canonical state hash invariant;
- action encode/decode roundtrip.

## Integration

- raw payload -> decoder -> state;
- extension capture -> daemon;
- daemon -> ONNX -> recommendation;
- observed update cancels search.

## Golden replay

Минимум 100 разных боёв до серьёзного ML; позже тысячи. Любой decoder/rule change прогоняет golden suite.

## Performance regression

CI/nightly сохраняет:

- decode us/update;
- transition ns/us;
- model batches/s;
- MCTS simulations/s;
- node bytes;
- total latency.

Regression >10–15% требует investigation.

---

# 39. Logging / observability

Каждая recommendation логирует:

```text
battle_id
state_seq/state_hash
model_ids
catalog/ruleset versions
search config
elapsed
simulations
nodes
best action
alternatives
win estimates
uncertainty
warnings
```

Debug bundle одной кнопкой:

```text
state.pb
recent raw envelope hashes
recommendation.json
search config
model manifests
logs tail
```

Не включать cookies.

---

# 40. Конфигурация

Пример `solver.yaml`:

```yaml
runtime:
  bind: 127.0.0.1
  port: 38471
  threads: auto

planner:
  profile: NORMAL
  time_budget_ms: 5000
  simulation_budget: 100000
  max_depth: 18
  enemy_mass_threshold: 0.98
  self_top_k: 12
  risk_mode: SAFE

inference:
  provider: auto
  batch_max: 256
  batch_wait_us: 500

capture:
  store_raw: false
  allowed_hosts:
    - www.heroeswm.ru

ui:
  show_principal_variation: true
  alternatives: 4
```

---

# 41. Приоритеты оптимизации

Не делать premature optimization. Порядок:

1. correctness decoder/state;
2. legal-action correctness;
3. model calibration;
4. planner correctness;
5. profiling;
6. state cloning/allocation reduction;
7. batched inference;
8. parallel MCTS;
9. SIMD/specialized allocators;
10. GPU/TensorRT только если ONNX Runtime benchmark показывает необходимость.

---

# 42. Что НЕ делать агенту

1. Не начинать с большой LLM/vision model.
2. Не делать OCR/canvas CV, пока network/runtime state доступен.
3. Не писать отдельный класс на каждое существо.
4. Не хардкодить output head на фиксированное число существ.
5. Не обучать на transitions с random train/test split.
6. Не считать human action ground-truth оптимумом.
7. Не пытаться brute-force 70 полуходов.
8. Не хранить полный BattleState в каждом MCTS node без профилирования.
9. Не подключать автоклик.
10. Не делать массовый crawler без explicit compliance decision.
11. Не скрывать unknown protocol tokens.
12. Не выдавать рекомендацию для stale state hash.
13. Не увеличивать neural model, пока bottleneck не доказан ablation/metrics.
14. Не считать one-step dynamics accuracy достаточной.

---

# 43. Первые конкретные задачи агенту

Агент после получения этого документа должен начать без дополнительных вопросов следующим образом.

## Sprint 0

1. Создать monorepo указанной структуры.
2. Создать `docs/adr/0001-architecture.md` и перенести ключевые решения.
3. Настроить CMake/Ninja/vcpkg, Python uv, pnpm/Vite.
4. Поднять C++ `solver-daemon` с `/health`.
5. Создать MV3 extension с side panel и websocket connection к daemon.
6. Реализовать MAIN-world instrumentor для `fetch` и XHR в режиме metadata-only.
7. Добавить allowlist HeroesWM battle URLs.
8. Написать browser integration tests на локальной fixture-page, эмулирующей fetch/XHR.
9. Сделать debug export capture.
10. Зафиксировать все неизвестности в `docs/protocol-notes.md`.

## Sprint 1

1. Получить реальные raw payload fixtures вручную через тестовый бой.
2. Реализовать tokenizer/decoder skeleton.
3. Создать Protobuf `BattleState/Action/Event`.
4. Реализовать CLI `replay-inspect`.
5. Восстановить хотя бы positions/counts/active side/turn из одного replay.
6. Сделать state timeline dump.
7. Сравнить с визуальным replay.
8. Добавить golden tests.

Только после Sprint 1 переходить к corpus/ML.

---

# 44. Decision gates, которые агент обязан соблюдать

## DG-1: State acquisition

**Pass:** live state автоматически подхватывается без лишнего polling.  
**Fail:** исследовать runtime adapter; не строить ML на неполных snapshots.

## DG-2: Replay reconstruction

**Pass:** key state timeline корректна.  
**Fail:** расширять decoder; не тренировать noisy targets.

## DG-3: Opponent predictability

**Pass:** top-K существенно лучше baseline.  
**Fail:** проверить missing state/history/PvE mode labels до увеличения модели.

## DG-4: Dynamics multi-step

**Pass:** error приемлема для search depth.  
**Fail:** hybrid exact plugins; не просто увеличивать Transformer.

## DG-5: Search usefulness

**Pass:** больше budget в среднем улучшает held-out tactical quality.  
**Fail:** искать ошибки value/dynamics/tree policy.

## DG-6: Online safety

**Pass:** read-only observer и manual action.  
**Fail:** функция не попадает в production build.

---

# 45. Оценка сложности и сроков

Для одного сильного разработчика/agent-assisted разработки:

| Этап | Оценка |
|---|---:|
| Phase 0 protocol spike | 3–7 дней |
| Decoder + canonical state | 1–3 недели |
| Closed-loop plumbing/UI | 1 неделя |
| Corpus/dataset MVP | 1–2 недели |
| Baseline policy/value | 1–2 недели |
| Dynamics v1 | 2–4 недели |
| Search v1 | 2–3 недели |
| Hybrid hardening | постоянно, первые результаты 2–6 недель |
| Полезный online advisor | ориентир 2–4 месяца |
| Сильный hard-PvE solver | 4–9+ месяцев итераций |

Это порядок величины. Самый большой риск — не coding volume, а protocol/data quality и редкие mechanics interactions.

---

# 46. Оценка вычислительной тяжести

Целевой solver должен запускаться на ПК.

### Почему модель не обязана быть огромной

State содержит десятки entities, а не длинный текст/изображение. Sequence length мала. Поэтому модели порядка десятков миллионов параметров достаточны как стартовая точка.

### Где тратится compute

Главный расход runtime — search: тысячи/сотни тысяч speculative nodes + dynamics/value inference. Именно поэтому важны C++ core, batching и pruning.

### Длинный бой

При 35 пользовательских decision points и 3–8 секунд NORMAL planning на decision — суммарно порядка нескольких минут вычислений на весь длинный бой, но они выполняются частями между ходами. FAST mode может быть существенно быстрее; DEEP — существенно медленнее.

---

# 47. Критерии выбора pure learned vs hybrid

Не принимать решение идеологически.

## Pure learned acceptable, если

- legal action coverage высока;
- one-step dynamics точна;
- 8–16 step rollout не деградирует критично;
- planner online trials дают стабильный uplift;
- rare ability uncertainty корректно детектируется.

## Hybrid обязателен, если

- отдельные mechanics дают systematic errors;
- learned model hallucinate effects;
- rollout error быстро накапливается;
- planner exploits model bugs;
- critical battle outcomes зависят от точных дискретных rules.

Planner exploitation of model error — ожидаемая проблема. Exact plugins и uncertainty penalty должны блокировать её.

---

# 48. Возможное развитие после v1

1. Distillation: большой training model -> маленький inference model.
2. Search policy distillation для быстрого FAST режима.
3. Learned latent dynamics/MuZero-like эксперимент после structured dynamics baseline.
4. Offline RL (IQL/CQL-подобные подходы) как дополнительный policy improvement, не как старт.
5. Automated counterexample mining: planner ищет состояния, где models disagree.
6. Active data curation по rare abilities.
7. GPU exact simulator batches, только если CPU действительно bottleneck.
8. Web UI для анализа завершённых боёв.
9. Visualization search tree.
10. Mode-specific adapters при наличии разных PvE AI policies.

---

# 49. Итоговая продуктовая формулировка

**Вход:** активный battle URL/warid или автоматически обнаруженный открытый HeroesWM бой.  
**Наблюдение:** passive read-only state capture.  
**Решение:** risk-sensitive stochastic planner, использующий learned PvE policy, value, dynamics и exact rule plugins.  
**Выход:** лучший следующий ручной ход + вероятность победы + альтернативы + условная principal variation.  
**Обновление:** автоматически после каждого фактического изменения battle state.  
**Конечная цель:** максимальный стабильный win rate на сложных PvE боях, а не имитация исторических человеческих ходов.

---

# 50. Источники и технические опоры

**S1. Пример боя пользователя:**  
https://www.heroeswm.ru/warlog.php?warid=1671960831

**S2. Общие правила HeroesWM, раздел об автоматических скриптах:**  
https://www.heroeswm.ru/ob-igre-obschie-pravila

**S3. Официальная страница линейки инициативы:**  
https://www.heroeswm.ru/ob-igre-lineyka-iniciativy

**S4. Официальная страница особых умений:**  
https://www.heroeswm.ru/ob-igre-osobye-umeniya

**S5. Официальные правила урона:**  
https://www.heroeswm.ru/ob-igre-pravila-urona

**S6. Пример/историческое обсуждение `battle.php?lastturn=-3&warid=...`:**  
https://mirror.heroeswm.ru/forum_messages.php?page=0&tid=1301855

**S7. Chrome Extensions: scripting / MAIN world:**  
https://developer.chrome.com/docs/extensions/reference/api/scripting

**S8. Chrome Extensions: content scripts / communication:**  
https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts

**S9. PyTorch C++ frontend:**  
https://docs.pytorch.org/cppdocs/frontend.html

**S10. ONNX Runtime C++ API:**  
https://onnxruntime.ai/docs/get-started/with-cpp.html

**S11. CMake current documentation / C++23 support:**  
https://cmake.org/cmake/help/latest/

---

# 51. Короткая инструкция coding agent

> Работай по фазам и decision gates этого ТЗ. Не начинай ML, пока не доказан стабильный live/replay state acquisition. Не автоматизируй действия игрока. Не делай лишних запросов к HeroesWM в primary path. Все внешние данные переводятся в canonical schema. Любая неопределённость протокола фиксируется в diagnostics и ADR, а не скрывается. Сначала correctness и end-to-end closed loop, затем ML, затем search, затем performance. При обнаружении блокирующей неизвестности сделай минимальный эксперимент, задокументируй результат и выбери предусмотренный fallback; не останавливай всю разработку из-за несущественных неизвестностей.

