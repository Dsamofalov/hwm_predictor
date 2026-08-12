# Ability Integration Status

Checkpoint: **2026-08-12**

Source lane: `ability`
Integration branch: `integration/ability-snapshot-20260812`
Functional snapshot commit: `f98ea913be9331ca393c49df82b2025303956f92`
Validated integration HEAD: `03d2fbe138e0dad929037315dce46d38256be8f3`
Current main integration reference: **`7e646733eded4a491b25ddae1c2efcb9287feeec`**
Current validated functional ability SHA: **`da7fd216f6b993f7e6a1770371004253b80d35cc`**
Authoritative hosted Windows run: **`31627726097` — PASS, 89/89 jobs including `publish_status`**

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

Run `31627726097` on `da7fd216...` completed with workflow conclusion `success` across **89/89 jobs**, including final `publish_status`. The Gribbomb registry/risk regression, replay-kill boundary, wrong-source/malformed-marker controls, non-`Sbom` death controls, and the new registry-risk CI trigger contract all completed successfully.

## Preserved semantic boundaries

- `cripplingwound` remains `partial_exact`; speculative probability remains disabled.
- `powerstrike` trigger prediction remains unresolved/learned rather than promoted to an exact speculative proc.
- Aura of Fire Vulnerability remains evidence-only until a direct Fire-spell execution substrate exists.
- `gribbomb` is `partial_exact` in the validated source-of-truth builder: raw `Sbom` discrimination, observed adjacent target-set evidence, and observed carrier self-removal are exact; predictive Earth/collateral-damage magnitude remains unresolved and is not enabled in the predictive collateral model.
- Existing closed Life Drain, Regeneration, Mana Feed, Mighty Slam, and Paw Strike mechanics are not reworked without contrary evidence.

## Next ownership state

**Stay on Gribbomb until checked generated registry/report artifacts match the validated builder. Do not start Taunt yet.**

1. Deterministically regenerate the canonical checked registry/report artifacts from the current source-of-truth builder and inputs; do not hand-edit generated JSON/CSV.
2. Verify the generated diff reflects only the evidence-backed Gribbomb `unresolved -> partial_exact`, risk `0.62 -> 0.25`, and corresponding aggregate/report changes.
3. Validate the artifact-sync functional SHA on authoritative hosted Windows/MSVC Ability CI (or the repository's canonical deterministic artifact gate if stricter).
4. Record that exact artifact-sync SHA/run in `ability_changelog.md` and this status file.
5. Only then recompute the weighted unfinished-ability queue and select the next ability, expected to begin with the existing Taunt evidence package if it remains highest priority.
