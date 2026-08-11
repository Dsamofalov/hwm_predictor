# Ability → Main Merge Canon

> **Status: canonical project procedure.**
>
> This document defines the mandatory procedure for integrating the `ability` branch into `main` in the HeroesWM PvE Battle Solver repository.
>
> The central invariant is:
>
> **tested commit == merged commit**

## 1. Purpose

The `ability` branch is developed separately from `main`. Most ability work is isolated in ability-owned implementation, registry, evidence, and tests, while `main` continues to evolve other solver subsystems.

Large commit-count divergence between the branches does **not** by itself mean that integration requires a custom synthetic merge pipeline. The correct integration model is an ordinary Git merge candidate followed by complete testing of that exact candidate.

The goal of this canon is to guarantee that:

- the current `main` is combined with the current `ability`;
- conflicts are resolved once in normal committed source;
- all tests run against one immutable merge candidate;
- CI does not rewrite source code or tests while validating the candidate;
- the exact green candidate is what reaches `main`.

## 2. Canonical integration equation

The only supported high-level flow is:

```text
current main
    +
current ability
    ↓
real Git merge on an integration branch
    ↓
one immutable merge candidate SHA
    ↓
full Linux + Windows/MSVC + Python + project-specific validation
    ↓
merge the exact tested candidate into main
```

Or, more compactly:

```text
current main + current ability -> committed integration SHA -> full CI -> main
```

## 3. Do not merge untested ability directly into main

The phrase “merge first, test after” means:

1. create a **real merge candidate** from current `main` and current `ability`;
2. test the resulting merged tree;
3. only after it is green, promote that exact result to `main`.

It does **not** mean pushing an untested merge directly to protected production history and hoping the post-merge tests pass.

The integration branch exists specifically so that the merged state can be tested before it becomes the accepted `main` state.

## 4. Required procedure

### Step 1 — Freeze the source refs

At the beginning of an integration attempt, record:

```text
MAIN_SOURCE=<current main SHA>
ABILITY_SOURCE=<current ability SHA>
```

These are audit metadata only. They must be resolved from the live branches at the start of the attempt, not hardcoded permanently into scripts or workflows.

If either source branch moves later, the already-created candidate remains valid and testable. A newer integration attempt may be created separately if desired.

### Step 2 — Create a clean integration branch from current main

Create a new temporary integration branch from the exact current `main`:

```bash
git switch main
git pull --ff-only
git switch -c integration/ability-<date-or-id>
```

The integration branch must begin from `MAIN_SOURCE`.

Do not base the candidate on an old cached `main` SHA from a workflow script.

### Step 3 — Merge current ability with normal Git

Merge `ABILITY_SOURCE` normally:

```bash
git merge --no-ff ability
```

If there are conflicts, resolve the **real Git conflicts** in the working tree, review the result, and commit the resolution normally.

No CI script may “resolve” semantic conflicts later by textual search-and-replace.

### Step 4 — Eliminate CI-only product patches

Before validation, inspect any historical integration/hotfix scripts.

If a CI script contains a legitimate source or test fix required for Linux, Windows/MSVC, Python, registry generation, or ability behavior, that fix must become a normal repository commit in the merge candidate.

A candidate is invalid if its success depends on CI modifying tracked source or tests after checkout.

The tested tree must be reproducible by:

```bash
git checkout <candidate-sha>
```

with no product-code mutation afterward.

### Step 5 — Commit the final candidate

After all real conflicts and required fixes are committed, record the exact candidate SHA:

```text
INTEGRATION_SHA=<merge candidate SHA>
```

From this point onward, validation is performed against this immutable SHA.

If code changes are needed after a failed test, commit them and obtain a **new** `INTEGRATION_SHA`. Previous test results do not transfer to the new SHA.

### Step 6 — Run the full validation matrix

At minimum, the exact same `INTEGRATION_SHA` must pass all validation normally required by the project, including:

- Linux build;
- Linux CTest/C++ test suite;
- Python test suite;
- Windows/MSVC build;
- Windows CTest/C++ test suite;
- ability-specific regression tests;
- Ability Registry generation/consistency checks where applicable;
- evidence/report validation required by current project tooling;
- any other mandatory checks defined by the repository’s normal CI.

No platform may test a different reconstructed tree while claiming to validate the same candidate.

### Step 7 — Verify repository cleanliness

Validation must not leave tracked modifications behind.

A useful invariant is:

```bash
git status --porcelain
```

returns no unexpected tracked changes after the test preparation/execution path.

Generated temporary build artifacts are fine when they are untracked/ignored and not part of the candidate.

### Step 8 — Promote the exact green result to main

When all required checks are green, merge the exact tested integration result into `main`.

The promotion operation must preserve the already-tested tree. Do not rebuild a “similar” candidate from newer branch heads and assume previous tests apply.

Before final promotion, verify:

```text
SHA/tree being promoted == SHA/tree that passed CI
```

If `main` moved after the candidate was created and project policy requires the latest `main`, create a **new integration candidate**, merge/rebase as appropriate, and rerun the complete required CI. Do not silently transplant old green status to a changed tree.

## 5. CI rules

CI is a **validator**, not a branch-rewriting integration engine.

### CI MAY

- check out the candidate SHA;
- install dependencies;
- configure/build in temporary build directories;
- generate disposable test artifacts;
- run C++/CTest/Python tests;
- regenerate outputs only when the check verifies they are already consistent with committed files;
- report failures and diagnostics.

### CI MUST NOT

- hardcode a historical `MAIN_SOURCE` as the permanent integration target;
- hardcode a historical `ABILITY_SOURCE` as the permanent integration target;
- patch tracked source or tests with exact string replacement before testing;
- create hidden semantic fixes that are absent from the commit being validated;
- force-push `ability` as a side effect of validation;
- rewrite `main` as a side effect of validation;
- manufacture a different synthetic tree independently on Linux and Windows;
- claim a branch is merge-ready if the current candidate SHA itself was never tested.

## 6. Branch mutation rules

Validation and branch mutation are separate concerns.

The following pattern is forbidden:

```text
checkout old ability
+ merge hardcoded main
+ CI hotfix source/tests
+ test synthetic tree
+ force-push synthetic result back to ability
```

This creates moving-target races and can make a red Action mean “branch changed while CI was running” instead of “code failed tests”.

The `ability` branch remains the development source branch. Testing a merge candidate must not rewrite it.

## 7. Why ordinary merge is the default

`main` and `ability` may have many commits of historical divergence while still touching largely different product areas.

Therefore:

- commit counts are not a substitute for file-level conflict analysis;
- a large ahead/behind count does not justify a custom integration engine;
- Git already provides the correct mechanism for combining mostly orthogonal histories;
- indirect compatibility changes are discovered by testing the merged tree.

Even if ability-owned files do not overlap directly with recent `main` edits, full post-merge testing remains mandatory because ability code can depend on shared battle state, data structures, APIs, scheduling, evaluation, parsing, build configuration, or test harness behavior changed by `main`.

## 8. Conflict policy

When a conflict occurs:

1. understand what both branches intended;
2. resolve the source semantically;
3. preserve current `main` behavior outside ability-owned scope unless an ability integration genuinely requires an interface change;
4. preserve intended ability mechanics and tests;
5. add/update regression coverage if conflict resolution changes behavior;
6. commit the resolution before CI;
7. document meaningful integration fixes in `changelog.md`.

Do not hide conflict resolution inside workflow scripts.

## 9. Handling Windows/MSVC fixes

Windows/MSVC-specific fixes are normal source/test portability fixes and belong in Git history.

Examples include:

- pointer/reference lifetime fixes;
- canonical ability-name corrections;
- portable temporary-directory handling;
- compiler-specific conformance corrections.

If such a fix is required for the candidate to pass Windows, commit it normally and test the new candidate SHA on all required platforms.

A Windows CI hotfix applied only after checkout is not an acceptable substitute.

## 10. Handling new commits during validation

Once `INTEGRATION_SHA` is created, new commits may continue to appear on `ability` or `main` without invalidating the meaning of the running tests: the tests still validate their immutable candidate.

However, those new commits are not part of that candidate.

Choose explicitly between:

- finish validating and merge the frozen candidate; or
- abandon it and create a new candidate from newer source refs.

Never mutate the candidate underneath an active CI run.

## 11. Required audit record

For every serious ability integration attempt, preserve at least:

```text
MAIN_SOURCE=<sha>
ABILITY_SOURCE=<sha>
INTEGRATION_SHA=<sha>
Linux CI=<result/run>
Windows/MSVC CI=<result/run>
Python tests=<result>
Ability checks=<result>
Final promoted SHA/tree=<sha>
```

This may live in the PR description, integration report, changelog, or other durable project record.

The essential property is that another agent can prove which exact code was tested and which exact code was accepted.

## 12. Definition of Done for Ability → Main

Ability integration is complete only when all of the following are true:

- [ ] `MAIN_SOURCE` was current when the candidate was created.
- [ ] `ABILITY_SOURCE` was the intended current ability head when the candidate was created.
- [ ] A normal Git merge produced the integration candidate.
- [ ] All merge conflicts were resolved in committed repository files.
- [ ] No tracked product source/test mutation is required inside CI.
- [ ] One immutable `INTEGRATION_SHA` was identified.
- [ ] Required Linux build/tests passed for that candidate.
- [ ] Required Windows/MSVC build/tests passed for that candidate.
- [ ] Required Python tests passed for that candidate.
- [ ] Ability-specific registry/evidence/regression checks passed as applicable.
- [ ] No validation job failed merely because it attempted to rewrite `ability`.
- [ ] The candidate tree that passed CI is exactly the tree promoted to `main`.
- [ ] `changelog.md` records meaningful integration/fix commits.

If any item is false, the integration is not canonically complete.

## 13. Anti-patterns

Do **not** solve integration failures by repeatedly doing any of the following:

- updating a hardcoded `ABILITY_SOURCE` in a one-shot script;
- updating a hardcoded `MAIN_SOURCE` in a one-shot script;
- adding another `replace_exact(...)` patch to make the synthetic candidate compile;
- force-pushing the tested result back into `ability`;
- cancelling a valid immutable candidate merely because the source branch received a newer unrelated commit;
- treating a candidate-preparation failure as proof that ability mechanics failed tests;
- treating tests of an old ability snapshot as evidence for the current ability head;
- merging a different tree than the one that received the green checks.

These approaches hide the actual state of the project and destroy the traceability between test result and merged code.

## 14. Agent instruction

Any agent tasked with integrating `ability` into `main` must follow this document before attempting to repair or extend historical one-shot integration machinery.

Unless a future project decision explicitly replaces this canon, the default action is:

> **Create a clean integration branch from current `main`, merge current `ability` with normal Git, commit all real fixes, run the full CI matrix on one immutable candidate SHA, and promote exactly that tested result to `main`.**

If legacy integration workflows contradict this rule, this canon takes precedence for the merge procedure; legacy automation should be simplified or retired rather than used to mutate the candidate during validation.
