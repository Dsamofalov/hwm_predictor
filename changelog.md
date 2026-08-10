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
  - Special-code distribution: `{'rag': 206, 'wnd': 129, 'ral': 86, 'ra2': 78, 'rn1': 76, 'raa': 60, 'enr': 60, 'blt': 43, 'eod': 32, 'spi': 24, 'at3': 21, 'pfr': 12, 'pss': 10, 'sld': 10, 'ato': 7, 'fd1': 7, 'fw3': 7, 'agl': 6, 'rn2': 6, 'dsp': 5, 'spt': 4, 'ent': 4, 'rn3': 2, 'psc': 2, 'tob': 2, 'rgl': 2, 'sor': 2, 'fw2': 2, 'br2': 1, 'bdd': 1, 'fdc': 1, 'zat': 1, 'cpt': 1, 'snu': 1, 'frz': 1, 'ab3': 1, 'crs': 1, 'rn0': 1, 'prp': 1, 'dsh': 1, 'sff': 1, 'eye': 1, 'fod': 1, 'fo2': 1, 'paa': 1, 'psa': 1, 'mga': 1, 'adp': 1}`.
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

### Paw Strike corpus probe

- Commit: `7414ea61070315efd34aa77a74181f2f17517eba`
  - Staged a self-removing full-corpus probe for `pawstrike` after Mighty Slam became exact.
- Commit: `da87dfa0c447506155c31caeaf659008be3a1690`
  - Stored `data/reports/pawstrike_probe.json` and `pawstrike_registry_entry.json`.
  - Reference: **Удар лапой.** — Существо при атаке имеет шанс сместить вражеский отряд на одну клетку и дополнительно отбросить его в начало ATB-шкалы. Шанс зависит от числа клеток, которых этому существу пришлось пройти, чтобы атаковать цель.
  - Matched decisions: **523** across **85** battles; candidates **415**; parse errors **0**.
  - Action types: `{'MELEE_ATTACK': 357, 'ABILITY': 65, 'MOVE': 63, 'WAIT': 35, 'DEFEND': 3}`; special codes: `{'rn9': 72, 'enr': 29, 'eod': 23, 'sld': 17, 'at3': 15, 'rn2': 14, 'spi': 12, 'rn7': 10, 'rag': 9, 'fw3': 9, 'psc': 8, 'pfr': 8, 'ra2': 6, 'rn1': 6, 'raa': 5, 'blt': 4, 'adp': 4, 'ato': 3, 'pss': 2, 'spt': 2, 'ent': 2, 'crs': 2, 'sff': 2, 'tob': 2, 'rgl': 2, 'zat': 2, 'bdd': 1, 'psf': 1, 'paa': 1, 'slw': 1, 'rn6': 1, 'psa': 1, 'mga': 1}`.
  - Target position deltas: `{'1,0': 28, '0,-1': 20, '0,1': 19, '1,1': 12, '-1,0': 10, '-1,-1': 7, '1,-1': 5, '-1,1': 4, '0,2': 1, '-9,1': 1, '-8,-1': 1, '0,-2': 1}`; effect additions: `{'sld': 9, 'spt': 1, 'ra2': 1, 'rag': 1, 'psa': 1, 'at3': 1, 'pfr': 1}`.

### Paw Strike proc/charge-distance analysis

- Commit: `c0c364f6ee78a0f27fbafe925d28fa78ab7d1532`
  - Staged a self-removing full-corpus derivation of the Paw Strike observable proc signature: primary target `FORCED_POSITION` plus target `I_RECORD`.
- Commit: `d427cf3f4f9a795f8c23562db6dd181fe97a76ca`
  - Stored `data/reports/pawstrike_proc_distance.json`.
  - Eligible melee samples: **357**; proc hits: **150** (0.4202).
  - Any forced-position / primary forced / primary forced+I: **161 / 150 / 150**.
  - Carrier overlap with other knockback abilities: `{}`.
  - Empirical rate by charge distance: `[{'distance': 0, 'n': 21, 'hits': 0, 'rate': 0.0}, {'distance': 1, 'n': 26, 'hits': 4, 'rate': 0.15384615384615385}, {'distance': 2, 'n': 49, 'hits': 15, 'rate': 0.30612244897959184}, {'distance': 3, 'n': 58, 'hits': 17, 'rate': 0.29310344827586204}, {'distance': 4, 'n': 87, 'hits': 47, 'rate': 0.5402298850574713}, {'distance': 5, 'n': 66, 'hits': 38, 'rate': 0.5757575757575758}, {'distance': 6, 'n': 30, 'hits': 19, 'rate': 0.6333333333333333}, {'distance': 7, 'n': 9, 'hits': 3, 'rate': 0.3333333333333333}, {'distance': 8, 'n': 7, 'hits': 4, 'rate': 0.5714285714285714}, {'distance': 9, 'n': 1, 'hits': 0, 'rate': 0.0}, {'distance': 10, 'n': 3, 'hits': 3, 'rate': 1.0}]`.

### Paw Strike temporal probability validation

- Commit: `a7de64d5e8f9a03e99ad42208e7c45971911f998`
  - Staged a self-removing chronological 80/20 validation of distance-conditioned Paw Strike proc probability and observed consequences.
- Commit: `bbe0f0aacdf53d3dff1b40c6493bda60d5df8e6c`
  - Stored `data/reports/pawstrike_probability_validation.json`.
  - Train: **111/249=0.4458**; held-out: **39/108=0.3611**.
  - Held-out Brier: train-frequency **0.23788**, fixed 10%/cell **0.20250**, train-selected linear **0.20495**.
  - Best train linear slope: **0.11/cell**; gate **False**.
  - Big-target stats: `{'train': {'n': 85, 'hits': 38, 'rate': 0.4470588235294118}, 'heldout': {'n': 52, 'hits': 15, 'rate': 0.28846153846153844}}`; small-target stats: `{'train': {'n': 164, 'hits': 73, 'rate': 0.4451219512195122}, 'heldout': {'n': 56, 'hits': 24, 'rate': 0.42857142857142855}}`.
  - Observed proc consequences: `{'proc_rows': 150, 'displacement': {'1': 105, '0': 42, '2': 1, '9': 1, '8': 1}, 'atb_after': {'90.0': 15, '98.0': 12, '95.0': 16, '96.0': 19, '92.0': 10, '99.0': 12, '97.0': 15, '94.0': 12, '100.0': 14, '93.0': 12, '91.0': 11, '50.0': 2}, 'i_tail': {'0023': 3, '0021': 1, '0020': 12, '0012': 28, '0006': 1, '0002': 6, '0010': 28, '0011': 30, '0015': 15, '0014': 7, '0003': 2, '0005': 3, '0013': 3, '0018': 2, '0007': 1, '0009': 8}, 'i_matches_actor': 150}`.

### Paw Strike HP-distance formula validation

- Commit: `0931bc137d4e969bc9794e5e75e8bd811c39d1af`
  - Staged a self-removing chronological validation of the historical HeroesWM base-HP formula combined with per-travelled-cell repeated proc attempts.
- Commit: `73242abd49819efa27768de89bbc2be962862ea7`
  - Stored `data/reports/pawstrike_formula_validation.json`.
  - Held-out Brier: HP-distance formula **0.24191**, train-frequency baseline **0.23788**, linear 10%/cell **0.20250**.
  - `I_RECORD` source matches Paw Strike actor in **150/150** observed procs.
  - Actor owners `{'1': 326, '2': 31}`; same-owner hero presence `{'hero': 339, 'no_hero': 18}`.
  - Formula gate: **False**.

### Paw Strike I-record scope audit

- Commit: `d788f2884fd909e7d8617d6959a1b2388e11f8fe`
  - First Paw Strike production staging was rejected by its corpus gate: parsing explicit I-record sources exposed 174 source-matching records, not the previously isolated 150 primary-target procs. No functional Paw Strike commit was produced.
- Commit: `804e5f62200539e27af2d6f79a38adb23ea645fc`
  - Staged a self-removing audit of all I-records whose four-digit source equals the active Paw Strike melee actor.
- Commit: `300f2a7e45b0e5a87a55731b4487b0606b8184d3`
  - Stored `data/reports/pawstrike_i_record_audit.json`.
  - Source-matching I-records: **174**; class distribution: `{'primary=True,damage=True,forced=True': 150, 'primary=False,damage=True,forced=True': 24}`.
  - Non-primary records retained with complete raw decision/damage/forced-position context instead of being silently labeled Paw Strike.

### Paw Strike I-record ownership/order audit

- Commit: `b1c584c292d4eeaaea09f7b531bfa2ec316c023c`
  - Staged a self-removing owner and raw-order audit for all 174 source-matching Paw Strike I-records.
- Commit: `5c9aaed1bb0f38363675845ae4d3a11d07e802b2`
  - Stored `data/reports/pawstrike_i_ownership_audit.json`.
  - Ownership: `{'opposing': 174}`; event order: `{'d<b<I': 174}`; exceptions: **0**.

### Paw Strike hybrid modeled proc

- Commit: `c85e7ac1349b67bb5300edc052d8960ecfe94e53`
  - Staged a self-removing verified patch after 357 melee observations, 150 primary-target probability samples plus 24 secondary-hit exact I-records, and chronological probability validation.
- Commit: `8805bb78c02d727ffff150a3d3fe9e08c042ab3b`
  - Parsed `I<affected3><source4>` with explicit source UID and validated the observed Paw Strike transition against the active attacker.
  - Marked **174/174** observed Paw Strike I-records semantic-safe and applied exact `ATB=0` in Python/C++ replay state.
  - Added speculative `p=min(1, 0.10*travelled_cells)` proc; held-out Brier **0.20250** vs **0.23788** train-frequency baseline. The older HP-ratio formula remains rejected (held-out Brier **0.24191**).
  - On speculative proc, ATB reset is unconditional; one-cell physical push is attempted away from the attacker only if `can_place()` accepts the resulting footprint. Retaliation is not hard-suppressed and naturally depends on post-push adjacency.
  - Promoted `pawstrike` from `learned_damage` to explicit runtime `modeled_proc`; registry is **85 exact-search / 9 modeled-proc / 176 learned-damage / 78 unresolved**.
  - Refreshed current ability risk to mean **0.22431**, p90 **0.37538**.
  - Updated active specification and reports, including the previously verified Mighty Slam full-CI Python count **42/42**.
  - C++ Debug build/CTest and targeted Python replay/probe tests passed before commit.

### Local daemon pairing/authentication

- Commit: `40665e57a42244ac5dfc07321aab5ced580173c4`
  - Staged the self-removing M16 security patch and verification runner.
- Commit: `a1012a73146fc9c832a31b7d48cc38464ddc8a76`
  - Added a persistent 256-bit local bearer token and explicit per-process pairing code; the bearer token survives daemon restarts while the human code rotates.
  - Private local API routes now require `Authorization: Bearer <token>`; only health/version, CORS preflight and `/pair` remain public.
  - Added pairing brute-force lock after 10 failed codes per daemon process and kept loopback-only binding/origin filtering.
  - Extension service worker and side panel persist the token in `chrome.storage.local`, attach it to capture/runtime-probe/recommend/status requests, and clear it on HTTP 401.
  - Added `scripts/test_local_api_auth.py`: unauthenticated private routes rejected, wrong code rejected, correct pair succeeds, token file persists, old token works after daemon restart.
  - Added the integration test to normal CI and updated M16 specification status.
  - Targeted C++ build/CTest, local API integration, TypeScript typecheck and extension build passed before commit.

### Revision-bound stale-search cancellation

- Commit: `8a7423546eb4df3c6309d81e85f107b90d78cbe2`
  - Staged the self-removing closed-loop cancellation patch and end-to-end regression.
- Commit: `ed20ee1f1bdb88200c65f74f13e60dc25a47f1b7`
  - Added monotonic SessionStore revision and atomic state+revision snapshots.
  - Planner now polls a cancellation callback between simulations and returns early when a newer observed revision arrives.
  - `/recommend` binds planning to the snapshot revision and returns structured `stale` metadata instead of spending the full search budget on an obsolete state.
  - Revision invalidation is intentionally stronger than hash-only invalidation: the regression republishes the same demo state (equal state hash) and still cancels the old search.
  - Extension recommendation epoch prevents an older in-flight result from overwriting a newer one;
  - side panel additionally checks recommendation `state_hash` against current daemon status before rendering.
  - Added `scripts/test_stale_cancellation.py`; C++/CTest, pairing auth, stale cancellation, TypeScript typecheck and extension build passed before commit.

### Live closed-loop trace and binding diagnostics

- Commit: `8605dec8e2f860a2e977b26b45b94411c3371aba`
  - Staged the self-removing live-validation instrumentation and binding contract regression.
- Commit: `21927bdc6b528a06018bad95e63540c9ce02d9fd`
  - Capture responses now carry canonical `revision` and `state_hash`; successful recommendations carry `state_revision`, `state_hash` and `battle_id`.
  - Extension stores a bounded 80-event metadata-only trace covering capture forwarding/result, planner requests/results, stale epoch discards and runtime-probe acknowledgements. Raw battle payloads, bearer tokens and full URLs are deliberately excluded.
  - Side panel exposes the latest trace for active-battle debugging;
  - Added `scripts/test_live_binding.py`, proving an OK recommendation is bound to the same daemon revision/hash as the observed demo state.
  - M01 status remains MOSTLY COMPLETE: live trace tooling is ready, but a real authenticated active-battle exercise and full runtime-object fallback remain required.
  - C++/CTest, pairing auth, stale cancellation, live binding, TypeScript typecheck and extension build passed before commit.

### Main-front live plumbing CI and report synchronization

- Commit: `a9be0434b940ef13220ed8f5628c4cddd47b07bd`
  - Added the local pairing/auth daemon integration test to the standard repository CI.
- Commit: `3850f1ccfc1283546e7c8ed0ec8d38f8dc31e3ec`
  - Added revision-bound stale-search cancellation integration to standard CI.
- Commit: `676da42b754ee9d1409cc27e8ad1dfec26d17e6c`
  - Added the live recommendation revision/hash binding contract to standard CI.
  - Workflow run `31365724181`: **PASS**.
  - Verified C++ configure/build/CTest, pairing/auth integration, stale-search cancellation integration, live recommendation binding, the full Python pytest suite, TypeScript typecheck and extension build.
- Commit: `d920ba47bf4e99832c377fe25467dee50f99235c`
  - Added `docs/LIVE_VALIDATION.md` with the active authenticated battle smoke gate, expected trace sequence, pass criteria, and evidence-driven runtime-fallback decision rule.
- Commit: `5af650101bedab884dddfbb9ffeeb48abe8f2283`
  - Added `docs/MAIN_FRONT_STATUS.md` to preserve the main-lane checkpoint while abilities continue independently on branch `ability`.
- Commit: `d77e25350464bc0d8d57e4793b11bfc21cb7cf8c`
  - Synchronized `TEST_REPORT.md` with the three mandatory closed-loop integration gates and current ability metrics.
- Commit: `6807a34dc4c7046db0ee5881a5383c93429eb43a`
  - Synchronized `IMPLEMENTATION_REPORT.md` with pairing, revision cancellation, live trace/binding, current ability risk and branch ownership.
- Commit: `499c9c8e20113aa5748f075e9a12dd6609c258fc`
  - Synchronized the duplicate implementation checkpoint `HeroesWM_Solver_Implementation_Report_0.3.0.md`.

### Authenticated local WebSocket revision stream

- Commit: `d05361f6b4bb80927ea82a0cca858b4d1ad4b403`
  - Staged the self-removing M16 WebSocket streaming patch and raw RFC6455 integration test.
- Commit: `68345f0afc89ed0e17884042592fb08b6edd83be`
  - Added RFC6455 `/ws` on the existing loopback daemon with SHA-1/WebSocket handshake and authenticated subprotocol `hwm-bearer.<token>`; the bearer is not placed in the URL.
  - Server pushes canonical `status` immediately and on every SessionStore revision change, plus a 20-second heartbeat for MV3 service-worker liveness.
  - Status now exposes `side_to_act` and `active_entity_uid` so the service worker schedules planning only for confirmed player decision states.
  - MV3 service worker reconnects the authenticated stream, stores the last daemon status, logs WS events in the bounded live trace and deduplicates replanning by canonical revision; capture remains passive HTTP and no extra HeroesWM traffic is introduced.
  - Side panel uses fresh streamed status for stale guards/diagnostics and falls back to HTTP `/status` only when streamed status is stale/unavailable.
  - Added `scripts/test_websocket_stream.py`: wrong bearer -> 401, valid RFC6455 accept verified, initial revision frame received, debug state publication produces pushed newer revision/hash.
  - M16 is now COMPLETE FOR CURRENT LOCAL API; Phase 2 remains MOSTLY COMPLETE until a real active authenticated browser battle is exercised.
  - C++/CTest, pairing, stale cancellation, live binding, WebSocket integration, TypeScript typecheck and extension build passed before commit.

### Main-front checkpoint handoff

- Commit: `68345f0afc89ed0e17884042592fb08b6edd83be`
  - Completed authenticated loopback WebSocket revision/status streaming and extension push-driven replanning.
- Commit: `7353e1ddcf17f27e981cac52f2b1e38f5545881e`
  - Standard CI now includes WebSocket streaming and current-MSVC Windows runtime gates.
  - Workflow run `31367488977`: **PASS** on Linux and Windows. Linux passed C++/CTest, all four daemon integrations, Python 42/42, TypeScript typecheck and extension build. Windows passed MSVC C++ build/CTest plus pairing/auth, stale cancellation, live binding and WebSocket integrations.
- Commit: `144d958fd4c8e87c6fd4ec538a4cbacc007098b7`
  - Updated the active general specification (`SPEC.md` and duplicate checkpoint), `TEST_REPORT.md`, and `docs/MAIN_FRONT_STATUS.md` with the current main-front state.
  - Explicit next M13 correctness gate: stochastic action outcomes must be separated by `state_hash` before transposition/persistent tree reuse; do not keep different sampled outcomes under a single first-initialized `Edge.child`.
  - Real authenticated active-battle smoke validation remains the immediate product gate before claiming live Browser Bridge/Orchestrator complete.

### M13 stochastic chance-outcome correctness and transpositions

- Commit: `d06217fd4aa531aa0e49cf7c8c2495a5ab0ca5e4`
  - Replaced the historical single `Edge.child` with per-action outcome bindings keyed by canonical `state_hash`, so different sampled damage/proc outcomes no longer share the first outcome's legal-action node.
  - Added a per-search transposition graph: equal canonical hashes reuse the same search node across actions/outcomes.
  - Principal variation now follows the most-visited sampled outcome for each action instead of an arbitrary first child.
  - Added a separate main-owned `hwm-planner-tests` CTest target proving two different outcome hashes keep different nodes/legal-action sets and the same hash reuses one node.
  - `cpp/tests/test_main.cpp` was deliberately left untouched because it is owned by the parallel `ability` lane.
  - Standard CI result for this functional tree has not yet been recorded; do not treat this entry as a CI-pass claim.

### M13 persistent exact tree re-root

- Commit: `135826c05d7f9b3d44e165ef6732bb6ede89a4c4`
  - Made the planner graph persistent across recommendation calls and re-rooted only when the newly observed canonical `state_hash` already exists in the same battle/perspective search graph.
  - Reused roots retain accumulated visits/statistics and prune unreachable old branches; unmatched observed states start a fresh graph rather than using approximate state matching.
  - Moved the daemon to one persistent, mutex-protected Planner instance while preserving revision-bound cooperative cancellation through a request-specific callback.
  - Added `/recommend` diagnostics: `tree_reused`, `reused_root_visits`, and `retained_nodes`.
  - Extended the dedicated main-owned planner regression with exact reuse, pruning, and battle-scope reset checks.

### WebSocket integration harness frame buffering

- Commit: `33aaea0cac7549972e4be93bf495d0a9dca7f301`
  - Fixed the raw RFC6455 regression client to preserve bytes received after the HTTP handshake delimiter instead of decoding a coalesced first WebSocket frame as UTF-8 headers.
  - The server protocol was not relaxed; the test now correctly handles normal TCP packet coalescing.
  - Final M13 verification run `31380236279` confirms the WebSocket streaming gate passes with this fix.

### M13 persistent-reuse structural safety guard

- Commit: `6edec4d8360169060d280cd07a6e63de9c0fda89`
  - Added a conservative search-structure fingerprint for board bounds/blocked cells and static entity geometry/capability fields that are not currently part of the global `state_hash`.
  - Persistent tree reuse now additionally requires the same non-empty battle id, perspective and structure fingerprint; otherwise the graph resets.
  - Regression proves a legal-action-relevant `is_flyer` change that currently collides in `state_hash` does not reuse the old tree.
  - Standard pull-request CI run `31380236279`: **PASS**. Linux passed C++ build, CTest 2/2, pairing/auth, stale cancellation, live binding, WebSocket streaming, full Python tests, TypeScript typecheck and extension build. Windows current-MSVC build/test job passed.

### Decoder geometry evidence audit

- Commit: `088df7346260a16cc086f59724157274b6d178de`
  - Added `scripts/decoder_geometry_audit.py`, a reproducible read-only corpus audit for decoder/legal geometry without changing ability-owned protocol/replay implementation.
  - Stored `data/reports/decoder-geometry-audit.json` from all 866 battles / 52,375 decisions.
  - Reproduces held-out basic-action coverage **5373/5481 = 98.03%** with failures 60 melee-destination, 45 target-adjacency, and 3 MOVE.
  - Finds **145** raw melee destinations intersecting a live stack in `state_before`, **141** involving a non-target stack.
  - Of 105 held-out failed melee rows, **64** have a legal landing for the current decoded target and **69** have one when all actor-originated DAMAGE targets are considered; 5 specifically require an alternate DAMAGE target by the conservative existence test.
  - Python replay final overlap remains **21 battles / 23 pairs**; the separate authoritative C++ corpus gate remains 19 invalid finals / 21 overlap pairs.
  - Diagnostic workflow job `93438285778`: **PASS**.

### M11 multi-step damage-residual ensemble gate

- Commit: `45581ae7d0f844f67797c590c3ed529390b76f1f`
  - Added `python/hwm_solver/evaluation/dynamics_multistep.py` and targeted tests for a five-member train-battle jackknife ensemble over the existing primary physical-damage residual.
  - Added autoregressive held-out evaluation at 2/4/8/16 halfturn horizons. Non-primary mechanics remain teacher-forced so the gate isolates primary physical-damage residual drift rather than attributing proc/collateral/resurrection errors to this submodel.
  - Predicted-invalid actions are preserved as divergence instead of silently teacher-forcing the observed primary damage after model drift makes the real action impossible.
  - Stored `data/reports/dynamics-multistep-damage.json` from 692 train / 174 chronological held-out battles and 23,451 train attack samples.
  - Ensemble mean force-L1 beats the generic exact-formula baseline at every measured horizon: 2-step **0.01137 vs 0.01679**, 4-step **0.01791 vs 0.02728**, 8-step **0.02986 vs 0.04710**, 16-step **0.04947 vs 0.08125**.
  - Production enablement remains intentionally **false**: at 16 steps the ensemble predicted-invalid-action fraction is **3.58%** vs **2.51%** generic and alive mismatch is **8.83%**. This closes the first M11 submodel multi-step evidence gate, not the full learned world-model requirement.
  - M11 diagnostic run `31384739406`: **PASS** with targeted tests **5/5**. Full standard CI run `31384739323`: **PASS** on Linux and Windows/MSVC.

### M11 dynamics uncertainty calibration

- Commit: `ef35d28aca6a044019896e3ecf6c4d4b52113d6f`
  - Added held-out calibration of the five-member damage-residual ensemble disagreement against absolute force error, learned-vs-generic excess error and invalid-action drift at 2/4/8/16 halfturn horizons.
  - Added tie-safe Spearman/AUC utilities, decile calibration tables and five targeted tests.
  - Disagreement tracks absolute ensemble error at every horizon (Spearman **0.589 / 0.659 / 0.666 / 0.630**), so it is a useful epistemic-drift indicator.
  - However, disagreement does **not** identify windows where learned dynamics underperform generic: AUC is **0.472 / 0.431 / 0.390 / 0.318**, and disagreement is negatively correlated with learned-minus-generic excess L1.
  - Therefore a naive high-disagreement fallback to generic is explicitly rejected and production uncertainty gating remains disabled.
  - Stored compact evidence at `data/reports/dynamics-uncertainty-calibration.json`; the CLI emits full ten-bin calibration tables.
  - Full-corpus calibration run `31385464567` and standard Linux/Windows CI run `31385464568`: **PASS**; targeted calibration tests **5/5**.

### M11 calibrated fallback-selector gate

- Commit: `7c5a4634da26b99ee5b74f824f98fe5dcce4dc5b`
  - Added a strict chronological **64% fit / 16% calibration / 20% final-test** fallback-selector experiment for the five-member primary physical-damage residual ensemble.
  - Selector features are pre-transition only: creature/action train support, relative ensemble disagreement, residual-correction magnitude/sign, generic lethality ratio and ranged/melee indicator.
  - Calibration chose threshold `0.5365`, using generic on about 16% of modeled attacks. On the untouched one-step final test, selector abs-log error is **0.38571**, slightly better than ensemble **0.38658** and generic **0.47968**; learned-worse AUC is **0.6020**.
  - The **multi-step gate fails**: selector is slightly worse than pure ensemble mean-force-L1 at every 2/4/8/16 horizon and still exceeds generic invalid-action rate. At 16 steps: selector **0.05205 L1 / 3.24% invalid**, ensemble **0.05172 / 3.40%**, generic **0.08125 / 2.51%**.
  - Runtime selector remains disabled. The experiment demonstrates that one-step fallback classification does not resolve the long-horizon accuracy/validity trade-off.
  - Stored `data/reports/dynamics-selector-gate.json`. Diagnostic run `31386006048` and full standard CI run `31386005987`: **PASS**; targeted selector tests **4/4**.

### Held-out 120-state planner recommendation validity gate

- Commit: `cde38a5a89684ff2691c80eeb3583195ffa31758`
  - Strengthened `planner-eval` from the historical first-N/status-only probe to a deterministic stratified sample across all chronological held-out safe states.
  - Recommendation validity now checks exact canonical `state_hash`, legal best action, legal alternatives, finite score/P(win)/uncertainty, visited candidates, positive simulations and search nodes.
  - Added permanent `scripts/test_planner_replay_gate.py` and wired a **120-state** held-out gate into standard Linux CI.
  - Permanent CI budget `1 -> 120` passes **120/120** recommendations sampled from **109** held-out battles with **0** invalid recommendations, hash mismatches, illegal best actions, illegal alternatives or non-finite metrics.
  - A stronger `80 -> 300` stress reference also passes **120/120**, with action-type stability **98.33%** and exact-action stability **85%**.
  - Stored `data/reports/planner-replay-validity-gate.json`. Diagnostic runs `31387183686` (permanent budget) and `31386809158` (stress) passed; standard CI run `31387423155` passed on Linux and Windows/MSVC with the permanent gate enabled.
  - This closes the replay half of the >=100-state invalid-recommendation acceptance gate; real authenticated active-battle smoke remains separately required.

### M11 stochastic survival-distribution gate

- Commit: `70c7b3a61058ca9e3cfc883cb826ac2b1ef15f4b`
  - Added a distributional held-out survival gate aligned with the C++ simulator's stochastic physical-damage roll instead of treating deterministic expected damage as the only rollout outcome.
  - Uses three midpoint-stratified quantile starts rotated by a deterministic golden-ratio shift on subsequent actions; five train-battle jackknife residual members yield 15 learned trajectories versus 3 generic trajectories.
  - On 692 train / 174 chronological held-out battles, learned mean force-L1 still beats generic at 2/4/8/16 steps: **0.01149/0.01842/0.03018/0.05028** vs **0.01697/0.02808/0.04732/0.08178**.
  - The survival/validity trade-off remains real but is smaller than the earlier deterministic member-count diagnostic: learned valid-observed-action coverage is **98.789% / 98.284% / 97.551% / 96.349%** vs generic **98.919% / 98.655% / 98.324% / 97.493%**.
  - Therefore the residual ensemble remains evidence-only and production enablement stays false; the next calibration experiment targets positive log-residual corrections rather than generic uncertainty fallback.
  - Full distributional workflow run `31389946209`: **PASS**, targeted tests **4/4**. Nearest full standard CI run `31389813735`: **PASS** Linux + Windows/MSVC before the final roll-decorrelation-only patch; exact final Windows standard job and exact Linux distributional evaluator path also passed before subsequent hosted jobs stopped reaching the `Set up job` step.

### M13 scheduler-recency hash completeness

- Commit: `56190d72d133d325cf5a71f369339b82ba2f3aa1`
  - Added `Entity.last_acted_seq` to canonical `state_hash`. `NextActorModel` uses `decision_seq + 1 - last_acted_seq` as a recency feature, so omitting it allowed transition-semantically different states to collide in the M13 transposition table.
  - Extended the dedicated planner regression: two otherwise identical states with different activation histories must have different hashes and distinct `SearchGraph` nodes.
  - Verified statically that both observed `TURN_START` decoding and simulator rollout assign `last_acted_seq` before incrementing `decision_seq`, so the new hash component uses the same counter convention on predicted and observed states.
  - Follow-up Markov-state audit found policy-prior/value-model dynamic inputs already represented in the hash; static board/entity capability fields remain protected by the existing persistent-search structure fingerprint.
  - Draft PR #4 standard CI run `31393097068` did **not execute code**: both hosted jobs completed before `Set up job` with no step list. This entry therefore makes no CI-pass claim; the correctness regression is committed and awaits an executable hosted/local CI run.

### M13 effect provenance hash canonicalization

- Commit: `5d31dfbd6cebb04716d76ba62698876a7ddb259f`
  - Removed `Effect.raw` from canonical `state_hash` while preserving effect id, duration, magnitude and current vector order.
  - `Effect.raw` is provenance only: observed decoder stores the server wire text, while speculative simulator transitions write descriptive strings such as `modeled ...`; transition logic consumes effect id/duration/magnitude rather than that text.
  - This prevents false exact-re-root/transposition misses when an observed status and its correctly modeled status have identical semantics but different provenance strings.
  - Extended the dedicated planner regression: equal semantic effects with different raw provenance must share a hash/SearchGraph node; changing duration must still split the hash.
  - Hosted CI was still not executing job steps at integration time, so this entry makes no CTest/CI-pass claim. The change is deliberately limited to provenance canonicalization and awaits the next executable standard CI run.

### Windows-only self-hosted CI migration

- Commit: `31c25740d4f6cbf27d802ad4e478993b7571f54f`
  - Replaced the previous Linux-full + Windows-partial CI matrix with one Windows self-hosted job and moved every standard gate onto Windows/MSVC.
  - Preserved C++/CTest, the 120-state planner replay validity gate, all four daemon integration tests, Python pytest, TypeScript typecheck and extension build.
  - Added same-branch stale-run cancellation and protection against running external-fork pull requests on the self-hosted machine.
- Commit: `6bd81ce9fabc6fa29fb0e3f9694c988ea69e7b8c`
  - Finalized runner routing to `[self-hosted, windows, x64, hwm-windows]` and added `workflow_dispatch` for manual current-HEAD validation after runner downtime.
- Commit: `09237be777671fa3697da05b1813b57e5fc19f78`
  - Declared Windows 10/11 x64 the sole supported product/CI platform in README and converted active build/evaluation examples to PowerShell/Windows paths.
- Commit: `0118f0586765962a987e5d50794319815b509763`
  - Synchronized the main-front status, moved the permanent planner replay gate to the Windows CI contract, and marked prior Linux CI results as historical evidence only.
- Commits: `4fa95fd07e7dc3faafb0ac19de71a4327c1aa2bd`, `53087329f842dc19a5de3806f458959d6e9c6d6c`, `99423460e859bb22fb01210ae07d165d17e910f0`, `df64b32cee8f7b77e5c48b5f7e1e0dc67d37bb48`
  - Removed the unsupported Linux bootstrap, validation, daemon-launch and demo-launch entry points. Windows scripts are the only supported product tooling path.
- Commits: `d746c4de9a8d6cb951a697774e1b4bfce3c68469`, `db5f029239ff2b3484b3c826577930d5418a4b20`
  - Removed the VS Code bash validation fallback and Linux/WSL debugger configuration; VS Code development tasks now target Windows/MSVC only.
- Commit: `1fe72e59cb10dfc1a40b0d53dcfa058a21385f75`
  - Stabilized the standard self-hosted Windows CI around service-owned uv/Python 3.13, Windows PowerShell with execution-policy bypass, system Node/CMake discovery, and the Visual Studio 2022 generator.
- Workflow repair commit: `3dc09576ce09996a1680bec86e3f79d0454a9591`
  - Fixed invalid YAML in this changelog workflow by removing the unindented PowerShell here-string and using a YAML-safe line array; also removed the unavailable `pwsh` dependency.
- Real Windows runner execution is required for PASS claims; historical hosted-runner results remain evidence only.


### Exhaustive Windows main-front validation and M11 uncertainty reproducibility

- Commit: `8dc9dc5b81db936089c7764fafb9c22cb79505a3`
  - Stabilized M11 uncertainty calibration with deterministic summation/member moments, sorted UID aggregation, and an explicit `1e-12` numerical-tie threshold so mathematically equal learned/generic windows are not classified by floating-point noise.
  - Added regressions for identical-member zero disagreement and sub-epsilon learned/generic ties; refreshed the compact uncertainty evidence from the final committed evaluator.
  - Dedicated Windows self-hosted run `31419316512`: 7/7 targeted tests PASS; two independent full-corpus uncertainty processes produced exactly identical JSON.
  - Production uncertainty fallback remains disabled: disagreement tracks absolute error but still does not identify learned-vs-generic underperformance reliably at every horizon.
- Commit: `bb8404606621966d8c688f22e93c6ce35dd695ea`
  - Kept permanent main-front CTest focused on `hwm-planner-tests` by excluding the independently owned `hwm-tests` executable; ability validation remains responsible for that executable and its MSVC failures.
- Exhaustive main-front validation run `31417309122` (temporary PR #5 harness): Debug MSVC build and `hwm-planner-tests` PASS; 120/120 held-out planner states valid with 0 invalid recommendations; all four daemon integrations PASS; Python 61/61 PASS; TypeScript/extension PASS; Release MSVC/CTest and `planner-demo 5000` PASS; all four M11 full-corpus evaluator commands PASS.
  - The ability-owned monolithic `hwm-tests` executable is intentionally excluded from the main-front PASS claim after exposing three independent ability-lane defects on MSVC: Mighty Slam test pointer invalidation after `vector::push_back`, a `frightful_aura`/`frightfulaura` test-code typo, and a subsequent `0xc0000409` hard termination. These remain for the ability branch validation pass.


### Windows CI normalization and branch cleanup

- Commit: `681b7f52d058773276967bad56c9d2163c89cd8a`
  - Centralized permanent Windows Core/Full validation in `scripts/ci_windows.ps1` rather than workflow-embedded bootstrap/test logic.
- Commit: `87b5bf03c2a4ac160ceccadb674416cb9b2d56a6`
  - Added canonical M11 evidence verification as normal Python code.
- Commit: `5f4d8311854d92efce8fcf71b9cc014effac4edd`
  - Added regression coverage that parses GitHub Actions YAML and enforces the Windows-only runner contract.
- Commit: `34fc8c5d2e295a85da26afaa7e76296c2f348d73`
  - Split CI into independent `Core` and `Full` Windows jobs so two matching runners can execute them concurrently.
- Commit: `99cd646bbc5c2a6a2c6d8d0aa90e530e98bc3230`
  - Aligned local Windows validation with the same Core/Full suites.
- Commit: `29bfe624852411d464a5c5d48e129d65dd506bed`
  - Preserved the recommendation-explanation integration contract before deleting the temporary diagnostics branch.
- Commits: `5bbfa3e5bd9e6a0f37aa0b7d73c4a3f5b77e87bb`, `767b842a6793f8da071637c6a45c1b21d7730936`
  - Preserved the M11 positive-residual temperature calibration experiment and unit tests; the unstable hard-PvE sampler was intentionally discarded.
- Commit: `8878d1da44aa74f6ad346afbd9bc81ca5c174665`
  - Added M11 temperature calibration to the permanent Full suite.
- Commit: `510b49931c87606522da17f13e3f1cff7b35579b`
  - Bounded OpenMP/MKL/OpenBLAS/NumExpr to two threads per job for safe two-runner concurrency on one Windows PC.
- Commit: `6f4c61d99eb7f06cfdb140a74d72a8bf5e978b79`
  - Locked the permanent Core/Full test inventory with regression coverage.
- Commit: `2c65ac15534ec3b648b3675f80388ae35d172a27`
  - Hardened service execution with explicit venv `python.exe`, `npm.cmd`, `cmake.exe`, and `ctest.exe` invocation.
- Commit: `6fe428fe25f4a3e4103620464f144ec21e7ab7b5`
  - Updated the CI contract regression for the explicit Windows executable paths.
- Commit: `151d568ee34a6fbf234d063a6c645d1341cebd9a`
  - Removed the redundant bootstrap helper after consolidation on `scripts/ci_windows.ps1`.
- Commit: `550f12f56d22e660c2a928a119e194fc44da65a6`
  - Updated README to document service-owned Python, Visual Studio generator, canonical Core/Full commands, two-runner parallelism, and the rule that new main-front tests belong in the permanent suites rather than temporary workflows.
- Repository branch cleanup completed: only `main` and `ability` remain.


### Final Windows self-hosted CI hardening and verification

- Commits: `3a7032c31f8b2dc81dd4f2cc420bf0eff5d12a75`, `e965f8f2ee3c021e3aa0ca09311de0019baa1db3`, `6660c994be4be4ee1c83f89945c78bcd46b36051`, `eef4c3da7d1fcd383f442293b2e60bb411577c8a`, `fc3e155c3290acafc7ce94a567b2eb077b0a5352`
  - Hardened all daemon integration tests for Windows service execution: loopback HTTP bypasses inherited proxy settings, ports are allocated dynamically, startup is bounded, and failures include daemon output.
- Commits: `514baa6b51a5e3229e3e271af00fa6ac2244144f`, `18e8d27cd047355cbb8338ffb0d85f9b1708d9a1`
  - Added canonical `HWM / Core` and `HWM / Full` pending/final commit statuses linked to the exact Actions run, making current-main CI observable through the GitHub API.
- Commit: `75abd0c68ebf8945d3da883bb8e8461ae623813e`
  - Fixed Windows PowerShell variable interpolation in the centralized CI script after executable run `31425282849` exposed the parser defect.
- Run `31425405632`: Core + Full PASS on the same main tree; 120/120 planner validity, all daemon integrations, Python 74/74, TypeScript/extension, Release planner/M11/evidence/temperature commands all completed successfully.
- Commit: `aa2408c159e82f8f8afa204aa7dd89981698047b`
  - Added a stable Windows PowerShell AST syntax-preflight entrypoint before bootstrap/build.
- Commit: `18af31955bd100c85a08f4d5f0e9ff647db98e75`
  - Replaced post-build fail-fast validation with independent gate execution and a final aggregated failure summary, so one failed test no longer hides the remaining gates.
- Commit: `15a5930a85c86f27238b9aa5064d2a0b406fdeea`
  - Routed local Windows validation through the same preflight/Core/Full entrypoint used by the self-hosted runners.
- Commit: `e56cf0f0fe8a767608f9b42dd9529df7ee60a4f0`
  - Locked workflow YAML parsing, Windows runner labels, syntax preflight, aggregate-gate behavior, and the permanent Core/Full inventory with Python regressions.
- Commit: `0a70948a3a66a5492a3fa79b7f5ca154f9881c4d`
  - Moved the permanent workflow to `actions/checkout@v6` and the stable preflight entrypoint.
- Commit: `da80a0aa853942d0585820022c92046f9e058d5c`
  - Fixed Windows PowerShell 5.1 empty typed-collection binding in the aggregate failure accumulator after run `31427555018` exposed it.
- Commit: `8778930993452f94fb4054aaf9f241e9c6abdc67`
  - Added regression coverage requiring the empty failure accumulator to remain accepted.
- Final functional-tree run `31427798132`: **Core PASS + Full PASS** on the same main commit.
  - Core: PowerShell syntax preflight PASS; MSVC Debug build; main-front CTest; 120/120 planner recommendations valid across 109 held-out battles; pairing/auth, stale-cancellation, live-binding and WebSocket integrations PASS; Python **75/75** PASS; npm/typecheck/extension build PASS.
  - Full: PowerShell syntax preflight PASS; MSVC Release build/CTest; planner benchmark; M11 multistep, uncertainty, selector, stochastic-survival, canonical evidence verification and positive-residual temperature calibration commands all PASS.
  - The M11 temperature experiment remains diagnostic-only: no production dynamics/selector/uncertainty enablement is implied by command success.
  - Ability-owned `hwm-tests` remains intentionally outside main-front CI and will be validated separately on branch `ability`.
  - Real authenticated active HeroesWM battle smoke remains the outstanding live product gate.

