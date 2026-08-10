from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8").replace("\r\n", "\n")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")


def replace_line(path: str, prefix: str, replacement: str) -> None:
    lines = read(path).splitlines()
    hits = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    if len(hits) != 1:
        raise RuntimeError(f"{path}: expected one line starting with {prefix!r}, found {len(hits)}")
    i = hits[0]
    lines[i : i + 1] = replacement.splitlines()
    write(path, "\n".join(lines) + "\n")


def replace_block(path: str, start: str, end: str, replacement: str) -> None:
    text = read(path)
    if text.count(start) != 1:
        raise RuntimeError(f"{path}: start anchor count for {start!r} is {text.count(start)}")
    s = text.index(start)
    e = text.find(end, s + len(start))
    if e < 0:
        raise RuntimeError(f"{path}: end anchor missing: {end!r}")
    write(path, text[:s] + replacement.rstrip() + "\n\n" + text[e:])


def replace_status_after(path: str, heading: str, replacement: str) -> None:
    text = read(path)
    h = text.find(heading)
    if h < 0:
        raise RuntimeError(f"{path}: heading missing: {heading!r}")
    marker = "> **Статус checkpoint 0.3.0"
    s = text.find(marker, h)
    if s < 0:
        raise RuntimeError(f"{path}: checkpoint status missing after {heading!r}")
    e = text.find("\n", s)
    if e < 0:
        e = len(text)
    write(path, text[:s] + replacement + text[e:])


def insert_after_heading(path: str, heading: str, marker: str, paragraph: str) -> None:
    text = read(path)
    if marker in text:
        return
    h = text.find(heading)
    if h < 0:
        raise RuntimeError(f"{path}: heading missing: {heading!r}")
    e = text.find("\n", h)
    if e < 0:
        raise RuntimeError(f"{path}: malformed heading: {heading!r}")
    write(path, text[: e + 1] + "\n" + paragraph.strip() + "\n" + text[e + 1 :])


def run(*args: str) -> str:
    proc = subprocess.run(args, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True)
    if proc.returncode:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(args)}\n{proc.stdout}\n{proc.stderr}")
    return proc.stdout.strip()


def commit(message: str, *paths: str) -> str:
    run("git", "add", "--", *paths)
    staged = run("git", "diff", "--cached", "--name-only")
    if not staged:
        raise RuntimeError(f"no staged changes for {message}")
    run("git", "diff", "--cached", "--check")
    run("git", "commit", "-m", message)
    return run("git", "rev-parse", "HEAD")


run("git", "config", "user.name", "github-actions[bot]")
run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
trigger_sha = run("git", "rev-parse", "HEAD")

last_update = "**Последнее обновление реализации:** 11.08.2026 — `main` переведён на Windows-only CI; M13 stochastic outcomes/transpositions/persistent exact re-root дополнены scheduler-recency и semantic-effect hash canonicalization; permanent held-out planner gate расширен до 120 состояний с 0 invalid recommendations; M11 получил reproducible 2/4/8/16-step ensemble, uncertainty/selector/survival/temperature evidence gates, но production learned dynamics остаётся выключенной; real authenticated active-battle smoke и decoder/legal >=99.9% всё ещё обязательны; ability-front ведётся отдельно в ветке `ability`."
planner_metric = "- Permanent held-out planner validity gate: **120/120** sampled states из **109** held-out battles, **0** invalid recommendations, state-hash mismatches, illegal best actions/alternatives или non-finite metrics. На validated Windows run `31431838319` budget `1 -> 120`: action-type stability **99.17%**, exact-action stability **85.83%**."
auto_tests = "- Automated tests / supported platform: Windows 10/11 x64 + MSVC. Последний полностью проверенный functional tree `7cd17878174529a40087ce5a78231dd93690851b`, run `31431838319`: **Core PASS + Full PASS**; MSVC Debug/Release main-front CTest, 120-state planner gate, pairing/auth, stale cancellation, live binding, WebSocket, Python **75/75**, TypeScript/extension, `planner-demo 5000` и все permanent M11 evidence commands PASS. Historical Linux results remain evidence only. После перевода repository в public CI должен использовать GitHub-hosted Windows runners; self-hosted runners больше не являются частью permanent contract. Ability-owned `hwm-tests` остаётся вне main-front CTest до интеграции ветки `ability`."
physical_m11 = """- Physical damage: median abs-log error **0.3574 -> 0.2812** после learned creature residual; для rare creatures ability transfer **0.2719 -> 0.2484**.
- M11 multi-step evidence: five-member train-only physical-damage residual ensemble evaluated at **2/4/8/16** halfturn horizons. Deterministic mean force-L1 at 16 steps **0.04947 vs 0.08125** generic, but invalid-action fraction **3.58% vs 2.51%**; stochastic survival gate at 16 steps **0.05028 vs 0.08178** force-L1 while valid-observed-action coverage is **96.349% vs 97.493%**. Uncertainty/selector experiments do not clear production criteria; leakage-safe positive-residual temperature calibration selects scale **0.0** because no candidate passes the hard joint accuracy/coverage gate. Production learned dynamics remains **disabled**."""
new_front = """1. **Real active-battle smoke gate:** выполнить `docs/LIVE_VALIDATION.md` на реальном активном авторизованном PvE-бою. Это остаётся главным продуктовым блокером для закрытия Browser Bridge/Orchestrator: network capture primary truth, runtime-object fallback только по доказанному отсутствующему полю.
2. **Decoder/legal correctness:** устранить **19** финальных structural-invalid replay без ослабления invariants и поднять held-out observed basic-action representability с **98.03%** к acceptance **>=99.9%**.
3. **M11 learned dynamics:** развить уже работающий 2/4/8/16-step evidence harness из primary physical-damage residual до полноценного structured ensemble. Не включать runtime selector/uncertainty/residual production path, пока одновременно не пройдены multi-step accuracy и observed-action survival/validity gates.
4. **M13 search quality после correctness closure:** safe stochastic outcome separation, transpositions и exact persistent re-root уже реализованы; следующий front — более сильное explicit opponent/chance branching, search calibration и quality/latency trade-offs, не ломая revision cancellation и exact hash/structure guards.
5. **Evaluation:** replay invalid-recommendation gate >=100 states уже закрыт (**120/120**). После stable live acquisition нужны live-state validation и hard-PvE human-in-loop benchmark / win-rate uplift / calibration."""

statuses = {
    "# 10. Модуль M03 — State Store / Battle Session": "> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE.** Thread-safe session, battle reset, duplicate/out-of-order handling, immutable observed state, state hash, revision-bound cooperative stale-search cancellation и incremental decode реализованы. Planner сохраняет search graph между recommendation calls и делает conservative exact re-root только при точном observed hash в том же non-empty battle/perspective и совпадающем structure fingerprint; иначе graph сбрасывается. Остаточный gate — real authenticated live-session validation.",
    "# 18. Модуль M11 — Learned World / Dynamics Model": "> **Статус checkpoint 0.3.0 — ADVANCED PARTIAL / EXPERIMENTAL.** Для primary physical-damage residual есть reproducible five-member train-only ensemble, deterministic и stochastic 2/4/8/16-step gates, uncertainty calibration, strict 64/16/20 selector experiment, committed-evidence reproducibility и leakage-safe positive-residual temperature experiment. Learned mean HP/force drift устойчиво лучше generic, но observed-action survival/invalid-action trade-off и calibration hard gates не позволяют production enablement. Runtime learned dynamics/selector/uncertainty выключены.",
    "# 20. Модуль M13 — Search Planner": "> **Статус checkpoint 0.3.0 — ADVANCED PARTIAL.** PUCT/search использует policy priors, value, next-actor model, stochastic damage/proc/collateral и ability-risk. Stochastic outcomes одного action разделены по canonical `state_hash`; равные hashes используют transposition nodes. Search graph сохраняется между requests и exact re-root выполняется только в том же non-empty battle/perspective при совпадающем structure fingerprint; unreachable branches pruning включён. `last_acted_seq` входит в hash, а provenance-only `Effect.raw` исключён. Permanent replay gate: 120/120 held-out states, 0 invalid recommendations. Остаются stronger opponent/chance branching, live quality validation и search calibration.",
    "# 21. Модуль M14 — Orchestrator / Replanning Loop": "> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE OFFLINE / LIVE NOT VALIDATED.** capture -> session -> decode -> plan -> state-hash validation -> auto-replan реализовано; revision-bound cancellation и conservative persistent exact re-root интегрированы. Incremental decoder детерминирован 866/866 replay, а replay recommendation-validity gate закрыт 120/120. Полный active-battle closed loop всё ещё требует проверки в пользовательском Chromium на живом авторизованном бою.",
    "# 26. Модуль M19 — Evaluation Harness": "> **Статус checkpoint 0.3.0 — ADVANCED PARTIAL.** Есть C++/Python regression, corpus-check, 866-battle shadow replay, held-out legal coverage, policy/value/damage metrics, permanent 120-state planner validity gate и M11 2/4/8/16-step uncertainty/selector/survival/temperature evidence suite. Replay invalid-recommendation gate >=100 states закрыт 120/120 с нулём invalid recommendations. Нет Level 4 authenticated live shadow и Level 5 human-in-loop hard-PvE win-rate suite.",
    "## Phase 5 — Dynamics v1": "> **Статус checkpoint 0.3.0 — ADVANCED PARTIAL / EXPERIMENTAL.** Hybrid exact simulator + learned residual/proc/collateral остаётся production baseline. Для primary physical-damage residual закрыт воспроизводимый 2/4/8/16-step ensemble/evidence harness, но full structured dynamics ensemble и joint accuracy+validity production gate ещё не закрыты.",
    "## Phase 6 — Search v1": "> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE.** PUCT/search на real states работает; stochastic outcome separation, transpositions, persistent exact re-root, reachable pruning и conservative structure/hash guards реализованы. Permanent held-out replay validity gate проходит 120/120 states. В развитии остаются stronger opponent/chance branching, live quality calibration и hard-PvE evaluation.",
    "## Phase 8 — Online advisor MVP": "> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE FOR PLUMBING / LIVE NOT VALIDATED.** Daemon+extension+sidepanel, pairing/auth, revision-bound cancellation, authenticated WebSocket push replanning и state-hash guards готовы и permanent integration-tested. Replay recommendation validity закрыта 120/120 states; всё ещё отсутствует обязательный authenticated active-battle end-to-end smoke и последующий hard-PvE human-in-loop benchmark.",
    "## Phase 9 — Search improvement loop": "> **Статус checkpoint 0.3.0 — IN PROGRESS / EVIDENCE-DRIVEN.** Permanent planner replay validity gate закрыт 120/120; search использует ability risk, next-actor и damage/value baselines, M13 safe reuse/transpositions и mechanic attribution. M11 multi-step evidence не разрешает production learned dynamics, поэтому следующий improvement loop должен опираться на decoder/legal correctness, stronger opponent/chance branching и measured live/hard-PvE quality.",
}
platform_note = "> **Текущий implementation/CI checkpoint (11.08.2026):** поддерживаемый product/CI target — Windows 10/11 x64 + MSVC. После перевода репозитория в public permanent CI должен выполняться на GitHub-hosted Windows runners; self-hosted runners удалены. Упоминания Clang/GCC/Linux ниже сохраняются как portability/training design goals и historical evidence, но не являются текущими permanent CI gates."
mvp_note = "> **Checkpoint 11.08.2026:** replay-часть пункта 10 закрыта permanent gate **120/120** с 0 invalid recommendations. Общий MVP всё ещё **не COMPLETE**, потому что live acquisition/closed-loop должны быть подтверждены реальным authenticated active-battle smoke; hard-PvE quality относится к следующему milestone."

for path in ("SPEC.md", "HeroesWM_Solver_TZ_Status_0.3.0.md"):
    replace_line(path, "**Дата:**", "**Дата:** 11.08.2026")
    replace_line(path, "**Последнее обновление реализации:**", last_update)
    replace_line(path, "## 0.3. Статус реализации на checkpoint 0.3.0", "## 0.3. Статус реализации на checkpoint 0.3.0 (11.08.2026)")
    replace_line(path, "- Planner real-state regression", planner_metric)
    replace_line(path, "- Automated tests:", auto_tests)
    replace_line(path, "- Physical damage:", physical_m11)
    replace_block(path, "1. **Real active-battle smoke gate:**", "Ability-front:", new_front)
    for heading, status in statuses.items():
        replace_status_after(path, heading, status)
    insert_after_heading(path, "## 6.1. Runtime core", "Текущий implementation/CI checkpoint (11.08.2026)", platform_note)
    insert_after_heading(path, "# 36. Definition of Done для MVP", "Checkpoint 11.08.2026:", mvp_note)

# SPEC.md is canonical. Keep the historical named checkpoint copy byte-identical.
if read("SPEC.md") != read("HeroesWM_Solver_TZ_Status_0.3.0.md"):
    write("HeroesWM_Solver_TZ_Status_0.3.0.md", read("SPEC.md"))

spec = read("SPEC.md")
for required in (
    "**Дата:** 11.08.2026",
    "Python **75/75**",
    "120/120",
    "ADVANCED PARTIAL / EXPERIMENTAL",
    "MOSTLY COMPLETE FOR PLUMBING / LIVE NOT VALIDATED",
    "Production learned dynamics remains **disabled**",
    "conservative exact re-root",
    "self-hosted runners удалены",
):
    if required not in spec:
        raise RuntimeError(f"missing required checkpoint marker: {required}")
for stale in (
    "Planner real-state regression (Release, 20 states)",
    "Persistent search-tree re-rooting по predicted child ещё не завершён.",
    "Tree reuse/transpositions и более сильная stochastic opponent branching ещё в развитии.",
):
    if stale in spec:
        raise RuntimeError(f"stale implementation statement remains: {stale}")
if read("SPEC.md") != read("HeroesWM_Solver_TZ_Status_0.3.0.md"):
    raise RuntimeError("SPEC and checkpoint copy diverged")

for temporary in (
    ROOT / ".github/scripts/spec_checkpoint_sync.py",
    ROOT / ".github/scripts/spec_checkpoint_sync.ps1",
    ROOT / ".github/workflows/spec_checkpoint_sync.yml",
):
    if temporary.exists():
        temporary.unlink()

spec_sha = commit(
    "docs: refresh active specification checkpoint",
    "SPEC.md",
    "HeroesWM_Solver_TZ_Status_0.3.0.md",
    ".github/scripts/spec_checkpoint_sync.py",
    ".github/scripts/spec_checkpoint_sync.ps1",
    ".github/workflows/spec_checkpoint_sync.yml",
)

log = f"""
## 2026-08-11

### Current CI/report/specification synchronization

- Functional test reference: `7cd17878174529a40087ce5a78231dd93690851b`, Windows run `31431838319`: **Core PASS + Full PASS**, Python **75/75**, planner validity **120/120** with 0 invalid recommendations.
- Commit: `deb8afbf37fee3543260f728e3e3ac97f044f2c4`.
  - Synchronized `TEST_REPORT.md` with the validated Windows Core/Full contract and current 75-test Python suite.
- Documentation sync staging/hardening commits between `a8d24e7b...` and `{trigger_sha}` were infrastructure-only; they did not change solver runtime or ability code. The self-hosted attempts were cancelled while the user removed the old runners; the final patcher moved to GitHub-hosted Windows after the repository became public.
- Commit: `{spec_sha}`.
  - Updated `SPEC.md` and `HeroesWM_Solver_TZ_Status_0.3.0.md` to checkpoint **11.08.2026** and synchronized them byte-for-byte.
  - Recorded permanent 120-state / 109-battle planner validity, M13 stochastic outcome/transposition/persistent re-root work, M11 2/4/8/16-step evidence and the still-disabled production learned-dynamics path.
  - Updated M03/M14/M19 and Phases 5/6/8/9 plus MVP DoD without claiming the still-missing authenticated live battle smoke.
  - Recorded the infrastructure change: repository is public; self-hosted runners are removed; Windows/MSVC remains the supported CI target and permanent workflows should use GitHub-hosted Windows.
  - Kept `ability` ownership separate from main-owned status claims.
"""
with (ROOT / "changelog.md").open("a", encoding="utf-8", newline="\n") as fh:
    fh.write("\n" + log.strip() + "\n")
changelog_sha = commit("docs: record specification checkpoint refresh", "changelog.md")

if run("git", "status", "--porcelain"):
    raise RuntimeError("working tree is dirty after documentation sync")
run("git", "push", "origin", "HEAD:main")
print(f"SPEC_SYNC_PASS spec={spec_sha} changelog={changelog_sha}")
