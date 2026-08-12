# Ability Integration Status

Checkpoint: **2026-08-12**

Source lane: `ability`
Integration branch: `integration/ability-snapshot-20260812`
Functional snapshot commit: `f98ea913be9331ca393c49df82b2025303956f92`
Validated integration HEAD: `03d2fbe138e0dad929037315dce46d38256be8f3`
Current main integration reference: **`7e646733eded4a491b25ddae1c2efcb9287feeec`**
Current validated functional ability SHA: **`eaca45fc3de060b030ee912c38efea234aa00c1f`**
Authoritative hosted Windows run: **`31631708571` — PASS on exact SHA; workflow conclusion `success`, 89 jobs total, 88 successful test/build/inventory jobs and final `publish_status` skipped by workflow condition**

## Resumed ability-development governance

- `7200ec0f24157ae545f1798c76036f9d26dfedc3` created the dedicated `docs/ability/ability_changelog.md` journal.
- `a4f359ccfcf9a3a8133986f6e51f441e4c7cdd29` corrected the canonical contract at `docs/ABILITY_AGENT_TZ.md`, where mandatory maintenance of the dedicated ability changelog is now the first/highest-priority rule.
- The mistakenly created `docs/ability/ABILITY_AGENT_TZ.md` is only a compatibility pointer to `docs/ABILITY_AGENT_TZ.md`; it is not a second contract.

## Current Gribbomb evidence package

Functional commits:

- `b6b27633154f12588071a3e94145308aceb57451` — changed the self-destruct evidence probe from a generic death heuristic to the raw carrier-only `SPECIAL:bom` marker; first hosted run `31621278975` exposed one incorrect handwritten HP expectation.
- `d04999b03a094e637223ec7925b3071e50e36ecf` — corrected only that expected HP to the replay-derived value `36101`; hosted run `31621756446` completed successfully.
- `2e82c969e0da708f5bbda6973c92d662a638aa3c` — made validated `Sbom` kill/remove only the server-declared Gribbomb carrier in observed replay; hosted run `31625718512` completed successfully.

Validated whole-corpus evidence on `2e82c969...`:

- 866 corpus battle directories;
- 7 Gribbomb carrier battles;
- exactly 1 carrier `Sbom` activation and 1/1 valid raw marker;
- exactly 3 living adjacent targets and exactly 3 outgoing raw damage records;
- exact adjacent target-set match: 1/1 activation;
- 0 missing adjacent targets and 0 non-adjacent extra targets;
- pre-activation carrier total HP: `36101`;
- observed damage: uid 6 = `36101`; uid 11 = `26354`; uid 13 = `26354`;
- observed damage/HP ratios: `1.000` once and `0.730` twice;
- validated `Sbom` now leaves the carrier dead in replay (`alive=false`, `count=0`, `top_hp=0`);
- wrong-source and malformed `Sbom` controls do not kill the source;
- replay now contains 4 active-carrier deaths: exactly 1 validated `Sbom` self-destruction plus the same 3 non-`Sbom` deaths explicitly explained by external damage.

Semantic boundary: the raw activation discriminator, observed adjacent target set, and carrier self-removal are exact replay semantics. The three target HP deltas remain raw-observed consequences only. Predictive Earth-damage magnitude remains unresolved because the single activation exhibits target-dependent deltas, so Gribbomb cannot be promoted to a fully exact runtime classification.

## Gribbomb registry/risk package

- `e4616a155fdd1e15def28f74c8c7af43391177ba` — source-of-truth registry builder promotes `gribbomb` to `partial_exact`, canonical risk `0.25`, with a held-out risk regression and an explicit guard that Gribbomb is not enabled in the predictive collateral model.
- Hosted run `31626881854` failed on a brittle global support-count constant in that new regression; the Gribbomb semantic/classification assertions passed.
- `19ba4e6caed9977839eaac8ebb0181ca57a32ede` — replaced the magic global cardinalities with the relative invariant `+1 partial_exact / -1 unresolved` against a synthetic pre-promotion baseline; no semantic gate was weakened.
- `da7fd216f6b993f7e6a1770371004253b80d35cc` — generalized Ability CI path filtering to `test_*_registry_risk.py` and added a workflow-contract regression proving registry-risk tests trigger hosted Ability validation.
- Authoritative run `31627726097` completed successfully with **89/89 jobs**, including the Gribbomb registry/risk node, Gribbomb replay/self-destruction controls, workflow-trigger regression, C++ matrix, and final `publish_status`.

Registry semantic status: **`gribbomb = partial_exact`, risk weight `0.25`** in the validated source-of-truth builder. This promotion covers exact observed carrier self-removal only. Predictive Earth/collateral damage remains unresolved and Gribbomb remains outside the predictive collateral model.

## Generated registry/report synchronization

- `c24cacf060182494092ef3e460301844639388e6` — deterministically regenerated `data/catalog/ability_registry.json` and `.csv` from the current builder and tracked inputs rather than hand-editing generated snapshots.
  - The generated diff brought checked registry artifacts up to the already validated source-of-truth state, including Gribbomb `partial_exact` and the previously stale Crippling Wound classification.
  - Resulting support totals include `partial_exact = 20` and `unresolved = 77`.
- `eaca45fc3de060b030ee912c38efea234aa00c1f` — deterministically regenerated `data/reports/ability-registry-current.json` and `data/reports/ability-risk-current.json` from the synchronized registry.
  - Current held-out ability-risk mean changed from `0.22431` to `0.21744`; p90 changed from `0.37538` to `0.36755`.
  - Stale unresolved Gribbomb risk disappeared from the unfinished top-risk slice; Crippling Wound is represented as `partial_exact` with canonical risk `0.25`.
- Hosted Windows run `31631708571` on exact SHA `eaca45fc...`: workflow **PASS / conclusion `success`**. All atomic test/build/inventory jobs succeeded; the final `publish_status` job was skipped by its workflow condition.

Repository-consistency boundary: the validated builder, checked registry artifacts, and checked current reports are now synchronized. Gribbomb is closed at its strongest evidence-supported `partial_exact` classification; its predictive Earth/collateral magnitude remains an explicit unresolved sub-boundary rather than an inferred formula.

## Integration state

The divergent raw `ability` history is **not** merged into `main`. The canonical lane continues from the integrated ability snapshot while preserving current main-owned planner, M11/evaluation, daemon/runtime, extension, general CI, specification, and report surfaces.

The ability snapshot includes:

- `python/hwm_solver/ability/**` evidence and analysis modules;
- corresponding ability/evidence Python regression tests;
- evidence-backed partial/exact ability registry classifications;
- ability-owned C++ regressions and Windows/MSVC fixes;
- the dedicated hosted-Windows atomic ability workflow.

## Atomic test execution

Ability CI follows `TESTS_CANON.md`: build once where appropriate, freeze exact inventories, and execute independent C++ test functions / pytest node IDs as separate jobs. Atomicity and exact coverage are correctness requirements; matrix width and worker count are scheduler details.

Run `31631708571` on `eaca45fc...` completed with workflow conclusion `success` across 89 jobs total. The real test/build/inventory jobs succeeded; `publish_status` was skipped by workflow condition. This exact-SHA run validates the synchronized registry/report package together with the existing Gribbomb evidence/runtime/regression package.

## Preserved semantic boundaries

- `cripplingwound` remains `partial_exact`; speculative probability remains disabled.
- `powerstrike` trigger prediction remains unresolved/learned rather than promoted to an exact speculative proc.
- Aura of Fire Vulnerability remains evidence-only until a direct Fire-spell execution substrate exists.
- `gribbomb` is `partial_exact`: raw `Sbom` discrimination, observed adjacent target-set evidence, and observed carrier self-removal are exact; predictive Earth/collateral-damage magnitude remains unresolved and is not enabled in the predictive collateral model.
- Existing closed Life Drain, Regeneration, Mana Feed, Mighty Slam, and Paw Strike mechanics are not reworked without contrary evidence.

## Next ownership state

**Gribbomb repository consistency is closed. Advance to Taunt as the highest-priority currently actionable unfinished ability after recomputing the synchronized risk queue.**

1. Reuse the existing `python/hwm_solver/ability/taunt_evidence.py` package; do not restart the evidence audit from scratch.
2. Strengthen the weak smoke-only Taunt regression into exact whole-corpus evidence gates: pin carrier counts, tooltip claims, attack/adjacency opportunities, and raw special-code contexts.
3. Require a carrier-specific raw discriminator before claiming a redirected Taunt proc. A final attack target alone is not a proc label and must not be used to infer the original intended target.
4. Promote runtime/registry semantics only to the strongest boundary independently supported by raw corpus evidence; otherwise record a precise blocker rather than inventing probability/targeting behavior.
5. Validate each functional SHA on authoritative hosted Windows/MSVC Ability CI and immediately record the real SHA/run in `ability_changelog.md`, `AGENT_STATUS.md`, and root `changelog.md`.
