# Ability Integration Status

Checkpoint: **2026-08-12**

Source lane: `ability`
Integration branch: `integration/ability-snapshot-20260812`
Functional snapshot commit: `f98ea913be9331ca393c49df82b2025303956f92`
Validated integration HEAD: `03d2fbe138e0dad929037315dce46d38256be8f3`
Last fully green executable ability run: **`31607886774` — PASS**
Current functional candidate: **`b6b27633154f12588071a3e94145308aceb57451` — validation failed on one new assertion**
Current hosted Windows run: **`31621278975` — FAIL expected**

## Resumed ability-development governance

Current resumed-development documentation commits:

- `7200ec0f24157ae545f1798c76036f9d26dfedc3` — created the dedicated `docs/ability/ability_changelog.md` journal;
- `a4f359ccfcf9a3a8133986f6e51f441e4c7cdd29` — corrected the canonical contract at `docs/ABILITY_AGENT_TZ.md`, where mandatory maintenance of the dedicated ability changelog is now the first/highest-priority rule.

The mistakenly created `docs/ability/ABILITY_AGENT_TZ.md` is now only a compatibility pointer to `docs/ABILITY_AGENT_TZ.md`; it is not a second contract.

## Current Gribbomb evidence package

Functional commit `b6b27633154f12588071a3e94145308aceb57451` changed the self-destruct evidence probe from a generic death heuristic to the raw carrier-only `Sbom` marker.

Hosted run `31621278975` established before the failing assertion:

- 866 corpus battle directories;
- 7 Gribbomb carrier battles;
- exactly 1 validated carrier `Sbom` activation;
- exactly 3 living adjacent targets and 3 outgoing damage records;
- exact adjacent target-set match: 1/1 activation;
- 0 missing adjacent targets and 0 non-adjacent extra targets;
- the failing handwritten HP expectation was `36356`; replay-derived pre-activation HP is `36101`.

The next functional correction changes only that incorrect expected HP. Generic replay still leaves the carrier alive after `Sbom`, so no registry promotion is claimed yet. The predictive Earth-damage formula remains unresolved because the single activation contains target-dependent damage ratios.

## Integration state

The divergent `ability` history is **not** merged into `main`. Instead, the final ability-owned state was recreated on top of the current `main` tree and validated there.

This keeps main-owned planner, M11/evaluation, daemon/runtime, extension, general CI, specification, and report changes from current `main` intact while importing only the ability lane's owned results and minimal integration hooks.

The snapshot includes:

- `python/hwm_solver/ability/**` evidence and analysis modules;
- the corresponding ability/evidence Python regression tests;
- the explicit `cripplingwound -> partial_exact` registry classification backed by the existing evidence package;
- the ability-owned C++ test tree with the Windows/MSVC test-only fixes for Mighty Slam pointer invalidation, canonical `frightfulaura`, and portable temporary paths;
- a minimal CMake target for an ability case runner;
- a dedicated hosted-Windows ability workflow.

The snapshot deliberately does **not** import old one-shot integration scripts/workflows, divergent main-owned `ci.yml` changes, planner/M11 tooling, or stale general-spec/report edits from the old lane history.

## Atomic test execution

Ability CI follows `TESTS_CANON.md`:

- C++ is built once as an immutable artifact;
- the runner freezes the exact C++ test-function inventory and exposes `--case <name>`;
- each C++ test function is one independently runnable matrix job;
- Python freezes exact pytest node IDs with `pytest --collect-only` from `python/tests/ABILITY_TESTS.txt`;
- each collected pytest node is one independently runnable matrix job;
- workflow-contract regressions verify inventory equality, uniqueness, and dynamic matrix plumbing;
- no correctness rule depends on a fixed shard count, worker count, matrix width, or `max-parallel` value.

Parallelism is therefore a scheduler optimization only; atomicity and exact coverage are the contract.

## Preserved semantic boundaries

- `cripplingwound` remains `partial_exact`: observed consequence is supported; speculative probability remains disabled.
- `powerstrike` trigger prediction remains unresolved/learned rather than promoted to an exact speculative proc.
- Aura of Fire Vulnerability remains evidence-only until a direct Fire-spell execution substrate exists.
- Gribbomb now has a validated raw `Sbom` activation discriminator and exact observed adjacent target set, but runtime self-destruction and predictive Earth-damage magnitude remain unresolved.
- Existing closed mechanics such as Life Drain, Regeneration, Mana Feed, Mighty Slam, and Paw Strike are not reworked without contrary evidence.

## Next ownership state

Correct the single Gribbomb expected-HP assertion, obtain a fully green hosted Windows run, then decide whether the self-destruction mutation can be integrated safely without speculating about predictive Earth damage. Taunt is the next high-impact evidence target; its raw `A<old_target><carrier>` records are a promising redirect discriminator that must be checked across the full corpus before any promotion.
