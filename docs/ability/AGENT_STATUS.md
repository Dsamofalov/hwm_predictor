# Ability Integration Status

Checkpoint: **2026-08-12**

Source lane: `ability`
Integration branch: `integration/ability-snapshot-20260812`
Functional snapshot commit: `f98ea913be9331ca393c49df82b2025303956f92`
Validated integration HEAD: `03d2fbe138e0dad929037315dce46d38256be8f3`
Current main integration reference: **`7e646733eded4a491b25ddae1c2efcb9287feeec`**
Current validated functional ability SHA: **`2e82c969e0da708f5bbda6973c92d662a638aa3c`**
Authoritative hosted Windows run: **`31625718512` — PASS, 87/87 atomic jobs**

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

Run `31625718512` on `2e82c969...` completed with workflow conclusion `success` across **87/87 atomic jobs**. The new `test_gribbomb_bom_replay_kills_only_validated_carrier`, the strict whole-corpus `Sbom` gate, and the non-`Sbom` death controls all completed successfully.

## Preserved semantic boundaries

- `cripplingwound` remains `partial_exact`; speculative probability remains disabled.
- `powerstrike` trigger prediction remains unresolved/learned rather than promoted to an exact speculative proc.
- Aura of Fire Vulnerability remains evidence-only until a direct Fire-spell execution substrate exists.
- Gribbomb has exact raw `Sbom` discrimination, exact observed adjacent target-set evidence, and exact observed carrier self-removal; predictive Earth-damage magnitude remains unresolved.
- Existing closed Life Drain, Regeneration, Mana Feed, Mighty Slam, and Paw Strike mechanics are not reworked without contrary evidence.

## Next ownership state

**Stay on Gribbomb until registry/risk reflects the now-validated boundary. Do not start Taunt yet.**

1. Promote Gribbomb only to the strongest evidence-supported registry classification; `partial_exact` is the current ceiling because carrier self-destruction is exact while predictive collateral Earth-damage magnitude remains unresolved.
2. Add a registry/risk regression proving the promotion does not imply a predictive target-damage formula.
3. Regenerate canonical registry artifacts and recompute the held-out ability-risk contribution.
4. Re-run authoritative hosted Windows/MSVC Ability CI and record the functional SHA/run in `ability_changelog.md` and this status file.
5. Only then recompute the weighted queue and select the next unfinished ability.
