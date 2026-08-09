#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for cmd in python3 cmake ninja node npm c++; do
  command -v "$cmd" >/dev/null || { echo "Missing command: $cmd" >&2; exit 2; }
done
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev]'
cmake --preset debug
cmake --build --preset debug
ctest --preset debug --output-on-failure
(cd extension && npm install && npm run typecheck && npm run build)
PYTHONPATH=python python -m hwm_solver.cli manifest data/input/battle_urls.txt data/manifests/battles.jsonl
echo "Bootstrap complete. Run ./scripts/start_daemon_linux.sh or ./scripts/validate_linux.sh"
