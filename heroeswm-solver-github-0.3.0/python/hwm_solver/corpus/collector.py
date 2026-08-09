from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen
import hashlib
import json
import time

from .urls import load_urls

UA = "HeroesWM-Solver-Research/0.1"


def collect(url_file: Path, out: Path, delay: float = 2.0, limit: int | None = None, enable: bool = False) -> dict:
    if not enable:
        raise RuntimeError("Remote collection is disabled by default; pass --enable only after checking current game rules.")
    out.mkdir(parents=True, exist_ok=True)
    rows = load_urls(url_file)
    rows = rows[:limit] if limit else rows
    ok = failed = skipped = 0
    for i, battle in enumerate(rows, 1):
        dest = out / f"{battle.battle_id}.txt"
        meta = out / f"{battle.battle_id}.json"
        if dest.exists() and dest.stat().st_size:
            ok += 1
            skipped += 1
            continue

        record = {
            "battle_id": battle.battle_id,
            "original_url": battle.original,
            "payload_candidates": list(battle.payload_candidates),
            "fetched_at": time.time(),
            "attempts": [],
        }
        data: bytes | None = None
        chosen_url: str | None = None
        for candidate in battle.payload_candidates:
            attempt = {"url": candidate}
            try:
                req = Request(candidate, headers={"User-Agent": UA, "Accept": "text/plain,text/html,*/*"})
                with urlopen(req, timeout=30) as response:
                    candidate_data = response.read()
                    status = getattr(response, "status", 200)
                    content_type = response.headers.get("Content-Type", "")
                attempt.update(http_status=status, bytes=len(candidate_data), content_type=content_type)
                record["attempts"].append(attempt)
                if status == 200 and candidate_data:
                    data = candidate_data
                    chosen_url = candidate
                    break
            except Exception as exc:  # noqa: BLE001 - collector must continue through corpus
                attempt["error"] = repr(exc)
                record["attempts"].append(attempt)

        if data is not None:
            dest.write_bytes(data)
            record.update(
                status="ok",
                chosen_url=chosen_url,
                bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
            )
            ok += 1
        else:
            record["status"] = "error"
            failed += 1

        meta.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{i}/{len(rows)}] {battle.battle_id}: {record['status']}")
        if i < len(rows):
            time.sleep(max(0.5, delay))
    return {"requested": len(rows), "ok": ok, "failed": failed, "skipped_existing": skipped}
