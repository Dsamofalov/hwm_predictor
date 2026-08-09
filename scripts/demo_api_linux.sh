#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
EXE=./build/release/solver-daemon
[[ -x "$EXE" ]] || EXE=./build/debug/solver-daemon
HWM_ENABLE_DEBUG=1 HWM_SEARCH_MS=1000 HWM_SEARCH_SIMS=5000 "$EXE" >/tmp/hwm-demo-daemon.log 2>&1 &
PID=$!
trap 'kill "$PID" 2>/dev/null || true' EXIT
sleep .4
curl -fsS http://127.0.0.1:38471/health; echo
curl -fsS -X POST http://127.0.0.1:38471/debug/demo-state; echo
curl -fsS -X POST http://127.0.0.1:38471/recommend; echo
