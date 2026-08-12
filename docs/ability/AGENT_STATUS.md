# Ability Agent Status

Branch: `ability`
Evidence HEAD before this status commit: `94d1694e26d07513e23befcddc71287cefbf72ee`
Draft integration PR: #1 (`ability` -> `main`)

## Lane state

- Ability work remains isolated from `main`; no ability commit has been pushed to `main`.
- A one-time synchronization was performed only after proven need: PR #3 merged `main` -> `ability` at `8307cdfda383b4a693560526e1579144c527f43d`. The lane was ~80 commits behind, PR #1 synthetic-merge CI had stopped before job steps, and the changed-file sets were disjoint.
- GitHub-hosted Actions is currently failing before runner allocation on both Linux and Windows (`steps=null`). The same no-step failure was observed on recent `main`, so this is treated as infrastructure failure, not a code/test failure. Do not modify workflows to chase it.
- Last complete ability-lane full green remains `97540370cacff733b23dcd76f7c6c088a1d23794`, CI #309 / run `31388803461`: C++ build PASS, CTest 2/2 PASS, held-out planner validity PASS, Python **74 passed**, TypeScript typecheck PASS, extension build PASS; Windows PASS.
- No local-test claim is made: this execution environment still cannot obtain a usable private local checkout.

## Last green risk / priority order

After Crippling Wound became `partial_exact`, held-out ability risk was:

- mean **0.2183514043**
- p50 **0.2045157859**
- p90 **0.3675486362**
- p99 **0.5468762844**

Highest non-exact weighted contributors at that point:

1. `auraoffirevul` **262,383.867**
2. `gribbomb` **254,058.622**
3. `taunt` **247,121.425**
4. `spider` **247,107.026**
5. `childofthelight` **233,930.111**
6. `hexingattack` **229,914.491**
7. `vulnerabilitytolight` **199,190.217**
8. `deathwail` **192,166.233**
9. `portal` **179,553.263**
10. `ragingblood` **169,360.790**
11. `shootbash` **167,467.323**
12. `packhunter` **163,536.136**
13. `purge` **163,266.053**
14. `six_heads` **160,870.893** (`modeled_collateral`, still non-exact)
15. `teleport` **156,510.384**
16. `venom` **156,253.661**
17. `torpor` **154,734.456** (`modeled_proc`, still non-exact)
18. `shieldguard` **153,302.046**
19. `stonegarden` **141,555.060**

`pawstrike` is intentionally skipped in this order because it is closed work. No new package below has changed production support during the runner outage, so no refreshed ranking is claimed yet.

## Completed package: Crippling Wound (`cripplingwound`)

Production classification: **`partial_exact`**.

Exact raw/server consequence:

- proc chance after successful attack;
- target Speed ×**0.5**;
- target Initiative ×**0.7**;
- duration **2** target activations;
- no numeric server proc probability.

Corpus evidence:

- `Swnd` records **157**;
- carrier source **157/157**;
- non-carrier collision **0**;
- same-pair DAMAGE before marker **157/157**;
- primary relation **129**;
- counter/retaliation relation **28**;
- all carrier DAMAGE hits **611**, proc **157**, no-proc **454**;
- primary **515 / 129 proc**;
- retaliation **95 / 28 proc**.

Battle `1632506509` has one static-same-owner `Swnd`; prior `Shyp009014...` temporary control explains it. Static owner inequality is therefore not a universal semantic gate.

Probability remains disabled. A single holdout `target_big_smoothed` gain was only ~**0.000673 Brier** and rolling-origin evaluation did not support a robust trait model. Integration request remains: validate observed `Swnd` through carrier tag + same-pair DAMAGE and preserve temporary-control side context.

## Completed evidence boundary: Power Strike (`powerstrike`)

Production trigger prediction remains **`learned_damage`**; no speculative proc.

- carrier melee attacks **389**;
- observed proc wires **32**, no-proc **357**;
- false raw-wire collisions **150/150 Paw Strike**;
- unexplained controls **0**;
- PowerStrike+PawStrike co-carrier attacks **0**;
- forced coordinate changed **20/32**, unchanged **12/32**;
- zero state after I **32/32**;
- retaliation on proc rows **0/32**;
- holdout baseline Brier **0.0626339004**;
- nominal best `target_big_smoothed` **0.0625030070**, improvement only **0.0001308935**.

If the exact observed consequence is later integrated, gate it by server-declared `powerstrike`, preserve raw forced position + `I<affected><source>` ATB reset, and retain the Leap/Slep canonical-position integration request for battle `1626555271`.

## Aura of Fire Vulnerability (`auraoffirevul`)

Exact server rule is proven: in **31/31** raw server tooltips, enemy stacks in adjacent cells receive **+50% additional damage from Fire-school spells**.

Green whole-corpus evidence:

- aura battles **31**;
- carrier entities **45**;
- creature 256 **28**, creature 961 **17**;
- Fire-spellbook actors **35**;
- spell names: `fireball` **33**, `firewall` **3**, `firearrow` **1**;
- Fire-spellbook actor decisions **121**;
- explicit actor DAMAGE hits **71**;
- only **2** such hits targeted a stack adjacent to an enemy Fire-aura carrier.

Focused wire commits: `3c5d859...`, `18a72ef...`, `6d6f251...`.

Interpretation guard: Fire spellbook presence does **not** make arbitrary actor DAMAGE a Fire spell. Fire Attack, Fire Shield, Magma Shield and other non-spell fire damage are negatives unless independently proven.

Production stays **`learned_damage`** because the executable Fire direct-spell substrate is missing: `cpp/src/protocol.cpp` does not construct Fireball/Fire Arrow/Firewall direct-spell specs, `models/hero_spell_damage.csv` has no Fireball row, and the simulator has Air/Water vulnerability multipliers but no Fire-school path.

Integration order: prove Fire spell wires -> add canonical Fire direct-spell model -> carry Fire school identity -> apply ×1.5 only to a target adjacent to a living enemy aura carrier -> regression-test non-adjacent/dead/ally/non-spell-fire negatives -> only then reconsider support.

## Evidence-only queue added during hosted-runner outage

No package in this section is claimed green and none changed runtime/support/risk.

### Gribbomb (`gribbomb`)

Commits: `6c41bf7...`, `6f0f937...`, focused self-destruct analyzer + `c208d9f...`, QA `bc80c8c...`.

Measures alive->dead carrier transitions, external kill DAMAGE, carrier outgoing DAMAGE, pre-action total HP, big-aware adjacency, missing/extra targets, owner relation, damage/HP ratio and target modifiers. Self-death + outgoing damage is only a discovery signature.

### Taunt (`taunt`)

Commits: `8f3687a...`, `ab058eee...`.

Separates attacks ending on a Taunt carrier with an adjacent ally from attacks ending on that ally. Final DAMAGE target is not a proc label; an unambiguous raw redirect discriminator is required.

### Spider (`spider`)

Commits: `d96af87...`, `3131173...`.

Collects server tooltip, carrier movement, carrier-source SPECIALs, target effect additions/removals, owner relation and multi-target count. Exact support requires an isolated Web wire, immobilization consequence and clear lifecycle on movement/death.

### Child of Light (`childofthelight`)

Commits: `8a146615...`, `570e2343...`.

Searches same-caster/same-code SPECIAL records applied to a normal target and a Child-of-Light carrier, comparing value/amount/effect delta. Exact copy semantics still require unambiguous Light spell identity and proof of damage/resurrection exclusions.

### Hexing Attack (`hexingattack`)

Commits: `04c5f64...`, `602c2ed...`.

Collects same-target status wires/effect deltas after carrier attacks. Co-carried abilities can emit their own statuses; collision audit outside Hexing Attack is mandatory before proc labels/probability.

### Vulnerability to Light (`vulnerabilitytolight`)

Commits: `5eda29e...`, `90fdd63...`.

Registry footprint is **1239 observed entity tags**. The probe joins server `school=light` spellbooks with raw target SPECIAL/DAMAGE and non-carrier controls. A Light-capable actor does not make every DAMAGE a Light damaging spell.

### Death Wail (`deathwail`)

Commits: `bcdb67b...`, `7b54050...`.

Reference equation `(15 - initial target morale_raw) * carrier count * {1,0.5,0.25}` for distances 1/2/3 is **falsification-only**. Probe records activation shape, target set, footprint distance, target tags, initial raw morale and exact/floor/round/ceil agreement. No canonical morale field was added.

### Portal (`portal`)

Commits: `90805286...`, `078405b...`.

Registry description is empty. The audit therefore makes no semantic assumption and measures carrier actions, related opcodes/SPECIALs, damage, position/count/death transitions. Identity-only classification is allowed only if corpus shows no independent mechanic.

### Raging Blood (`ragingblood`)

Commits: `fc520a2a...`, `82502e67...`.

Measures same-owner hero context, carrier SPECIAL/effect transitions and attack/defense/speed/initiative/ATB deltas. It is not assumed equivalent to generic `enraged`; same-owner hero presence is only context and not faction truth.

### Shoot Bash (`shootbash`)

Commits: `28affecc...`, `27aba3f0...`; static-QA fix `9743e5d...`.

Collects ranged same-target SPECIAL/effect/ATB changes, relevant co-carriers and retaliation. Mechanical diagnostic context uses `{mechanical,warmachine,statix}` and is explicitly context-only. Warding Arrows / Shield Bash / other control collisions must be excluded before proc labels.

### Pack Hunter (`packhunter`)

Commits: `aa52fd5...`, `077d83c...`; static-QA fix `9ce34a07...`.

Geometry candidates are living same-owner/same-creature Pack Hunter stacks adjacent to the primary melee target. Observed secondaries are collected independently from **all** same-owner/same-creature raw DAMAGE sources, then compared for missing/extra helpers. This fixes the earlier tautological extra-source diagnostic.

### Purge (`purge`)

Commits: `f93ddd7f...`, `1fb06321...`; static-QA fix `ce3f520d...`.

Collects effect disappearance from attacked targets and same-target SPECIAL wires. Lethal target cleanup is explicitly excluded from candidate removal and reported separately. No effect wire id is called “positive” without server/corpus mapping.

### Six Heads (`six_heads`)

Current production support: **`modeled_collateral`**, but the existing model's held-out exact target set was only **0.282051** despite target precision/recall reported as 1.0.

Evidence commits: initial analyzer `ab4726b5...`, gate `7af71650...`, important geometry fix `4bb89ff7...`.

The first probe incorrectly used the actor's `state_before` position. The corrected probe anchors geometry at the actor's raw `MOVEMENT` destination immediately before primary DAMAGE, then compares all actor-source DAMAGE targets against all living visible enemy footprints adjacent to that attack anchor. This directly tests whether stale pre-move geometry explains the old 28% exact-set rate.

Additional integration risk found statically: generic `collateral_candidates()`/collateral application does not itself enforce enemy side for every secondary candidate. The server-side “enemy only” rule must be confirmed from raw tooltip/corpus before any narrow Six Heads runtime fix. Probe reports `friendly_damage_hits` explicitly.

No runtime change yet.

### Teleport (`teleport`)

Commits: analyzer `aea5ee59...`, gate `8f648056...`.

Collects tagged carrier MOVEMENT/melee-anchor commands, displacement vs server speed field, run modifier, source SPECIALs and state-after destination. It does not infer obstacle/path bypass from Chebyshev distance alone.

### Venom (`venom`)

Commits: analyzer `a73965e6...`, gate `899ece3e...`.

Two-stage audit: carrier attack -> same-target SPECIAL/effect addition, then lifecycle for candidate effects. HP loss is always compared against raw direct DAMAGE so ordinary hits are not mislabeled poison ticks. Exact 3-turn / 5-per-carrier-creature consequence requires a unique effect/wire mapping and corpus-perfect lifecycle; trigger probability remains unresolved.

### Torpor (`torpor`)

Current production support: **`modeled_proc`**. Existing simulator already models `proc_torpor`, cannot-act, retaliation suppression and wake-on-positive-DAMAGE. Reference metadata also claims maximum possible damage from Torpor carriers against a sleeping target; no corresponding explicit runtime implementation was found in the static audit.

Evidence commits: analyzer `e52fa1ba...`, gate `5a6c077b...`.

The audit uses raw `Stor/tor` only for a torpor-tagged melee source + primary target, verifies 3-turn effect, ineligible tags, immediate retaliation and wake-on-damage. The max-damage-against-sleeping-target component is kept explicitly **unresolved**.

### Shield Guard (`shieldguard`)

Commits: initial analyzer `1c3f825...`, gate `7aca9707...`, static-QA fix `97815daa...`.

Eligible candidates are living same-owner adjacent Shield Guard stacks. Observed records are independently collected from attacker-source DAMAGE to **all** live same-owner Shield Guard carriers before comparing missing/extra sources. The audit also records guard/target damage ratio and `2*guard_damage - target_damage` for rounding semantics. No exact support yet.

### Stone Garden (`stonegarden`)

Commits: analyzer `9846ef92...`, gate `94d1694e...`.

This is a modifier of the existing `stoning` proc, not assumed to be a separate action. The analyzer uses raw same-target `Ssta` on Stone-Garden carriers and records the pre-hit battlefield population in two interpretations:

- number of living visible stone-effect stacks;
- sum of creature counts in those stone-effect stacks.

Both historical/reference formulas `min(1, 0.10 + 0.05*N)` are treated as falsification candidates and compared against train-frequency on a battle-level chronological holdout. No probability change is allowed unless one interpretation robustly beats baseline.

Static integration implication: current C++ `ProcModel::probability_for` receives only attacker/target and therefore cannot represent battlefield stone population. If the holdout confirms the modifier, use a narrow battlefield-state feature derived from existing entity effects/counts; do **not** add a new canonical state field solely for this model.

## Existing closed work

- Paw Strike functional commit `8805bb78c02d727ffff150a3d3fe9e08c042ab3b`; observed I-record coverage **174/174** exact raw/state invariants.
- Do not redo Life Drain, Regeneration, Mana Feed, Mighty Slam or Paw Strike without new corpus evidence.

## Validation gate when hosted runners recover

No package after `97540370...` is claimed green. Use the normal PR pipeline unchanged:

1. C++ build + CTest;
2. inherited held-out planner replay validity gate;
3. full `python -m pytest python/tests -q` whole-corpus suite;
4. inspect emitted reports in weighted order, starting with Fire wire, Gribbomb, Taunt and Six Heads/Stone Garden high-leverage diagnostics;
5. Windows MSVC + TypeScript typecheck/build;
6. tighten assertions only from observed corpus invariants;
7. change runtime/support only for proven semantics;
8. regenerate held-out ability-risk and continue from refreshed `weighted_contribution`.
