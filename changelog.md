# HeroesWM Solver — Change Log

This file is the development diary for repository changes performed against the active specification (`SPEC.md` / `HeroesWM_Solver_TZ_Status_0.3.0.md`).

## Working convention

- Functional changes are committed as separate logical change sets.
- After each functional commit, this file is updated with the real commit SHA in a bookkeeping commit.
- Specification/status documents are updated when a requirement is verified or its implementation status changes.
- A bookkeeping commit cannot record its own SHA; entries therefore reference the functional commit they document.

## 2026-08-10

### Repository layout and CI activation

- Commit: `d0daf171bb7c3fdee84a943eabde37e8905a4435`
- Moved the project contents from `heroeswm-solver-github-0.3.0/` directly to the repository root without changing file contents.
- This made `.github/workflows/ci.yml` visible to GitHub Actions.
- Verified workflow run `31337305152`: completed successfully.

### Review focus started

- Started source-vs-spec review with priority on `hwm_battles/`, the two supplied creature HTML snapshots, and creature ability semantics/coverage.
- No implementation claim is marked complete until verified against repository data and tests.

### Changelog initialization

- Commit: `b3c085477c0d55ea8aac6bf2f1be1a8fb36abc5a`
- Added `changelog.md` and established the commit-linked development diary convention.

### Life Drain patch tooling

- Commit: `4b4d18fd8727fe9e9c9fec72edd26eff1cc0cf08`
  - First one-shot workflow staging attempt; GitHub rejected the embedded multiline YAML before creating a job. No functional source change was produced.
- Commit: `539eba4ebf9ff075a420f2da6e01990351f86e55`
  - Moved the large patch logic into a temporary Python script to keep the workflow YAML small and parseable.
- Commit: `66150992861f3641a1cba32ef2c3e089dfb50a0a`
  - Fixed the temporary workflow and reached a real build/test run. C++ build and CTest passed, but an over-broad `git diff --check` rejected intentional Markdown hard-break spaces and generated CRLF CSV, so no functional commit was produced.
- Commit: `73e7cdd743fdf3606b62c5bfddd5aa1316334c31`
  - Narrowed the whitespace gate to C++/Python source files and added cleanup of the first temporary script.
- Commit: `e5fc43c25792f5a66c12931f07d9070c30ccf7b1`
  - Re-ran the verified patch pipeline successfully. The functional commit below deletes all temporary patch infrastructure.

### Exact Life Drain transition

- Commit: `132cb2b35118845acb24c25573a6088b846a58af`
- Implemented `lifedrain` healing from 50% of actually inflicted physical damage, including resurrection up to `max_count`.
- Applied the same rule to normal and concentration/pre-emptive retaliation paths.
- Added a phantom-damage guard so phantom dissipation cannot inflate healing.
- Added C++ regression coverage for primary healing/resurrection, max-count cap, and retaliation healing.
- Promoted `lifedrain` from `learned_damage` to `exact_search`; regenerated Ability Registry to 82 exact-search / 180 learned-damage / 78 unresolved.
- Updated active Markdown specification, implementation report, and test report status.
- C++ Debug build and CTest passed before commit.

### Regeneration patch tooling

- Commit: `9ae958b2bc2aed3382bb05af0578d3db3224b27d`
  - Initial Regeneration staging runner. Production code and registry generation compiled far enough to verify 83/179/78 counts, but the new C++ test did not compile because the project `CHECK` macro returns `false` inside lambdas. No functional commit was produced.
- Commit: `4a4d9947a63ab4246d0a853c148ae6a6cee1ab70`
  - Corrected the regression helper lambdas and the scheduler indentation warning; re-ran the self-removing patch pipeline.
- The temporary workflow and patch scripts were removed by the functional commit below.

### Exact Regeneration turn-start transition

- Commit: `ed108d79169bb21720bc830f846865fcf9c1a9b6`
- Implemented `regeneration` as a start-of-turn transition when the rollout advances to the next actor.
- Uses an exact 30–50 HP integer roll and heals only the current top creature; stack `count` never increases.
- Explicitly excludes Srn2 preparatory same-actor reactivation and terminal states to avoid duplicate/non-turn healing.
- Added C++ regression coverage for 30/40/50 HP rolls, max-HP cap, next-actor timing, and no-resurrection invariant.
- Promoted `regeneration` from `learned_damage` to `exact_search`; regenerated Ability Registry to 83 exact-search / 179 learned-damage / 78 unresolved.
- Updated active Markdown specification, implementation reports, and test report status.
- C++ Debug build and CTest passed before commit.

### Regeneration formula correction

- Commit: `c60b3c9af08e5a88973b86809191f89720aee67a`
  - Staged a self-removing correction after cross-checking the HeroesWM reference formula against the fixed 30–50 implementation.
- Commit: `00dd1074ad6c83d92f43bb90a1fe1dc5083aaadf`
  - Corrected Regeneration from a fixed 30–50 HP roll to `random(3,5) * min(current_count, 10)`.
  - Preserved the already-correct start-of-turn timing, Srn2 exclusion, top-unit-only healing, and no-resurrection invariant from `ed108d79169bb21720bc830f846865fcf9c1a9b6`.
  - Expanded regression coverage for 3-creature 9/12/15 HP healing and the 10-creature 50 HP cap.
  - Updated the active Markdown specification formula. Ability Registry counts remain 83 exact-search / 179 learned-damage / 78 unresolved.
  - C++ Debug build and CTest passed before commit.

### Ability decision corpus probe

- Commit: `0346b7befb70ac3d47540ed60f4d857016c9ddbe`
  - Added `scripts/ability_probe.py`, a read-only analyzer built on the canonical `iter_battle_decisions()` replay stream.
- Commit: `2f8ffc8f7ef92cc531b77e60c7b099af68368203`
  - Ran the probe over the repository `hwm_battles` corpus for `manafeed` and stored `data/reports/manafeed_probe.json`.
  - Matched decisions: **730** across **125** battles; mechanic-like candidates: **243**.
  - The report preserves raw decision records/opcodes and already-decoded mana deltas for evidence-driven wire decoding.
  - Probe parse errors: **0**.

### Exact Mana Feed action

- Commit: `5f01febfbc542f662f99f49acb401201edb18099`
  - Initial verified patch staging. Registry regeneration and the 42-record corpus probe passed, C++ compiled, but CTest exposed a regression-test bug caused by `begin()`/`end()` from two temporary legal-action vectors. No functional commit was produced.
- Commit: `aabf7ed4bbab7df68238370e637fc1562e81bf71`
  - Corrected the regression test to retain one legal-action vector and re-ran the self-removing verified patch.
- Commit: `80ded68159636f3d3b497e00cc86aa422823eefa`
  - Decoded `Smfd` as actor3 + own-hero3 + amount2 + zero trailer and marked it exact only when actor ability, ownership and `amount=min(count,mana)` invariants hold.
  - Added Python and C++ canonical mana transitions: creature mana decreases and own hero mana increases by the same amount.
  - Added exact C++ legal `Ability` generation and simulator execution targeting only the actor's own hero.
  - Reclassified observed Mana Feed decisions as target-bound `ABILITY` actions instead of generic targetless `CAST_OR_ABILITY`.
  - Re-ran the full 866-battle Mana Feed probe: **42/42 `Smfd` records** satisfy the exact action/target/mana-delta invariant.
  - Added Python and C++ regressions, promoted `manafeed` to exact-search and regenerated the registry to 84 exact-search / 178 learned-damage / 78 unresolved.
  - Updated active Markdown specification, implementation reports, test report and `data/reports/manafeed_probe.json`.
  - Targeted C++ build/CTest and Python replay pytest passed before commit.

### Mana Feed full integration verification

- Commit: `255c2c088a206383136de9e69fc8311b98f44bfc`
- Triggered the standard repository CI against the final Mana Feed functional tree because pushes made by the self-removing workflow do not recursively trigger GitHub Actions.
- Workflow run `31341290199`: **PASS**.
- Verified C++ configure/build/CTest, the complete Python pytest suite, extension dependency installation, TypeScript typecheck, and extension build.

### Current ability-risk refresh

- Commit: `84407eddc17a82b160bca2c4c3da1422714e3474`
  - Staged a one-shot self-removing risk refresh against the current Ability Registry.
- Commit: `7bdc2186ed430d46e629a5eece22db5eb42efee7`
  - Recomputed held-out ability risk from the 866-battle corpus using current registry support/risk weights after Life Drain, Regeneration and Mana Feed.
  - Risk mean / p90: **0.2347 / 0.3971** across **1748** sampled player states.
  - Current top contributors: caster(dynamic_spellbook,2425), enraged(modeled_kill_trigger,2070), cripplingwound(learned_damage,312), shieldbash(modeled_proc,538), mightyslam(learned_damage,181), pawstrike(learned_damage,218), powerstrike(learned_damage,163), entroots(modeled_proc,667), bloodlust(partial_exact,481), waterproof50(partial_exact,647).
  - Stored reproducible report at `data/reports/ability-risk-current.json`.

### Ability probe state-delta upgrade

- Commit: `d5716c42ba023e0ab084c1fa0f5ced9afe9047d8`
  - Extended `scripts/ability_probe.py` with actor/target before-after snapshots and HP/count/speed/initiative/ATB/effect/position deltas while preserving Mana Feed fields.
- Commit: `2304ef3f2ac33f73e555d49e8f391e0a5e174292`
  - Added regression coverage for state-delta aggregation.
- Commit: `ff90c77c483d1e0291ffcdfde73f4d23061aaf5b`
  - Verified the enhanced probe with targeted pytest and staged a Crippling Wound corpus run.
- Commit: `72c3502ac61da10b233c563b03e7b3ac72e35052`
  - Stored `data/reports/cripplingwound_probe.json` from the full repository corpus.
  - Matched decisions: **808** across **173** battles; mechanic-like candidates: **585**; parse errors: **0**.
  - Special-code distribution: `{'rag': 206, 'wnd': 129, 'ral': 86, 'ra2': 78, 'rn1': 76, 'raa': 60, 'enr': 60, 'blt': 43, 'eod': 32, 'spi': 24, 'at3': 21, 'pfr': 12, 'pss': 10, 'sld': 10, 'ato': 7, 'fd1': 7, 'fw3': 7, 'agl': 6, 'rn2': 6, 'dsp': 5, 'rn7': 4, 'spt': 4, 'ent': 4, 'rn3': 2, 'psc': 2, 'tob': 2, 'rgl': 2, 'sor': 2, 'fw2': 2, 'br2': 1, 'bdd': 1, 'fdc': 1, 'zat': 1, 'cpt': 1, 'snu': 1, 'frz': 1, 'ab3': 1, 'crs': 1, 'rn0': 1, 'prp': 1, 'dsh': 1, 'sff': 1, 'eye': 1, 'fod': 1, 'fo2': 1, 'paa': 1, 'psa': 1, 'mga': 1, 'adp': 1}`.
  - Target speed deltas: `{'0.0': 477}`; initiative deltas: `{'0.0': 477}`; effect additions: `{'proc_cripple': 108, 'proc_shieldbash': 7, 'ra2': 6, 'pfr': 5, 'sld': 2, 'ent': 2, 'fdc': 1, 'tob': 1, 'mga': 1}`.

### Crippling Wound conditional-proc evaluation

- Commit: `5f8547c6f29c5b4bc277f2b5e55f9a939da009f8`
  - Added a reusable chronological proc-context evaluator with state-conditioned logistic validation and creature/action stratification.
- Commit: `885046ae8beeb4ff4c02217ac8238ecb3237d04b`
  - Staged a self-removing evaluation of `cripplingwound` / `Swnd` on the 866-battle corpus.
- Commit: `dcb752be44bca17fbe75ec5dee8f05dac1e88915`
  - Stored `data/reports/cripplingwound_proc_context.json`.
  - Train/held-out: **110/391 = 0.2813** vs **14/86 = 0.1628**.
  - Conditional held-out Brier: **0.15168** vs baseline **0.15034**; AUC **0.5833**; gate: **False**.
  - No production proc is enabled by this report alone; it is an evidence gate for the next functional change.

### Crippling Wound hero-context inspection

- Commit: `65538f5a3cb09904107526a7faa8343cefb59315`
  - Extended the reusable proc-context evaluator with same-owner hero creature/tag buckets from canonical `state_before`.
- Commit: `6bee9f22d39381f80c7a48a60050f7a077428d29`
  - Staged a self-removing full-corpus refresh for the new hero-context output.
- Commit: `89aaee7716f093f19de644fbc972f8b840df8b9c`
  - Refreshed `data/reports/cripplingwound_proc_context.json`.
  - Largest train hero-context buckets: `[{'hero_creature_id': 547, 'hero_tags': ['shooter'], 'n': 83, 'hits': 19, 'rate': 0.2289156626506024}, {'hero_creature_id': 170, 'hero_tags': ['shooter'], 'n': 75, 'hits': 25, 'rate': 0.3333333333333333}, {'hero_creature_id': 1215, 'hero_tags': ['shooter'], 'n': 73, 'hits': 24, 'rate': 0.3287671232876712}, {'hero_creature_id': 0, 'hero_tags': [], 'n': 46, 'hits': 21, 'rate': 0.45652173913043476}, {'hero_creature_id': 1029, 'hero_tags': ['shooter'], 'n': 33, 'hits': 6, 'rate': 0.18181818181818182}, {'hero_creature_id': 1174, 'hero_tags': ['shooter'], 'n': 32, 'hits': 7, 'rate': 0.21875}, {'hero_creature_id': 171, 'hero_tags': ['shooter'], 'n': 10, 'hits': 4, 'rate': 0.4}, {'hero_creature_id': 1451, 'hero_tags': ['shooter'], 'n': 9, 'hits': 0, 'rate': 0.0}]`.
  - Largest held-out hero-context buckets: `[{'hero_creature_id': 170, 'hero_tags': ['shooter'], 'n': 61, 'hits': 9, 'rate': 0.14754098360655737}, {'hero_creature_id': 0, 'hero_tags': [], 'n': 12, 'hits': 4, 'rate': 0.3333333333333333}, {'hero_creature_id': 1029, 'hero_tags': ['shooter'], 'n': 6, 'hits': 0, 'rate': 0.0}, {'hero_creature_id': 1174, 'hero_tags': ['shooter'], 'n': 3, 'hits': 0, 'rate': 0.0}, {'hero_creature_id': 1258, 'hero_tags': ['shooter'], 'n': 2, 'hits': 0, 'rate': 0.0}, {'hero_creature_id': 737, 'hero_tags': ['shooter'], 'n': 1, 'hits': 1, 'rate': 1.0}, {'hero_creature_id': 1144, 'hero_tags': ['shooter'], 'n': 1, 'hits': 0, 'rate': 0.0}]`.
  - This report is diagnostic only and does not enable a production proc probability.

### Mighty Slam / Power Strike corpus probes

- Commit: `6a86fa62e09bac1db3818d76814a6ed2334003a0`
  - Staged self-removing full-corpus probes for two high-impact movement/control abilities.
- Commit: `987cf2c9a76931642ce801782dfe5b954bc4d387`
  - Stored `data/reports/mightyslam_probe.json` and `data/reports/powerstrike_probe.json`.
  - Mighty Slam: **260** decisions / **73** battles; specials `{'enc': 44, 'psf': 33, 'msl': 32, 'enr': 21, 'ra2': 14, 'adp': 7, 'pss': 6, 'spt': 6, 'blt': 5, 'agl': 5, 'paa': 4, 'ral': 3, 'spi': 2, 'raa': 2, 'at3': 2, 'bld': 2, 'plf': 1, 'fdc': 1, 'sld': 1, 'rn7': 1, 'chm': 1, 'rag': 1, 'lzb': 1, 'rgl': 1, 'ent': 1, 'sff': 1}`; position deltas `{'1,-1': 2, '1,0': 1, '0,-1': 1, '-1,1': 1, '0,1': 1, '3,0': 1}`.
  - Power Strike: **659** decisions / **125** battles; specials `{'rag': 393, 'ral': 116, 'ra2': 101, 'prp': 90, 'raa': 90, 'blt': 53, 'rgm': 50, 'enr': 44, 'eod': 33, 'wnd': 31, 'ray': 23, 'at3': 18, 'spi': 13, 'sld': 12, 'pfr': 10, 'pss': 9, 'psc': 7, 'fd1': 6, 'dsp': 3, 'cpt': 3, 'snu': 3, 'ato': 3, 'mrb': 3, 'sff': 3, 'fdc': 2, 'rgl': 2, 'plf': 1, 'br2': 1, 'zat': 1, 'cha': 1, 'agl': 1, 'tob': 1, 'dsh': 1, 'sta': 1, 'fod': 1, 'fo2': 1, 'adp': 1}`; position deltas `{'-1,1': 5, '0,-1': 4, '-1,0': 3, '-1,-1': 2, '1,-1': 2, '1,1': 2, '-9,0': 1, '0,1': 1, '1,0': 1, '-4,0': 1}`.
  - Parse errors: Mighty Slam **0**, Power Strike **0**.

### Mighty Slam wire isolation

- Commit: `885c8b5acb18a3b7aa78d819ed08218fb93ce9a6`
  - Staged a self-removing extraction of `Smsl` decisions from the full Mighty Slam probe.
- Commit: `964807052e9ef91095093ca617042bb782c378dc`
  - Stored `data/reports/mightyslam_msl_evidence.json` with **32** observed `Smsl` decisions.
  - Action types: `{'MELEE_ATTACK': 32}`; carrier creature IDs: `{'435': 3, '652': 12, '792': 4, '1053': 5, '1081': 1, '1189': 7}`.
  - Full raw records and actor/target before-after deltas are retained for exact wire/cooldown/knockback reconstruction.

### Mighty Slam damage/knockback wire enrichment

- Commit: `4ee0b0baa7fa3b2cbbcb4002e035454d56bfc6da`
  - Staged a self-removing canonical `parse_commands()` pass over all isolated `Smsl` records.
- Commit: `56989dce764e7d30e2a53a8c56c8726d61af9a2a`
  - Enriched `data/reports/mightyslam_msl_evidence.json` with every `DAMAGE` and `FORCED_POSITION` record.
  - Damage-event count distribution: `{'1': 14, '2': 16, '3': 2}`; multi-target damage rows: **18/32**.
  - Forced-position count distribution: `{'0': 21, '1': 8, '2': 3}`; rows with knockback: **11/32**.

### Mighty Slam splash-target geometry analysis

- Commit: `0e46fa88a1d2f5a01e193d8b978eafc48a3718fb`
  - Staged a self-removing full-corpus ownership/adjacency check for all `Smsl` secondary damage and knockback records.
- Commit: `ce06bc32be5ae3762c8b6675c21b5fbff23d755e`
  - Stored `data/reports/mightyslam_target_geometry.json`.
  - Secondary damage targets: **20**; enemy **20**, friendly **0**.
  - Secondary adjacency to primary: **8** adjacent, **12** non-adjacent.
  - Forced-position records: small **14**, big **0**.

### Mighty Slam cooldown measurement

- Commit: `28ae9f2f4ba2ea5153b619a76654a38b3ec5b7c7`
  - Staged a self-removing same-actor activation-gap measurement for repeated `Smsl` uses.
- Commit: `6418a74f63bd3df7ba51e257db87e5829a42723f`
  - Stored `data/reports/mightyslam_cooldown.json`.
  - Repeat pairs: **3**; minimum own-activation gap: **3**; distribution: `{'3': 1, '4': 1, '6': 1}`.
  - This measurement is used to avoid an off-by-one cooldown in speculative search.

### Exact Mighty Slam action

- Commit: `b56315fec926d020a9950b5abb9e61aed0459009`
  - Initial staging stopped before source/test execution because a legal/apply patch anchor was not unique. No functional commit was produced.
- Commit: `0b33c7091ffaacdb885918192775856046775ad6`
  - Second staging reached the corpus gate, which rejected `Smsl` because generic DAMAGE classification still won over the explicit ability marker. No functional commit was produced.
- Commit: `ac3da0ee1ed039a3148ffcbaea88ddf2986e4f73`
  - Third staging passed 32/32 corpus classification, registry/risk refresh and C++ build/CTest, but exposed a generated Python-test newline bug. No functional commit was produced.
- Commit: `665e6e0d5105023c5ad348e1a17bc44a38f4cd0e`
  - Fourth staging failed before patch execution because its temporary wrapper contained an unterminated string literal. No functional commit was produced.
- Commit: `9462be7c91600dc5538d1019f4b2612cf038ac17`
  - Consolidated the already validated fixes into one clean runner and re-ran the self-removing Mighty Slam verification.
- Commit: `9cdb8d870de04b0ad6bbd8fd1a47c0ab16e2fb0a`
  - Promoted `mightyslam` to an explicit legal `ABILITY` sharing normal melee reach/move anchors.
  - Added selected-target + target-adjacent **enemy-only** splash using the simulator's authoritative footprint geometry.
  - Added one-cell knockback away from the actor only for surviving small targets and only when `can_place()` accepts the destination; observed corpus has 14/14 forced targets small.
  - Suppressed ordinary retaliation for the Slam branch and retained core physical damage/resistance plus Life Drain, Weakening Strike and reflect interactions.
  - Added a 3-activation cooldown marker; minimum observed same-actor repeat gap is 3.
  - Decoded `Smsl<actor>000000000000` as semantic-safe in Python and C++; server DAMAGE/FORCED_POSITION remain authoritative for observed replay.
  - Re-ran the 866-battle probe: **32/32 `Smsl` decisions classify as `ABILITY`**.
  - Promoted registry to **85 exact-search / 177 learned-damage / 78 unresolved** and refreshed `ability-risk-current.json` (mean 0.2288, p90 0.3960).
  - Synchronized top-level and stale M04/M12/Phase7 ability counts in the active specification/reports.
  - C++ Debug build/CTest and **targeted replay+ability-probe tests** passed before commit; full Python/TypeScript integration is verified by standard CI on the final tree.
