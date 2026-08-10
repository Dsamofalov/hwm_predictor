$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $root
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Read-Lf([string]$Path) {
    return ([System.IO.File]::ReadAllText((Join-Path $root $Path), [System.Text.Encoding]::UTF8)).Replace("`r`n", "`n")
}

function Write-Lf([string]$Path, [string]$Text) {
    [System.IO.File]::WriteAllText((Join-Path $root $Path), $Text.Replace("`r`n", "`n"), $utf8)
}

function Replace-Line([string]$Path, [string]$Prefix, [string]$Replacement) {
    $text = Read-Lf $Path
    $lines = @($text -split "`n")
    $hits = @()
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].StartsWith($Prefix)) { $hits += $i }
    }
    if ($hits.Count -ne 1) { throw "$Path: expected one line starting with '$Prefix', found $($hits.Count)" }
    $lines[$hits[0]] = $Replacement
    Write-Lf $Path ($lines -join "`n")
}

function Replace-Block([string]$Path, [string]$Start, [string]$End, [string]$Replacement) {
    $text = Read-Lf $Path
    $s = $text.IndexOf($Start)
    if ($s -lt 0) { throw "$Path: missing start anchor: $Start" }
    if ($text.IndexOf($Start, $s + $Start.Length) -ge 0) { throw "$Path: non-unique start anchor: $Start" }
    $e = $text.IndexOf($End, $s + $Start.Length)
    if ($e -lt 0) { throw "$Path: missing end anchor: $End" }
    Write-Lf $Path ($text.Substring(0, $s) + $Replacement.TrimEnd() + "`n`n" + $text.Substring($e))
}

function Replace-StatusAfter([string]$Path, [string]$Heading, [string]$Replacement) {
    $text = Read-Lf $Path
    $h = $text.IndexOf($Heading)
    if ($h -lt 0) { throw "$Path: missing heading: $Heading" }
    $s = $text.IndexOf('> **Статус checkpoint 0.3.0', $h)
    if ($s -lt 0) { throw "$Path: missing status after: $Heading" }
    $e = $text.IndexOf("`n", $s)
    if ($e -lt 0) { $e = $text.Length }
    Write-Lf $Path ($text.Substring(0, $s) + $Replacement + $text.Substring($e))
}

function Insert-After-Heading([string]$Path, [string]$Heading, [string]$Marker, [string]$Paragraph) {
    $text = Read-Lf $Path
    if ($text.Contains($Marker)) { return }
    $h = $text.IndexOf($Heading)
    if ($h -lt 0) { throw "$Path: missing heading: $Heading" }
    $e = $text.IndexOf("`n", $h)
    if ($e -lt 0) { throw "$Path: malformed heading: $Heading" }
    Write-Lf $Path ($text.Substring(0, $e + 1) + "`n" + $Paragraph.Trim() + "`n" + $text.Substring($e + 1))
}

function Append-Block([string]$Path, [string]$Block) {
    $text = Read-Lf $Path
    if (-not $text.EndsWith("`n")) { $text += "`n" }
    Write-Lf $Path ($text + "`n" + $Block.Trim() + "`n")
}

function Commit-Staged([string]$Message) {
    $staged = @(git diff --cached --name-only)
    if ($LASTEXITCODE -ne 0) { throw "git diff failed: $Message" }
    if ($staged.Count -eq 0) { throw "No staged changes: $Message" }
    git diff --cached --check
    if ($LASTEXITCODE -ne 0) { throw "git diff --check failed: $Message" }
    git commit -m $Message
    if ($LASTEXITCODE -ne 0) { throw "git commit failed: $Message" }
    return (git rev-parse HEAD).Trim()
}

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'

$scriptCommit = (git rev-parse HEAD).Trim()
$workflowCommit = (git rev-parse HEAD^).Trim()

$lastUpdate = '**Последнее обновление реализации:** 11.08.2026 — `main` переведён на Windows-only self-hosted Core/Full CI; M13 stochastic outcomes/transpositions/persistent exact re-root дополнены scheduler-recency и semantic-effect hash canonicalization; permanent held-out planner gate расширен до 120 состояний с 0 invalid recommendations; M11 получил reproducible 2/4/8/16-step ensemble, uncertainty/selector/survival/temperature evidence gates, но production learned dynamics остаётся выключенной; real authenticated active-battle smoke и decoder/legal >=99.9% всё ещё обязательны; ability-front ведётся отдельно в ветке `ability`.'
$plannerMetric = '- Permanent held-out planner validity gate: **120/120** sampled states из **109** held-out battles, **0** invalid recommendations, state-hash mismatches, illegal best actions/alternatives или non-finite metrics. На validated Windows run `31431838319` budget `1 -> 120`: action-type stability **99.17%**, exact-action stability **85.83%**.'
$autoTests = '- Automated tests / supported platform: Windows 10/11 x64 self-hosted CI only. Последний полностью проверенный functional tree `7cd17878174529a40087ce5a78231dd93690851b`, run `31431838319`: **Core PASS + Full PASS**; MSVC Debug/Release main-front CTest, 120-state planner gate, pairing/auth, stale cancellation, live binding, WebSocket, Python **75/75**, TypeScript/extension, `planner-demo 5000` и все permanent M11 evidence commands PASS. Historical Linux results remain evidence only. Ability-owned `hwm-tests` intentionally outside main-front CTest until branch `ability` integration.'
$physicalM11 = @'
- Physical damage: median abs-log error **0.3574 -> 0.2812** после learned creature residual; для rare creatures ability transfer **0.2719 -> 0.2484**.
- M11 multi-step evidence: five-member train-only physical-damage residual ensemble evaluated at **2/4/8/16** halfturn horizons. Deterministic mean force-L1 at 16 steps **0.04947 vs 0.08125** generic, but invalid-action fraction **3.58% vs 2.51%**; stochastic survival gate at 16 steps **0.05028 vs 0.08178** force-L1 while valid-observed-action coverage is **96.349% vs 97.493%**. Uncertainty/selector experiments do not clear production criteria; leakage-safe positive-residual temperature calibration selects scale **0.0** because no candidate passes the hard joint accuracy/coverage gate. Production learned dynamics remains **disabled**.
'@
$newFront = @'
1. **Real active-battle smoke gate:** выполнить `docs/LIVE_VALIDATION.md` на реальном активном авторизованном PvE-бою. Это остаётся главным продуктовым блокером для закрытия Browser Bridge/Orchestrator: network capture primary truth, runtime-object fallback только по доказанному отсутствующему полю.
2. **Decoder/legal correctness:** устранить **19** финальных structural-invalid replay без ослабления invariants и поднять held-out observed basic-action representability с **98.03%** к acceptance **>=99.9%**.
3. **M11 learned dynamics:** развить уже работающий 2/4/8/16-step evidence harness из primary physical-damage residual до полноценного structured ensemble. Не включать runtime selector/uncertainty/residual production path, пока одновременно не пройдены multi-step accuracy и observed-action survival/validity gates.
4. **M13 search quality после correctness closure:** safe stochastic outcome separation, transpositions и exact persistent re-root уже реализованы; следующий front — более сильное explicit opponent/chance branching, search calibration и quality/latency trade-offs, не ломая revision cancellation и exact hash/structure guards.
5. **Evaluation:** replay invalid-recommendation gate >=100 states уже закрыт (**120/120**). После stable live acquisition нужны live-state validation и hard-PvE human-in-loop benchmark / win-rate uplift / calibration.
'@
$m03Status = '> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE.** Thread-safe session, battle reset, duplicate/out-of-order handling, immutable observed state, state hash, revision-bound cooperative stale-search cancellation и incremental decode реализованы. Planner сохраняет search graph между recommendation calls и делает conservative exact re-root только при точном observed hash в том же non-empty battle/perspective и совпадающем structure fingerprint; иначе graph сбрасывается. Остаточный gate — real authenticated live-session validation.'
$m11Status = '> **Статус checkpoint 0.3.0 — ADVANCED PARTIAL / EXPERIMENTAL.** Для primary physical-damage residual теперь есть reproducible five-member train-only ensemble, deterministic и stochastic 2/4/8/16-step gates, uncertainty calibration, strict 64/16/20 selector experiment, committed-evidence reproducibility и leakage-safe positive-residual temperature experiment. Learned mean HP/force drift устойчиво лучше generic, но observed-action survival/invalid-action trade-off и calibration hard gates не позволяют production enablement. Основной rollout остаётся hybrid exact + conservative learned evidence path; runtime learned dynamics/selector/uncertainty выключены.'
$m13Status = '> **Статус checkpoint 0.3.0 — ADVANCED PARTIAL.** PUCT/search использует policy priors, value, next-actor model, stochastic damage/proc/collateral и ability-risk. Stochastic outcomes одного action разделены по canonical `state_hash`; равные hashes используют transposition nodes. Search graph сохраняется между requests и exact re-root выполняется только в том же non-empty battle/perspective при совпадающем structure fingerprint; unreachable branches pruning включён. `last_acted_seq` входит в hash, а provenance-only `Effect.raw` исключён. Permanent replay gate: 120/120 held-out states, 0 invalid recommendations. Остаются более сильное explicit opponent/chance branching, live quality validation и дальнейшая search calibration.'
$m14Status = '> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE OFFLINE / LIVE NOT VALIDATED.** capture -> session -> decode -> plan -> state-hash validation -> auto-replan реализовано; revision-bound cancellation и conservative persistent exact re-root интегрированы. Incremental decoder детерминирован 866/866 replay, а replay recommendation-validity gate закрыт 120/120. Полный active-battle closed loop всё ещё требует проверки в пользовательском Chromium на живом авторизованном бою.'
$m19Status = '> **Статус checkpoint 0.3.0 — ADVANCED PARTIAL.** Есть C++/Python regression, corpus-check, 866-battle shadow replay, held-out legal coverage, policy/value/damage metrics, permanent 120-state planner validity gate и M11 2/4/8/16-step uncertainty/selector/survival/temperature evidence suite. Replay invalid-recommendation gate >=100 states закрыт 120/120 с нулём invalid recommendations. Нет Level 4 authenticated live shadow на активном бою и Level 5 human-in-loop hard-PvE win-rate suite.'
$phase5Status = '> **Статус checkpoint 0.3.0 — ADVANCED PARTIAL / EXPERIMENTAL.** Hybrid exact simulator + learned residual/proc/collateral остаётся production baseline. Для primary physical-damage residual закрыт воспроизводимый 2/4/8/16-step ensemble/evidence harness и несколько calibration/selector/survival experiments, но full structured dynamics ensemble и joint accuracy+validity production gate ещё не закрыты.'
$phase6Status = '> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE.** PUCT/search на real states работает; stochastic outcome separation, transpositions, persistent exact re-root, reachable pruning и conservative structure/hash guards реализованы. Permanent held-out replay validity gate проходит 120/120 states. В развитии остаются более сильная stochastic opponent/chance branching, live quality calibration и hard-PvE evaluation.'
$phase8Status = '> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE FOR PLUMBING / LIVE NOT VALIDATED.** Daemon+extension+sidepanel, pairing/auth, revision-bound cancellation, authenticated WebSocket push replanning и state-hash guards готовы и permanent integration-tested. Replay recommendation validity закрыта 120/120 states; всё ещё отсутствует обязательный authenticated active-battle end-to-end smoke и последующий hard-PvE human-in-loop benchmark.'
$phase9Status = '> **Статус checkpoint 0.3.0 — IN PROGRESS / EVIDENCE-DRIVEN.** Permanent planner replay validity gate закрыт 120/120; search использует ability risk, next-actor и damage/value baselines, M13 safe reuse/transpositions и mechanic attribution. M11 multi-step evidence не разрешает production learned dynamics, поэтому следующий improvement loop должен опираться на decoder/legal correctness, stronger opponent/chance branching и measured live/hard-PvE quality, а не на включение экспериментального selector.'
$platformNote = '> **Текущий implementation/CI checkpoint (11.08.2026):** поддерживаемый product/CI target сейчас Windows 10/11 x64 + MSVC на self-hosted Windows runners. Упоминания Clang/GCC/Linux ниже сохраняются как portability/training design goals и историческая evidence, но не являются текущими permanent CI gates.'
$mvpNote = '> **Checkpoint 11.08.2026:** replay-часть пункта 10 уже закрыта permanent gate **120/120** с 0 invalid recommendations. Общий MVP всё ещё **не COMPLETE**, потому что live acquisition/closed-loop должны быть подтверждены реальным authenticated active-battle smoke; hard-PvE quality относится к следующему milestone.'

foreach ($path in @('SPEC.md', 'HeroesWM_Solver_TZ_Status_0.3.0.md')) {
    Replace-Line $path '**Дата:**' '**Дата:** 11.08.2026'
    Replace-Line $path '**Последнее обновление реализации:**' $lastUpdate
    Replace-Line $path '## 0.3. Статус реализации на checkpoint 0.3.0' '## 0.3. Статус реализации на checkpoint 0.3.0 (11.08.2026)'
    Replace-Line $path '- Planner real-state regression' $plannerMetric
    Replace-Line $path '- Automated tests:' $autoTests
    Replace-Line $path '- Physical damage:' $physicalM11.TrimEnd()
    Replace-Block $path '1. **Real active-battle smoke gate:**' 'Ability-front:' $newFront
    Replace-StatusAfter $path '# 10. Модуль M03 — State Store / Battle Session' $m03Status
    Replace-StatusAfter $path '# 18. Модуль M11 — Learned World / Dynamics Model' $m11Status
    Replace-StatusAfter $path '# 20. Модуль M13 — Search Planner' $m13Status
    Replace-StatusAfter $path '# 21. Модуль M14 — Orchestrator / Replanning Loop' $m14Status
    Replace-StatusAfter $path '# 26. Модуль M19 — Evaluation Harness' $m19Status
    Replace-StatusAfter $path '## Phase 5 — Dynamics v1' $phase5Status
    Replace-StatusAfter $path '## Phase 6 — Search v1' $phase6Status
    Replace-StatusAfter $path '## Phase 8 — Online advisor MVP' $phase8Status
    Replace-StatusAfter $path '## Phase 9 — Search improvement loop' $phase9Status
    Insert-After-Heading $path '## 6.1. Runtime core' 'Текущий implementation/CI checkpoint (11.08.2026)' $platformNote
    Insert-After-Heading $path '# 36. Definition of Done для MVP' 'Checkpoint 11.08.2026:' $mvpNote
}

# Canonical SPEC wins if historical duplicate had any unrelated drift.
if ((Read-Lf 'SPEC.md') -ne (Read-Lf 'HeroesWM_Solver_TZ_Status_0.3.0.md')) {
    Write-Lf 'HeroesWM_Solver_TZ_Status_0.3.0.md' (Read-Lf 'SPEC.md')
}

foreach ($path in @('SPEC.md', 'HeroesWM_Solver_TZ_Status_0.3.0.md')) {
    $text = Read-Lf $path
    foreach ($required in @('**Дата:** 11.08.2026', 'Python **75/75**', '120/120', 'ADVANCED PARTIAL / EXPERIMENTAL', 'MOSTLY COMPLETE FOR PLUMBING / LIVE NOT VALIDATED', 'Production learned dynamics remains **disabled**', 'conservative exact re-root')) {
        if (-not $text.Contains($required)) { throw "$path missing required checkpoint marker: $required" }
    }
    foreach ($stale in @('Planner real-state regression (Release, 20 states)', 'Persistent search-tree re-rooting по predicted child ещё не завершён.', 'Tree reuse/transpositions и более сильная stochastic opponent branching ещё в развитии.')) {
        if ($text.Contains($stale)) { throw "$path still contains stale statement: $stale" }
    }
}

if ((Read-Lf 'SPEC.md') -ne (Read-Lf 'HeroesWM_Solver_TZ_Status_0.3.0.md')) {
    throw 'Active SPEC and status checkpoint duplicate are not synchronized.'
}

git add -- SPEC.md HeroesWM_Solver_TZ_Status_0.3.0.md
git rm -- .github/scripts/spec_checkpoint_sync.ps1 .github/workflows/spec_checkpoint_sync.yml
$specSha = Commit-Staged 'docs: refresh active specification checkpoint'

$log = @"
### 2026-08-11 — Current CI/report/specification synchronization

- Aborted/temporary documentation staging history: `a8d24e7bccc297d124d15e21e1e61332510af97a`, `bca05a03faa07e54385bfd0ee8482c52b54ec0fd`, `ca984c154f1357786966bfebf7067fbb1028d212`, `6534ee7eb5f493252b1a58f76d514fcf0d0546de`, `cb6658b9326a27231b34de2d69f94a6890304456`, `0e5cf2d8536476db0acf1a2a609044295e4e94ee`, `550eeadbad1139b1c0c6576ae5c2400b9fdcee68`, `6248f6ee885c32b75b38aa7be03a641ad7511051`, `75dbb0bb57dfc1526ae503af07b9f744e67be14f`.
  - These commits only staged/hardened/removed one-shot documentation tooling; no solver runtime code changed.
- Commit: `deb8afbf37fee3543260f728e3e3ac97f044f2c4`.
  - Synchronized `TEST_REPORT.md` from the stale Python 42/42 snapshot to the validated Windows-only Core/Full contract: Python 75/75, permanent 120-state planner validity gate, Release benchmark and permanent M11 evidence suite.
- One-shot specification sync staging commits: `$workflowCommit` and `$scriptCommit`.
  - Repository-owned temporary workflow/script used only for this anchor-based refresh and deleted in the functional documentation commit below.
- Commit: `$specSha`.
  - Updated both `SPEC.md` and `HeroesWM_Solver_TZ_Status_0.3.0.md` to checkpoint date 11.08.2026 and synchronized them byte-for-byte.
  - Recorded Windows-only self-hosted Core/Full CI, Python 75/75 and permanent 120-state / 109-battle planner validity with zero invalid recommendations.
  - Updated M03/M13/M14 for stochastic outcome separation, transpositions, persistent exact re-root, structure fingerprint, scheduler-recency hashing and semantic-effect provenance canonicalization.
  - Updated M11/Phase 5 for reproducible 2/4/8/16-step ensemble, uncertainty, selector, stochastic-survival, evidence-reproducibility and temperature gates; production learned dynamics remains disabled.
  - Updated M19/Phase 9/MVP DoD to mark the >=100-state replay recommendation gate closed at 120/120 while keeping authenticated live shadow and hard-PvE quality open.
  - Reordered the main autonomous front to live smoke, decoder/legal >=99.9%, structured learned dynamics, then stronger search/evaluation quality work.
  - Kept branch `ability` explicitly separate from main-owned status claims.
"@
Append-Block 'changelog.md' $log
git add -- changelog.md
$changelogSha = Commit-Staged 'docs: record specification checkpoint refresh'

$dirty = @(git status --porcelain)
if ($dirty.Count -ne 0) { throw "Dirty tree after documentation sync: $($dirty -join '; ')" }

git push origin HEAD:main
if ($LASTEXITCODE -ne 0) { throw 'git push failed' }
Write-Host "SPEC_SYNC_PASS spec=$specSha changelog=$changelogSha"
