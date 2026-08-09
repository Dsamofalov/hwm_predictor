# HeroesWM PvE Solver / Advisor — research build 0.3.0

Локальный **read-only** советник для PvE-боёв HeroesWM. Пользователь выполняет ход вручную; система наблюдает battle state, строит recommendation и после нового observed state перепланирует. Полное ТЗ со статусами реализации: [`SPEC.md`](SPEC.md).

## Текущий checkpoint

Проект уже использует **реальный raw corpus 866 боёв**, а не synthetic protocol. Independent decoder, C++ simulator/search и несколько train-only baseline-моделей работают совместно.

- 866/866 raw battles (`init.txt` + `turns0.txt`) разобраны; low-level coverage 100%.
- Incremental replay совпадает с one-shot 866/866.
- Final structural-ready: 847/866; held-out player-state structural-ready: 97.72%.
- Dataset: 52,357 accepted decisions, 644 creature ID.
- Ability catalog: 421 codes; 81 exact-search, 11 exact-targeting, 18 partial-exact, 8 modeled-proc, 5 modeled-collateral, 2 kill-trigger; 78 unresolved.
- Held-out action priors: PLAYER 70.76% top-1 / 93.46% top-3; PvE 62.81% / 96.11%.
- P(win): test Brier 0.05176 vs 0.11891 constant baseline; AUC 0.9889.
- Planner real-state regression: 20/20 recommendations, 100% action-type stability, 90% exact-action stability at 300→1200 simulations.
- Tests: C++ 100%, Python 39/39, TypeScript typecheck/build PASS.

**Не считается готовым production-продуктом:** остаются rare geometry/mechanics, часть сложных abilities, full learned-dynamics gate, tree reuse и главное — end-to-end validation на реальном активном бою в пользовательском Chromium. Подробно: [`IMPLEMENTATION_REPORT.md`](IMPLEMENTATION_REPORT.md).

## Архитектура

```text
HeroesWM Chromium page
        | passive fetch/XHR capture
        v
MV3 Browser Bridge
        v
C++ local daemon / BattleSession
        v
Independent protocol decoder -> canonical BattleState
        v
Legal actions + exact/learned ability mechanics
        v
PUCT planner + policy/value/damage/proc models
        v
Side panel recommendation
        |
        +-- user performs move manually
        v
new observed state -> stale plan invalidation -> replanning
```

## Что в репозитории

- `cpp/` — C++23 state/decoder/session/simulator/search/API/tests.
- `python/` — raw replay decoder, dataset pipeline, catalog, training/evaluation tooling.
- `extension/` — Chromium Manifest V3 passive browser bridge + side panel.
- `models/` — текущие compact production baseline artifacts (CSV/JSON) и experimental checkpoints.
- `data/catalog/` — каталог 644 creature ID / 421 ability code + Ability Registry.
- `data/reference/` — два HTML reference-source + parsed metadata. Raw ability tags из battle payload остаются authoritative.
- `data/reports/` — corpus/shadow/model/planner/ability-risk metrics.
- `schemas/` — protobuf target contracts.
- `fixtures/` — deterministic protocol/simulator fixtures.
- `.vscode/` — tasks/launch/settings.
- `scripts/` — bootstrap/validate/start/demo.

**Не включены в GitHub snapshot:** build outputs, caches и многосотмегабайтные materialized training datasets (`data/real_dataset_v3..v6`). Их можно воспроизвести из raw corpus. Сам raw 866-battle corpus также хранится отдельно.

# Запуск на Windows 10/11 через VS Code

## 1. Установить

1. Visual Studio 2022 Build Tools → **Desktop development with C++** + Windows SDK.
2. CMake 3.25+.
3. Ninja.
4. Python 3.12/3.13 x64.
5. Node.js 22 LTS + npm.
6. VS Code.
7. Git.

Открой **Developer PowerShell for VS 2022**:

```powershell
cd C:\path\to\heroeswm-solver
code .
```

## 2. Bootstrap

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\bootstrap_windows.ps1
```

## 3. Полная локальная проверка

```powershell
.\scripts\validate_windows.ps1
```

Или в VS Code: `Ctrl+Shift+P` → `Tasks: Run Task` → `Validate all`.

## 4. Demo planner без браузера

```powershell
.\scripts\demo_api_windows.ps1
```

## 5. Daemon

```powershell
.\scripts\start_daemon_windows.ps1
```

Health-check:

```powershell
Invoke-RestMethod http://127.0.0.1:38471/health
Invoke-RestMethod http://127.0.0.1:38471/status
```

## 6. Chromium extension

После `npm run build` / bootstrap:

1. `chrome://extensions` или `edge://extensions`.
2. Developer mode.
3. `Load unpacked`.
4. Выбрать `extension/dist`.
5. Открыть replay/бой HeroesWM и side panel.

Extension read-only: никаких автокликов/боевых команд.

# Raw corpus и dataset

Raw corpus ожидается в виде:

```text
hwm_battles/
  battles/<warid>/
    init.txt
    turns0.txt
    metadata.json
  manifest.jsonl
  summary.json
```

В текущем исследовательском корпусе 866/866 боёв имеют оба raw файла. Сам corpus намеренно не лежит в GitHub snapshot.

Последний materialized dataset report:

```text
observed decisions: 52,375
accepted decisions: 52,357
unknown low-level commands: 0
creature ids: 644
chronological split: 80/10/10 by battle id
```

# Knowledge / abilities

Основное правило: **raw server-declared ability tags определяют, что реально есть у конкретного стека**. HTML-reference не является ground truth; он используется для имени/описания/coverage.

Rebuild catalog (Linux example):

```bash
PYTHONPATH=python python -m hwm_solver.knowledge.build_catalog /path/to/hwm_battles \
  --out data/catalog/generated_v4 \
  --reference-creatures-html data/reference/creatures_daily_help.html \
  --hwm-daily-html data/reference/creatures_hwm_daily.html
```

Rebuild Ability Registry:

```bash
PYTHONPATH=python python -m hwm_solver.knowledge.build_ability_registry data/catalog/generated_v4.json \
  --out data/catalog/ability_registry.json \
  --ability-damage models/ability_damage_model.csv \
  --collateral models/collateral_model.csv \
  --proc models/proc_model.csv \
  --kill-trigger models/kill_trigger_model.csv
```

Support statuses distinguish `exact_search`, `partial_exact`, `exact_targeting`, `modeled_proc`, `modeled_collateral`, `modeled_kill_trigger`, `learned_damage`, `dynamic_spellbook`, `reference_only`, `unresolved`. Unknown/high-impact mechanics raise `ability_risk`; they are not silently treated as ordinary stacks.

# Evaluation commands

C++ corpus validation:

```bash
./build/debug/corpus-check /path/to/hwm_battles
./build/debug/shadow-replay /path/to/hwm_battles
```

Ability risk:

```bash
PYTHONPATH=python python -m hwm_solver.evaluation.ability_risk_report \
  /path/to/hwm_battles --registry data/catalog/ability_registry.json \
  --out data/reports/ability-risk-current.json
```

Key reproducible reports are stored under `data/reports/`.

# Local API

```text
GET  /health
GET  /version
GET  /status
GET  /state
GET  /session/current/state
POST /capture
POST /session/raw-envelope
POST /recommend
POST /session/current/plan
GET  /debug/last-raw
POST /debug/import-replay   (HWM_ENABLE_DEBUG=1)
POST /debug/demo-state      (HWM_ENABLE_DEBUG=1)
```

Daemon bind: `127.0.0.1`. Browser Origin filtering включён. Pairing-token/WebSocket из полного ТЗ пока не закрыты.

# Linux / WSL

```bash
sudo apt update
sudo apt install -y build-essential cmake ninja-build python3 python3-venv nodejs npm
chmod +x scripts/*.sh
./scripts/bootstrap_linux.sh
./scripts/validate_linux.sh
```

# Безопасность и границы продукта

- read-only advisor;
- user performs moves manually;
- no auto-click;
- no gameplay command injection;
- daemon loopback only;
- cookies/authorization headers не пересылаются в daemon;
- raw/HAR/credentials не коммитить;
- unknown mechanics сохраняются и повышают uncertainty, а structural-invalid state блокирует recommendation.

# Что делать дальше

Текущий development frontier:

1. Life Drain и другие high-impact assist/counter/stateful abilities.
2. 19 structural-invalid финальных replay / rare geometry.
3. Full learned dynamics + multi-step divergence gate.
4. Search tree reuse/transposition.
5. Проверка extension/daemon на активном бою в пользовательском Chromium.
6. После этого — hard-PvE human-in-loop benchmark и win-rate uplift.
