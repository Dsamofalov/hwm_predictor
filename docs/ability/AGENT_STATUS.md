# Ability Integration Status

Checkpoint: **2026-08-12**

Source lane: `ability`
Integration branch: `integration/ability-snapshot-20260812`
Functional snapshot commit: `f98ea913be9331ca393c49df82b2025303956f92`
Validated integration HEAD: `03d2fbe138e0dad929037315dce46d38256be8f3`
Authoritative hosted Windows run: **`31607886774` — PASS**

## Resumed ability-development governance

Current resumed-development documentation commits:

- `7200ec0f24157ae545f1798c76036f9d26dfedc3` — created the dedicated `docs/ability/ability_changelog.md` journal;
- `a4f359ccfcf9a3a8133986f6e51f441e4c7cdd29` — corrected the canonical contract at `docs/ABILITY_AGENT_TZ.md`, where mandatory maintenance of the dedicated ability changelog is now the first/highest-priority rule.

The mistakenly created `docs/ability/ABILITY_AGENT_TZ.md` is now only a compatibility pointer to `docs/ABILITY_AGENT_TZ.md`; it is not a second contract.

These are documentation/process changes only. The last authoritative executable ability validation remains hosted Windows run `31607886774` until a new functional ability package is committed and validated.

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

## Validation evidence

Hosted Windows workflow run `31607886774` on `03d2fbe138e0dad929037315dce46d38256be8f3` completed successfully.

The run expanded to **85 jobs** in total, including:

- C++ build + exact inventory discovery;
- one job per discovered C++ regression function;
- Python exact node inventory discovery;
- one job per discovered ability pytest node;
- aggregate status publication.

Both inventory jobs passed, all generated C++ and Python case jobs passed, and the aggregate workflow conclusion was `success`.

## Preserved semantic boundaries

Integration does not promote evidence-only mechanics merely because their probes/tests are now present on `main`.

- `cripplingwound` remains `partial_exact`: observed consequence is supported; speculative probability remains disabled.
- `powerstrike` trigger prediction remains unresolved/learned rather than promoted to an exact speculative proc.
- Aura of Fire Vulnerability and the remaining evidence queue keep their documented evidence boundaries until executable runtime semantics are independently proven.
- Existing closed mechanics such as Life Drain, Regeneration, Mana Feed, Mighty Slam, and Paw Strike are not reworked by this integration.

## Next ownership state

Continue directly on the current `ability` branch from the integrated snapshot. Preserve the semantic boundaries above, use weighted ability-risk contribution to select the next genuinely unclosed mechanic, and validate each functional package with the atomic hosted-Windows ability workflow before claiming PASS.
