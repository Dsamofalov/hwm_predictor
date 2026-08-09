from hwm_solver.protocol.spell_effect_analyze import parse_spellbook


def test_parse_spellbook_all_adjacent_records():
    blob = (
        "fast-4-1-40-0-1-neutral-slow-4-1-20-0-1-neutral-"
        "bless-4-1-100-0-1-neutral-mfast-8-1-40-0-1-neutral-^abc"
    )
    book = parse_spellbook(blob)
    assert set(book) == {"fast", "slow", "bless", "mfast"}
    assert book["fast"].mana_cost == 4
    assert book["fast"].effect == 40
    assert book["mfast"].mana_cost == 8
