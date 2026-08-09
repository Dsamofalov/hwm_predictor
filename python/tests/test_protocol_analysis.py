from pathlib import Path
from hwm_solver.protocol.analyze import analyze_directory


def test_protocol_directory_analysis(tmp_path: Path):
    (tmp_path / "1.txt").write_text("turns=>3^M007^luck^mystery=1", encoding="utf-8")
    report = analyze_directory(tmp_path, top_n=10)
    assert report["files"] == 1
    assert report["unique_entity_hints"] == 1
    assert report["top_entity_hints"][0][0] == 7
    assert report["top_unknown_tokens"]
