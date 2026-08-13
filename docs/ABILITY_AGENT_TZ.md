# HeroesWM Solver — ТЗ для агента по abilities

Версия контракта: 2026-08-13
Рабочая ветка: `ability`
Draft PR: `#1` (`ability` -> `main`)
Целевая product/CI платформа: **Windows 10/11 x64 + Visual Studio 2022 / MSVC**

## 0. Текущий обязательный checkpoint

На момент актуализации ТЗ текущий validated functional ability SHA:

- **`a2c06ef10048486cc84239b045f3710e9f7db795`** — `test(ability): pin Hexing baseline and wire audit`;
- authoritative hosted Ability Windows CI run **`31680364027` — PASS / conclusion `success`**;
- check-suite **`85941007397`**;
- workflow: `.github/workflows/ability.yml`, hosted `windows-latest`.

Этот checkpoint важнее старых handoff-текстов. Перед началом новой functional работы агент обязан сверить фактический HEAD ветки `ability`, этот документ, `docs/ability/AGENT_STATUS.md`, `docs/ability/ability_changelog.md` и `TESTS_CANON.md`.

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

### Текущий active lead: Hexing Attack

Weighted unfinished queue после закрытия Child of the Light ведёт к **`hexingattack`**.

Уже validated на Windows baseline:

- 866 battle dirs;
- 32 Hexing carrier battles;
- 88 carriers;
- carrier creature IDs: `333 = 41`, `269 = 27`, `268 = 20`;
- exact carrier ability sets: `caster,hexingattack,undead` (47) и `alive,caster,hexingattack,ragingblood,sacrificegoblin,swiftattack` (41);
- 115 carrier attacks, все `MELEE_ATTACK`;
- generic parser на carrier attack windows видит 12 zero-cost same-actor/same-target status records: `sff = 5`, `crs = 4`, `slw = 3`;
- raw attack windows дополнительно содержат 3 `Sray...` records, которые generic parser пока не относит к status grammar;
- tooltip перечисляет четыре возможных expert-level эффекта: Curse, Slow, Weakness, Disrupting Ray, но говорит только «с некоторой вероятностью» и **не содержит numeric probability / percentage / integer constant**.

Functional SHA `a2c06ef...` уже добавил whole-corpus collision/layout auditor `python/hwm_solver/ability/hexingattack_wire_evidence.py` для raw candidate codes `crs/slw/sff/ray` и strict baseline assertions в `python/tests/test_hexingattack_evidence.py`. Сам факт PASS этого пакета **не означает**, что `ray` уже доказан как Disrupting Ray или что proc probability известна.

Следующий агент обязан продолжить именно с этого места:

1. Извлечь и проверить whole-corpus output `HEXINGATTACK_WIRE_COLLISION_EVIDENCE` для exact SHA `a2c06ef...` либо повторно запустить exact Hexing node на hosted Windows при необходимости получения полного отчёта.
2. Перевести exploratory lower bounds в **exact corpus contract**: exact counts для `crs/slw/sff/ray`, fixed-width payload shapes, source/target presence, actor/target agreement, attack-bound populations, source ability sets, Hexing vs non-Hexing collisions, zero/positive field populations.
3. Отдельно исследовать normal-cast/server-spellbook controls. Нельзя считать `ray == Disrupting Ray` только из мнемоники `ray` или из соседства с Hexing tooltip. Требуется независимая связь raw wire с server-declared spell identity/cast context.
4. `sff` также нельзя автоматически называть Weakness без независимого discriminator/collision evidence.
5. Не моделировать proc probability из наблюдаемой частоты `12/115`, гипотетической `15/115` или любой другой corpus frequency. Tooltip не даёт numeric constant; trigger attribution и probability — отдельные задачи.
6. Не менять runtime/registry до доказанной semantic boundary. Если wire identity остаётся confounded — закрыть Hexing precise blocker'ом и пересчитать weighted queue.
7. Если независимая identity доказана, сначала pin protocol/wire semantics и positive/negative controls; только затем рассматривать replay/runtime consequence. Никаких speculative formulas/percentages.

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

Ability-agent отвечает только за creature abilities и связанные evidence/tests:

- raw/corpus evidence;
- ability protocol decoding;
- ability-specific replay/simulator/proc/collateral mechanics;
- ability registry/risk evidence;
- C++/Python regressions;
- merge-ready состояние Draft PR #1.

Не переключаться на main-owned planner/M11/live/UI/extension/daemon задачи и не дублировать main-agent.

Ability-agent **не merge'ит `ability` в `main` самостоятельно**. Финальная интеграция принадлежит main/integration agent.

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

- `python/hwm_solver/protocol/replay.py` только для ability decoding;
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

`changelog.md` менять только bookkeeping commit'ом после functional SHA либо docs correction checkpoint.

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
- main-owned product/spec/report docs.

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

- current ability HEAD;
- validated functional SHA;
- main integration reference, если известен;
- hosted Windows run/check-suite/status;
- exact remaining failures/blockers;
- corpus support counts;
- observed coverage;
- baseline/candidate metrics, если есть probability model;
- ability-risk / weighted contribution change;
- exact/modeled/unresolved boundary;
- integration requests;
- следующую механику.

## 11. Коммиты

Делать небольшие логические functional commits.

Каждый functional commit обязан получить hosted Windows validation на exact SHA до semantic claim и до bookkeeping.

После этого — отдельный bookkeeping commit с `ability_changelog.md`, `AGENT_STATUS.md`, `changelog.md`.

Не использовать temporary self-modifying workflows. Не ослаблять assertions ради green CI. Evidence-fail, который опровергает гипотезу, фиксировать как evidence, а не маскировать rerun'ом.

## 12. Review-ready завершение блока

Перед handoff/integration:

1. работа остаётся в `ability`;
2. нет случайных main-owned изменений;
3. exact functional SHA имеет completed/success hosted Windows Ability CI;
4. все evidence claims соответствуют strict corpus tests;
5. `AGENT_STATUS.md` и changelogs актуальны;
6. Draft PR #1 review-ready;
7. **не merge `ability` в `main` самостоятельно**.

Если `main` продвинулся параллельно, не вливать его в ability автоматически после каждой итерации. Синхронизация — только при реальной integration/review необходимости.