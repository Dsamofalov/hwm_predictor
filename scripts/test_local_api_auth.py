from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from local_api_test_utils import free_port, launch_daemon, request_json


def main() -> None:
    exe = sys.argv[1] if len(sys.argv) > 1 else "build/debug/solver-daemon"
    with tempfile.TemporaryDirectory() as td:
        token_file = Path(td) / "pairing.token"
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        process = launch_daemon(
            exe,
            port,
            token_file=token_file,
            pairing_code="123456",
        )
        try:
            assert request_json(base, "/status")[0] == 401
            assert request_json(base, "/recommend", method="POST")[0] == 401
            assert request_json(
                base, "/runtime-probe", method="POST", payload={"x": 1}
            )[0] == 401
            assert request_json(
                base, "/pair", method="POST", payload={"code": "000000"}
            )[0] == 403
            status, paired = request_json(
                base, "/pair", method="POST", payload={"code": "123456"}
            )
            assert status == 200 and paired.get("paired") is True
            token = paired.get("token")
            assert isinstance(token, str) and len(token) == 64
            assert token_file.read_text().strip() == token
            assert request_json(base, "/status", token=token)[0] == 200
            status, recommendation = request_json(
                base, "/recommend", method="POST", token=token
            )
            assert status == 200 and recommendation.get("status") == "not_ready"
        finally:
            process.terminate()
            process.wait(timeout=5)

        # A restart rotates only the human pairing code, not the bearer secret.
        port2 = free_port()
        base2 = f"http://127.0.0.1:{port2}"
        process2 = launch_daemon(
            exe,
            port2,
            token_file=token_file,
            pairing_code="654321",
        )
        try:
            assert request_json(base2, "/status", token=token)[0] == 200
            status, paired2 = request_json(
                base2, "/pair", method="POST", payload={"code": "654321"}
            )
            assert status == 200 and paired2.get("token") == token
        finally:
            process2.terminate()
            process2.wait(timeout=5)

    print("local API pairing/auth integration: PASS")


if __name__ == "__main__":
    main()
