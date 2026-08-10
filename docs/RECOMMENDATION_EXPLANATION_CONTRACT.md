# Recommendation explanation contract

Status: main-lane implementation design; not yet wired into production API/UI.

The product specification requires every recommendation to include a short human-readable explanation. This explanation is a **read-only rendering of already computed planner facts**. It must not invent a creature mechanic, hidden server rule, probability, or causal claim that is not represented by the canonical state/search result.

## Required fields

A successful recommendation explanation must be derivable from the same revision/hash as the recommendation and contain:

1. **Action summary** — action type plus target and/or destination when present.
2. **Selection reason** — whether the chosen action clearly leads the next visited alternative in risk-adjusted planner score, or whether the top actions are close.
3. **Confidence/risk qualifier** — calibrated P(win), candidate uncertainty, and ability-risk tier using existing numeric planner outputs.
4. **Optional safety note** — only from existing recommendation warnings; warnings are not themselves the explanation.

## Forbidden content

- no claim that an unmodeled ability definitely will/will not proc;
- no invented tactical causal story (for example, "this blocks retaliation") unless the exact modeled action/ability branch explicitly establishes it;
- no raw protocol payload, bearer token, full HeroesWM URL, or hidden runtime-object data;
- no claim that replay agreement or planner score is measured live win-rate uplift;
- no explanation for a stale/cancelled/not-ready result as though it were an executable recommendation.

## Deterministic wording rules

The API should expose both a compact structured explanation object and a ready-to-render summary string. Suggested structured shape:

```json
{
  "summary": "Attack target 12 from (6,4); this is the highest risk-adjusted visited action, but the top alternatives are close.",
  "action": "MELEE_ATTACK",
  "selection_margin": 0.031,
  "confidence": "guarded",
  "p_win": 0.68,
  "uncertainty": 0.22,
  "ability_risk": 0.27
}
```

The numeric values remain authoritative; the wording is only a deterministic presentation layer.

### Selection margin

For visited candidates sorted by the planner's existing result ordering, define a presentation-only margin as `best.score - second.score` when an alternative exists. Do not reinterpret this value as probability. Suggested wording tiers can be fixed constants and must have unit tests.

### Confidence

Use existing outputs only. A conservative presentation tier may combine candidate uncertainty and `ability_risk`, but its thresholds must be explicit constants with tests. The implementation must not silently override the planner's `p_win`.

## API / UI integration gate

Before marking the specification item complete:

- `Recommendation`/JSON must expose the explanation bound to the same `state_hash`/revision;
- successful responses have a non-empty bounded summary;
- stale/cancelled/not-ready responses never carry an executable-looking explanation;
- side panel renders the server-provided explanation and continues rendering existing warnings separately;
- pairing/auth, stale-cancellation, live-binding and 120-state recommendation-validity integrations still pass;
- add regression coverage for melee/ranged/move/wait-defend and close-alternative wording.

This layer does not change action generation, simulator transitions, search scores or HeroesWM acquisition traffic.
