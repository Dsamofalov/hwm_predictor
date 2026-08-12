# HWM Test Execution Canon

This document defines the canonical testing policy for HeroesWM Solver.

It applies to the supported **Windows/MSVC** validation path and to Core, Full, Ability, planner, runtime, extension, corpus, evidence, regression, and future test surfaces.

The central rule is simple:

> **Make tests as atomic, independent, deterministic, and exactly accountable as practical. Parallelism is an execution optimization, not a correctness contract.**

There is deliberately **no fixed required shard count, worker count, matrix width, or `max-parallel` value** in this canon. Those values may change as test inventory, runner availability, setup cost, and execution times change.

---

## 1. Correctness is invariant under test scheduling

Changing the execution plan may change where and when a test runs. It must not change what is tested or what counts as success.

For a given candidate SHA, any serial, sharded, or highly parallel execution plan must preserve:

1. the complete mandatory test inventory;
2. the same production sources and generated inputs;
3. the same assertions and acceptance thresholds;
4. the same corpus/sample population unless sampling is itself part of the canonical gate;
5. the same deterministic or stochastic semantics;
6. the same required Debug/Release configuration;
7. the same evidence fields and final reduction logic;
8. the same failure semantics;
9. the rule that every mandatory atomic unit must succeed before the aggregate gate succeeds.

CI must never be made faster by deleting tests, reducing mandatory samples, weakening tolerances, suppressing failures, retrying until green, or validating a different source tree.

---

## 2. Atomicity is the primary design goal

A test unit should contain the smallest meaningful piece of validation that can execute independently without relying on mutable state produced by another unrelated test.

Prefer exposing independent cases separately instead of hiding them inside one long process or one monolithic script.

Examples of useful atomic units include:

- one C++ regression function;
- one pytest node ID;
- one protocol scenario;
- one daemon integration scenario with its own process tree;
- one planner replay case or a small deterministic bundle of replay cases;
- one corpus/evidence map unit whose result can be reduced exactly;
- one extension/typecheck/build gate when that gate is itself indivisible.

A genuinely stateful ordered scenario remains one atomic unit. Do not split inside a sequence when later assertions intentionally depend on earlier state transitions.

Atomicity is preferred because it improves:

- failure localization;
- crash and hang isolation;
- test-order independence;
- parallel scheduling opportunities;
- incremental diagnosis;
- confidence that one early failure did not hide later independent failures.

---

## 3. No hard parallelism contract

The repository must not encode a correctness requirement such as:

- an exact number of shards;
- an exact number of matrix jobs;
- an exact worker count;
- a mandatory `max-parallel` value;
- a permanent mapping of "suite X must always use N jobs".

Those are scheduler choices, not semantic requirements.

The desired execution shape is:

```text
small prerequisite(s)
        |
        +--> build immutable artifact once
        |
        +--> discover/freeze exact test inventory once
                    |
                    v
          independent atomic jobs
        /   /   /   |   \   \
      t0   t1  t2   ...  tN
        \   \   \   |   /   /
                    v
              strict aggregate
```

Use as much concurrency as is useful and available, but do not couple correctness to any particular concurrency setting.

A workflow may temporarily choose a concrete shard count or `max-parallel` for cost, runner-capacity, or startup-overhead reasons. CI contract tests should validate that such values are internally consistent, not that they equal a magic number.

Changing a scheduling value alone should normally not require changing test semantics or this canon.

---

## 4. Exact inventory before partitioning

Every sharded surface must be able to prove that no mandatory case was lost or duplicated.

Conceptually, first freeze a canonical inventory:

```text
case-id-a
case-id-b
case-id-c
...
```

Then partition that exact inventory.

The aggregate validation must enforce:

```text
UNION(all executed case IDs) == canonical inventory
INTERSECTION(any two shard case-ID sets) == empty
count(executed case IDs) == count(canonical inventory)
```

Additional requirements:

- inventory ordering/canonicalization must be deterministic;
- every selected ID must correspond to a real test;
- every mandatory test must be selected exactly once;
- a silently empty mandatory shard is an error when emptiness indicates a partitioning mistake;
- a test must not disappear merely because the chosen shard count changes.

When a workflow builds its matrix dynamically, the matrix is an execution representation of the canonical inventory, not the source of truth for what tests exist.

---

## 5. Shard-count invariance

`ShardIndex`, `ShardCount`, matrix position, worker number, and job order are scheduling metadata only.

They must not affect:

- test inputs;
- random seeds;
- expected results;
- tolerances;
- sample membership;
- model selection;
- acceptance thresholds;
- production behavior under test.

Bad pattern:

```text
seed = base_seed + shard_index
```

because changing the execution layout changes the experiment.

Preferred pattern:

```text
seed = deterministic_hash(base_seed, canonical_case_id, sample_id)
```

The same case/sample must receive the same semantics regardless of which worker runs it.

---

## 6. Independence and hermetic execution

Independent jobs must not depend on shared mutable state.

Each atomic unit should own its temporary resources, including where applicable:

- temporary directories;
- output/evidence files;
- daemon/process trees;
- dynamically allocated ports;
- caches that can be safely read but not mutated as shared test state;
- generated per-job manifests.

Do not make unrelated jobs communicate through a shared mutable file, fixed TCP port, database, process instance, or reused workspace state.

Tests must not depend on execution order unless order is explicitly part of one atomic scenario.

If two tests fail only when reordered or run concurrently, that is a test-isolation defect unless the shared dependency is intentional and documented.

---

## 7. Build once, fan out immutable artifacts

Recompiling the same target in every atomic test job wastes wall-clock time and runner capacity.

For a required configuration:

1. build the required binaries once when practical;
2. associate the build with the exact candidate SHA;
3. publish/transfer immutable artifacts;
4. fan those artifacts out to independent test jobs;
5. never treat successful compilation as successful testing.

Debug and Release artifacts remain distinct when both configurations are required.

A test job must not mutate and republish a shared binary under the same artifact identity.

Tests should wait only for prerequisites they actually require. An unrelated build, corpus job, or evaluator is not a valid dependency merely because an old workflow placed it earlier.

### 7.1 CI completion is not a global work barrier

Hosted CI is a required verification source, not a reason to idle independent development work.

When CI for a candidate SHA is still running, continue any useful task whose correctness does not depend on that pending verdict. In particular, independent code/documentation work, read-only audits, evidence attribution, test design, benchmark analysis, and preparation of another atomic change should proceed in parallel when safe.

Waiting for CI is justified only when the next action materially depends on its result, for example when:

- the result is required before declaring a checkpoint validated or updating verified status/metrics;
- a failure must be diagnosed before safely changing the same surface;
- the next change would depend on behavior that the pending run is specifically validating;
- stacking another dependent change would make failure attribution ambiguous.

Parallel work must preserve attribution: keep candidate SHAs and logical changes separately identifiable, do not claim a pending job passed, and do not use concurrency as a reason to mix unrelated changes into one commit.

**Default rule: do not wait for CI if another useful independent task can be executed safely in parallel.**

---

## 8. C++ / MSVC policy

For C++ test executables containing independent hand-written cases, prefer an explicit stable inventory and direct case selection, for example conceptually:

```text
hwm-tests --list
hwm-tests --case <case-id>
```

A deterministic shard interface is also acceptable:

```text
hwm-tests <shard-index> <shard-count>
```

provided that:

- the complete case list is explicit and deterministic;
- every case maps to exactly one execution unit;
- the selected case names are logged;
- shard metadata cannot affect case semantics;
- aggregate validation proves exact coverage.

One-case-per-job is desirable when cases are expensive, crash-prone, hang-prone, or otherwise benefit from process isolation.

Bundling several tiny cases is acceptable when runner/setup overhead would dominate, provided the bundle remains deterministic and exact coverage is preserved.

A monolithic executable should not remain monolithic solely because it historically ran that way.

---

## 9. Python policy

For Python tests, the preferred atomic identity is the pytest node ID when stable collection makes that practical.

Discovery must use the same environment, markers, selection rules, and candidate SHA as real execution.

File-level sharding is acceptable as an intermediate or efficient representation, but it must not be mistaken for the smallest possible semantic unit.

Environment rules:

- each job gets an isolated execution environment;
- caches may accelerate immutable dependency/download inputs;
- a mutable `.venv` must not be concurrently shared as test state;
- the local project must correspond to the exact candidate SHA;
- cache hits are never evidence that tests passed.

Use in-process parallelism such as pytest worker pools only where it helps after preserving atomic identity and deterministic accounting.

---

## 10. Runtime and integration tests

Independent daemon/runtime checks should be independent jobs or independently runnable atomic units unless they intentionally share one ordered persistent session.

Each independent runtime test should normally:

- start its own process tree;
- allocate its own temporary state;
- use a free/dynamic port where possible;
- bound startup and execution time;
- clean up its processes/resources;
- report enough output to diagnose failure.

Authentication/pairing, stale cancellation, binding, WebSocket streaming, and similar unrelated scenarios should not be serialized merely because they use the same executable.

---

## 11. Planner, replay, corpus, and evidence tests

Independent battle IDs, held-out states, replay IDs, or sample IDs are naturally partitionable once their canonical manifest is frozen.

Requirements:

- freeze the full input set before partitioning;
- execute every mandatory input exactly once;
- keep planner/model settings identical across workers;
- keep random streams independent of shard layout;
- prove exact input coverage at aggregation;
- preserve the original global acceptance calculation.

Workers must not independently "discover whatever files happen to exist" when discovery order, filtering, or sampling could differ. Use one canonical manifest or an equivalently deterministic discovery rule.

---

## 12. Exact map/reduce for global metrics

Parallelizing evidence computation must not change the mathematics of the gate.

### Independently reducible work

Per-case parsing, prediction, residual computation, structural validation, and replay are good map operations.

### Exact reducers

When the serial gate computes a global metric, workers should emit raw observations or mathematically sufficient statistics, and one reducer should reproduce the original global calculation.

Examples of mergeable data include:

- counts;
- sums;
- sums of squares;
- confusion-matrix cells;
- explicitly mergeable histograms;
- per-case residual records.

Do **not** average shard percentages, shard RMSE values, shard quantiles, shard calibration errors, or shard pass/fail values unless that operation is mathematically identical to the canonical serial metric.

Globally coupled operations such as fitting one calibration parameter, selecting one threshold/model, or evaluating a non-mergeable quantile may parallelize preprocessing but must preserve one deterministic global decision stage.

---

## 13. Balancing is an optimization, not a semantic rule

When atomic cases have very different runtimes, deterministic weighted partitioning may reduce wall-clock time.

Historical durations may be used only as scheduling weights. They must never decide whether a case is included.

A balancing algorithm should be deterministic for the same inventory and duration metadata and should log the resulting mapping sufficiently for diagnosis.

The optimization objective is to avoid one unnecessarily slow execution unit becoming the critical path while preserving exact coverage and atomic semantics.

There is no canonical required number of buckets.

---

## 14. CI contract tests: what they should and should not assert

Workflow-contract regressions should test semantic invariants.

They should validate, as applicable:

- Windows/MSVC is the supported execution lane;
- mandatory suites are represented;
- test inventory discovery is deterministic;
- all discovered mandatory cases are assigned;
- assignments contain no duplicates or omissions;
- shard indices are unique and valid for the declared plan;
- shard parameters passed to runners are derived consistently from the active plan;
- build artifacts correspond to the candidate SHA/configuration;
- unrelated atomic jobs do not acquire accidental dependencies;
- aggregate jobs require every mandatory child result;
- global evidence reducers preserve exact semantics;
- timeout/crash failures remain visible.

They should **not** treat the following as permanent correctness requirements:

- `len(matrix) == <magic number>`;
- `ShardCount == <magic number>`;
- `max-parallel == <magic number>`;
- a fixed number of pytest files per shard;
- a fixed worker budget.

If an implementation currently uses a concrete count, a contract test may verify consistency, for example that declared indices cover the declared shard count exactly. It should not require that count to remain unchanged forever.

---

## 15. Failure handling and aggregation

Fail-fast inside one atomic scenario is acceptable when continuing that same scenario has no diagnostic value.

Across independent units, one failure should not unnecessarily prevent unrelated units from running when the CI system can still collect their results.

The aggregate gate must fail if any mandatory atomic unit fails, crashes, times out, is missing, or produces invalid evidence.

Do not convert missing child results into success.

Do not hide flaky behavior through unconditional retries. A retry policy, if ever introduced for infrastructure-only failures, must distinguish infrastructure failure from product/test failure and must not erase the original result.

---

## 16. Timeouts

Timeouts should be bounded at the smallest useful level so one hang does not block an entire large validation surface.

Atomic jobs make short, meaningful timeouts practical.

Timeout values are operational settings and may evolve with runner performance. They are not substitutes for assertions and must not be relaxed merely to conceal deterministic hangs or deadlocks.

---

## 17. Adding a new test

When adding a regression or validation case:

1. define the smallest meaningful independent unit;
2. give it a stable identity;
3. make its inputs deterministic or reproducibly stochastic;
4. avoid shared mutable resources;
5. add it to canonical discovery/inventory;
6. ensure the execution planner assigns it exactly once;
7. ensure aggregate validation cannot silently omit it;
8. keep its semantics invariant under shard-count or worker-count changes;
9. update workflow-contract coverage when the new surface changes the CI structure.

A new test is not fully integrated if it exists in source but can silently disappear from the active validation inventory.

---

## 18. Review checklist

Before accepting a test-parallelization change, verify:

- [ ] Is each execution unit as atomic as practical?
- [ ] Are independent units free of unintended ordering/state dependencies?
- [ ] Is the canonical inventory complete and deterministic?
- [ ] Does every mandatory case execute exactly once?
- [ ] Can shard/worker counts change without changing test semantics?
- [ ] Are concrete parallelism settings treated as tuning rather than canon?
- [ ] Are builds reused safely as immutable artifacts where practical?
- [ ] While hosted CI is running, is useful independent work continuing instead of idling on an unrelated pending verdict?
- [ ] Are crashes and hangs isolated rather than able to hide many unrelated cases?
- [ ] Are runtime resources isolated per independent job?
- [ ] Are global evidence metrics reduced exactly rather than approximately?
- [ ] Does the aggregate gate fail for every missing/failed mandatory child?
- [ ] Do workflow-contract tests assert invariants instead of magic parallelism numbers?

---

## Canonical summary

**Tests should be decomposed to the smallest meaningful independent units and made exactly accountable.**

**Independent units should be allowed to run concurrently, but the repository does not prescribe a fixed level of concurrency.**

**Hosted CI is a verification barrier only for decisions that depend on its verdict; independent useful work should continue in parallel while CI runs.**

**Shard count, worker count, matrix width, and `max-parallel` are implementation details that may change without changing test semantics.**

**The permanent contract is atomicity, independence, determinism, exact coverage, exact reduction, failure visibility, and Windows/MSVC correctness.**
