from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: test_corpus_structural_budget.py <corpus-check.exe> <corpus> <max-invalid>")
    exe = Path(sys.argv[1])
    corpus = Path(sys.argv[2])
    max_invalid = int(sys.argv[3])

    proc = subprocess.run([str(exe), str(corpus)], text=True, encoding="utf-8", errors="replace", capture_output=True)
    if proc.returncode not in (0, 1):
        raise SystemExit(f"corpus-check exited unexpectedly with {proc.returncode}:\n{proc.stderr}")
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip().startswith("{")]
    if not lines:
        raise SystemExit(f"corpus-check JSON missing. stdout={proc.stdout!r} stderr={proc.stderr!r}")
    report = json.loads(lines[-1])

    assert report["battles"] == 866, report
    assert report["with_unknown"] == 0, report
    assert report["coverage_min"] == 1, report
    assert report["coverage_mean"] == 1, report
    assert report["structural_not_ready"] <= max_invalid, report
    assert report["invalid"] <= max_invalid, report
    assert report["structural_ready"] >= report["battles"] - max_invalid, report
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
