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
  - Runtime boundary remains unresolved: generic replay still leaves the carrier alive after `Sbom`, and predictive Earth/collateral magnitude is not inferred from one activation.

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

### Gribbomb generated registry/report synchronization

- Commit: `c24cacf060182494092ef3e460301844639388e6` — `chore(ability): regenerate ability registry artifacts`.
  - Regenerated `data/catalog/ability_registry.json` and `.csv` from the current source-of-truth builder and tracked inputs instead of hand-editing snapshots.
  - The deterministic output incorporated the already validated Gribbomb `partial_exact` promotion and also corrected the previously stale checked Crippling Wound classification.
  - Checked registry support totals became `partial_exact = 20` and `unresolved = 77`.

- Commit: `eaca45fc3de060b030ee912c38efea234aa00c1f` — `chore(ability): regenerate current ability reports`.
  - Regenerated `data/reports/ability-registry-current.json` and `data/reports/ability-risk-current.json` from the synchronized registry.
  - Current held-out ability-risk mean improved from `0.22431` to `0.21744`; p90 improved from `0.37538` to `0.36755`.
  - Stale unresolved Gribbomb risk disappeared from the unfinished top-risk slice; Crippling Wound is represented as `partial_exact` with canonical risk `0.25`.
  - Authoritative hosted Windows run `31631708571` on exact SHA `eaca45fc...`: workflow **PASS / conclusion `success`**. All real atomic test/build/inventory jobs succeeded; the final `publish_status` job was skipped by its workflow condition.
  - Repository-consistency conclusion: builder, checked registry, and current report artifacts now agree. Gribbomb is closed at `partial_exact`; predictive Earth/collateral magnitude remains explicitly unresolved and disabled rather than guessed.

### Next weighted ability after Gribbomb closure

- Recomputed from the synchronized current risk report: Taunt is the highest-priority currently actionable unfinished ability after excluding already documented semantic/substrate blockers.
- Reuse the existing Taunt evidence auditor. Its current regression is only a smoke gate and must be strengthened to exact corpus counts and raw contexts before any semantic promotion.
- A final attack landing on a Taunt carrier is not itself a proc discriminator. Do not infer an original intended target from the damage destination; require carrier-specific raw evidence before claiming redirect behavior or probability.

### Taunt strict redirect-evidence boundary

- Commit: `e7dffd54b1777766e4916f7b6f5f548e25e2cfab` — `test(ability): pin Taunt redirect evidence boundary`.
  - Replaced the old smoke-only Taunt regression with exact whole-corpus gates and explicit target-source special-code contexts.
  - Pinned 866 battle directories, 24 Taunt carrier battles, 25 carrier entities, 24/24 identical Taunt tooltip descriptions, 712 attacks in carrier battles, 169 carrier-plus-adjacent-ally opportunity states, 78 attacks ending on carriers, 31 carrier-target attacks with an adjacent ally, and 37 attacks ending on an adjacent ally.
  - The tooltip states only a chance to redirect an attack aimed at a neighboring friendly unit; it provides no numeric probability.
  - `ra2`/`ral` occur as target-source reactions in both carrier-target and adjacent-ally control contexts, so they are not accepted as a Taunt proc discriminator. Final DAMAGE destination is likewise not used to infer the attacker's original intended target.
  - Hosted Windows run `31639091346`: **FAIL** only in the new negative-control node because two handwritten expected control counts were wrong (`ra2` adjacent-ally `19` vs observed `18`; `ral` adjacent-ally `13` vs observed `9`). The corpus/tooltip/geometry gate itself passed.

- Commit: `7f143d9050d42a20300be3a54511cdae16682f0e` — `fix(ability): correct Taunt reaction control counts`.
  - Corrected only those two expected target-source control counts (`ra2 19 -> 18`, `ral 13 -> 9`); no Taunt semantic, corpus, geometry, or negative-discriminator gate was weakened.
  - Authoritative hosted Windows run `31639884205` on branch `ability`: **PASS / conclusion `success`** on the exact functional SHA.
  - Validated Taunt ceiling: exact evidence now pins the server tooltip, neighboring-friendly geometry, opportunity counts, and absence of a usable raw redirect-proc label in the observed corpus. A numeric redirect probability and per-attack proc outcome remain unobservable from current evidence.
  - No runtime or registry promotion is made. Taunt remains `unresolved` as predictive/search semantics and is closed for this pass as a precise evidence blocker rather than being modeled from final-target heuristics.

## 2026-08-13

### Spider / `Sent` wire attribution — corpus-wide negative control

- Commit: `2596f59a065604dd5a525d19969712cebbd9c3eb` — `test(ability): audit Spider Sent wire attribution`.
  - Added a whole-corpus `Sent`/`ent` wire auditor plus an atomic Windows pytest node without changing replay/runtime or registry semantics.
  - Authoritative hosted Ability Windows CI run `31644823929`: **PASS / check-suite conclusion `success`** on the exact functional SHA. The Spider wire node `94276046646` passed on the hosted Windows runner.
  - Corpus scope is exactly 866 battle directories, 182 battles containing `ent`, and 806 raw `Sent` records. Every observed payload has the exact structural shape `Sent + 15 decimal digits`; all 806 split as `source3 + target3 + 000000000`, and the target candidate exists in replay state both before and after the record.
  - Current parser behavior is now pinned: first UID is decoded as actor for 806/806 records, while `target_uid` remains `None` for 806/806 records.
  - Spider is fully confounded with Entroots at carrier level: all 89 initial Spider carriers also declare `entroots`, and zero Spider carriers without `entroots` exist in this corpus.
  - Decisive negative control: among 491 nonzero-source `Sent` records, 405 are sourced by entities with `entroots` **without** `spider`, while only 84 are sourced by entities carrying both; therefore raw `Sent` is **not Spider-specific**.
  - Two additional nonzero sources carry `alive,netshooter,nopenalty,rangepenalty,shooter` with neither `spider` nor `entroots`, so the raw `ent` code is not promoted to an Entroots-exclusive semantic label either. It is treated only as a shared immobilization/entangle wire substrate until further evidence.
  - Zero-source records total 315 and retain a target UID; they are evidence for lifecycle/clear-style wire behavior, not a second Spider mechanic.
  - Runtime/registry boundary: **no Spider runtime effect or registry promotion is created.** The next safe step is to lock these exact corpus counts as protocol tests, then separately consider structural `ent` target decoding without assigning ability ownership.

### Spider / `Sent` exact corpus contract

- Commit: `1744354e79713569f7598e424f890801db88c8d5` — `test(ability): pin Spider Sent wire corpus`.
  - Replaced exploratory lower-bound assertions with exact corpus cardinalities and exact source/target controls: 866 battle dirs, 89 initial Spider carriers, 182 `ent` battles, 806 `Sent` records, payload length/trailer invariants, 315 zero-source records, 491 nonzero-source records, and exact `405 / 84 / 2` source-class split.
  - Pinned exact Spider/source ability sets and required the second UID to remain nonzero and present in replay state before/after for 806/806 records.
  - The parser gap remains explicit and intentional in this package: first UID maps to actor for 806/806, while `target_uid` remains absent for 806/806. No parser/runtime/registry semantic was changed.
  - Authoritative hosted Ability Windows CI run `31645840641`: **PASS / combined status `HWM / Ability = success`** on the exact functional SHA.
  - Validated ceiling is unchanged but now corpus-locked: `Sent` is not Spider-specific and is not safely Entroots-exclusive because of the two Netshooter controls. No second Spider runtime effect and no Spider registry promotion are justified.
  - Spider is closed for this evidence pass at a precise protocol blocker. Structural decoding of the second UID may be pursued only as a separate protocol-level package with its own negative controls and Windows validation, independently of ability ownership.

### Child of the Light spellbook-school probe

- Commit: `58965925cfe09552e9e5a4e22ff3d2cae86cbd69` — `test(ability): audit Child of Light spell wire`.
  - Replaced the old Child smoke gate with exact known corpus assertions and added a server-spellbook/status-wire discriminator, without touching replay/runtime/registry semantics.
  - Hosted Ability Windows run `31647277552`: **FAIL** in the Child atomic node because the exploratory assumption that the raw seven-token spellbook school field was literally `light` was false: the corpus contained zero such spellbook actors/entries.
  - The failure was treated as protocol evidence rather than worked around by hardcoding a Light spell list or weakening the assertion.

- Commit: `87c661aadcbcfd1b9ffd750aef20c6e9418e4c89` — `test(ability): inventory Child of Light spellbook schools`.
  - Added a raw school-token inventory and explicitly pinned the previous literal-`light` assumption as false.
  - Authoritative hosted Ability Windows run `31647544114`: **PASS**; check-suite `85854980801` completed with conclusion `success` on the exact SHA.
  - Exact Child baseline is now pinned: 866 battle dirs, 108 carrier battles, 137 carriers, one 121-battle tooltip statement, 5634 decisions in carrier battles and 206 carrier-targeted SPECIAL records.
  - Raw spellbook inventory in carrier battles is exactly 651 actors / 2031 entries with school tokens `neutral 1405`, `air 275`, `earth 144`, `cold 141`, `other 31`, `fire 18`, `nt 17`; there is no `light` token.
  - The `neutral` bucket mixes `fast/bless/righteous_might/stoneskin` with `slow/curse/confusion/suffering`, plus `raisedead`; `nt` also mixes harmful statuses with `resurrection2`. Therefore the raw school field cannot safely identify game Light-school status spells.
  - Status-wire controls currently comprise 158 source+code groups hitting Child carriers, 146 with positive effective cost and 12 zero-cost follow-ups; all positive-cost groups have a source spellbook. Direct-damage controls are exactly three records (`ltn 2`, `mfs 1`).
  - No Child runtime copy rule or registry promotion is made. The next evidence layer is independent decoded `bm_tooltips`/server metadata for per-spell school identity; absent such metadata, Child closes for this pass at that precise blocker rather than from a guessed spell taxonomy.

### Child of the Light decoded tooltip metadata blocker

- Commit: `7d63aad9ae992cd9b949da43a7ec42a82f627a7d` — `test(ability): audit Child tooltip spell metadata`.
  - Added a generic decoded `bm_tooltips` inventory and strict-pinned the already validated Child school/status-wire counts; no runtime/registry semantics changed.
  - Authoritative hosted Ability Windows run `31648327688`: **PASS**; check-suite `85857041871` completed with conclusion `success` on the exact SHA, including the Child atomic node `94287152093`.
  - In all 108 Child carrier battles, decoded `bm_tooltips` exposes exactly three top-level dictionary sections: `abil_names`, `abil_desc`, and `perk_hints`.
  - Exact key overlap between any of those three tooltip maps and the same battle's raw server spellbook spell names is zero.
  - The only Light/school wording is the Child ability description itself: `child_light_text_hits = 108`, `non_child_light_text_hits = 0`, `non_child_school_light_hits = 0`.
  - Thus decoded tooltip metadata provides no independent per-spell Light-school identity to resolve the raw `neutral`/`nt` collapse. No Child runtime copy rule, registry promotion, hardcoded spell taxonomy, or inferred probability is justified.
  - One final strict regression package should pin these exact zero-overlap/zero-independent-Light cardinalities, after which Child can be closed for this pass at this precise evidence blocker.

### Child of the Light strict metadata closure and correction

- Commit: `c5a2acaded82d36e5c32b6af9833554a44c60ce2` — `test(ability): lock Child tooltip metadata blocker`.
  - Converted the final decoded-tooltip observations into strict assertions in the existing atomic Child node, without changing replay/runtime/registry semantics.
  - Authoritative hosted Ability Windows run `31679297822`: **PASS / completed with conclusion `success`** on the exact functional SHA; check-suite `85938145984` also belongs to that exact SHA.
  - Strictly pinned `bm_tooltips` structure: all 108 carrier battles expose only `abil_desc`, `abil_names`, and `perk_hints` dictionaries; exact mapping-key overlap with same-battle spellbook names is zero (`mapping_spellbook_overlap_counts = {}`, `overlap_spell_names = {}`, `overlap_examples = []`).
  - Correction to the previous `7d63aad9...` bookkeeping wording: there are **92 non-Child text hits mentioning Light**, not zero. The decisive zero is narrower and independent: `non_child_school_light_hits = 0`. The strict gate also pins `child_light_text_hits = 216` and `school_text_hits = 112`.
  - Therefore the corpus contains Light-related ability/perk prose, but no server metadata that simultaneously identifies a concrete spell and independently classifies it as Light. The raw spellbook still collapses relevant statuses into `neutral`/`nt`.
  - Child of the Light is closed for this evidence pass as **`unresolved` with a precise missing per-spell school discriminator**. No runtime copy rule, registry promotion, hardcoded Light spell list, or numeric probability is introduced.
  - The weighted unfinished queue now advances to `hexingattack`; any Hexing proc attribution must first pass whole-corpus source/collision controls, and its tooltip's non-numeric “some probability” wording is not a probability constant.

### Hexing Attack baseline and whole-corpus wire audit

- Commit: `a2c06ef10048486cc84239b045f3710e9f7db795` — `test(ability): pin Hexing baseline and wire audit`.
  - Hardened the existing Hexing smoke test into exact baseline assertions and added `python/hwm_solver/ability/hexingattack_wire_evidence.py`, a whole-corpus collision/layout auditor for raw candidate codes `crs`, `slw`, `sff`, and `ray`.
  - Exact baseline now pins 866 battle dirs, 32 carrier battles, 88 carriers, creature IDs `333 = 41`, `269 = 27`, `268 = 20`, exact carrier ability sets, 115 carrier attacks (all `MELEE_ATTACK`), and 12 parsed zero-cost same-actor/same-target status records: `sff = 5`, `crs = 4`, `slw = 3`.
  - Raw Hexing attack windows also contain exactly 3 `Sray...` records that generic parser still leaves outside status grammar; this package intentionally does **not** identify `ray` as Disrupting Ray from its mnemonic.
  - The tooltip lists Curse, Slow, Weakness, and Disrupting Ray at expert level but provides only “some probability”; it has no numeric percentage/probability constant.
  - Authoritative hosted Ability Windows run `31680364027`: **PASS / completed with conclusion `success`** on exact functional SHA `a2c06ef...`; check-suite `85941007397`.
  - Semantic boundary remains evidence-only: `ray == disrupting ray`, `sff == weakness`, per-event Hexing ownership, and proc probability are all still unproven. No replay/runtime/registry promotion was made.
  - Next step is to extract the full `HEXINGATTACK_WIRE_COLLISION_EVIDENCE` report and convert the exploratory lower bounds into exact corpus assertions for payload shapes, source/target agreement, Hexing/non-Hexing collision populations, source ability sets, zero/positive fields, owner relations, and independent normal-cast/server-spellbook controls.
  - Observed frequency `12/115` or a hypothetical `15/115` must **not** be used as a proc probability. Probability work starts only after independent per-event attribution is solved.

### Hexing wire evidence artifact and atomic split

- Commit: `46a707c90f7053bf944592c9b1fd8d26aa88a2fa` — `test(ability): export Hexing wire evidence artifact`.
  - Split the Hexing baseline and whole-corpus wire collision auditor into independent pytest nodes so the 866-battle scans fan out independently under `TESTS_CANON.md`.
  - Added deterministic `hexingattack-wire.json` export from the exact wire node and a one-day hosted artifact upload; no replay/runtime/registry semantics changed.
  - Authoritative hosted Ability Windows run `31685964687`: **PASS / completed with conclusion `success`** on exact functional SHA `46a707...`; check-suite `85956077927`. The dedicated wire node `94402248165` and artifact upload both passed.
  - Recovered exact whole-corpus population: `crs=480`, `slw=1412`, `sff=824`, `ray=1179` (3895 total), with source/target state present for every record and all records other-owner.
  - Exact Hexing attack-bound subset is `crs=4`, `slw=3`, `sff=5`, `ray=3`; non-Hexing attack-bound controls are `crs=64`, `slw=24`, `sff=502`, `ray=1`.
  - `ray` is decisively shared rather than Hexing-specific: 1179 total records include 406 `CAST_OR_ABILITY` and only 3 Hexing attack-bound records. Positive `field2` controls are dominated by costs `05` and `10`, with same-source spellbooks producing `dray`/`mdray` exact-cost matches hundreds of times; other same-cost spells also collide and remain explicit.
  - `sff` is likewise shared: 824 total, 77 `CAST_OR_ABILITY`, 658 `MELEE_ATTACK`, 5 Hexing attack-bound. Its positive-cost controls are dominated by `suffering`/`msuffering` but are not unique solely by cost.
  - This commit therefore establishes evidence plumbing and collision evidence, not final spell identity or proc probability. The next functional package must strict-pin all exported aggregates and only then decide the strongest identity/observed-consequence boundary supported by independent controls.

### Hexing strict corpus contract and normal-cast discriminator

- Commit: `baaeb4436a91962bf9a5f59f8b1b66876dbd8645` — `test(ability): lock Hexing wire collision corpus`.
  - Converted the whole-corpus Hexing collision audit from exploratory/conservation checks into a strict exact contract over 3895 raw records, including record/payload widths, full field2 distribution, field3/field4 canonical digests, source/target agreement, action types, attack-bound controls, Hexing/non-Hexing source populations, owner relation, source ability/creature/spellbook inventories and representative rows.
  - Authoritative hosted Ability Windows run `31687089866`: **PASS / completed with conclusion `success`** on this exact SHA; check-suite `85959134496`. Dedicated Hexing wire job `94405812591` and evidence-artifact upload passed.
  - `CAST_OR_ABILITY` controls are exactly `crs=79`, `slw=430`, `sff=77`, `ray=406`. Unique same-source exact-cost spellbook matches independently resolve only the expected internal families: `crs -> curse=52,mcurse=5`; `slw -> slow=261`; `sff -> suffering=51`; `ray -> dray=65,mdray=63`. Same-cost ambiguous sets remain explicit and are not promoted from cost alone.
  - The complete Hexing attack-bound subset is exactly 15 rows (`crs=4`, `slw=3`, `sff=5`, `ray=3`), all with `field2=00`; exact field3 shapes are `crs:096x1,100x3`, `slw:040x3`, `sff:012x5`, `ray:006x3`.
  - These controls establish shared wire-family identity and isolate the zero-cost Hexing attack-bound population without relying on mnemonic resemblance or tooltip wording. They do **not** justify a proc probability from `15/115`, a blanket zero-cost status exactness rule, runtime mutation, or registry promotion.
  - Next evidence layer is the observed consequence path: strict-pin the newly exported compact normal-cast/15-row aggregates, then audit replay status application (`crs/slw/sff`) and currently unresolved `ray` before any executable semantic change.
