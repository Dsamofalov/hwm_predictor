from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_ALLOWED = {"battle.php", "war.php", "warlog.php"}


def _battle_id(url: str) -> str | None:
    try:
        p = urlparse(url)
        if p.netloc.lower() not in {"heroeswm.ru", "www.heroeswm.ru"}:
            return None
        if Path(p.path).name not in _ALLOWED:
            return None
        warid = (parse_qs(p.query).get("warid") or [None])[0]
        return warid if warid and warid.isdigit() else None
    except Exception:
        return None


def import_har(har_file: Path, out_dir: Path) -> dict:
    data = json.loads(har_file.read_text(encoding="utf-8"))
    entries = data.get("log", {}).get("entries", [])
    out_dir.mkdir(parents=True, exist_ok=True)
    imported = skipped = 0
    per_battle: dict[str, int] = {}
    manifest: list[dict] = []

    for entry in entries:
        request = entry.get("request", {})
        response = entry.get("response", {})
        url = str(request.get("url", ""))
        battle_id = _battle_id(url)
        if not battle_id:
            skipped += 1
            continue
        content = response.get("content", {})
        text = content.get("text")
        if text is None:
            skipped += 1
            continue
        if content.get("encoding") == "base64":
            try:
                raw = base64.b64decode(text)
            except Exception:
                skipped += 1
                continue
        else:
            raw = str(text).encode("utf-8")
        seq = per_battle.get(battle_id, 0) + 1
        per_battle[battle_id] = seq
        suffix = "" if seq == 1 else f"_{seq}"
        dest = out_dir / f"{battle_id}{suffix}.txt"
        dest.write_bytes(raw)
        manifest.append({
            "battle_id": battle_id,
            "sequence": seq,
            "url": url,
            "status": response.get("status"),
            "mime_type": content.get("mimeType", ""),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "file": dest.name,
        })
        imported += 1

    (out_dir / "har_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"entries": len(entries), "imported": imported, "skipped": skipped, "battles": len(per_battle)}
