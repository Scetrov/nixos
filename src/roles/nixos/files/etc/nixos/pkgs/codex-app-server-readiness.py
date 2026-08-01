#!/usr/bin/env python3
"""Bounded, payload-redacting readiness probe for Codex app-server."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import socket
import struct
import time
from typing import Any


class ReadinessError(RuntimeError):
    """A sanitized readiness failure."""


def remaining(deadline: float) -> float:
    timeout = deadline - time.monotonic()
    if timeout <= 0:
        raise ReadinessError("deadline exceeded")
    return timeout


def recv_exact(conn: socket.socket, length: int, deadline: float) -> bytes:
    data = bytearray()
    while len(data) < length:
        conn.settimeout(remaining(deadline))
        chunk = conn.recv(length - len(data))
        if not chunk:
            raise ReadinessError("connection closed")
        data.extend(chunk)
    return bytes(data)


def send_frame(conn: socket.socket, opcode: int, payload: bytes) -> None:
    mask = os.urandom(4)
    header = bytearray([0x80 | opcode])
    length = len(payload)
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.extend((0x80 | 126,))
        header.extend(struct.pack("!H", length))
    else:
        header.extend((0x80 | 127,))
        header.extend(struct.pack("!Q", length))
    masked = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
    conn.sendall(bytes(header) + mask + masked)


def recv_text(conn: socket.socket, deadline: float) -> str:
    while True:
        first, second = recv_exact(conn, 2, deadline)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", recv_exact(conn, 2, deadline))[0]
        elif length == 127:
            length = struct.unpack("!Q", recv_exact(conn, 8, deadline))[0]
        mask = recv_exact(conn, 4, deadline) if second & 0x80 else None
        payload = recv_exact(conn, length, deadline)
        if mask:
            payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        if opcode == 0x8:
            raise ReadinessError("server closed WebSocket")
        if opcode == 0x9:
            send_frame(conn, 0xA, payload)
            continue
        if opcode == 0x1:
            return payload.decode("utf-8")


def rpc(
    conn: socket.socket,
    request_id: int,
    method: str,
    deadline: float,
    params: Any | None = None,
) -> dict[str, Any]:
    request: dict[str, Any] = {"id": request_id, "method": method}
    if params is not None:
        request["params"] = params
    send_frame(conn, 0x1, json.dumps(request, separators=(",", ":")).encode())
    while True:
        try:
            response = json.loads(recv_text(conn, deadline))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ReadinessError("invalid JSON-RPC response") from error
        if isinstance(response, dict) and response.get("id") == request_id:
            if "result" not in response:
                raise ReadinessError(f"{method} returned an error")
            return response


def probe(socket_path: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while not os.path.exists(socket_path):
        time.sleep(min(0.1, remaining(deadline)))

    conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        conn.settimeout(remaining(deadline))
        conn.connect(socket_path)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            "GET / HTTP/1.1\r\n"
            "Host: localhost\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        conn.sendall(request.encode())
        headers = bytearray()
        while b"\r\n\r\n" not in headers:
            headers.extend(recv_exact(conn, 1, deadline))
            if len(headers) > 16384:
                raise ReadinessError("oversized WebSocket response headers")
        lines = bytes(headers).decode("latin-1").split("\r\n")
        if not lines or not lines[0].startswith("HTTP/1.1 101"):
            raise ReadinessError("WebSocket upgrade rejected")
        header_map = {
            name.strip().lower(): value.strip()
            for line in lines[1:]
            if ":" in line
            for name, value in [line.split(":", 1)]
        }
        expected_accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode()
        if header_map.get("sec-websocket-accept") != expected_accept:
            raise ReadinessError("invalid WebSocket accept header")

        rpc(
            conn,
            1,
            "initialize",
            deadline,
            {
                "clientInfo": {
                    "name": "nixos-readiness",
                    "title": "NixOS readiness probe",
                    "version": "1.0.0",
                },
                "capabilities": None,
            },
        )
        send_frame(
            conn,
            0x1,
            json.dumps({"method": "initialized", "params": {}}, separators=(",", ":")).encode(),
        )
        rpc(conn, 2, "account/read", deadline, {"refreshToken": False})
    finally:
        try:
            send_frame(conn, 0x8, struct.pack("!H", 1000))
        except OSError:
            pass
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    try:
        probe(args.socket, args.timeout)
    except (OSError, ReadinessError) as error:
        print(f"Codex app-server readiness failed: {error}", file=os.sys.stderr)
        return 1
    print("Codex app-server readiness passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
