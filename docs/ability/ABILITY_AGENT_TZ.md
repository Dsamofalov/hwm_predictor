# Ability Agent TZ — canonical operating rules

This file is the canonical operating contract for continued creature-ability work on branch `ability`.

## 1. Ability changelog is mandatory

**This is the first and highest-priority process rule.** Maintain [`docs/ability/ability_changelog.md`](ability_changelog.md) as the canonical journal of ability development, in the same commit-oriented style as the root `changelog.md` on `main`.

For every functional ability commit:

1. make the functional commit as one logical change set;
2. run/obtain the required validation for that functional SHA;
3. make a separate bookkeeping commit that updates both `docs/ability/ability_changelog.md` and `docs/ability/AGENT_STATUS.md` with the real functional commit SHA, semantic result, and authoritative CI evidence.

Do not rely on chat history as the development journal. Do not rewrite or drop historical changelog entries; append corrections when needed.

The root `changelog.md` is the main/integration log. Ability work is recorded in `ability_changelog.md` first; root changelog updates belong to integration/main bookkeeping unless the active handoff explicitly requires otherwise.

## 2. Branch and ownership discipline

- Work directly on branch `ability`; do not create temporary development branches unless an explicit user instruction overrides this rule.
- Treat the current integrated snapshot as canonical. Do not restore or merge old divergent ability history merely to recover commits.
- Avoid modifying main-owned planner/runtime/evaluation surfaces unless an ability package genuinely requires a cross-owned substrate and the change is justified by current evidence.
- New evidence artifacts under `data/reports/abilities/**` are allowed. Do not delete tracked files to make tests pass.

## 3. Mandatory startup context

Before selecting or modifying an ability, read the current versions of:

- `SPEC.md`;
- `docs/ability/ABILITY_AGENT_TZ.md`;
- `docs/ability/AGENT_STATUS.md`;
- `docs/ability/ability_changelog.md`;
- the canonical test policy (`TESTS_CANON.md` or its current repository location);
- current ability registry/catalog and current ability-risk reports.

Recompute or verify the current ability-risk ordering from the current registry plus current corpus before choosing the next target. Prefer the highest-impact genuinely unclosed ability by `weighted_contribution`, while respecting already-proven blockers.

## 4. Evidence first; no speculative exact semantics

- Exact or `partial_exact` mechanics require executable evidence sufficient for the claimed boundary.
- Tooltip text, observed packets, correlations, or naming alone do not justify an exact trigger probability or exact consequence model when alternative explanations remain.
- If required substrate or discriminating evidence is absent, preserve the learned/unresolved boundary explicitly, document the blocker, and move to the next risk-ranked ability instead of inventing semantics.
- A negative evidence package is useful only when it is deterministic, regression-protected, and materially narrows the unresolved boundary.

## 5. Preserved semantic boundaries

Until new evidence changes them:

- Aura of Fire Vulnerability is evidence-only/unresolved until direct Fire-spell execution provides a testable substrate.
- Power Strike trigger prediction is learned/unresolved; do not add speculative proc prediction.
- Crippling Wound is `partial_exact`: observed consequence is represented, trigger probability remains unresolved.
- Paw Strike may retain a latent trigger boundary while preserving any already-evidence-backed exact consequence.
- Previously closed ability mechanics should not be reworked without evidence of a defect or a higher-fidelity executable model.

## 6. Atomic tests and hosted Windows authority

- Follow the canonical atomic test policy: maximize independent fan-out without weakening correctness, exact inventory coverage, or exact aggregation.
- Build once where appropriate, then fan out independent test cases/node IDs. Do not replace exact case coverage with coarse long-running monoliths merely for convenience.
- Hosted Windows/MSVC Ability CI is authoritative for Windows-specific correctness.
- Do not weaken assertions, skip failing cases, or repeatedly rerun the same failure in lieu of diagnosing it.
- A functional package is not closed until its required atomic tests pass and its semantic claim matches the evidence those tests exercise.

## 7. Ability-selection loop

For each target:

1. inspect current registry classification and weighted risk contribution;
2. inspect existing evidence modules/tests and current whole-corpus evidence;
3. identify the smallest evidence-backed executable improvement;
4. implement one logical functional package;
5. validate atomically, including hosted Windows/MSVC when applicable;
6. update `ability_changelog.md` and `AGENT_STATUS.md` in the required bookkeeping commit;
7. recompute/verify risk ordering and continue to the next highest-impact genuinely unclosed ability.

The objective is maximum solver completeness without converting uncertainty into fake exactness.
