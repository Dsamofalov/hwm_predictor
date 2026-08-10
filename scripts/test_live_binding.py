from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from local_api_test_utils import free_port, launch_daemon, request_json


def main() -> None:
    exe = sys.argv[1] if len(sys.argv) > 1 else "build/debug/solver-daemon"
    with tempfile.TemporaryDirectory() as td:
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        process = launch_daemon(
            exe,
            port,
            token_file=Path(td) / "token",
            pairing_code="123456",
            extra_env={
                "HWM_ENABLE_DEBUG": "1",
                "HWM_SEARCH_SIMS": "64",
                "HWM_SEARCH_MS": "1000",
                "HWM_SEARCH_DEPTH": "4",
            },
        )
        try:
            _, paired = request_json(
                base, "/pair", method="POST", payload={"code": "123456"}
            )
            token = paired["token"]
            assert request_json(
                base, "/debug/demo-state", method="POST", payload={}, token=token
            )[0] == 200
            _, status = request_json(base, "/status", token=token)
            assert status["revision"] >= 1 and status["state_hash"]

            code, recommendation = request_json(
                base, "/recommend", method="POST", token=token
            )
            assert code == 200, recommendation
            assert recommendation.get("status") == "ok", recommendation
            assert recommendation.get("state_hash") == status["state_hash"], (
                recommendation,
                status,
            )
            assert recommendation.get("state_revision") == status["revision"], (
                recommendation,
                status,
            )
            assert recommendation.get("battle_id") == "demo", recommendation
            print(
                "live recommendation binding contract: PASS",
                recommendation["state_revision"],
                recommendation["state_hash"],
            )
        finally:
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
