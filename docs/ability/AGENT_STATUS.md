# Ability Integration Status

Checkpoint: **2026-08-13**

Source lane: `ability`
Integration branch: `integration/ability-snapshot-20260812`
Functional snapshot commit: `f98ea913be9331ca393c49df82b2025303956f92`
Validated integration HEAD: `03d2fbe138e0dad929037315dce46d38256be8f3`
Current main integration reference: **`7e646733eded4a491b25ddae1c2efcb9287feeec`**
Current validated functional ability SHA: **`1744354e79713569f7598e424f890801db88c8d5`**
Authoritative hosted Windows run: **`31645840641` — PASS / `HWM / Ability` combined status `success` on exact SHA and branch `ability`**

## Governance

- `docs/ABILITY_AGENT_TZ.md` is the canonical ability-agent contract.
- `docs/ability/ability_changelog.md` is the canonical ability development journal and must record real functional SHAs plus hosted Windows validation evidence.
- `TESTS_CANON.md` governs atomic test execution: exact inventories and exact coverage are correctness requirements; worker/matrix width is only scheduling.
- Linux/WSL results are diagnostic only. Hosted Windows/MSVC is the PASS/FAIL authority for ability functional packages.
- Ability development does not merge itself into `main`; the main/integration agent owns final integration.

## Closed Gribbomb boundary

- `2e82c969e0da708f5bbda6973c92d662a638aa3c` made canonical carrier-sourced `Sbom` remove the Gribbomb carrier in observed replay (`alive=false`, `count=0`, `top_hp=0`) without synthesizing predictive target damage.
- `da7fd216f6b993f7e6a1770371004253b80d35cc` completed the registry/risk validation path; hosted run `31627726097` passed.
- `c24cacf060182494092ef3e460301844639388e6` and `eaca45fc3de060b030ee912c38efea234aa00c1f` synchronized checked registry/report artifacts; run `31631708571` passed.
- Current supported classification: **`gribbomb = partial_exact`, risk `0.25`**. Exact observed carrier self-removal is represented; predictive Earth/collateral magnitude remains unresolved and disabled.

## Closed Taunt boundary

- `7f143d9050d42a20300be3a54511cdae16682f0e` is the validated Taunt functional SHA; authoritative hosted Windows run `31639884205` passed.
- Exact corpus evidence pins the server tooltip, neighboring-friendly geometry and opportunity/control counts, but exposes neither a carrier-specific per-attack redirect discriminator nor numeric redirect probability.
- `ra2`/`ral` occur in both carrier-target and adjacent-ally controls; final DAMAGE destination is not used to reconstruct original intent.
- Therefore Taunt remains `unresolved` for predictive/search semantics and is closed for this pass as a precise evidence blocker. Do not reopen it from final-target heuristics.

## Spider / `Sent` wire attribution and exact corpus lock

Validated functional commits:

- `2596f59a065604dd5a525d19969712cebbd9c3eb` — added `spider_wire_evidence.py`, an exact atomic test surface in `ABILITY_TESTS.txt`, and corpus-wide source-ability controls. It deliberately changed no replay/runtime/registry semantics. Hosted Ability Windows run `31644823929`: **PASS**.
- `1744354e79713569f7598e424f890801db88c8d5` — hardened the observed Spider/`Sent` evidence into exact corpus cardinality and wire-layout assertions without changing parser/runtime/registry semantics. Authoritative hosted Ability Windows run `31645840641`: **PASS / combined status `HWM / Ability = success`** on the exact SHA.

Validated whole-corpus facts:

- 866 battle directories;
- 182 battles containing raw `SPECIAL` code `ent` / `Sent...`;
- 806 `Sent` records, all numeric and all exactly 15 payload digits;
- every record structurally splits as `source3 + target3 + 000000000`;
- current parser maps the first UID to `actor_uid` for 806/806 and leaves `target_uid=None` for 806/806;
- the second UID is nonzero in 806/806 and resolves to a replay entity both before and after in 806/806;
- all 491 nonzero-source records point to an other-owner target; 315 records have source `000` and retain a target UID;
- all 89 initial Spider carriers also have `entroots`; there are zero Spider-without-Entroots carriers;
- source controls among nonzero-source `Sent`: **405 `entroots_without_spider`, 84 `spider_and_entroots`, 2 `neither`**;
- exact nonzero source ability sets are pinned, including the two `alive,netshooter,nopenalty,rangepenalty,shooter` controls with neither Spider nor Entroots.

Semantic boundary: **raw `Sent` is conclusively not Spider-specific.** The exact Windows-validated corpus contract supports only a shared immobilization/entangle wire substrate. The two non-Entroots Netshooter controls prevent promoting `ent` to an Entroots-exclusive ability label. No second Spider runtime effect and no Spider registry promotion are justified.

Protocol boundary: the second 3-digit UID is structurally target-shaped and exists in replay state for 806/806 records, but the current parser still deliberately leaves it undecoded. Any parser promotion must be a separate protocol-level functional package with explicit negative controls and must not assign Spider ownership.

## Preserved semantic boundaries

- `cripplingwound` remains `partial_exact`; speculative probability remains disabled.
- `powerstrike` trigger prediction remains unresolved/learned rather than promoted to an exact speculative proc.
- Aura of Fire Vulnerability remains evidence-only until a direct Fire-spell execution substrate exists.
- `gribbomb` remains `partial_exact` with predictive Earth/collateral damage disabled.
- Existing closed Life Drain, Regeneration, Mana Feed, Mighty Slam, and Paw Strike mechanics are not reworked without contrary evidence.

## Next ownership state

1. Treat Spider as closed for this pass at the exact evidence/protocol blocker above; do **not** create or register a Spider runtime effect from `Sent`.
2. Recompute the current weighted unfinished queue from `data/reports/ability-risk-current.json`, excluding Gribbomb, Taunt, Spider and other already documented blockers only for actionability, not by mutating their stored risk.
3. Start from the existing evidence code for the highest actionable unfinished lead; harden smoke gates into exact whole-corpus facts before any runtime/registry promotion.
4. Structural `ent` target decoding remains a separate protocol opportunity and may be revisited only with its own functional commit and hosted Windows validation; it is not a prerequisite for inventing Spider semantics.
5. Every next functional package must again receive hosted Windows Ability CI, followed by a separate bookkeeping commit updating `ability_changelog.md`, this status file, and root `changelog.md`.
