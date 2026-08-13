# Ability Integration Status

Checkpoint: **2026-08-13**

Source lane: `ability`
Integration branch: `integration/ability-snapshot-20260812`
Functional snapshot commit: `f98ea913be9331ca393c49df82b2025303956f92`
Validated integration HEAD: `03d2fbe138e0dad929037315dce46d38256be8f3`
Current main integration reference: **`7e646733eded4a491b25ddae1c2efcb9287feeec`**
Current validated functional ability SHA: **`c5a2acaded82d36e5c32b6af9833554a44c60ce2`**
Authoritative hosted Windows run: **`31679297822` — PASS / check-suite `85938145984`, completed with conclusion `success` on exact SHA and branch `ability`**

## Governance

- `docs/ABILITY_AGENT_TZ.md` is the canonical ability-agent contract.
- `docs/ability/ability_changelog.md` is the canonical ability development journal and records real functional SHAs plus hosted Windows validation evidence.
- `TESTS_CANON.md` governs atomic test execution: exact inventories and exact coverage are correctness requirements; worker/matrix width is only scheduling.
- Linux/WSL results are diagnostic only. Hosted Windows/MSVC is the PASS/FAIL authority for ability functional packages.
- Ability development does not merge itself into `main`; the main/integration agent owns final integration.

## Closed Gribbomb boundary

- `gribbomb = partial_exact`, canonical risk `0.25`.
- Exact observed carrier self-removal is represented for canonical carrier-sourced `Sbom`; predictive Earth/collateral magnitude remains unresolved and disabled.
- Registry/report artifacts were synchronized by `c24cacf060182494092ef3e460301844639388e6` and `eaca45fc3de060b030ee912c38efea234aa00c1f`; hosted run `31631708571` passed.

## Closed Taunt boundary

- Validated functional SHA `7f143d9050d42a20300be3a54511cdae16682f0e`; hosted Windows run `31639884205` passed.
- Exact evidence pins tooltip, neighboring-friendly geometry and opportunity/control counts, but exposes neither a carrier-specific per-attack redirect discriminator nor numeric redirect probability.
- `ra2`/`ral` collide across carrier-target and adjacent-ally controls; final DAMAGE destination is not used to reconstruct original intent.
- Taunt remains `unresolved` for predictive/search semantics and is closed for this pass at that blocker.

## Closed Spider / `Sent` boundary

- `2596f59a065604dd5a525d19969712cebbd9c3eb` added corpus-wide `Sent` source controls; run `31644823929` passed.
- `1744354e79713569f7598e424f890801db88c8d5` strict-pinned the exact wire corpus; run `31645840641` passed.
- Locked facts: 866 battle dirs, 182 `ent` battles, 806 `Sent` records, 315 zero-source and 491 nonzero-source records; nonzero sources split exactly `405 Entroots-without-Spider / 84 Spider+Entroots / 2 neither`.
- Every payload is `source3 + target3 + 000000000`; current parser deliberately leaves the second UID as `target_uid=None` although it is state-resolvable for 806/806 records.
- Raw `Sent` is not Spider-specific and is not safely Entroots-exclusive because of the two Netshooter controls. No Spider runtime effect or registry promotion is justified.

## Closed Child of the Light evidence boundary

Validated functional evidence sequence:

- `58965925cfe09552e9e5a4e22ff3d2cae86cbd69` — exploratory spellwire probe; hosted run `31647277552` **FAIL** because the raw spellbook contains no literal `light` school token. The failure was retained as protocol evidence.
- `87c661aadcbcfd1b9ffd750aef20c6e9418e4c89` — raw spellbook-school inventory; run `31647544114` **PASS**.
- `7d63aad9ae992cd9b949da43a7ec42a82f627a7d` — decoded `bm_tooltips` metadata audit; run `31648327688` **PASS**.
- `c5a2acaded82d36e5c32b6af9833554a44c60ce2` — final strict metadata lock; authoritative run `31679297822` **PASS**, check-suite `85938145984` completed with conclusion `success` on the exact SHA.

Strict Child corpus facts:

- 866 battle directories; 108 carrier battles; 137 carriers (`creature_id 588 = 102`, `928 = 35`).
- 121 tooltip battles expose one exact statement: any Light-school spell except damage and resurrection is also applied to the creature at expert level; the tooltip has no numeric probability/percentage.
- Raw spellbook inventory in carrier battles is 651 actors / 2031 entries with school tokens `neutral 1405`, `air 275`, `earth 144`, `cold 141`, `other 31`, `fire 18`, `nt 17`; there is no raw `light` token.
- `neutral`/`nt` mix statuses from incompatible game-school semantics, so the raw school token cannot identify Light membership.
- Current status-wire subset hitting Child carriers contains 158 source+code groups, 146 positive-cost and 12 zero-cost follow-ups; direct-damage controls are exactly 3 (`ltn 2`, `mfs 1`).
- Decoded `bm_tooltips` in all 108 carrier battles contains only `abil_desc`, `abil_names`, `perk_hints` dictionaries. Exact key overlap with same-battle raw spellbook spell names is zero.
- Correction to the earlier exploratory wording: `non_child_light_text_hits = 92`, not zero. The decisive independent discriminator remains absent: `non_child_school_light_hits = 0`, while `child_light_text_hits = 216` and `school_text_hits = 112`.

Semantic ceiling: **Child of the Light remains `unresolved` and is closed for this pass at the precise missing per-spell Light-school discriminator.** No runtime copy rule, registry promotion, hardcoded Light spell taxonomy, or inferred probability is allowed from the current corpus.

## Current lead — Hexing Attack

The weighted unfinished queue advances to `hexingattack` (current report contribution approximately `229914`, subject to the same actionability/blocker filter).

Existing hosted baseline from the atomic Hexing node on exact SHA `c5a2acad...`:

- 866 battle dirs; 32 Hexing carrier battles; 88 carriers.
- Carrier creatures: `268 = 20`, `269 = 27`, `333 = 41`.
- Exact carrier ability sets: `caster,hexingattack,undead` (47) and `alive,caster,hexingattack,ragingblood,sacrificegoblin,swiftattack` (41).
- 115 carrier attacks, all `MELEE_ATTACK`; attacking creature counts are `333 = 94`, `269 = 16`, `268 = 5`.
- Current parser finds 12 zero-cost same-actor/same-target status records after carrier attacks: `sff 5`, `crs 4`, `slw 3`.
- The exact tooltip names four possible expert-level effects — Curse, Slow, Weakness, Disrupting Ray — and says only “with some probability”; it supplies no numeric probability, percentage, or integer constant.
- Raw Hexing attack windows also contain three `Sray...` records, but generic parser currently leaves `ray` outside status grammar. `ray` is only an evidence candidate until a whole-corpus layout/source/collision audit proves what it represents.

## Next ownership state

1. Harden the existing Hexing smoke node to the exact baseline above.
2. Add a whole-corpus collision/layout auditor for `crs`, `slw`, `sff`, and raw `ray`, including source ability sets, attack actor/target agreement, payload shape, target-state presence and non-Hexing controls.
3. Do not infer `ray == disrupting ray` from its mnemonic or from the tooltip. Require independent corpus evidence, including normal spellbook/cast controls where available.
4. Do not model a proc probability from `12/115` or a hypothetical `15/115`; the tooltip has no numeric constant and attribution must be solved first.
5. Every functional package must receive hosted Windows Ability CI on its exact SHA, followed by separate bookkeeping updates to `ability_changelog.md`, this status file and root `changelog.md`.
