#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
cmake --preset debug
cmake --build --preset debug
ctest --preset debug --output-on-failure
cmake --preset release
cmake --build --preset release
ctest --preset release --output-on-failure
PY="${PWD}/.venv/bin/python"
[[ -x "$PY" ]] || PY=python3
export PYTHONPATH="$PWD/python"
"$PY" -m pytest -q
"$PY" -m hwm_solver.cli manifest data/input/battle_urls.txt data/manifests/battles.jsonl
(cd extension && npx tsc --noEmit && npm run build)
./build/release/planner-demo 5000
echo 'ALL CHECKS PASSED'
