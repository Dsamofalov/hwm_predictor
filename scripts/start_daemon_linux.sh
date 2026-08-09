#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export HWM_CAPTURE_DIR="${HWM_CAPTURE_DIR:-$PWD/data/captured-live}"
export HWM_SEARCH_MS="${HWM_SEARCH_MS:-5000}"
export HWM_SEARCH_SIMS="${HWM_SEARCH_SIMS:-100000}"
mkdir -p "$HWM_CAPTURE_DIR"
EXE=./build/release/solver-daemon
[[ -x "$EXE" ]] || EXE=./build/debug/solver-daemon
[[ -x "$EXE" ]] || { echo "solver-daemon not found; run bootstrap first" >&2; exit 2; }
echo "Daemon: $EXE"
echo "Raw battle bodies: $HWM_CAPTURE_DIR"
echo "Planner budget: $HWM_SEARCH_MS ms / max $HWM_SEARCH_SIMS simulations"
exec "$EXE"
