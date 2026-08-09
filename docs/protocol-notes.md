# Protocol research notes

## Confirmed integration shape

Historical and recent public HeroesWM forum stack traces point to an HTML5 battle flow where an XHR loader passes data through functions named similarly to `refresh_data_onLoad` / `loader_data_onLoad`, then `razbor_data`, then object processing such as `set_obj_data` / `procceed_data`. Public battle references also repeatedly use `battle.php?lastturn=-3&warid=...` for battle-log data.

A 2026 forum discussion explicitly describes per-battle creature/object ordering using `MNNN` identifiers. Therefore the bootstrap decoder preserves and indexes uppercase `M<digits>` occurrences but does **not** yet assume the surrounding grammar.

Research references (used as clues, not as a substitute for real captures):

- https://www.heroeswm.ru/forum_messages.php?tid=3070955
- https://www.heroeswm.ru/forum_messages.php?tid=3070937
- https://www.heroeswm.ru/forum_messages.php?tid=3079345
- https://www.heroeswm.ru/forum_messages.php?tid=2349623

## Current decoder policy

1. Raw compact body is immutable input.
2. Tokenization is deliberately simple and loss-aware.
3. Recognized hints are emitted as structured events.
4. UNKNOWN records are retained verbatim for clustering.
5. Coverage below 90%, or absence of entity reconstruction, fails the training gate.
6. A partial decode cannot silently become the observed canonical state used by planner.

## Next reverse-engineering loop

```text
real extension/HAR capture
  -> `hwm analyze`
  -> identify dominant UNKNOWN token families
  -> add one grammar rule
  -> golden fixture from real payload
  -> differential/replay test
  -> recompute coverage
```

Do not implement undocumented field meanings solely from numeric coincidence. Each semantic mapping should be backed by multiple replay transitions or an observable client-state correlation.
