from pathlib import Path
from hwm_solver.knowledge.external_catalog import (
    build_reference_catalog,
    parse_daily_help_creatures,
    parse_hwm_daily_slugs,
)


def test_daily_help_parser_minimal(tmp_path: Path):
    p = tmp_path / "c.html"
    p.write_text("""<table><tr align='center'><td><img src='../img/creatures/icons/x.png'><td><a href='../creature.php?id=42'>Лучники</a><td>2<td>Рыц.<td>4<td>3<td>2-5<td>10<td>4<td>8<td>12<td>&ndash;<td>6<td>19<td><a href='../ability.php?name=shooter'>Стрелок</a>, <a href='../ability.php?name=nopenalty'>Нет штрафов</a></tr></table>""", encoding="utf-8")
    rows = parse_daily_help_creatures(p)
    assert len(rows) == 1
    c = rows[0]
    assert c.id == 42 and c.name == "Лучники"
    assert (c.attack, c.defense, c.min_damage, c.max_damage, c.hp) == (4.0, 3.0, 2.0, 5.0, 10.0)
    assert [a.code for a in c.abilities] == ["shooter", "nopenalty"]


def test_hwm_daily_slug_parser(tmp_path: Path):
    p = tmp_path / "d.html"
    p.write_bytes("""<a title='Лучники' href='https://www.heroeswm.ru/army_info.php?name=bowman'>x</a>""".encode("cp1251"))
    slugs = parse_hwm_daily_slugs(p)
    assert slugs["лучники"] == "bowman"


def test_combined_catalog(tmp_path: Path):
    c = tmp_path / "c.html"
    c.write_text("""<tr align='center'><td><td><a href='../creature.php?id=1'>Тест</a><td>1<td>-<td>1<td>2<td>3-4<td>5<td>6<td>7<td>-<td>-<td>-<td>8<td><a href='../ability.php?name=flyer'>Летающее существо</a></tr>""", encoding="utf-8")
    d = tmp_path / "d.html"
    d.write_bytes("""<a title='Тест' href='https://www.heroeswm.ru/army_info.php?name=test'>x</a>""".encode("cp1251"))
    x = build_reference_catalog(c, d)
    assert x["coverage"]["creatures"] == 1
    assert x["coverage"]["abilities"] == 1
    assert x["creatures"][0]["hwm_name"] == "test"
