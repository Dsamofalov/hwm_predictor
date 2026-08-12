# HeroesWM Solver — Ability Change Log

This is the canonical change log for work performed on the `ability` branch and ability-owned code/data/docs.

The root [`changelog.md`](../../changelog.md) remains the main/integration change log. Ability development must be recorded here first; main integration may later summarize the same work in the root change log.

## Working convention

- Every functional ability change is committed as its own logical change set.
- Immediately after a functional commit, a separate bookkeeping commit updates this file and [`AGENT_STATUS.md`](AGENT_STATUS.md) with the real functional commit SHA and validation evidence.
- A bookkeeping commit cannot record its own SHA; entries therefore reference the functional commits they document.
- Record semantic status changes explicitly: `exact`, `partial_exact`, learned/unresolved boundaries, and evidence blockers.
- Record the authoritative hosted Windows/MSVC Ability CI run when a functional package changes executable behavior, tests, registry classification, or ability-owned tooling.
- Never rewrite or silently drop historical entries. Corrections are appended as corrections.

## 2026-08-12

### Ability snapshot integration baseline

- Commit: `f98ea913be9331ca393c49df82b2025303956f92` — `feat: integrate ability evidence snapshot with atomic CI`.
  - Recreated the final ability-owned snapshot on top of current `main` without merging divergent raw ability history.
  - Imported ability evidence modules, regressions, registry state, ability-owned C++ tests, and dedicated atomic Ability CI.

- Commit: `53a2e08b9eb2d8185f9d72f8ebf03b5b77b1a886` — `fix: delimit PowerShell case labels`.
  - Fixed hosted-Windows PowerShell interpolation exposed by the first real atomic run.

- Commit: `03d2fbe138e0dad929037315dce46d38256be8f3` — `fix: preserve C++ inventory JSON for matrix`.
  - Fixed matrix inventory transport; authoritative integration run `31607886774` passed with 85 independent jobs.

- Commit: `a9dab68a0e6720f415571cad2bc4865b50a5f4f0` — `docs: record validated ability snapshot integration`.
  - Recorded the validated snapshot handoff and semantic boundaries after hosted CI became green.

- Commit: `fee222f21746521dcbb1a81bfbce581001d5f0c5` — `docs: record ability snapshot integration [skip ci]`.
  - Current ability-branch baseline before resumed development.

### Semantic boundaries at resumed-development baseline

- `cripplingwound` remains `partial_exact`: observed consequence is represented; speculative proc probability is disabled.
- `powerstrike` trigger prediction remains learned/unresolved rather than being promoted to an exact speculative proc.
- Aura of Fire Vulnerability remains evidence-only until an executable direct-Fire-spell substrate exists.
- Existing closed Life Drain, Regeneration, Mana Feed, Mighty Slam, and Paw Strike mechanics are preserved unless new evidence falsifies their current model.

### Dedicated ability changelog contract

- Commit: `7200ec0f24157ae545f1798c76036f9d26dfedc3` — `docs(ability): add canonical ability changelog and agent rules`.
  - Added this dedicated ability development journal.
  - The same commit mistakenly created a duplicate agent-TZ path under `docs/ability/`; that path is not canonical.

- Commit: `a4f359ccfcf9a3a8133986f6e51f441e4c7cdd29` — `docs(ability): make ability changelog rule canonical`.
  - Corrected the canonical contract at `docs/ABILITY_AGENT_TZ.md`.
  - Made mandatory maintenance of this file the first/highest-priority process rule.
  - Converted the mistaken `docs/ability/ABILITY_AGENT_TZ.md` duplicate into a compatibility pointer to the canonical TZ instead of maintaining two competing contracts.
  - No executable ability semantics changed; hosted Windows/MSVC validation is therefore not claimed for this documentation-only correction.

### Gribbomb `Sbom` discriminator — first strict gate

- Commit: `b6b27633154f12588071a3e94145308aceb57451` — `test(ability): pin Gribbomb Sbom activation boundary`.
  - Replaced the old death-shape heuristic with carrier-sourced `SPECIAL:bom` as the primary Gribbomb activation discriminator.
  - Whole-corpus evidence reached one validated `Sbom` activation, three adjacent living targets, three damage hits, zero missing adjacent targets, and zero non-adjacent extras before the first failing assertion.
  - Hosted Windows run `31621278975`: **FAIL** on the new atomic node because the manually entered expected carrier HP was `36356`, while replay-derived pre-activation HP is `36101`.
  - The failure does not invalidate the discriminator/target-set evidence; it identifies an incorrect handwritten expected value. No rerun is used as a substitute for fixing that value.
  - Runtime boundary remains unresolved: generic replay still leaves the carrier alive after `Sbom`, and predictive Earth-damage magnitude is not inferred from one activation.

- Commit: `d04999b03a094e637223ec7925b3071e50e36ecf` — `fix(ability): use replay-derived Gribbomb pre-bomb HP`.
  - Corrected only the bad expected pre-activation HP (`36356 -> 36101`); no structural evidence assertion was weakened.
  - Hosted Windows run `31621756446`: **PASS**, 86/86 atomic jobs successful on this exact SHA.
  - Whole-corpus gate: 866 battle dirs, 7 carrier battles, exactly 1 validated `Sbom`, exactly 3 adjacent living targets and 3 damage hits, exact target-set match 1/1, zero missing/extra targets, and all 3 non-`Sbom` carrier deaths externally explained.
  - Observed damage deltas are `36101` to one adjacent same-owner stack and `26354` to each of two other-owner adjacent stacks; ratios `1.000` and `0.730` demonstrate that predictive Earth-damage magnitude cannot be inferred as a universal raw-HP delta from this single activation.
  - Generic replay still leaves the carrier alive after the raw `Sbom`; therefore Gribbomb is not promoted in the registry yet. The next executable step is exact self-destruction replay handling without synthesizing predictive Earth damage.

### Gribbomb handoff lock

- User directive after the validated `Sbom` evidence block: **do not advance to the next ability yet**.
- The next agent must continue Gribbomb from the exact replay self-destruction boundary documented above.
- Taunt and the rest of the weighted queue remain deferred until Gribbomb is either safely promoted to the strongest evidence-supported classification or explicitly blocked by a precise remaining evidence/substrate gap.

### Gribbomb observed replay self-destruction

- Commit: `2e82c969e0da708f5bbda6973c92d662a638aa3c` — `fix(ability): replay Gribbomb Sbom self-destruction`.
  - Added a strict replay validator for canonical `Sbom<actor>000000000000`, requiring a living server-declared `gribbomb` carrier.
  - Exact observed replay now removes that carrier (`alive=false`, `count=0`, `top_hp=0`); wrong-source and malformed-marker negative controls remain alive.
  - The three adjacent target HP deltas remain sourced exclusively from raw `DAMAGE` records; no predictive Earth-damage formula was added.
  - Whole-corpus boundary remains 866 battle dirs, 7 carrier battles, exactly 1 validated `Sbom`, exactly 3 adjacent living targets and 3 raw damage hits, exact target-set match 1/1, and zero missing/non-adjacent extra targets.
  - Hosted Windows run `31625718512`: **PASS, 87/87 atomic jobs** on this exact functional SHA, including the new replay-kill, wrong-source/malformed-marker, and non-`Sbom` death controls.
  - Carrier self-destruction is now exact observed replay. Predictive Earth-damage magnitude remains unresolved, so no `exact_search`/fully exact promotion is justified.

### Gribbomb `partial_exact` registry/risk promotion

- Commit: `e4616a155fdd1e15def28f74c8c7af43391177ba` — `feat(ability): classify Gribbomb partial exact`.
  - Promoted `gribbomb` in the source-of-truth registry builder from `unresolved` to `partial_exact`, assigning the canonical `partial_exact` risk `0.25` instead of the old unresolved `0.62`.
  - Added `test_gribbomb_partial_exact_registry_and_risk`, which builds a candidate registry, synthesizes the old Gribbomb `unresolved/0.62` baseline, and requires candidate held-out ability risk to improve without worsening the p90 gate.
  - The same regression requires Gribbomb to stay out of the predictive collateral model, so the promotion cannot be mistaken for a solved Earth-damage formula.
  - Hosted run `31626881854`: **FAIL** only on a brittle magic assertion for the repository-wide `partial_exact`/`unresolved` totals. Gribbomb's semantic classification/risk/collateral-boundary assertions passed before that count check.

- Commit: `19ba4e6caed9977839eaac8ebb0181ca57a32ede` — `fix(ability): compare Gribbomb registry counts relatively`.
  - Replaced the global magic cardinalities with a leakage-safe relative invariant: the candidate registry must be exactly `+1 partial_exact / -1 unresolved` versus the synthetic pre-promotion baseline.
  - No semantic assertion, risk threshold, or evidence boundary was weakened.

- Commit: `da7fd216f6b993f7e6a1770371004253b80d35cc` — `fix(ability): trigger registry risk tests in CI`.
  - Found that Ability CI path filters named only `test_cripplingwound_registry_risk.py`, so a new registry-risk test could fail to trigger the workflow when changed alone.
  - Generalized push/PR filtering to `python/tests/test_*_registry_risk.py` and added `test_registry_risk_manifest_tests_trigger_ability_ci` to lock that contract.
  - Authoritative hosted Windows run `31627726097`: **PASS, 89/89 jobs** on the exact SHA, including the Gribbomb registry/risk node, all Gribbomb self-destruction controls, the workflow-trigger contract, all C++ cases, and final `publish_status`.
  - Validated semantic ceiling: `gribbomb = partial_exact`, risk `0.25`; exact observed carrier self-removal is represented, while predictive Earth/collateral-damage magnitude remains unresolved and disabled.
  - Remaining Gribbomb repository-consistency task: deterministically regenerate the checked registry/report artifacts from the validated builder before advancing the weighted queue to Taunt.
