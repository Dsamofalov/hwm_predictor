from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import hashlib
import json


@dataclass(frozen=True)
class BattleUrl:
    original: str
    battle_id: str
    endpoint: str
    show_token: str | None
    show_param: str | None
    canonical_replay_url: str
    battle_payload_url: str
    payload_candidates: tuple[str, ...]

    def as_dict(self):
        return asdict(self)


def parse_battle_url(url: str) -> BattleUrl:
    url = url.strip()
    p = urlparse(url)
    if p.scheme not in {"http", "https"} or p.netloc.lower() not in {"heroeswm.ru", "www.heroeswm.ru"}:
        raise ValueError(f"unsupported host: {url}")
    q = parse_qs(p.query)
    warid = (q.get("warid") or [None])[0]
    if not warid or not warid.isdigit():
        raise ValueError(f"missing warid: {url}")
    endpoint = Path(p.path).name
    if endpoint not in {"war.php", "warlog.php", "battle.php"}:
        raise ValueError(f"unsupported endpoint: {endpoint}")

    show_param = "show" if q.get("show") else ("show_for_all" if q.get("show_for_all") else None)
    show = ((q.get(show_param) if show_param else None) or [None])[0]
    replay = f"https://www.heroeswm.ru/war.php?lt=-1&warid={warid}"
    if show:
        replay += f"&{show_param}={show}"

    base = f"https://www.heroeswm.ru/battle.php?lastturn=-3&warid={warid}"
    candidates = [base]
    if show:
        # Historical/public links have used both names over the years. Try both locally;
        # do not assume either is universally correct for current battles.
        candidates.insert(0, base + f"&show_for_all={show}")
        candidates.insert(1, base + f"&show={show}")
    payload_candidates = tuple(dict.fromkeys(candidates))
    return BattleUrl(url, warid, endpoint, show, show_param, replay, payload_candidates[0], payload_candidates)


def load_urls(path: Path) -> list[BattleUrl]:
    rows: list[BattleUrl] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        battle = parse_battle_url(line)
        if battle.battle_id in seen:
            continue
        seen.add(battle.battle_id)
        rows.append(battle)
    return rows


def write_manifest(rows: list[BattleUrl], out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row.as_dict(), ensure_ascii=False) + "\n")
    stats = {
        "battles": len(rows),
        "unique_battle_ids": len({r.battle_id for r in rows}),
        "with_show": sum(r.show_token is not None for r in rows),
        "without_show": sum(r.show_token is None for r in rows),
        "endpoint_counts": {k: sum(r.endpoint == k for r in rows) for k in sorted({r.endpoint for r in rows})},
    }
    stats["manifest_sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
    return stats
