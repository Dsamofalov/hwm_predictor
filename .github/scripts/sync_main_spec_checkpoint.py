from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'.github/scripts/sync_main_spec_checkpoint.py'
WORKFLOW=ROOT/'.github/workflows/sync_main_spec_checkpoint.yml'


def replace_once(path,old,new):
    p=ROOT/path
    text=p.read_text(encoding='utf-8')
    n=text.count(old)
    if n!=1:
        raise SystemExit(f'{path}: expected one anchor, found {n}: {old[:160]!r}')
    p.write_text(text.replace(old,new,1),encoding='utf-8')


def run(*args): subprocess.run(args,cwd=ROOT,check=True)

for spec in ('SPEC.md','HeroesWM_Solver_TZ_Status_0.3.0.md'):
    replace_once(spec,'**Дата:** 09.08.2026  ','**Дата:** 10.08.2026  ')
    replace_once(
        spec,
        '**Последнее обновление реализации:** 10.08.2026 — Life Drain, Regeneration, Mana Feed и Mighty Slam переведены в exact-search.  ',
        '**Последнее обновление реализации:** 10.08.2026 — основной front: persistent pairing/bearer auth, revision-bound cooperative stale-search cancellation, live revision/hash trace/binding, authenticated local WebSocket streaming и Linux + Windows/MSVC CI gates реализованы; ability-front ведётся отдельно в ветке `ability`.  ',
    )
    replace_once(
        spec,
        '- Automated tests: C++ CTest **100%**, Python **42/42**, TypeScript typecheck/build **PASS**; local API pairing/auth, stale-search cancellation, live binding и WebSocket streaming integration **PASS**.',
        '- Automated tests: Linux C++ CTest **100%**, Python **42/42**, TypeScript typecheck/build **PASS**; pairing/auth, stale-search cancellation, live binding и WebSocket streaming integrations **PASS**. Windows/MSVC job также **PASS**: C++ build/CTest + все четыре daemon integration gates.',
    )
    old='''### Текущий незавершённый фронт разработки

1. Закрытие high-impact unresolved creature abilities; `Life Drain`, `Regeneration`, `Mana Feed` и `Mighty Slam` закрыты 10.08.2026; `Paw Strike` переведён в validated hybrid modeled-proc 10.08.2026, текущая точка исследования — remaining assist/counter/summon/control abilities.
2. Устранение 19 финальных structural-invalid replay (в основном geometry/rare mechanics) без ослабления invariants.
3. Full learned dynamics ensemble и multi-step validation gate.
4. Tree reuse/transposition и дальнейшее улучшение opponent branching.
5. Live validation расширения на **активном** бою (closed-loop trace уже подготовлен) и затем hard-PvE human-in-loop benchmark.
'''
    new='''### Текущий незавершённый фронт разработки

Основной `main`-front и ability-front теперь разделены. Creature abilities продолжаются независимо в ветке `ability`; нижеприведённый порядок — приоритет **основного** фронта.

1. **Real active-battle smoke gate:** выполнить `docs/LIVE_VALIDATION.md` на реальном активном авторизованном PvE-бою. Network capture остаётся primary truth; полноценный runtime-object fallback добавлять только если live trace докажет конкретно отсутствующее canonical/legal-action поле.
2. **M13 chance-outcome correctness → transpositions/tree reuse:** текущий planner исторически хранит один `Edge.child`, хотя `sim_.apply(..., roll)` стохастический. Следующий main-planner набор должен индексировать sampled child outcomes по `state_hash`, не смешивать разные stochastic outcomes в одном первом child-node, затем добавить transposition sharing и только после этого persistent re-root между наблюдаемыми состояниями.
3. **Decoder/legal correctness:** устранить 19 финальных structural-invalid replay без ослабления invariants и поднять held-out observed basic-action representability с **98.03%** к acceptance **>=99.9%**.
4. **Learned dynamics:** full ensemble + multi-step divergence/validation gate; one-step качество само по себе не считать достаточным.
5. **Evaluation:** после стабильного live acquisition — >=100 live/replay state invalid-recommendation gate, затем hard-PvE human-in-loop benchmark / win-rate uplift / calibration.

Ability-front: high-impact unresolved assist/counter/summon/control mechanics ведутся отдельно в `ability` и должны попадать в `main` только после corpus/CI review.
'''
    replace_once(spec,old,new)

# Keep TEST_REPORT honest about the newly validated primary target.
p=ROOT/'TEST_REPORT.md';text=p.read_text(encoding='utf-8')
text=text.replace(
    'WebSocket revision streaming:            PASS\nPython pytest:',
    'WebSocket revision streaming:            PASS\nWindows/MSVC C++ + daemon integrations:     PASS\nPython pytest:',
    1,
)
text=text.replace(
    '1. Active authenticated battle capture/replanning in the user\'s Chromium session. The metadata-only closed-loop trace and `docs/LIVE_VALIDATION.md` are ready for this gate, but the real live exercise has not yet been claimed as complete.\n2. Windows MSVC execution (source/tasks/scripts supplied; current validation environment is Linux).\n3. Hard-PvE human-in-loop win-rate uplift.\n4. Full learned dynamics ensemble / ONNX Runtime C++ production path.',
    '1. Active authenticated battle capture/replanning in the user\'s Chromium session. The metadata-only closed-loop trace and `docs/LIVE_VALIDATION.md` are ready for this gate, but the real live exercise has not yet been claimed as complete.\n2. Hard-PvE human-in-loop win-rate uplift.\n3. Full learned dynamics ensemble / ONNX Runtime C++ production path.',
    1,
)
p.write_text(text,encoding='utf-8')

# Main-front checkpoint: record the platform gate and the audited next M13 risk.
p=ROOT/'docs/MAIN_FRONT_STATUS.md';text=p.read_text(encoding='utf-8')
text += '''\n\n## 2026-08-10 final handoff update\n\n- Authenticated WebSocket functional commit: `68345f0afc89ed0e17884042592fb08b6edd83be`.\n- Standard CI now includes WebSocket streaming and a Windows/MSVC job. CI commit `7353e1ddcf17f27e981cac52f2b1e38f5545881e`: **PASS** on both Linux and Windows; Windows executes C++ build/CTest plus pairing, stale cancellation, live binding and WebSocket daemon integrations.\n- Next main-planner correctness issue identified during audit: `planner.cpp` currently gives each action edge one child while `sim_.apply(..., roll)` is stochastic. Before persistent tree reuse, split sampled outcomes by `state_hash`, share equal states via a transposition table, and regression-test that different sampled outcomes do not reuse a node initialized from the first outcome's legal actions.\n- Stop point for this agent: do not begin that M13 patch in this checkpoint; hand off from here.\n'''
p.write_text(text,encoding='utf-8')

WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True)
run('git','diff','--check')

base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
run('git','config','user.name','github-actions[bot]');run('git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
run('git','add','-A');run('git','commit','-m','docs: sync main specification after live plumbing')
docs_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();run('git','push','origin','HEAD:main')

with (ROOT/'changelog.md').open('a',encoding='utf-8') as f:
    f.write(f'''\n\n### Main-front checkpoint handoff\n\n- Commit: `68345f0afc89ed0e17884042592fb08b6edd83be`\n  - Completed authenticated loopback WebSocket revision/status streaming and extension push-driven replanning.\n- Commit: `7353e1ddcf17f27e981cac52f2b1e38f5545881e`\n  - Standard CI now requires WebSocket streaming and current-MSVC Windows runtime gates.\n  - Workflow run `31367488977`: **PASS** on Linux and Windows. Linux passed C++/CTest, all four daemon integrations, Python 42/42, TypeScript typecheck and extension build. Windows passed MSVC C++ build/CTest plus pairing/auth, stale cancellation, live binding and WebSocket integrations.\n- Commit: `{docs_sha}`\n  - Updated the active general specification (`SPEC.md` and duplicate checkpoint), `TEST_REPORT.md`, and `docs/MAIN_FRONT_STATUS.md` with the current main-front state.\n  - Explicit next M13 correctness gate: stochastic action outcomes must be separated by `state_hash` before transposition/persistent tree reuse; do not keep different sampled outcomes under a single first-initialized `Edge.child`.\n  - Real authenticated active-battle smoke validation remains the immediate product gate before claiming live Browser Bridge/Orchestrator complete.\n''')
run('git','add','changelog.md');run('git','commit','-m','docs: record final main-front handoff checkpoint');run('git','push','origin','HEAD:main')
