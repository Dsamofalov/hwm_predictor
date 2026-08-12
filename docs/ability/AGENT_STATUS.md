# Ability Integration Status

Checkpoint: **2026-08-12**

Source lane: `ability`
Integration branch: `integration/ability-snapshot-20260812`
Functional snapshot commit: `f98ea913be9331ca393c49df82b2025303956f92`
Validated integration HEAD: `03d2fbe138e0dad929037315dce46d38256be8f3`
Current validated functional ability SHA: **`d04999b03a094e637223ec7925b3071e50e36ecf`**
Authoritative hosted Windows run: **`31621756446` — PASS, 86/86 atomic jobs**

## Resumed ability-development governance

- `7200ec0f24157ae545f1798c76036f9d26dfedc3` created the dedicated `docs/ability/ability_changelog.md` journal.
- `a4f359ccfcf9a3a8133986f6e51f441e4c7cdd29` corrected the canonical contract at `docs/ABILITY_AGENT_TZ.md`, where mandatory maintenance of the dedicated ability changelog is now the first/highest-priority rule.
- The mistakenly created `docs/ability/ABILITY_AGENT_TZ.md` is only a compatibility pointer to `docs/ABILITY_AGENT_TZ.md`; it is not a second contract.

## Current Gribbomb evidence package

Functional commits:

- `b6b27633154f12588071a3e94145308aceb57451` — changed the self-destruct evidence probe from a generic death heuristic to the raw carrier-only `SPECIAL:bom` marker; first hosted run `31621278975` exposed one incorrect handwritten HP expectation.
- `d04999b03a094e637223ec7925b3071e50e36ecf` — corrected only that expected HP to the replay-derived value `36101`; hosted run `31621756446` completed successfully.

Validated whole-corpus evidence on `d04999b...`:

- 866 corpus battle directories;
- 7 Gribbomb carrier battles;
- exactly 1 carrier `Sbom` activation and 1/1 valid raw marker;
- exactly 3 living adjacent targets and exactly 3 outgoing damage records;
- exact adjacent target-set match: 1/1 activation;
- 0 missing adjacent targets and 0 non-adjacent extra targets;
- pre-activation carrier total HP: `36101`;
- observed damage: uid 6 = `36101`; uid 11 = `26354`; uid 13 = `26354`;
- observed damage/HP ratios: `1.000` once and `0.730` twice;
- 3 other active-carrier deaths are all explicitly externally damaged and therefore are not self-destruct candidates;
- generic replay still reports the `Sbom` carrier alive after the activation because the self-destruction has no ordinary DAMAGE-to-self record.

Semantic boundary: the raw activation discriminator and observed adjacent target set are exact replay evidence. Predictive Earth-damage magnitude remains unresolved because the single activation exhibits target-dependent deltas. No registry promotion is claimed until replay can apply the carrier self-destruction exactly without inventing the target-damage formula.

## Integration state

The divergent raw `ability` history is **not** merged into `main`. The canonical lane continues from the integrated ability snapshot while preserving current main-owned planner, M11/evaluation, daemon/runtime, extension, general CI, specification, and report surfaces.

The ability snapshot includes:

- `python/hwm_solver/ability/**` evidence and analysis modules;
- corresponding ability/evidence Python regression tests;
- the evidence-backed `cripplingwound -> partial_exact` registry classification;
- ability-owned C++ regressions and Windows/MSVC fixes;
- the dedicated hosted-Windows atomic ability workflow.

## Atomic test execution

Ability CI follows `TESTS_CANON.md`: build once where appropriate, freeze exact inventories, and execute independent C++ test functions / pytest node IDs as separate jobs. Atomicity and exact coverage are correctness requirements; matrix width and worker count are scheduler details.

Run `31621756446` on `d04999b...` expanded to **86 jobs** after the additional Gribbomb regression node and completed with workflow conclusion `success`.

## Preserved semantic boundaries

- `cripplingwound` remains `partial_exact`; speculative probability remains disabled.
- `powerstrike` trigger prediction remains unresolved/learned rather than promoted to an exact speculative proc.
- Aura of Fire Vulnerability remains evidence-only until a direct Fire-spell execution substrate exists.
- Gribbomb now has an exact raw `Sbom` discriminator and exact observed adjacent target-set evidence, but generic replay self-destruction and predictive Earth-damage magnitude remain open.
- Existing closed Life Drain, Regeneration, Mana Feed, Mighty Slam, and Paw Strike mechanics are not reworked without contrary evidence.

## Next ownership state

**Stay on Gribbomb. Do not start Taunt or another ability yet.**

1. Implement or prove the minimal exact replay hook for carrier self-destruction on the validated carrier-sourced `SPECIAL:bom` discriminator.
2. Add regressions proving that `Sbom` kills/removes the carrier in replay without inventing any target-damage formula.
3. Keep the three observed target damage records replay-observed only until the Earth-damage modifier rule is independently proven; do not synthesize universal predictive damage from the single activation.
4. Re-run authoritative hosted Windows/MSVC Ability CI and record the functional SHA/run in `ability_changelog.md` and this status file.
5. Only after Gribbomb is either safely promoted to the strongest evidence-supported classification or explicitly blocked by a precise remaining substrate/evidence gap may the agent recompute weighted risk and select the next ability.
