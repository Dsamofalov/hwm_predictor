# Ability Integration Status

Checkpoint: **2026-08-13**

Source lane: `ability`
Integration branch: `integration/ability-snapshot-20260812`
Functional snapshot commit: `f98ea913be9331ca393c49df82b2025303956f92`
Validated integration HEAD: `03d2fbe138e0dad929037315dce46d38256be8f3`
Current main integration reference: **`7e646733eded4a491b25ddae1c2efcb9287feeec`**
Current validated functional ability SHA: **`7f143d9050d42a20300be3a54511cdae16682f0e`**
Authoritative hosted Windows run: **`31639884205` — PASS / workflow conclusion `success` on exact SHA and branch `ability`**

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

## Taunt validated evidence package

Functional commits:

- `e7dffd54b1777766e4916f7b6f5f548e25e2cfab` — replaced the smoke-only Taunt test with exact whole-corpus targeting/tooltip/geometry gates and target-source special-code controls.
- Hosted run `31639091346` failed only because two handwritten negative-control counts were wrong; the corpus/tooltip/geometry gate passed.
- `7f143d9050d42a20300be3a54511cdae16682f0e` — corrected only `ra2` adjacent-ally `19 -> 18` and `ral` adjacent-ally `13 -> 9`.
- Authoritative hosted Windows run `31639884205`: **PASS / conclusion `success` on exact SHA**.

Validated whole-corpus Taunt evidence:

- 866 corpus battle directories;
- 24 Taunt carrier battles and 25 carrier entities;
- 24/24 identical server tooltip descriptions;
- tooltip semantics: the creature has a **chance** to redirect an enemy attack aimed at a neighboring friendly unit;
- no numeric Taunt probability is present in the tooltip;
- 712 attacks observed in Taunt carrier battles;
- 169 states with a carrier and at least one adjacent friendly unit that can serve as a targeting-opportunity context;
- 78 attacks ended on a Taunt carrier;
- 31 carrier-target attacks occurred while an adjacent ally was present;
- 37 attacks ended on an adjacent ally;
- target-source `ra2`/`ral` records occur in both carrier-target and adjacent-ally control contexts and therefore are not accepted as Taunt redirect markers;
- final DAMAGE destination is not treated as evidence of the attacker's original intended target.

Semantic boundary: **Taunt is closed for this pass as a precise evidence blocker, not as a predictive implementation.** The corpus exactly supports tooltip/geometry/opportunity facts, but it does not expose a carrier-specific per-attack redirect discriminator or numeric proc probability. Therefore Taunt remains `unresolved` for predictive/search semantics, with no runtime or registry promotion and no invented redirect heuristic.

## Preserved semantic boundaries

- `cripplingwound` remains `partial_exact`; speculative probability remains disabled.
- `powerstrike` trigger prediction remains unresolved/learned rather than promoted to an exact speculative proc.
- Aura of Fire Vulnerability remains evidence-only until a direct Fire-spell execution substrate exists.
- `gribbomb` remains `partial_exact` with predictive Earth/collateral damage disabled.
- Existing closed Life Drain, Regeneration, Mana Feed, Mighty Slam, and Paw Strike mechanics are not reworked without contrary evidence.

## Next ownership state

**Taunt evidence work is complete at the strongest currently supportable boundary. Do not spend another cycle trying to infer redirect proc outcomes from final targets or `ra2/ral`.**

1. Advance to the next weighted actionable unfinished ability after recomputing the current risk queue.
2. Current read-only lead is Spider, but first disambiguate Spider-specific wire semantics from the co-occurring `entroots` mechanic before assigning any `Sent` record to Spider.
3. Treat any parser target-decoding gap as protocol evidence work first; do not add a second runtime mechanic merely because a carrier has both tags.
4. For each new functional package, use exact corpus gates, hosted Windows/MSVC Ability CI, then immediately record the functional SHA/run in `ability_changelog.md`, this status file, and root `changelog.md`.
