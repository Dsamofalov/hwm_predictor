from pathlib import Path
from hwm_solver.corpus.urls import parse_battle_url, load_urls


def test_parse_show_variant():
    b = parse_battle_url("https://www.heroeswm.ru/war.php?lt=-1&warid=123&show=ABC")
    assert b.battle_id == "123" and b.show_token == "ABC" and b.show_param == "show"
    assert b.payload_candidates[0].endswith("show_for_all=ABC")
    assert any(x.endswith("show=ABC") for x in b.payload_candidates)


def test_parse_show_for_all_variant():
    b = parse_battle_url("https://www.heroeswm.ru/warlog.php?warid=456&show_for_all=XYZ")
    assert b.endpoint == "warlog.php" and b.show_param == "show_for_all"
    assert "show_for_all=XYZ" in b.canonical_replay_url


def test_real_list():
    rows = load_urls(Path("data/input/battle_urls.txt"))
    assert len(rows) == 866 and len({r.battle_id for r in rows}) == 866
