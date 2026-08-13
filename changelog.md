# HeroesWM Solver — Change Log

Historical entries through **2026-08-11** are preserved verbatim in [`docs/changelog_archive_through_2026-08-11.md`](docs/changelog_archive_through_2026-08-11.md). The archive is the exact previous `changelog.md` blob; no historical entry was rewritten or dropped during this rollover.

## Working convention

- Functional changes are committed as separate logical change sets.
- After functional changes, this file records the real commit SHA(s) in a bookkeeping commit.
- Specification/status documents are updated when a requirement is verified or its implementation status changes.
- A bookkeeping commit cannot record its own SHA; entries therefore reference the functional commits they document.

## 2026-08-12

### Atomic test execution canon

- Commit: `d4424f5bc861f8eae58b0c6c723f99b8b3b58341` — `docs: define atomic test execution canon`.
  - Added `TESTS_CANON.md` to `main` as the canonical testing policy.
  - Atomicity, independence, deterministic execution, exact inventory coverage, no duplicate/omitted cases, and exact aggregation are correctness requirements.
  - Shard count, worker count, matrix width, and `max-parallel` are explicitly implementation details rather than fixed correctness contracts.

### Ability snapshot integration without divergent-history merge

- Commit: `f98ea913be9331ca393c49df82b2025303956f92` — `feat: integrate ability evidence snapshot with atomic CI`.
  - Recreated the final ability-owned state directly on top of current `main` instead of merging the divergent raw `ability` history.
  - Imported `python/hwm_solver/ability/**`, matching evidence regressions, registry state, ability ownership/status documentation, and the evidence-backed `cripplingwound -> partial_exact` registry classification.
  - Preserved current main-owned planner, M11/evaluation, daemon/runtime, extension, general CI, specification, and report files rather than taking their divergent ability-branch versions.
  - Imported the ability-owned C++ test state with the Windows/MSVC test-only fixes: Mighty Slam pointers are reacquired after `vector::push_back`, the canonical `frightfulaura` tag is used, and temporary files use `std::filesystem::temp_directory_path()`.
  - Added a minimal CMake target for an ability case runner and a dedicated hosted-Windows atomic ability workflow.
  - C++ builds once, freezes the exact `hwm-tests` function inventory, then executes one named function per matrix job.
  - Python freezes exact pytest node IDs from the explicit ability test manifest and executes one node per matrix job.
  - No ability correctness regression requires a particular shard count, worker count, matrix width, or `max-parallel` value.

- Commit: `53a2e08b9eb2d8185f9d72f8ebf03b5b77b1a886` — `fix: delimit PowerShell case labels`.
  - Corrected PowerShell variable interpolation exposed by real hosted run `31607100702`; both C++ and Python syntax preflights then passed.

- Commit: `03d2fbe138e0dad929037315dce46d38256be8f3` — `fix: preserve C++ inventory JSON for matrix`.
  - Preserved the case runner's JSON array verbatim for GitHub matrix expansion after run `31607254689` exposed an accidental single `Object` matrix value.
  - Authoritative integration run `31607886774`: **PASS**, expanding to **85 jobs** with independent C++ function jobs, independent pytest node jobs, inventory gates, and aggregate status publication.

- Commit: `a9dab68a0e6720f415571cad2bc4865b50a5f4f0` — `docs: record validated ability snapshot integration`.
  - Replaced the stale outage-era ability status with the validated snapshot handoff, preserved semantic boundaries, and documented the new atomic CI ownership model.
  - `main` was advanced to this commit by a normal non-forced fast-forward; the raw 134-commit divergent `ability` history was not merged.
  - Post-merge atomic Ability run `31609098962`: **PASS**.
  - Post-merge standard Windows run `31609098960`: **PASS** — Core and Full both completed successfully on the same functional SHA.

### Ability semantic boundary after integration

- `cripplingwound` is `partial_exact`: observed consequence is represented, while speculative proc probability remains disabled.
- `powerstrike` trigger prediction remains unresolved/learned rather than being promoted to an exact speculative proc.
- Evidence-only Aura of Fire Vulnerability and the remaining ability queue remain evidence-only until executable semantics satisfy their own gates.
- Existing closed Life Drain, Regeneration, Mana Feed, Mighty Slam, and Paw Strike mechanics were not reworked by this integration.

### Gribbomb evidence resumption

- Commit: `b6b27633154f12588071a3e94145308aceb57451` — `test(ability): pin Gribbomb Sbom activation boundary`.
  - Promoted raw carrier `SPECIAL:bom` to the primary evidence discriminator and added strict whole-corpus adjacency/target-set regression gates.
  - Hosted Windows run `31621278975` failed only on a handwritten expected pre-activation HP (`36356` vs replay-derived `36101`); the preceding discriminator and 3/3 adjacent-target assertions passed.
  - No runtime/registry promotion is claimed from the failed package; predictive Earth-damage magnitude remains unresolved.

- Commit: `d04999b03a094e637223ec7925b3071e50e36ecf` — `fix(ability): use replay-derived Gribbomb pre-bomb HP`.
  - Fixed only the incorrect expected pre-activation HP while keeping all strict discriminator, geometry, target-set, and negative-control assertions intact.
  - Hosted Windows run `31621756446`: **PASS**, 86/86 atomic jobs on the exact functional SHA.
  - Validated corpus evidence: 866 battle dirs, 7 carrier battles, 1/1 valid `Sbom`, 3/3 adjacent living targets hit, zero missing/extra targets, and 3 non-`Sbom` carrier deaths externally explained.
  - Runtime self-destruction and predictive Earth-damage magnitude remain intentionally unresolved; no registry promotion is claimed yet.

- Commit: `2e82c969e0da708f5bbda6973c92d662a638aa3c` — `fix(ability): replay Gribbomb Sbom self-destruction`.
  - Validated canonical carrier-sourced `Sbom` as an exact observed replay self-removal transition and added wrong-source/malformed-marker negative controls.
  - The carrier now becomes `alive=false`, `count=0`, `top_hp=0`; adjacent HP changes remain sourced only from raw `DAMAGE` records and no predictive Earth-damage formula was introduced.
  - Hosted Windows run `31625718512`: **PASS, 87/87 atomic jobs** on the exact functional SHA.
  - Gribbomb's carrier-removal boundary is exact observed replay; predictive collateral magnitude remains unresolved, so the next ability-owned step is a bounded registry/risk promotion rather than a fully exact claim.

### Gribbomb bounded registry/risk promotion

- Commit: `e4616a155fdd1e15def28f74c8c7af43391177ba` — `feat(ability): classify Gribbomb partial exact`.
  - Promoted `gribbomb` in the source-of-truth registry builder from `unresolved` to `partial_exact`, giving the canonical `partial_exact` risk weight `0.25` instead of the old unresolved `0.62`.
  - Added a leakage-safe registry/risk regression that synthesizes the old Gribbomb baseline and proves the candidate registry lowers held-out ability risk.
  - The regression also requires Gribbomb to remain outside the predictive collateral model: the exact claim is carrier self-removal, not an inferred Earth-damage formula.
  - Hosted Windows run `31626881854`: **FAIL** only because the new regression encoded a brittle global support-count constant; the Gribbomb classification and semantic assertions themselves passed.

- Commit: `19ba4e6caed9977839eaac8ebb0181ca57a32ede` — `fix(ability): compare Gribbomb registry counts relatively`.
  - Replaced the brittle global registry cardinality assertion with the invariant that the candidate has exactly `+1 partial_exact / -1 unresolved` versus the synthesized pre-promotion baseline.
  - No semantic or risk threshold was weakened.

- Commit: `da7fd216f6b993f7e6a1770371004253b80d35cc` — `fix(ability): trigger registry risk tests in CI`.
  - Closed a workflow path-filter gap by matching `python/tests/test_*_registry_risk.py` for Ability push/PR triggers instead of naming only the older Crippling Wound file.
  - Added an atomic workflow-contract regression so future ability registry-risk tests cannot silently fall outside the hosted validation trigger.
  - Authoritative hosted Windows run `31627726097`: **PASS, 89/89 jobs**, including the Gribbomb registry/risk node, all Gribbomb self-destruction controls, the new workflow-trigger regression, and final `publish_status`.
  - Gribbomb's supported classification ceiling is now `partial_exact`: observed carrier self-removal is exact, while predictive Earth/collateral-damage magnitude remains unresolved.
  - Checked generated registry/report artifacts still require deterministic regeneration from the validated builder before the Gribbomb package is considered repository-consistent and the queue advances to Taunt.

### Gribbomb generated artifact closure

- Commit: `c24cacf060182494092ef3e460301844639388e6` — `chore(ability): regenerate ability registry artifacts`.
  - Deterministically regenerated checked `data/catalog/ability_registry.json` and `.csv` from the validated source-of-truth builder and tracked inputs.
  - The generated output incorporates the Gribbomb `partial_exact` promotion and also corrects the previously stale checked Crippling Wound classification; support totals are `partial_exact = 20`, `unresolved = 77`.

- Commit: `eaca45fc3de060b030ee912c38efea234aa00c1f` — `chore(ability): regenerate current ability reports`.
  - Regenerated `data/reports/ability-registry-current.json` and `data/reports/ability-risk-current.json` from the synchronized checked registry.
  - Held-out ability-risk mean changed `0.22431 -> 0.21744`; p90 changed `0.37538 -> 0.36755`.
  - Stale unresolved Gribbomb risk dropped out of the unfinished top-risk slice, while Crippling Wound is now represented as `partial_exact` with canonical risk `0.25`.
  - Hosted Windows run `31631708571` on exact SHA `eaca45fc...`: workflow **PASS / conclusion `success`**. All test/build/inventory jobs succeeded; final `publish_status` was skipped by workflow condition.
  - Builder, checked registry, and current report artifacts are now repository-consistent. Gribbomb is closed at the strongest evidence-supported `partial_exact` boundary; predictive Earth/collateral magnitude remains explicitly unresolved and disabled.

### Ability queue after Gribbomb closure

- Recomputed from the synchronized current risk report: Taunt is the highest-priority currently actionable unfinished ability after excluding already documented semantic/substrate blockers.
- Taunt development resumes from the existing evidence auditor rather than restarting from scratch. Its current smoke regression must be upgraded to exact whole-corpus counts and raw special-code contexts before any semantic promotion.
- Final-target observations alone are not accepted as Taunt proc evidence; a carrier-specific raw discriminator is required before claiming redirected targeting or proc probability.

### Taunt strict evidence closure

- Commit: `e7dffd54b1777766e4916f7b6f5f548e25e2cfab` — `test(ability): pin Taunt redirect evidence boundary`.
  - Replaced the smoke-only Taunt regression with exact corpus/tooltip/geometry/opportunity gates and target-source special-code controls.
  - Pinned 866 battle dirs, 24 carrier battles, 25 carriers, 24/24 identical tooltips, 712 attacks, 169 carrier-plus-adjacent-ally opportunity states, 78 attacks ending on carriers, 31 carrier-target attacks with an adjacent ally, and 37 attacks ending on an adjacent ally.
  - Tooltip evidence states only a chance to redirect an attack aimed at a neighboring friendly unit and provides no numeric probability.
  - `ra2`/`ral` target-source records appear in both carrier-target and adjacent-ally control contexts, so they are not accepted as Taunt proc labels; final target is not used to reconstruct original intent.
  - Hosted Windows run `31639091346`: **FAIL** only because two handwritten expected negative-control counts were wrong (`ra2 19` vs observed `18`; `ral 13` vs observed `9`).

- Commit: `7f143d9050d42a20300be3a54511cdae16682f0e` — `fix(ability): correct Taunt reaction control counts`.
  - Corrected only the two bad expected counts (`ra2 19 -> 18`, `ral 13 -> 9`) and preserved all semantic/evidence gates.
  - Authoritative hosted Windows run `31639884205` on branch `ability`: **PASS / workflow conclusion `success`** on the exact functional SHA.
  - Taunt is therefore closed for this evidence pass at a precise blocker: server tooltip/geometry/opportunity facts are exact, but current corpus evidence does not expose a carrier-specific per-attack redirect discriminator or numeric probability.
  - No runtime or registry promotion is made; Taunt remains `unresolved` for predictive/search semantics instead of introducing a heuristic from final attack targets.

## 2026-08-13

### Spider / `Sent` wire attribution boundary

- Commit: `2596f59a065604dd5a525d19969712cebbd9c3eb` — `test(ability): audit Spider Sent wire attribution`.
  - Added corpus-wide raw `Sent`/`ent` protocol evidence and source-ability controls without changing replay/runtime or registry semantics.
  - Authoritative hosted Ability Windows run `31644823929`: **PASS / GitHub Actions check-suite conclusion `success`** on exact SHA; Spider wire job `94276046646` passed.
  - Exact observed wire population: 866 battle dirs, 182 `ent` battles, 806 numeric `Sent` records, all with a 15-digit payload structurally splitting as `source3 + target3 + 000000000`.
  - Current parser decodes the first UID as actor for 806/806 but leaves the second UID undecoded as `target_uid=None` for 806/806; the second UID is nonzero and present in state before/after for every record.
  - Spider attribution is disproved: all 89 Spider carriers also have `entroots`, while 405 nonzero-source `Sent` records come from `entroots` sources **without** Spider versus 84 from sources carrying both.
  - Two more nonzero `Sent` sources carry `netshooter` with neither Spider nor Entroots, so raw `ent` is treated as a shared immobilization/entangle wire substrate rather than an Entroots-exclusive ability label.
  - No Spider runtime effect or registry promotion was added. The next safe layer is strict exact corpus locking, followed only then by a separate structural parser-target decision that remains independent of ability ownership.

### Spider / `Sent` exact corpus contract

- Commit: `1744354e79713569f7598e424f890801db88c8d5` — `test(ability): pin Spider Sent wire corpus`.
  - Hardened the exploratory wire evidence into exact corpus cardinality, source-class, source-ability-set, target-presence and parser-gap assertions without changing parser/runtime/registry semantics.
  - Exact locked population remains 866 battle dirs, 89 initial Spider carriers, 182 `ent` battles and 806 `Sent` records with `source3 + target3 + 000000000` layout; source classes are exactly 405 Entroots-without-Spider, 84 Spider+Entroots and 2 neither.
  - The second UID is nonzero and state-resolvable for 806/806 records, while current parser behavior remains explicitly `target_uid=None` for 806/806.
  - Authoritative hosted Ability Windows CI run `31645840641`: **PASS / combined status `HWM / Ability = success`** on the exact functional SHA.
  - Semantic ceiling is unchanged and now strict-regression protected: raw `Sent` is not Spider-specific and is not safely Entroots-exclusive because of the Netshooter controls. No Spider runtime effect or registry promotion is created.
  - Any structural target decode must be a separate protocol-level functional package with independent negative controls and hosted Windows validation; it must not be used to manufacture Spider ownership.

### Child of the Light spellbook evidence frontier

- Commit: `58965925cfe09552e9e5a4e22ff3d2cae86cbd69` — `test(ability): audit Child of Light spell wire`.
  - Hardened the old Child smoke evidence into exact corpus assertions and added a raw server-spellbook/status-wire probe, without changing runtime/registry semantics.
  - Hosted Ability Windows run `31647277552`: **FAIL** because the probe's tentative literal raw-school assumption `light` was contradicted by the corpus: zero spellbook entries used that token.

- Commit: `87c661aadcbcfd1b9ffd750aef20c6e9418e4c89` — `test(ability): inventory Child of Light spellbook schools`.
  - Added a school-token inventory and locked the failed `light` token assumption as a negative protocol fact instead of replacing it with a guessed spell list.
  - Authoritative hosted Ability Windows run `31647544114`: **PASS**; check-suite `85854980801` completed with conclusion `success` on the exact SHA.
  - Pinned Child baseline: 866 battles, 108 carrier battles, 137 carriers, one exact server tooltip statement across 121 battles, 5634 decisions and 206 carrier-targeted SPECIAL records.
  - Raw spellbook inventory in carrier battles is 651 actors / 2031 entries with exact tokens `neutral 1405`, `air 275`, `earth 144`, `cold 141`, `other 31`, `fire 18`, `nt 17`; no `light` token exists.
  - `neutral` mixes candidate Light-like and Dark-like status identities plus Raise Dead, so the field cannot independently classify game Light school. No Child runtime/registry promotion is made.
  - Next evidence step is independent decoded `bm_tooltips`/server metadata for per-spell school identity; if absent, Child will close for this pass at that precise evidence blocker.

### Child of the Light decoded tooltip metadata blocker

- Commit: `7d63aad9ae992cd9b949da43a7ec42a82f627a7d` — `test(ability): audit Child tooltip spell metadata`.
  - Added decoded `bm_tooltips` structure/key/text evidence and strict-pinned the already validated spellbook/status-wire counts without changing runtime or registry semantics.
  - Authoritative hosted Ability Windows run `31648327688`: **PASS**; check-suite `85857041871` completed with conclusion `success` on the exact SHA.
  - All 108 Child carrier battles have decoded tooltip payloads, but the payload contains only `abil_names`, `abil_desc`, and `perk_hints` dictionaries; none has any exact key overlap with the same battle's raw spellbook spell names.
  - The previous bookkeeping wording incorrectly described all non-Child Light prose as absent. The final strict package below corrects that distinction while preserving the actual missing discriminator.
  - Combined with the raw spellbook `neutral`/`nt` collapse, current server evidence lacks an independent per-spell Light-vs-Dark discriminator. No runtime copy rule, registry promotion, hardcoded spell taxonomy or inferred probability is justified.

### Child of the Light strict metadata closure

- Commit: `c5a2acaded82d36e5c32b6af9833554a44c60ce2` — `test(ability): lock Child tooltip metadata blocker`.
  - Converted the final decoded-tooltip observations into exact regression assertions in the existing atomic Child node; no parser/runtime/registry semantics changed.
  - Authoritative hosted Ability Windows run `31679297822`: **PASS / completed with conclusion `success`** on the exact SHA; check-suite `85938145984`.
  - All 108 carrier battles expose only `abil_desc`, `abil_names`, `perk_hints` dictionaries; there are zero exact mapping-key overlaps with same-battle server spellbook spell names.
  - Corrected text counts are `child_light_text_hits = 216`, `non_child_light_text_hits = 92`, `school_text_hits = 112`, while the independent joint discriminator remains `non_child_school_light_hits = 0`.
  - Thus Light-related ability/perk prose exists, but no metadata identifies a concrete spell and independently classifies it as Light. Child of the Light is closed for this evidence pass as `unresolved` at that precise missing per-spell school discriminator.
  - No runtime copy rule, registry promotion, hardcoded Light spell list, or numeric probability is introduced. The weighted unfinished queue advances to Hexing Attack with source/collision auditing required before any proc attribution.

### Hexing Attack baseline and wire-collision evidence

- Commit: `a2c06ef10048486cc84239b045f3710e9f7db795` — `test(ability): pin Hexing baseline and wire audit`.
  - Hardened the Hexing smoke test to exact corpus baseline assertions and added a whole-corpus raw candidate-wire collision/layout auditor for `crs`, `slw`, `sff`, and `ray`.
  - Baseline pins 866 battle dirs, 32 carrier battles, 88 carriers, 115 carrier attacks (all melee), 12 parsed zero-cost same-actor/same-target status records (`sff = 5`, `crs = 4`, `slw = 3`), plus 3 raw `Sray...` occurrences in Hexing attack windows that remain outside generic status grammar.
  - Tooltip names Curse, Slow, Weakness and Disrupting Ray but supplies no numeric proc probability.
  - Authoritative hosted Ability Windows run `31680364027`: **PASS / conclusion `success`** on exact SHA; check-suite `85941007397`.
  - The package is evidence-only. It does not prove `ray == Disrupting Ray`, `sff == Weakness`, Hexing ownership of every candidate record, or any proc percentage; no replay/runtime/registry promotion was made.
  - Next ability step is strict whole-corpus collision locking and independent normal-cast/server-spellbook identity controls before any semantic decode or probability model.

### Hexing wire evidence artifact and atomic split

- Commit: `46a707c90f7053bf944592c9b1fd8d26aa88a2fa` — `test(ability): export Hexing wire evidence artifact`.
  - Split the Hexing baseline and raw collision auditor into independent pytest nodes and exported deterministic `hexingattack-wire.json` from the dedicated wire node; the hosted workflow uploads it as a short-lived evidence artifact.
  - Authoritative hosted Ability Windows run `31685964687`: **PASS / completed with conclusion `success`** on exact functional SHA `46a707...`; check-suite `85956077927`. Dedicated wire node `94402248165` and artifact upload succeeded.
  - Exact recovered raw population is 3895 records: `crs=480`, `slw=1412`, `sff=824`, `ray=1179`; source and target state are present for every record and all records are other-owner.
  - Hexing attack-bound subset is exactly `crs=4`, `slw=3`, `sff=5`, `ray=3`; non-Hexing attack-bound controls are `crs=64`, `slw=24`, `sff=502`, `ray=1`.
  - `ray` and `sff` are therefore shared spell/status wires rather than Hexing-owned proc labels. `ray` has 406 normal `CAST_OR_ABILITY` contexts and strong same-source `dray/mdray` cost controls; `sff` has 77 normal cast contexts and strong `suffering/msuffering` cost controls, with same-cost collisions retained as ambiguity evidence.
  - No replay/runtime/registry semantic or proc probability was introduced. The next functional step is an exact corpus contract over the exported aggregates before any stronger internal spell-identity or observed-consequence claim.

### Hexing strict collision contract

- Commit: `baaeb4436a91962bf9a5f59f8b1b66876dbd8645` — `test(ability): lock Hexing wire collision corpus`.
  - Strictly locked the 3895-record `crs/slw/sff/ray` corpus, including fixed widths, field distributions/digests, source-target agreement, owner relation, attack/Hexing/non-Hexing controls, spellbook collisions and representative rows.
  - Authoritative hosted Ability Windows run `31687089866`: **PASS / completed with conclusion `success`** on exact SHA; check-suite `85959134496`. Dedicated wire node `94405812591` and artifact upload succeeded.
  - Normal `CAST_OR_ABILITY` controls are `crs=79`, `slw=430`, `sff=77`, `ray=406`; unique exact-cost same-source spellbook matches independently identify `curse/mcurse`, `slow`, `suffering`, and `dray/mdray` families respectively, while ambiguous same-cost sets remain explicit.
  - The complete Hexing attack-bound subset is 15 rows (`4/3/5/3`), all zero-field2, and remains distinct from ordinary positive-cost cast validation. No proc probability, blanket zero-cost exactness, runtime mutation or registry promotion is inferred.
  - Next safe step is to lock the new compact identity/subset aggregates and audit observed replay consequence before any executable Hexing semantic change.
