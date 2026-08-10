$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Read-Lf([string]$Path) {
    return ([System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)).Replace("`r`n", "`n")
}

function Write-Lf([string]$Path, [string]$Text) {
    [System.IO.File]::WriteAllText($Path, $Text.Replace("`r`n", "`n"), $utf8)
}

function Replace-Line([string]$Path, [string]$Prefix, [string]$Replacement) {
    $lines = [System.Collections.Generic.List[string]](Read-Lf($Path) -split "`n")
    $hits = @()
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].StartsWith($Prefix, [System.StringComparison]::Ordinal)) {
            $hits += $i
        }
    }
    if ($hits.Count -ne 1) {
        throw "$Path: expected one line starting with '$Prefix', found $($hits.Count)."
    }
    $index = $hits[0]
    $before = @()
    if ($index -gt 0) { $before = $lines.GetRange(0, $index) }
    $afterStart = $index + 1
    $after = @()
    if ($afterStart -lt $lines.Count) { $after = $lines.GetRange($afterStart, $lines.Count - $afterStart) }
    $replacementLines = $Replacement -split "`n"
    $out = @($before) + @($replacementLines) + @($after)
    Write-Lf $Path ($out -join "`n")
}

function Replace-Block([string]$Path, [string]$StartAnchor, [string]$EndAnchor, [string]$Replacement) {
    $text = Read-Lf $Path
    $start = $text.IndexOf($StartAnchor, [System.StringComparison]::Ordinal)
    if ($start -lt 0) { throw "$Path: start anchor not found: $StartAnchor" }
    $secondStart = $text.IndexOf($StartAnchor, $start + $StartAnchor.Length, [System.StringComparison]::Ordinal)
    if ($secondStart -ge 0) { throw "$Path: start anchor is not unique: $StartAnchor" }
    $end = $text.IndexOf($EndAnchor, $start + $StartAnchor.Length, [System.StringComparison]::Ordinal)
    if ($end -lt 0) { throw "$Path: end anchor not found after start: $EndAnchor" }
    $updated = $text.Substring(0, $start) + $Replacement.TrimEnd() + "`n`n" + $text.Substring($end)
    Write-Lf $Path $updated
}

function Replace-StatusAfter([string]$Path, [string]$Heading, [string]$Replacement) {
    $text = Read-Lf $Path
    $headingIndex = $text.IndexOf($Heading, [System.StringComparison]::Ordinal)
    if ($headingIndex -lt 0) { throw "$Path: heading not found: $Heading" }
    $statusIndex = $text.IndexOf('> **Статус checkpoint 0.3.0', $headingIndex, [System.StringComparison]::Ordinal)
    if ($statusIndex -lt 0) { throw "$Path: status line not found after heading: $Heading" }
    $lineEnd = $text.IndexOf("`n", $statusIndex)
    if ($lineEnd -lt 0) { $lineEnd = $text.Length }
    $updated = $text.Substring(0, $statusIndex) + $Replacement + $text.Substring($lineEnd)
    Write-Lf $Path $updated
}

function Append-Lines([string]$Path, [string[]]$Lines) {
    $text = Read-Lf $Path
    if (-not $text.EndsWith("`n")) { $text += "`n" }
    $text += (($Lines -join "`n") + "`n")
    Write-Lf $Path $text
}

function Commit-Staged([string]$Message) {
    git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) { throw "No staged changes for commit: $Message" }
    git commit -m $Message
    if ($LASTEXITCODE -ne 0) { throw "Commit failed: $Message" }
    return (git rev-parse HEAD).Trim()
}

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'

$workflowSha = (git rev-parse HEAD).Trim()
$scriptSha = (git rev-parse HEAD^).Trim()

# 1. Synchronize TEST_REPORT.md with the exact current Windows-only main-front CI result.
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

Current-tree reference: `main` commit `7cd17878174529a40087ce5a78231dd93690851b`, Windows self-hosted Actions run `31431838319`: **Core PASS + Full PASS**. Core compiled all C++ targets under MSVC Debug, executed the main-owned `hwm-planner-tests`, validated 120 held-out planner states from 109 battles with zero invalid recommendations/hash mismatches/illegal root actions/non-finite metrics, passed all four daemon integrations, Python **75/75**, TypeScript typecheck and extension build. Full passed MSVC Release main-front CTest, `planner-demo 5000`, all M11 full-corpus evaluators, committed-evidence verification and the positive-residual temperature experiment.

The ability-owned monolithic `hwm-tests` target is still built but deliberately excluded from the `main` CTest gate until branch `ability` completes its independent MSVC validation. This ownership split is intentional and must be removed after ability integration rather than treated as permanent coverage.
'@
Replace-Block 'TEST_REPORT.md' '## Automated build/test snapshot' '## Closed-loop safety regressions' $testSnapshot
git add TEST_REPORT.md
$reportSha = Commit-Staged 'docs: synchronize test report with current Windows CI'

$syncLines = @(
    '',
    '',
    '### Current Windows CI and test-report synchronization',
    '',
    ('- Temporary documentation script staging commit: `{0}`.' -f $scriptSha),
    ('- Temporary documentation workflow staging commit: `{0}`.' -f $workflowSha),
    '  - Staged a Windows self-hosted one-shot documentation synchronizer; both temporary files are removed by the specification refresh commit below.',
    '- Commit: `7cd17878174529a40087ce5a78231dd93690851b`',
    '  - Hardened daemon integration harnesses for bounded Windows cold-start latency without relaxing failure semantics.',
    '  - Current-tree Windows self-hosted workflow run `31431838319`: Core + Full PASS.',
    '  - Core: MSVC Debug main-front CTest; 120/120 held-out planner states from 109 battles; 0 invalid recommendations/hash mismatches/illegal root actions/non-finite metrics; pairing/auth, stale cancellation, live binding and WebSocket PASS; Python 75/75; TypeScript/extension PASS.',
    '  - Full: MSVC Release main-front CTest; planner-demo 5000; M11 multistep, uncertainty, selector, stochastic-survival, committed-evidence and temperature commands PASS.',
    ('- Commit: `{0}`' -f $reportSha),
    '  - Synchronized `TEST_REPORT.md` with the current Windows-only Core/Full contract and exact current-tree test counts.',
    '  - Kept ability-owned `hwm-tests` explicitly outside the main-front PASS claim until branch `ability` integration.'
)
Append-Lines 'changelog.md' $syncLines
git add changelog.md
Commit-Staged 'docs: record current Windows CI synchronization' | Out-Null

# 2. Refresh the canonical SPEC and its status-checkpoint duplicate from work since 144d958.
$lastUpdate = '**Последнее обновление реализации:** 11.08.2026 — `main` переведён на Windows-only self-hosted Core/Full CI; M13 stochastic outcomes/transpositions/persistent exact re-root дополнены scheduler-recency и semantic-effect hash canonicalization; permanent held-out planner gate расширен до 120 состояний с 0 invalid recommendations; M11 получил reproducible 2/4/8/16-step ensemble, uncertainty/selector/survival/temperature evidence gates, но production learned dynamics остаётся выключенной; real authenticated active-battle smoke и decoder/legal >=99.9% всё ещё обязательны; ability-front ведётся отдельно в ветке `ability`.'
$plannerMetric = '- Permanent held-out planner validity gate: **120/120** sampled states из **109** held-out battles, **0** invalid recommendations, state-hash mismatches, illegal best actions/alternatives или non-finite metrics. На current-tree Windows run `31431838319` budget `1 -> 120`: action-type stability **99.17%**, exact-action stability **85.83%**.'
$autoTests = '- Automated tests / supported platform: Windows 10/11 x64 self-hosted CI only. Current-tree run `31431838319` on `7cd17878174529a40087ce5a78231dd93690851b`: **Core PASS + Full PASS**; MSVC Debug/Release main-front CTest, 120-state planner gate, pairing/auth, stale cancellation, live binding, WebSocket, Python **75/75**, TypeScript/extension, `planner-demo 5000` и все permanent M11 evidence commands PASS. Historical Linux results remain evidence only. Ability-owned `hwm-tests` is intentionally outside main-front CTest until branch `ability` integration.'
$physicalAndM11 = @'
- Physical damage: median abs-log error **0.3574 -> 0.2812** после learned creature residual; для rare creatures ability transfer **0.2719 -> 0.2484**.
- M11 multi-step evidence: five-member train-only physical-damage residual ensemble evaluated at **2/4/8/16** halfturn horizons. Deterministic mean force-L1 at 16 steps **0.04947 vs 0.08125** generic, but invalid-action fraction **3.58% vs 2.51%**; stochastic survival gate at 16 steps **0.05028 vs 0.08178** force-L1 while valid-observed-action coverage is **96.349% vs 97.493%**. Uncertainty and calibrated selector gates do not clear production criteria; leakage-safe positive-residual temperature calibration selects scale **0.0** because no calibration candidate passes the hard joint accuracy/coverage gate. Production learned dynamics remains **disabled**.
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

foreach ($path in @('SPEC.md', 'HeroesWM_Solver_TZ_Status_0.3.0.md')) {
    Replace-Line $path '**Дата:**' '**Дата:** 11.08.2026'
    Replace-Line $path '**Последнее обновление реализации:**' $lastUpdate
    Replace-Line $path '## 0.3. Статус реализации на checkpoint 0.3.0' '## 0.3. Статус реализации на checkpoint 0.3.0 (11.08.2026)'
    Replace-Line $path '- Planner real-state regression' $plannerMetric
    Replace-Line $path '- Automated tests:' $autoTests
    Replace-Line $path '- Physical damage:' $physicalAndM11.TrimEnd()
    Replace-Block $path '1. **Real active-battle smoke gate:**' 'Ability-front:' $newFront
    Replace-StatusAfter $path '# 18. Модуль M11 — Learned World / Dynamics Model' $m11Status
    Replace-StatusAfter $path '# 20. Модуль M13 — Search Planner' $m13Status
    Replace-StatusAfter $path '## Phase 5 — Dynamics v1' $phase5Status
    Replace-StatusAfter $path '## Phase 6 — Search v1' $phase6Status
    Replace-StatusAfter $path '## Phase 8 — Online advisor MVP' $phase8Status
}

Remove-Item '.github/scripts/sync_current_docs_checkpoint.ps1' -Force
Remove-Item '.github/workflows/sync_current_docs_checkpoint.yml' -Force
git add SPEC.md HeroesWM_Solver_TZ_Status_0.3.0.md .github/scripts/sync_current_docs_checkpoint.ps1 .github/workflows/sync_current_docs_checkpoint.yml
$specSha = Commit-Staged 'docs: refresh active specification checkpoint'

$specLines = @(
    '',
    '',
    '### Active specification refresh after Windows/M13/M11 work',
    '',
    ('- Commit: `{0}`' -f $specSha),
    '  - Updated both `SPEC.md` and `HeroesWM_Solver_TZ_Status_0.3.0.md` to the 11.08.2026 implementation checkpoint.',
    '  - Recorded Windows-only self-hosted Core/Full CI and current 75/75 Python regression count.',
    '  - Replaced the historical 20-state planner metric with the permanent 120-state / 109-battle validity gate (0 invalid recommendations).',
    '  - Updated M13 status for stochastic outcome separation, transpositions, persistent exact re-root, structure fingerprint, scheduler-recency hashing and semantic-effect provenance canonicalization.',
    '  - Updated M11/Phase 5 status for reproducible 2/4/8/16-step ensemble, uncertainty, selector, stochastic-survival, evidence-reproducibility and temperature gates; production learned dynamics remains disabled.',
    '  - Updated Phase 6/Search and Phase 8/online-advisor status without claiming the still-missing authenticated active-battle smoke or hard-PvE benchmark.',
    '  - Reordered the main-front priorities: live smoke and decoder/legal >=99.9% remain blockers; replay >=100-state recommendation validity is now closed.',
    '  - Removed the temporary documentation synchronization script/workflow.'
)
Append-Lines 'changelog.md' $specLines
git add changelog.md
Commit-Staged 'docs: record specification checkpoint refresh' | Out-Null

if ((git status --porcelain).Length -ne 0) { throw 'Working tree is not clean before push.' }
git push origin HEAD:main
if ($LASTEXITCODE -ne 0) { throw 'Push failed.' }
