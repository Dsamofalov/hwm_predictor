from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def request(base: str, path: str, *, method: str = "GET", payload=None, token: str | None = None):
    data = None if payload is None else json.dumps(payload).encode()
    headers = {}
    if data is not None: headers["Content-Type"] = "application/json"
    if token: headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def wait_health(base: str) -> None:
    deadline = time.time() + 8
    while time.time() < deadline:
        try:
            if request(base, "/health")[0] == 200: return
        except Exception:
            pass
        time.sleep(0.05)
    raise AssertionError("daemon did not become healthy")


def launch(exe: str, port: int, token_file: Path, code: str):
    env = os.environ.copy(); env["HWM_TOKEN_FILE"] = str(token_file); env["HWM_PAIRING_CODE"] = code
    p = subprocess.Popen([exe, str(port)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    wait_health(f"http://127.0.0.1:{port}")
    return p


def main() -> None:
    exe = sys.argv[1] if len(sys.argv) > 1 else "build/debug/solver-daemon"
    with tempfile.TemporaryDirectory() as td:
        token_file = Path(td) / "pairing.token"
        port = free_port(); base = f"http://127.0.0.1:{port}"
        p = launch(exe, port, token_file, "123456")
        try:
            assert request(base, "/status")[0] == 401
            assert request(base, "/recommend", method="POST")[0] == 401
            assert request(base, "/runtime-probe", method="POST", payload={"x": 1})[0] == 401
            assert request(base, "/pair", method="POST", payload={"code": "000000"})[0] == 403
            status, paired = request(base, "/pair", method="POST", payload={"code": "123456"})
            assert status == 200 and paired.get("paired") is True
            token = paired.get("token"); assert isinstance(token, str) and len(token) == 64
            assert token_file.read_text().strip() == token
            assert request(base, "/status", token=token)[0] == 200
            status, rec = request(base, "/recommend", method="POST", token=token)
            assert status == 200 and rec.get("status") == "not_ready"
        finally:
            p.terminate(); p.wait(timeout=5)

        # A restart rotates only the human pairing code, not the bearer secret.
        port2 = free_port(); base2 = f"http://127.0.0.1:{port2}"
        p2 = launch(exe, port2, token_file, "654321")
        try:
            assert request(base2, "/status", token=token)[0] == 200
            status, paired2 = request(base2, "/pair", method="POST", payload={"code": "654321"})
            assert status == 200 and paired2.get("token") == token
        finally:
            p2.terminate(); p2.wait(timeout=5)
    print("local API pairing/auth integration: PASS")


if __name__ == "__main__": main()
