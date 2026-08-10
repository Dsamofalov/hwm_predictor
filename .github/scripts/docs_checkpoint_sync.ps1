$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $root
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Read-Lf([string]$Path) {
  ([IO.File]::ReadAllText((Join-Path $root $Path), [Text.Encoding]::UTF8)).Replace("`r`n", "`n")
}
function Write-Lf([string]$Path, [string]$Text) {
  [IO.File]::WriteAllText((Join-Path $root $Path), $Text.Replace("`r`n", "`n"), $utf8)
}
function Replace-Line([string]$Path, [string]$Prefix, [string]$Replacement) {
  $text = Read-Lf $Path
  $lines = $text -split "`n", -1
  $hits = @()
  for ($i=0; $i -lt $lines.Count; $i++) {
    if ($lines[$i].StartsWith($Prefix, [StringComparison]::Ordinal)) { $hits += $i }
  }
  if ($hits.Count -ne 1) { throw "$Path: expected one '$Prefix' line, found $($hits.Count)" }
  $lines[$hits[0]] = $Replacement
  Write-Lf $Path ($lines -join "`n")
}
function Replace-Block([string]$Path, [string]$Start, [string]$End, [string]$Replacement) {
  $text = Read-Lf $Path
  $s = $text.IndexOf($Start, [StringComparison]::Ordinal)
  if ($s -lt 0) { throw "$Path: missing start anchor: $Start" }
  if ($text.IndexOf($Start, $s + $Start.Length, [StringComparison]::Ordinal) -ge 0) { throw "$Path: non-unique start anchor: $Start" }
  $e = $text.IndexOf($End, $s + $Start.Length, [StringComparison]::Ordinal)
  if ($e -lt 0) { throw "$Path: missing end anchor: $End" }
  Write-Lf $Path ($text.Substring(0,$s) + $Replacement.TrimEnd() + "`n`n" + $text.Substring($e))
}
function Replace-StatusAfter([string]$Path, [string]$Heading, [string]$Replacement) {
  $text = Read-Lf $Path
  $h = $text.IndexOf($Heading, [StringComparison]::Ordinal)
  if ($h -lt 0) { throw "$Path: missing heading: $Heading" }
  $s = $text.IndexOf('> **Статус checkpoint 0.3.0', $h, [StringComparison]::Ordinal)
  if ($s -lt 0) { throw "$Path: missing checkpoint status after: $Heading" }
  $e = $text.IndexOf("`n", $s)
  if ($e -lt 0) { $e = $text.Length }
  Write-Lf $Path ($text.Substring(0,$s) + $Replacement + $text.Substring($e))
}
function Append-Text([string]$Path, [string]$Block) {
  $text = Read-Lf $Path
  if (-not $text.EndsWith("`n")) { $text += "`n" }
  Write-Lf $Path ($text + "`n" + $Block.Trim() + "`n")
}
function Commit([string]$Message, [string[]]$Paths) {
  git add -- $Paths
  if ($LASTEXITCODE -ne 0) { throw "git add failed: $Message" }
  git diff --cached --quiet
  if ($LASTEXITCODE -eq 0) { throw "No staged change for: $Message" }
  git diff --cached --check
  if ($LASTEXITCODE -ne 0) { throw "git diff --check failed: $Message" }
  git commit -m $Message
  if ($LASTEXITCODE -ne 0) { throw "git commit failed: $Message" }
  (git rev-parse HEAD).Trim()
}

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
$workflowCommit = (git rev-parse HEAD).Trim()
$scriptCommit = (git rev-parse HEAD^).Trim()

# 1) Synchronize the test report with the exact validated current-tree Windows run.
Replace-Line 'TEST_REPORT.md' '**Дата:**' '**Дата:** 11.08.2026'
$testSnapshot = @'
## Automated build/test snapshot

```text
Supported product/CI platform:                  Windows 10/11 x64
PowerShell syntax preflight:                    PASS
MSVC Debug main-front CTest:                    1/1 PASS (hwm-planner-tests)
Held-out planner validity:                      120/120 PASS; 0 invalid recommendations
Local API pairing/auth integration:             PASS
Stale-search cancellation integration:          PASS
Live recommendation binding contract:           PASS
WebSocket revision streaming:                    PASS
Python pytest:                                  75/75 PASS
TypeScript typecheck:                           PASS
Extension build:                                PASS
MSVC Release main-front CTest:                  1/1 PASS (hwm-planner-tests)
Release planner benchmark (5000 simulations):   PASS
M11 full-corpus diagnostic/evidence suite:      PASS
```

Current-tree reference: `main` commit `7cd17878174529a40087ce5a78231dd93690851b`, Windows self-hosted Actions run `31431838319`: **Core PASS + Full PASS**. Core compiled all C++ targets under MSVC Debug, executed the main-owned `hwm-planner-tests`, validated 120 held-out planner states from 109 battles with zero invalid recommendations, state-hash mismatches, illegal best/alternative actions or non-finite metrics, passed pairing/auth, stale cancellation, live binding and WebSocket integrations, Python **75/75**, TypeScript typecheck and extension build. Full passed MSVC Release main-front CTest, `planner-demo 5000`, all permanent M11 full-corpus evaluators, committed-evidence verification and the positive-residual temperature experiment.

The ability-owned monolithic `hwm-tests` target is still built but deliberately excluded from the `main` CTest gate until branch `ability` completes its independent MSVC validation. This ownership split is temporary integration debt, not a permanent reduction of the final test contract.
'@
Replace-Block 'TEST_REPORT.md' '## Automated build/test snapshot' '## Closed-loop safety regressions' $testSnapshot
$reportSha = Commit 'docs: synchronize test report with current Windows CI' @('TEST_REPORT.md')

$syncLog = @"
### Current Windows CI / report synchronization

- Prior autonomous-sync staging commits: `a8d24e7bccc297d124d15e21e1e61332510af97a` and `bca05a03faa07e54385bfd0ee8482c52b54ec0fd`.
  - The first staged an over-broad draft synchronizer; the second removed it before execution. No specification content was changed by that aborted attempt.
- Temporary one-shot sync staging commits: `$scriptCommit` and `$workflowCommit`.
  - They execute this reviewed anchor-based documentation refresh on the Windows self-hosted runner and are removed by the specification commit below.
- Commit: `7cd17878174529a40087ce5a78231dd93690851b`.
  - Bounded Windows daemon cold-start tolerance; current-tree workflow `31431838319`: **Core PASS + Full PASS**.
  - Core includes MSVC Debug main-front CTest, 120/120 held-out planner validity, four daemon integrations, Python 75/75 and extension checks.
  - Full includes MSVC Release main-front CTest, planner benchmark and all permanent M11 evidence commands.
- Commit: `$reportSha`.
  - Synchronized `TEST_REPORT.md` from the stale 42-test snapshot to the exact current Windows-only Core/Full contract.
  - Kept ability-owned `hwm-tests` outside the main-front PASS claim until branch integration.
"@
Append-Text 'changelog.md' $syncLog
$syncLogSha = Commit 'docs: record current Windows CI synchronization' @('changelog.md')

# 2) Refresh both copies of the active 0.3.0 specification from work completed since 144d958.
$lastUpdate = '**Последнее обновление реализации:** 11.08.2026 — `main` переведён на Windows-only self-hosted Core/Full CI; M13 stochastic outcomes/transpositions/persistent exact re-root дополнены scheduler-recency и semantic-effect hash canonicalization; permanent held-out planner gate расширен до 120 состояний с 0 invalid recommendations; M11 получил reproducible 2/4/8/16-step ensemble, uncertainty/selector/survival/temperature evidence gates, но production learned dynamics остаётся выключенной; real authenticated active-battle smoke и decoder/legal >=99.9% всё ещё обязательны; ability-front ведётся отдельно в ветке `ability`.'
$plannerMetric = '- Permanent held-out planner validity gate: **120/120** sampled states из **109** held-out battles, **0** invalid recommendations, state-hash mismatches, illegal best actions/alternatives или non-finite metrics. На current-tree Windows run `31431838319` budget `1 -> 120`: action-type stability **99.17%**, exact-action stability **85.83%**.'
$autoTests = '- Automated tests / supported platform: Windows 10/11 x64 self-hosted CI only. Current-tree run `31431838319` on `7cd17878174529a40087ce5a78231dd93690851b`: **Core PASS + Full PASS**; MSVC Debug/Release main-front CTest, 120-state planner gate, pairing/auth, stale cancellation, live binding, WebSocket, Python **75/75**, TypeScript/extension, `planner-demo 5000` и все permanent M11 evidence commands PASS. Historical Linux results remain evidence only. Ability-owned `hwm-tests` is intentionally outside main-front CTest until branch `ability` integration.'
$physicalM11 = @'
- Physical damage: median abs-log error **0.3574 -> 0.2812** после learned creature residual; для rare creatures ability transfer **0.2719 -> 0.2484**.
- M11 multi-step evidence: five-member train-only physical-damage residual ensemble evaluated at **2/4/8/16** halfturn horizons. Deterministic mean force-L1 at 16 steps **0.04947 vs 0.08125** generic, but invalid-action fraction **3.58% vs 2.51%**; stochastic survival gate at 16 steps **0.05028 vs 0.08178** force-L1 while valid-observed-action coverage is **96.349% vs 97.493%**. Uncertainty and calibrated selector experiments do not clear production criteria; leakage-safe positive-residual temperature calibration selects scale **0.0** because no candidate passes the hard joint accuracy/coverage gate. Production learned dynamics remains **disabled**.
'@
$newFront = @'
1. **Real active-battle smoke gate:** выполнить `docs/LIVE_VALIDATION.md` на реальном активном авторизованном PvE-бою. Это остаётся главным продуктовым блокером для закрытия Browser Bridge/Orchestrator: network capture primary truth, runtime-object fallback только по доказанному отсутствующему полю.
2. **Decoder/legal correctness:** устранить **19** финальных structural-invalid replay без ослабления invariants и поднять held-out observed basic-action representability с **98.03%** к acceptance **>=99.9%**.
3. **M11 learned dynamics:** развить уже работающий 2/4/8/16-step evidence harness из primary physical-damage residual до полноценного structured ensemble. Не включать runtime selector/uncertainty/residual production path, пока одновременно не пройдены multi-step accuracy и observed-action survival/validity gates.
4. **M13 search quality после correctness closure:** safe stochastic outcome separation, transpositions и exact persistent re-root уже реализованы; следующий поиск — более сильное explicit opponent/chance branching, search calibration и quality/latency trade-offs, не ломая revision cancellation и exact hash/structure guards.
5. **Evaluation:** replay invalid-recommendation gate >=100 states уже закрыт (**120/120**). После stable live acquisition нужны live-state validation и hard-PvE human-in-loop benchmark / win-rate uplift / calibration.
'@
$m11Status = '> **Статус checkpoint 0.3.0 — ADVANCED PARTIAL / EXPERIMENTAL.** Для primary physical-damage residual теперь есть reproducible five-member train-only ensemble, deterministic и stochastic 2/4/8/16-step gates, uncertainty calibration, strict 64/16/20 selector experiment, committed-evidence reproducibility и leakage-safe positive-residual temperature experiment. Learned mean HP/force drift устойчиво лучше generic, но observed-action survival/invalid-action trade-off и calibration hard gates не позволяют production enablement. Основной rollout остаётся hybrid exact + conservative learned evidence path; runtime learned dynamics/selector/uncertainty выключены.'
$m13Status = '> **Статус checkpoint 0.3.0 — ADVANCED PARTIAL.** PUCT/search использует policy priors, value, next-actor model, stochastic damage/proc/collateral и ability-risk. Stochastic outcomes одного action разделены по canonical `state_hash`; равные hashes используют transposition nodes. Search graph сохраняется между requests и exact re-root выполняется только в том же non-empty battle/perspective при совпадающем structure fingerprint; unreachable branches pruning включён. `last_acted_seq` входит в hash, а provenance-only `Effect.raw` исключён. Permanent replay gate: 120/120 held-out states, 0 invalid recommendations. Остаются более сильное explicit opponent/chance branching, live quality validation и дальнейшая search calibration.'
$phase5Status = '> **Статус checkpoint 0.3.0 — ADVANCED PARTIAL / EXPERIMENTAL.** Hybrid exact simulator + learned residual/proc/collateral остаётся production baseline. Для primary physical-damage residual закрыт воспроизводимый 2/4/8/16-step ensemble/evidence harness и несколько calibration/selector/survival experiments, но full structured dynamics ensemble и joint accuracy+validity production gate ещё не закрыты.'
$phase6Status = '> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE.** PUCT/search на real states работает; stochastic outcome separation, transpositions, persistent exact re-root, reachable pruning и conservative structure/hash guards реализованы. Permanent held-out replay validity gate проходит 120/120 states. В развитии остаются более сильная stochastic opponent/chance branching, live quality calibration и hard-PvE evaluation.'
$phase8Status = '> **Статус checkpoint 0.3.0 — MOSTLY COMPLETE FOR PLUMBING / LIVE NOT VALIDATED.** Daemon+extension+sidepanel, pairing/auth, revision-bound cancellation, authenticated WebSocket push replanning и state-hash guards готовы и permanent integration-tested. Replay recommendation validity закрыта 120/120 states; всё ещё отсутствует обязательный authenticated active-battle end-to-end smoke и последующий hard-PvE human-in-loop benchmark.'

foreach ($path in @('SPEC.md','HeroesWM_Solver_TZ_Status_0.3.0.md')) {
  Replace-Line $path '**Дата:**' '**Дата:** 11.08.2026'
  Replace-Line $path '**Последнее обновление реализации:**' $lastUpdate
  Replace-Line $path '## 0.3. Статус реализации на checkpoint 0.3.0' '## 0.3. Статус реализации на checkpoint 0.3.0 (11.08.2026)'
  Replace-Line $path '- Planner real-state regression' $plannerMetric
  Replace-Line $path '- Automated tests:' $autoTests
  Replace-Line $path '- Physical damage:' $physicalM11.TrimEnd()
  Replace-Block $path '1. **Real active-battle smoke gate:**' 'Ability-front:' $newFront
  Replace-StatusAfter $path '# 18. Модуль M11 — Learned World / Dynamics Model' $m11Status
  Replace-StatusAfter $path '# 20. Модуль M13 — Search Planner' $m13Status
  Replace-StatusAfter $path '## Phase 5 — Dynamics v1' $phase5Status
  Replace-StatusAfter $path '## Phase 6 — Search v1' $phase6Status
  Replace-StatusAfter $path '## Phase 8 — Online advisor MVP' $phase8Status
}

if ((Read-Lf 'SPEC.md') -ne (Read-Lf 'HeroesWM_Solver_TZ_Status_0.3.0.md')) {
  throw 'SPEC.md and HeroesWM_Solver_TZ_Status_0.3.0.md diverged after synchronized patch.'
}
$specText = Read-Lf 'SPEC.md'
foreach ($required in @('Python **75/75**','120/120','ADVANCED PARTIAL / EXPERIMENTAL','MOSTLY COMPLETE FOR PLUMBING / LIVE NOT VALIDATED','production learned dynamics remains **disabled**')) {
  if (-not $specText.Contains($required)) { throw "SPEC validation missing: $required" }
}

Remove-Item '.github/scripts/docs_checkpoint_sync.ps1' -Force
Remove-Item '.github/workflows/docs_checkpoint_sync.yml' -Force
$specSha = Commit 'docs: refresh active specification checkpoint' @('SPEC.md','HeroesWM_Solver_TZ_Status_0.3.0.md','.github/scripts/docs_checkpoint_sync.ps1','.github/workflows/docs_checkpoint_sync.yml')

$specLog = @"
### Active specification refresh after M13/M11/Windows CI work

- Commit: `$syncLogSha`.
  - Recorded the test-report synchronization and its exact current-tree validation evidence.
- Commit: `$specSha`.
  - Updated both `SPEC.md` and `HeroesWM_Solver_TZ_Status_0.3.0.md` to checkpoint date 11.08.2026.
  - Recorded Windows-only self-hosted Core/Full CI and Python 75/75.
  - Replaced the historical 20-state planner snapshot with the permanent 120-state / 109-battle validity gate with zero invalid recommendations.
  - Updated M13 for stochastic outcome separation, transpositions, persistent exact re-root, structure fingerprint, scheduler-recency hashing and semantic-effect provenance canonicalization.
  - Updated M11/Phase 5 for reproducible 2/4/8/16-step ensemble, uncertainty, selector, stochastic-survival, evidence-reproducibility and temperature gates; production learned dynamics remains disabled.
  - Updated Phase 6/Search and Phase 8/online-advisor without claiming the still-missing authenticated active-battle smoke or hard-PvE benchmark.
  - Reordered main-front priorities: live smoke and decoder/legal >=99.9% remain blockers; replay >=100-state recommendation validity is closed at 120/120.
  - Removed the temporary synchronization script/workflow.
"@
Append-Text 'changelog.md' $specLog
$finalSha = Commit 'docs: record specification checkpoint refresh' @('changelog.md')

if ((git status --porcelain).Length -ne 0) { throw 'Working tree is not clean.' }
git push origin HEAD:main
if ($LASTEXITCODE -ne 0) { throw 'git push failed' }
Write-Host "DOC_SYNC_PASS final=$finalSha spec=$specSha report=$reportSha"
