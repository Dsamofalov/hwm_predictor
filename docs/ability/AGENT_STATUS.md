# Ability Integration Status

Checkpoint: **2026-08-13**

Source lane: `ability`
Integration branch: `integration/ability-snapshot-20260812`
Functional snapshot commit: `f98ea913be9331ca393c49df82b2025303956f92`
Validated integration HEAD: `03d2fbe138e0dad929037315dce46d38256be8f3`
Current main integration reference: **`7e646733eded4a491b25ddae1c2efcb9287feeec`**
Current validated functional ability SHA: **`2596f59a065604dd5a525d19969712cebbd9c3eb`**
Authoritative hosted Windows run: **`31644823929` — PASS / GitHub Actions check-suite conclusion `success` on exact SHA and branch `ability`**

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

## Spider / `Sent` wire attribution validated package

Functional commit:

- `2596f59a065604dd5a525d19969712cebbd9c3eb` — added `spider_wire_evidence.py`, an exact atomic test surface in `ABILITY_TESTS.txt`, and corpus-wide source-ability controls. It deliberately changed no replay/runtime/registry semantics.
- Authoritative hosted Ability Windows run `31644823929`: **PASS / GitHub Actions check-suite `85847738967` completed with conclusion `success`** on exact SHA. Exact Spider wire job `94276046646` passed.

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
- the two `neither` sources are `alive,netshooter,nopenalty,rangepenalty,shooter`.

Semantic boundary: **raw `Sent` is conclusively not Spider-specific.** The corpus strongly supports a shared immobilization/entangle wire substrate, but the two non-Entroots Netshooter controls mean `ent` is not promoted to an Entroots-exclusive ability label either. No second Spider runtime effect and no Spider registry promotion are justified.

## Preserved semantic boundaries

- `cripplingwound` remains `partial_exact`; speculative probability remains disabled.
- `powerstrike` trigger prediction remains unresolved/learned rather than promoted to an exact speculative proc.
- Aura of Fire Vulnerability remains evidence-only until a direct Fire-spell execution substrate exists.
- `gribbomb` remains `partial_exact` with predictive Earth/collateral damage disabled.
- Existing closed Life Drain, Regeneration, Mana Feed, Mighty Slam, and Paw Strike mechanics are not reworked without contrary evidence.

## Next ownership state

1. Harden the newly observed Spider/`Sent` wire facts into exact corpus cardinality gates before changing parser semantics.
2. After that strict wire lock is separately validated on hosted Windows, structural decoding of the second `ent` UID as protocol `target_uid` may be considered independently of ability ownership.
3. Do **not** create or register a Spider runtime effect from `Sent`; current evidence disproves Spider-specific attribution.
4. Any later semantic interpretation of the two `netshooter` controls or source-`000` lifecycle records requires its own evidence package; do not guess.
5. Every next functional package must again receive hosted Windows Ability CI, followed by a separate bookkeeping commit updating `ability_changelog.md`, this status file, and root `changelog.md`.
