# Game / Ability catalog

Current authoritative rule:

- **Raw battle payload (`init.txt`) ability tags decide what the current entity actually has.**
- `data/reference/creatures_daily_help.html` and `creatures_hwm_daily.html` are reference metadata only (names/descriptions/coverage).
- Old historical parsed state dumps are not ground truth.

Latest generated catalog: `generated_v4.json` / `generated_v4.tsv`.

Current raw-corpus coverage:

- 644 creature IDs
- 421 ability codes in merged catalog
- 405 ability tags observed directly in corpus
- 109 perk codes
- 189 special codes
- 362 ability tags with server tooltip descriptions

`ability_registry.json` assigns each ability a support status (`exact_search`, `partial_exact`, `modeled_proc`, `modeled_collateral`, `modeled_kill_trigger`, `learned_damage`, etc.) and risk weight.
