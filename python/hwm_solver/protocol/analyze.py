from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .decoder import decode, tokenize

_PREFIX = re.compile(r"^([A-Za-z_]+)")


def analyze_directory(raw_dir: Path, top_n: int = 50) -> dict:
    files = sorted(raw_dir.glob("*.txt"))
    coverage: list[float] = []
    unknown = Counter()
    token_prefixes = Counter()
    entity_ids = Counter()
    safe = 0
    empty = 0

    for path in files:
        payload = path.read_text(encoding="utf-8", errors="replace")
        if not payload:
            empty += 1
            continue
        result = decode(payload, path.stem)
        coverage.append(result.coverage)
        safe += int(result.training_safe)
        entity_ids.update(result.entity_hints)
        for token in tokenize(payload):
            m = _PREFIX.match(token)
            token_prefixes.update([m.group(1).lower() if m else "<nonalpha>"])
        for token in result.unknown:
            compact = token[:120]
            unknown.update([compact])

    def pct(v: float) -> float:
        return round(v * 100.0, 3)

    ordered = sorted(coverage)
    q = lambda f: ordered[min(len(ordered) - 1, int((len(ordered) - 1) * f))] if ordered else 0.0
    return {
        "raw_dir": str(raw_dir),
        "files": len(files),
        "empty_files": empty,
        "training_safe": safe,
        "training_safe_pct": pct(safe / max(1, len(files) - empty)),
        "coverage": {
            "min": q(0.0),
            "p25": q(0.25),
            "median": q(0.5),
            "p75": q(0.75),
            "p90": q(0.9),
            "max": q(1.0),
        },
        "unique_entity_hints": len(entity_ids),
        "top_entity_hints": entity_ids.most_common(top_n),
        "top_token_prefixes": token_prefixes.most_common(top_n),
        "top_unknown_tokens": unknown.most_common(top_n),
    }


def write_analysis(raw_dir: Path, output: Path, top_n: int = 50) -> dict:
    report = analyze_directory(raw_dir, top_n=top_n)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
