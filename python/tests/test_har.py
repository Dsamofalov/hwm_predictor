import base64
import json
from pathlib import Path
from hwm_solver.corpus.har import import_har


def test_import_har(tmp_path: Path):
    payload = "turns=>2^M007"
    har = {
        "log": {"entries": [
            {"request": {"url": "https://www.heroeswm.ru/battle.php?lastturn=-3&warid=123"},
             "response": {"status": 200, "content": {"text": base64.b64encode(payload.encode()).decode(), "encoding": "base64", "mimeType": "text/plain"}}},
            {"request": {"url": "https://example.com/x"}, "response": {"status": 200, "content": {"text": "ignore"}}},
        ]}
    }
    src = tmp_path / "capture.har"
    src.write_text(json.dumps(har), encoding="utf-8")
    out = tmp_path / "raw"
    report = import_har(src, out)
    assert report == {"entries": 2, "imported": 1, "skipped": 1, "battles": 1}
    assert (out / "123.txt").read_text() == payload
