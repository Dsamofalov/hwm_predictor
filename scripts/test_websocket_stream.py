from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import sys
import tempfile
from pathlib import Path

from local_api_test_utils import free_port, launch_daemon, request_json

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def recv_until(sock: socket.socket, marker: bytes) -> bytes:
    data = b""
    while marker not in data:
        data += sock.recv(4096)
    return data


def take(sock: socket.socket, buffer: bytes, size: int) -> tuple[bytes, bytes]:
    data = bytearray(buffer)
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        assert chunk, "websocket closed while reading frame"
        data.extend(chunk)
    return bytes(data[:size]), bytes(data[size:])


def recv_frame(sock: socket.socket, buffer: bytes = b""):
    header, buffer = take(sock, buffer, 2)
    assert len(header) == 2 and (header[0] & 0x0F) == 1, header
    size = header[1] & 0x7F
    if size == 126:
        extension, buffer = take(sock, buffer, 2)
        size = int.from_bytes(extension, "big")
    elif size == 127:
        extension, buffer = take(sock, buffer, 8)
        size = int.from_bytes(extension, "big")
    assert not (header[1] & 0x80)
    data, buffer = take(sock, buffer, size)
    return json.loads(data.decode()), buffer


def connect_ws(port: int, token: str):
    sock = socket.create_connection(("127.0.0.1", port), timeout=3)
    sock.settimeout(4)
    key = base64.b64encode(os.urandom(16)).decode()
    request = (
        f"GET /ws HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        f"Sec-WebSocket-Protocol: hwm-v1, hwm-bearer.{token}\r\n"
        "Origin: chrome-extension://integration-test\r\n\r\n"
    ).encode()
    sock.sendall(request)
    received = recv_until(sock, b"\r\n\r\n")
    header_bytes, buffer = received.split(b"\r\n\r\n", 1)
    headers = (header_bytes + b"\r\n\r\n").decode("ascii")
    assert "101 Switching Protocols" in headers, headers
    expected = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
    assert f"Sec-WebSocket-Accept: {expected}" in headers, headers
    assert "Sec-WebSocket-Protocol: hwm-v1" in headers
    return sock, buffer


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
            extra_env={"HWM_ENABLE_DEBUG": "1"},
        )
        try:
            _, paired = request_json(
                base, "/pair", method="POST", payload={"code": "123456"}
            )
            token = paired["token"]

            bad = socket.create_connection(("127.0.0.1", port), timeout=3)
            bad.sendall(
                (
                    f"GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                    "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                    "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
                    "Sec-WebSocket-Version: 13\r\n"
                    "Sec-WebSocket-Protocol: hwm-v1, hwm-bearer.bad\r\n"
                    "Origin: chrome-extension://integration-test\r\n\r\n"
                ).encode()
            )
            bad_headers = recv_until(bad, b"\r\n\r\n")
            assert bad_headers.startswith(b"HTTP/1.1 401 "), bad_headers
            assert b"101 Switching Protocols" not in bad_headers
            bad.close()

            websocket, buffer = connect_ws(port, token)
            first, buffer = recv_frame(websocket, buffer)
            assert first["type"] == "state" and first["status"]["revision"] == 0, first
            assert request_json(
                base, "/debug/demo-state", method="POST", payload={}, token=token
            )[0] == 200
            pushed, buffer = recv_frame(websocket, buffer)
            assert pushed["type"] == "state", pushed
            status = pushed["status"]
            assert (
                status["revision"] >= 1
                and status["state_hash"]
                and status["side_to_act"] == 1
                and status["active_entity_uid"]
            ), status
            websocket.close()
            print(
                "local websocket revision stream: PASS",
                status["revision"],
                status["state_hash"],
            )
        finally:
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
