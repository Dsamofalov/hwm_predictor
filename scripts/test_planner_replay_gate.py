from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(
            "usage: test_planner_replay_gate.py <planner-eval> [corpus=hwm_battles] [states=120] [low=1] [high=120]"
        )
    exe = Path(sys.argv[1])
    corpus = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("hwm_battles")
    states = int(sys.argv[3]) if len(sys.argv) > 3 else 120
    low = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    high = int(sys.argv[5]) if len(sys.argv) > 5 else 120

    proc = subprocess.run(
        [str(exe), str(corpus), str(states), str(low), str(high), "0"],
        text=True,
        capture_output=True,
        timeout=240,
    )
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    lines = [line for line in proc.stdout.splitlines() if line.strip().startswith("{")]
    if not lines:
        raise AssertionError(f"planner-eval emitted no JSON; exit={proc.returncode}")
    report = json.loads(lines[-1])

    assert proc.returncode == 0, report
    assert report["sampled_states"] >= 100, report
    assert report["sampled_states"] == states, report
    assert report["sampled_battles"] >= 50, report
    assert report["high_ok"] == report["sampled_states"], report
    assert report["high_valid_recommendations"] == report["sampled_states"], report
    assert report["high_invalid_recommendations"] == 0, report
    assert report["high_state_hash_mismatch"] == 0, report
    assert report["high_illegal_best"] == 0, report
    assert report["high_illegal_alternatives"] == 0, report
    assert report["high_nonfinite_metrics"] == 0, report
    print(
        "planner replay validity gate: PASS",
        report["sampled_states"],
        "states from",
        report["sampled_battles"],
        "held-out battles",
    )


if __name__ == "__main__":
    main()
