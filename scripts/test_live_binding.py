from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from local_api_test_utils import free_port, launch_daemon, request_json


def main() -> None:
    exe = sys.argv[1] if len(sys.argv) > 1 else "build/debug/solver-daemon"
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "live_closed_loop"
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

            def capture(name: str, captured_at: int, sequence_hint: int):
                return request_json(
                    base,
                    "/capture",
                    method="POST",
                    payload={
                        "battleId": "sanitized-live",
                        "capturedAt": captured_at,
                        "source": "xhr",
                        "urlKind": "battle_update",
                        "sequenceHint": sequence_hint,
                        "body": (fixture / name).read_text(encoding="utf-8"),
                        "url": "https://example.invalid/battle.php?warid=sanitized-live",
                    },
                    token=token,
                )

            code, first = capture("semantic_snapshot.txt", 10000, 41)
            assert code == 200 and first.get("accepted"), first
            assert first.get("canonical_state_updated"), first
            assert first.get("revision") == 1, first
            assert first.get("state_hash"), first
            _, first_status = request_json(base, "/status", token=token)
            assert first_status.get("revision") == first["revision"], first_status
            assert first_status.get("state_hash") == first["state_hash"], first_status

            code, heartbeat = capture("heartbeat.txt", 10050, 42)
            assert code == 200 and heartbeat.get("accepted"), heartbeat
            assert heartbeat.get("reason") == "heartbeat_noop", heartbeat
            assert not heartbeat.get("canonical_state_updated"), heartbeat
            assert heartbeat.get("revision") == first["revision"], heartbeat
            assert heartbeat.get("state_hash") == first["state_hash"], heartbeat
            _, heartbeat_status = request_json(base, "/status", token=token)
            assert heartbeat_status.get("revision") == first_status["revision"], heartbeat_status
            assert heartbeat_status.get("state_hash") == first_status["state_hash"], heartbeat_status

            # MAIN-world sequenceHint is process-local and can reset after a page/service-worker
            # lifecycle. A newer semantic capture must still advance canonical state even when
            # the hint goes backwards; capturedAt and protocol continuity are authoritative.
            code, second = capture("incremental_update.txt", 10100, 1)
            assert code == 200 and second.get("accepted"), second
            assert second.get("canonical_state_updated"), second
            assert second.get("revision") == first["revision"] + 1, second
            assert second.get("state_hash") and second["state_hash"] != first["state_hash"], second
            _, second_status = request_json(base, "/status", token=token)
            assert second_status.get("revision") == second["revision"], second_status
            assert second_status.get("state_hash") == second["state_hash"], second_status
            print(
                "live HTTP capture progression contract: PASS",
                first["revision"],
                second["revision"],
                second["state_hash"],
            )

            assert request_json(
                base, "/debug/demo-state", method="POST", payload={}, token=token
            )[0] == 200
            _, status = request_json(base, "/status", token=token)
            assert status["revision"] >= second["revision"] + 1 and status["state_hash"]

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
