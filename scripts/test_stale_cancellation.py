from __future__ import annotations

import concurrent.futures
import sys
import tempfile
import time
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
                "HWM_SEARCH_SIMS": "100000000",
                "HWM_SEARCH_MS": "10000",
                "HWM_SEARCH_DEPTH": "20",
                "HWM_SEARCH_CANCEL_POLL": "1",
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
            _, before = request_json(base, "/status", token=token)
            assert before["revision"] >= 1

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    request_json,
                    base,
                    "/recommend",
                    method="POST",
                    token=token,
                    timeout=15,
                )
                time.sleep(0.15)

                # The authenticated live client emitted `t=950` battle.php frames. They are
                # transport heartbeats, not canonical updates, and must not publish a
                # revision/hash or cancel this in-flight search.
                heartbeat_status, heartbeat = request_json(
                    base,
                    "/capture",
                    method="POST",
                    payload={
                        "battleId": "demo",
                        "source": "xhr",
                        "urlKind": "battle_update",
                        "url": "https://example.invalid/battle.php?warid=demo",
                        "capturedAt": int(time.time() * 1000),
                        "sequenceHint": 100,
                        "body": "t=950",
                    },
                    token=token,
                )
                assert heartbeat_status == 200 and heartbeat.get("accepted") is True, heartbeat
                assert heartbeat.get("canonical_state_updated") is False, heartbeat
                assert heartbeat.get("reason") == "heartbeat_noop", heartbeat
                assert heartbeat.get("revision") == before["revision"], heartbeat
                assert heartbeat.get("state_hash") == before["state_hash"], heartbeat
                _, after_heartbeat = request_json(base, "/status", token=token)
                assert after_heartbeat["revision"] == before["revision"], after_heartbeat
                assert after_heartbeat["state_hash"] == before["state_hash"], after_heartbeat

                # A real canonical publication still invalidates the pre-change search.
                assert request_json(
                    base, "/debug/demo-state", method="POST", payload={}, token=token
                )[0] == 200
                status, result = future.result(timeout=8)

            _, after = request_json(base, "/status", token=token)
            assert status == 200 and result.get("status") == "stale", result
            assert result.get("cancelled_search") is True, result
            assert result.get("requested_revision") == before["revision"], result
            assert result.get("current_revision") == before["revision"] + 1, result
            assert before["state_hash"] == after["state_hash"], (
                "test must prove revision invalidation even with equal hash"
            )
            assert result.get("elapsed_ms", 99999) < 5000, result
            print(
                "heartbeat-neutral stale search cooperative cancellation: PASS",
                result.get("simulations"),
                result.get("elapsed_ms"),
            )
        finally:
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
