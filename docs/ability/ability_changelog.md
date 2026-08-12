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
