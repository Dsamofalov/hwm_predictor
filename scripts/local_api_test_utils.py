from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# Local daemon integration tests must never depend on machine/user proxy settings.
# This matters for Windows services, which can inherit a different proxy context
# from an interactive user session.
_NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request_json(
    base: str,
    path: str,
    *,
    method: str = "GET",
    payload: Any = None,
    token: str | None = None,
    timeout: float = 5,
):
    data = None if payload is None else json.dumps(payload).encode()
    headers: dict[str, str] = {}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with _NO_PROXY_OPENER.open(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def _stop_and_collect(process: subprocess.Popen[str]) -> str:
    if process.poll() is None:
        process.terminate()
    try:
        stdout, _ = process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, _ = process.communicate(timeout=5)
    return stdout or ""


def wait_health(base: str, process: subprocess.Popen[str], timeout: float = 8) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout is not None else ""
            raise AssertionError(
                f"daemon exited before health check, code={process.returncode}\n{output}"
            )
        try:
            if request_json(base, "/health", timeout=1)[0] == 200:
                return
        except Exception as exc:  # diagnostics are reported after the bounded retry window
            last_error = exc
        time.sleep(0.05)

    output = _stop_and_collect(process)
    raise AssertionError(
        "daemon did not become healthy"
        + (f"; last client error: {last_error!r}" if last_error is not None else "")
        + (f"\ndaemon output:\n{output}" if output else "")
    )


def launch_daemon(
    exe: str,
    port: int,
    *,
    token_file: Path,
    pairing_code: str,
    extra_env: dict[str, str] | None = None,
) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["HWM_TOKEN_FILE"] = str(token_file)
    env["HWM_PAIRING_CODE"] = pairing_code
    if extra_env:
        env.update(extra_env)
    process = subprocess.Popen(
        [exe, str(port)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    wait_health(f"http://127.0.0.1:{port}", process)
    return process
