# Retired: Ability → Main Merge Canon

> **Status: historical / superseded on 2026-08-13.**
>
> Ability development no longer uses a dedicated `ability` source branch or a merge-back lane. The ability domain is a logical module and ownership boundary inside normal development on `main`.

## Current canon

1. All ability implementation, protocol/evidence work, tests, registry/risk updates, and ability documentation are committed directly to `main`.
2. `docs/ABILITY_AGENT_TZ.md` defines the ability-module contract; `docs/ability/AGENT_STATUS.md` and `docs/ability/ability_changelog.md` carry module status/history.
3. Ability-specific CI remains a module validation surface. It does not imply a separate development branch.
4. Shared files such as `python/hwm_solver/protocol/replay.py` remain shared `main` substrate. Ability changes there must preserve generic parser/runtime invariants and run all applicable main + ability validation surfaces.
5. There is no normal ability PR/merge-back/integration-candidate phase. The commit under test is already a `main` development commit/candidate.
6. The project-wide immutable-validation invariant still applies: **a PASS belongs only to the exact SHA/tree that was tested**. Any later functional change requires validation of the new SHA.
7. The historical Git ref named `ability` is legacy provenance only: it is not source of truth, not an active development lane, not a handoff destination, and not a normal merge source.

## Historical provenance

The old two-branch integration procedure was used for the final migration into unified `main` development:

- validated historical ability source: `2ae1046c48e99c94da3481a8b3ed81285b9125ab`;
- pre-integration main source: `2d6c985fbc4a6725e64871f12b127d68f86f1000`;
- historical two-parent merge: `e69592eaa9461825e231cc73656d1e58b9ac4ffd`;
- tested/promoted functional checkpoint: `3df0d5ee4434d3cc401dba1b765a4dca068c15c1`;
- Ability Windows run `31700597609` — PASS;
- Main Windows CI run `31700599112` — Core PASS + Full PASS.

These identifiers are retained only to explain repository history. They do **not** define the workflow for future ability development.
