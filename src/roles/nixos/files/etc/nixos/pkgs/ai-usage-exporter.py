#!/usr/bin/env python3
"""Prometheus exporter for Codex and OpenRouter usage.

Codex subscription limits are read from the local Codex app-server over its
Unix WebSocket JSON-RPC interface. Codex owns managed ChatGPT authentication;
this exporter never reads or refreshes OAuth credentials.

OpenRouter usage remains collected from its management API.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import math
import os
import socket
import ssl
import struct
import time
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Lock, Thread
from typing import Any

LOG = logging.getLogger("ai-usage-exporter")
DEFAULT_POLL_INTERVAL = 900
CODEX_STAGGER = 5
REQUEST_TIMEOUT = 10.0
MAX_WEBSOCKET_PAYLOAD = 2 * 1024 * 1024
OPENROUTER_KEYS_URL = "https://openrouter.ai/api/v1/keys"
KNOWN_WINDOW_LABELS = {
    300: "5h",
    10080: "weekly",
}


# ---------------------------------------------------------------------------
# Prometheus text helpers
# ---------------------------------------------------------------------------


def prom_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def labels(**values: str | int | bool) -> str:
    parts = []
    for key, value in values.items():
        escaped = prom_escape(str(value).lower() if isinstance(value, bool) else str(value))
        parts.append(f'{key}="{escaped}"')
    return "{" + ",".join(parts) + "}"


def metric_number(value: float | int) -> str:
    return f"{value:.15g}" if isinstance(value, float) else str(value)


# ---------------------------------------------------------------------------
# Codex app-server protocol
# ---------------------------------------------------------------------------


class CodexError(RuntimeError):
    """Base class for sanitized Codex collection failures."""


class CodexTransportError(CodexError):
    """The app-server transport could not be reached or completed."""


class CodexProtocolError(CodexError):
    """The app-server returned an invalid or unsuccessful protocol response."""


class CodexSchemaError(CodexError):
    """The app-server rate-limit payload did not satisfy the expected schema."""


class RPCResponseError(Exception):
    def __init__(self, code: int | None, message: str):
        super().__init__("JSON-RPC request failed")
        self.code = code
        self.message = message

    @property
    def transient(self) -> bool:
        message = self.message.lower()
        return self.code in {-32001, -32002, -32003} or any(
            marker in message
            for marker in ("overload", "server busy", "temporarily unavailable", "try again")
        )


class UnixWebSocketJSONRPC:
    """Minimal bounded WebSocket JSON-RPC client for a local Unix socket."""

    def __init__(self, socket_path: str, timeout: float = REQUEST_TIMEOUT):
        self._socket_path = socket_path
        self._deadline = time.monotonic() + timeout
        self._conn: socket.socket | None = None
        self._request_id = 0

    def __enter__(self) -> "UnixWebSocketJSONRPC":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _remaining(self) -> float:
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("app-server request deadline exceeded")
        return remaining

    def _recv_exact(self, length: int) -> bytes:
        assert self._conn is not None
        output = bytearray()
        while len(output) < length:
            self._conn.settimeout(self._remaining())
            chunk = self._conn.recv(length - len(output))
            if not chunk:
                raise ConnectionError("app-server closed the connection")
            output.extend(chunk)
        return bytes(output)

    def connect(self) -> None:
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.settimeout(self._remaining())
        conn.connect(self._socket_path)
        self._conn = conn

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
            headers.extend(self._recv_exact(1))
            if len(headers) > 16384:
                raise CodexProtocolError("oversized WebSocket response headers")
        lines = bytes(headers).decode("latin-1").split("\r\n")
        if not lines or not lines[0].startswith("HTTP/1.1 101"):
            raise CodexProtocolError("WebSocket upgrade rejected")
        header_map = {
            name.strip().lower(): value.strip()
            for line in lines[1:]
            if ":" in line
            for name, value in [line.split(":", 1)]
        }
        expected = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode()
        if header_map.get("sec-websocket-accept") != expected:
            raise CodexProtocolError("invalid WebSocket accept header")

    def close(self) -> None:
        if self._conn is None:
            return
        try:
            self._send_frame(0x8, struct.pack("!H", 1000))
        except (OSError, TimeoutError):
            pass
        self._conn.close()
        self._conn = None

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        assert self._conn is not None
        if len(payload) > MAX_WEBSOCKET_PAYLOAD:
            raise CodexProtocolError("WebSocket request payload exceeds limit")
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
        self._conn.settimeout(self._remaining())
        self._conn.sendall(bytes(header) + mask + masked)

    def _recv_frame(self) -> tuple[bool, int, bytes]:
        first, second = self._recv_exact(2)
        final = bool(first & 0x80)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        if length > MAX_WEBSOCKET_PAYLOAD:
            raise CodexProtocolError("WebSocket response payload exceeds limit")
        mask = self._recv_exact(4) if second & 0x80 else None
        payload = self._recv_exact(length)
        if mask:
            payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        return final, opcode, payload

    def _recv_text(self) -> str:
        fragments = bytearray()
        expecting_continuation = False
        while True:
            final, opcode, payload = self._recv_frame()
            if opcode == 0x8:
                raise ConnectionError("app-server closed the WebSocket")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            if opcode == 0x1 and not expecting_continuation:
                fragments.extend(payload)
                expecting_continuation = not final
            elif opcode == 0x0 and expecting_continuation:
                fragments.extend(payload)
                expecting_continuation = not final
            else:
                raise CodexProtocolError("unexpected WebSocket frame")
            if final:
                try:
                    return bytes(fragments).decode("utf-8")
                except UnicodeDecodeError as error:
                    raise CodexProtocolError("non-UTF-8 WebSocket response") from error

    def notify(self, method: str, params: dict[str, Any]) -> None:
        request = {"method": method, "params": params}
        self._send_frame(0x1, json.dumps(request, separators=(",", ":")).encode())

    def rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._request_id += 1
        request_id = self._request_id
        request: dict[str, Any] = {"id": request_id, "method": method}
        if params is not None:
            request["params"] = params
        self._send_frame(0x1, json.dumps(request, separators=(",", ":")).encode())
        while True:
            try:
                response = json.loads(self._recv_text())
            except json.JSONDecodeError as error:
                raise CodexProtocolError("invalid JSON-RPC response") from error
            if not isinstance(response, dict) or response.get("id") != request_id:
                continue
            if "error" in response:
                error_data = response.get("error")
                code = error_data.get("code") if isinstance(error_data, dict) else None
                message = error_data.get("message", "") if isinstance(error_data, dict) else ""
                raise RPCResponseError(code if isinstance(code, int) else None, str(message))
            if "result" not in response:
                raise CodexProtocolError(f"{method} response omitted result")
            return response["result"]


@dataclass(frozen=True)
class CodexPollResult:
    authenticated: bool
    rate_limits: dict[str, Any] | None


class CodexClient:
    """Reads account state and rate limits from local Codex app-server."""

    def __init__(self, socket_path: str, timeout: float = REQUEST_TIMEOUT, retries: int = 1):
        self._socket_path = socket_path
        self._timeout = timeout
        self._retries = retries

    def poll(self) -> CodexPollResult:
        deadline = time.monotonic() + self._timeout
        for attempt in range(self._retries + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CodexTransportError("app-server polling deadline exceeded")
            try:
                with UnixWebSocketJSONRPC(self._socket_path, remaining) as rpc:
                    rpc.rpc(
                        "initialize",
                        {
                            "clientInfo": {
                                "name": "ai-usage-exporter",
                                "title": "AI usage exporter",
                                "version": "1.0.0",
                            },
                            "capabilities": None,
                        },
                    )
                    rpc.notify("initialized", {})
                    account = rpc.rpc("account/read", {"refreshToken": False})
                    if not isinstance(account, dict) or "account" not in account:
                        raise CodexProtocolError("account/read returned an invalid result")
                    if account["account"] is None:
                        return CodexPollResult(authenticated=False, rate_limits=None)
                    rate_limits = rpc.rpc("account/rateLimits/read")
                    if not isinstance(rate_limits, dict):
                        raise CodexProtocolError("account/rateLimits/read returned an invalid result")
                    return CodexPollResult(authenticated=True, rate_limits=rate_limits)
            except RPCResponseError as error:
                if error.transient and attempt < self._retries:
                    self._retry_pause(deadline)
                    continue
                raise CodexProtocolError(f"app-server JSON-RPC error code {error.code}") from error
            except CodexError:
                raise
            except (OSError, TimeoutError, ConnectionError) as error:
                if attempt < self._retries:
                    self._retry_pause(deadline)
                    continue
                raise CodexTransportError("app-server transport failed") from error
        raise CodexTransportError("app-server polling failed")

    @staticmethod
    def _retry_pause(deadline: float) -> None:
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(0.2, remaining))


@dataclass(frozen=True)
class CodexWindow:
    label: str
    duration_seconds: int
    used_percent: float
    reset_timestamp: float | None


def _finite_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CodexSchemaError(f"Codex {field_name} has an unexpected type")
    number = float(value)
    if not math.isfinite(number):
        raise CodexSchemaError(f"Codex {field_name} is not finite")
    return number


def select_rate_limit_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    by_limit_id = result.get("rateLimitsByLimitId")
    if by_limit_id is not None:
        if not isinstance(by_limit_id, dict):
            raise CodexSchemaError("Codex rateLimitsByLimitId is not an object")
        if "codex" in by_limit_id:
            snapshot = by_limit_id["codex"]
            if not isinstance(snapshot, dict):
                raise CodexSchemaError("Codex-specific rate-limit snapshot is not an object")
            return snapshot
    snapshot = result.get("rateLimits")
    if not isinstance(snapshot, dict):
        raise CodexSchemaError("Codex rate-limit response omitted a usable snapshot")
    return snapshot


def normalize_codex_snapshot(
    snapshot: dict[str, Any],
) -> tuple[dict[str, CodexWindow], str, int]:
    windows: dict[str, CodexWindow] = {}
    for slot in ("primary", "secondary"):
        raw = snapshot.get(slot)
        if raw is None:
            continue
        if not isinstance(raw, dict):
            raise CodexSchemaError(f"Codex {slot} window is not an object")
        duration_value = _finite_number(raw.get("windowDurationMins"), f"{slot} window duration")
        if duration_value <= 0 or not duration_value.is_integer():
            raise CodexSchemaError(f"Codex {slot} window duration is not a positive integer")
        duration_minutes = int(duration_value)
        label = KNOWN_WINDOW_LABELS.get(duration_minutes, f"duration_{duration_minutes}m")
        if label in windows:
            raise CodexSchemaError(f"Codex duplicate semantic window {label}")

        used_percent = _finite_number(raw.get("usedPercent"), f"{slot} used percentage")
        clamped_percent = min(100.0, max(0.0, used_percent))
        if clamped_percent != used_percent:
            LOG.warning("Codex used percentage outside 0-100 for window %s; clamped", label)

        reset_timestamp: float | None = None
        if raw.get("resetsAt") is not None:
            reset_timestamp = _finite_number(raw["resetsAt"], f"{slot} reset timestamp")
            if reset_timestamp <= 0:
                raise CodexSchemaError(f"Codex {slot} reset timestamp is not positive")

        windows[label] = CodexWindow(
            label=label,
            duration_seconds=duration_minutes * 60,
            used_percent=clamped_percent,
            reset_timestamp=reset_timestamp,
        )

    plan_value = snapshot.get("planType")
    plan_type = plan_value if isinstance(plan_value, str) and plan_value else "unknown"
    limit_reached = int(
        snapshot.get("rateLimitReachedType") is not None or snapshot.get("spendControlReached") is True
    )
    return windows, plan_type, limit_reached


# ---------------------------------------------------------------------------
# OpenRouter API client
# ---------------------------------------------------------------------------


def http_get_json(url: str, headers: dict[str, str], timeout: float = REQUEST_TIMEOUT) -> dict:
    request = urllib.request.Request(url, headers=headers, method="GET")
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        return json.loads(response.read())


class OpenRouterClient:
    """Polls the OpenRouter keys endpoint using a management key."""

    def __init__(self, management_key: str):
        self._management_key = management_key

    def poll(self) -> list[dict[str, Any]] | None:
        headers = {
            "Authorization": f"Bearer {self._management_key}",
            "User-Agent": "ai-usage-exporter/1.0",
            "Accept": "application/json",
        }
        try:
            data = http_get_json(OPENROUTER_KEYS_URL, headers)
            return data.get("data") if isinstance(data, dict) else None
        except Exception:
            LOG.exception("OpenRouter keys request failed")
            return None


# ---------------------------------------------------------------------------
# Metrics cache and collector
# ---------------------------------------------------------------------------


@dataclass
class MetricsCache:
    text: str = (
        "# HELP ai_exporter_ready Whether the exporter has completed an initial scrape.\n"
        "# TYPE ai_exporter_ready gauge\n"
        "ai_exporter_ready 0\n"
    )
    lock: Lock = field(default_factory=Lock)

    def get(self) -> bytes:
        with self.lock:
            return self.text.encode()

    def set(self, text: str) -> None:
        with self.lock:
            self.text = text


class Collector:
    """Collects Codex and OpenRouter metrics and renders Prometheus text."""

    def __init__(
        self,
        codex: CodexClient,
        openrouter: OpenRouterClient,
        cache: MetricsCache,
        poll_interval: int,
    ):
        self._codex = codex
        self._openrouter = openrouter
        self._cache = cache
        self._poll_interval = poll_interval

        self._codex_windows: dict[str, CodexWindow] = {}
        self._codex_limit_reached = 0
        self._codex_plan_type = "unknown"
        self._codex_has_snapshot = False
        self._codex_authenticated: int | None = None
        self._openrouter_keys: list[dict[str, Any]] = []
        self._openrouter_total_usage = 0.0
        self._openrouter_total_usage_daily = 0.0
        self._openrouter_total_usage_weekly = 0.0
        self._openrouter_total_usage_monthly = 0.0
        self._openrouter_total_byok_usage = 0.0
        self._openrouter_total_byok_usage_daily = 0.0
        self._openrouter_total_byok_usage_weekly = 0.0
        self._openrouter_total_byok_usage_monthly = 0.0
        self._openrouter_keys_enabled = 0
        self._codex_scrape_success = 0
        self._openrouter_scrape_success = 0
        self._codex_scrape_duration = 0.0
        self._openrouter_scrape_duration = 0.0
        self._codex_last_success: float | None = None
        self._openrouter_last_success: float | None = None

    def collect(self) -> str:
        self._scrape_codex()
        time.sleep(CODEX_STAGGER)
        self._scrape_openrouter()
        return self._render()

    def _scrape_codex(self) -> None:
        started = time.time()
        try:
            result = self._codex.poll()
            self._codex_authenticated = int(result.authenticated)
            if not result.authenticated:
                self._codex_scrape_success = 0
                return
            assert result.rate_limits is not None
            snapshot = select_rate_limit_snapshot(result.rate_limits)
            windows, plan_type, limit_reached = normalize_codex_snapshot(snapshot)
            self._codex_windows = windows
            self._codex_plan_type = plan_type
            self._codex_limit_reached = limit_reached
            self._codex_has_snapshot = True
            self._codex_last_success = time.time()
            self._codex_scrape_success = 1
        except CodexError as error:
            self._codex_scrape_success = 0
            LOG.warning("Codex scrape failed: %s", error)
        except Exception:
            self._codex_scrape_success = 0
            LOG.exception("Codex scrape failed unexpectedly")
        finally:
            self._codex_scrape_duration = time.time() - started

    def _scrape_openrouter(self) -> None:
        started = time.time()
        try:
            keys = self._openrouter.poll()
            if keys is None:
                self._openrouter_scrape_success = 0
                return
            self._openrouter_scrape_success = 1
            self._openrouter_last_success = time.time()
            self._openrouter_keys = keys
            self._openrouter_total_usage = sum(float(key.get("usage") or 0) for key in keys)
            self._openrouter_total_usage_daily = sum(float(key.get("usage_daily") or 0) for key in keys)
            self._openrouter_total_usage_weekly = sum(float(key.get("usage_weekly") or 0) for key in keys)
            self._openrouter_total_usage_monthly = sum(float(key.get("usage_monthly") or 0) for key in keys)
            self._openrouter_total_byok_usage = sum(float(key.get("byok_usage") or 0) for key in keys)
            self._openrouter_total_byok_usage_daily = sum(
                float(key.get("byok_usage_daily") or 0) for key in keys
            )
            self._openrouter_total_byok_usage_weekly = sum(
                float(key.get("byok_usage_weekly") or 0) for key in keys
            )
            self._openrouter_total_byok_usage_monthly = sum(
                float(key.get("byok_usage_monthly") or 0) for key in keys
            )
            self._openrouter_keys_enabled = sum(1 for key in keys if not key.get("disabled"))
        except Exception:
            self._openrouter_scrape_success = 0
            LOG.exception("OpenRouter scrape failed")
        finally:
            self._openrouter_scrape_duration = time.time() - started

    def _render(self) -> str:
        lines = [
            "# HELP ai_codex_window_used_percent Percentage of the Codex usage window consumed.",
            "# TYPE ai_codex_window_used_percent gauge",
        ]
        for label in sorted(self._codex_windows):
            window = self._codex_windows[label]
            window_labels = labels(window=window.label)
            lines.append(
                f"ai_codex_window_used_percent{window_labels} {metric_number(window.used_percent)}"
            )

        lines.extend(
            [
                "# HELP ai_codex_window_duration_seconds Provider-reported Codex window duration.",
                "# TYPE ai_codex_window_duration_seconds gauge",
            ]
        )
        for label in sorted(self._codex_windows):
            window = self._codex_windows[label]
            lines.append(
                f"ai_codex_window_duration_seconds{labels(window=window.label)} "
                f"{window.duration_seconds}"
            )

        lines.extend(
            [
                "# HELP ai_codex_window_reset_timestamp_seconds Absolute Codex window reset time.",
                "# TYPE ai_codex_window_reset_timestamp_seconds gauge",
            ]
        )
        for label in sorted(self._codex_windows):
            window = self._codex_windows[label]
            if window.reset_timestamp is not None:
                lines.append(
                    f"ai_codex_window_reset_timestamp_seconds{labels(window=window.label)} "
                    f"{metric_number(window.reset_timestamp)}"
                )

        lines.extend(
            [
                "# HELP ai_codex_window_present Whether a semantic Codex window is present.",
                "# TYPE ai_codex_window_present gauge",
            ]
        )
        for label in sorted(self._codex_windows):
            lines.append(f"ai_codex_window_present{labels(window=label)} 1")

        lines.extend(
            [
                "# HELP ai_codex_authenticated Last explicit Codex app-server authentication state.",
                "# TYPE ai_codex_authenticated gauge",
            ]
        )
        if self._codex_authenticated is not None:
            lines.append(f"ai_codex_authenticated {self._codex_authenticated}")

        if self._codex_has_snapshot:
            lines.extend(
                [
                    "# HELP ai_codex_limit_reached Whether Codex reports a reached limit.",
                    "# TYPE ai_codex_limit_reached gauge",
                    f"ai_codex_limit_reached {self._codex_limit_reached}",
                    "# HELP ai_codex_plan_type Codex subscription plan type.",
                    "# TYPE ai_codex_plan_type gauge",
                    f"ai_codex_plan_type{labels(plan_type=self._codex_plan_type)} 1",
                ]
            )

        lines.extend(
            [
                "# HELP ai_openrouter_key_usage Lifetime OpenRouter spend for each key (USD, management-key view).",
                "# TYPE ai_openrouter_key_usage gauge",
                "# HELP ai_openrouter_key_usage_daily OpenRouter spend today for each key (USD).",
                "# TYPE ai_openrouter_key_usage_daily gauge",
                "# HELP ai_openrouter_key_usage_weekly OpenRouter spend this week for each key (USD).",
                "# TYPE ai_openrouter_key_usage_weekly gauge",
                "# HELP ai_openrouter_key_usage_monthly OpenRouter spend this month for each key (USD).",
                "# TYPE ai_openrouter_key_usage_monthly gauge",
                "# HELP ai_openrouter_key_byok_usage Lifetime BYOK spend for each key (USD, user-owned model keys).",
                "# TYPE ai_openrouter_key_byok_usage gauge",
                "# HELP ai_openrouter_key_limit Spend limit configured for each key (USD, 0 = unlimited).",
                "# TYPE ai_openrouter_key_limit gauge",
                "# HELP ai_openrouter_key_limit_remaining Remaining spend budget in current period for each key (USD, 0 = unlimited).",
                "# TYPE ai_openrouter_key_limit_remaining gauge",
                "# HELP ai_openrouter_key_enabled Whether the key is enabled (1) or disabled (0).",
                "# TYPE ai_openrouter_key_enabled gauge",
            ]
        )
        for key in self._openrouter_keys:
            # Preserve the existing OpenRouter label-escaping behavior.
            key_name = prom_escape(str(key.get("name") or "unknown"))
            key_labels = labels(key=key_name)
            lines.extend(
                [
                    f"ai_openrouter_key_usage{key_labels} {float(key.get('usage') or 0)}",
                    f"ai_openrouter_key_usage_daily{key_labels} {float(key.get('usage_daily') or 0)}",
                    f"ai_openrouter_key_usage_weekly{key_labels} {float(key.get('usage_weekly') or 0)}",
                    f"ai_openrouter_key_usage_monthly{key_labels} {float(key.get('usage_monthly') or 0)}",
                    f"ai_openrouter_key_byok_usage{key_labels} {float(key.get('byok_usage') or 0)}",
                    f"ai_openrouter_key_limit{key_labels} {float(key.get('limit') or 0)}",
                    f"ai_openrouter_key_limit_remaining{key_labels} {float(key.get('limit_remaining') or 0)}",
                    f"ai_openrouter_key_enabled{key_labels} {0 if key.get('disabled') else 1}",
                ]
            )

        lines.extend(
            [
                "# HELP ai_openrouter_total_usage Total OpenRouter spend across all keys (USD).",
                "# TYPE ai_openrouter_total_usage gauge",
                f"ai_openrouter_total_usage {self._openrouter_total_usage}",
                "# HELP ai_openrouter_total_usage_daily Aggregated OpenRouter spend today across all keys (USD).",
                "# TYPE ai_openrouter_total_usage_daily gauge",
                f"ai_openrouter_total_usage_daily {self._openrouter_total_usage_daily}",
                "# HELP ai_openrouter_total_usage_weekly Aggregated OpenRouter spend this week across all keys (USD).",
                "# TYPE ai_openrouter_total_usage_weekly gauge",
                f"ai_openrouter_total_usage_weekly {self._openrouter_total_usage_weekly}",
                "# HELP ai_openrouter_total_usage_monthly Aggregated OpenRouter spend this month across all keys (USD).",
                "# TYPE ai_openrouter_total_usage_monthly gauge",
                f"ai_openrouter_total_usage_monthly {self._openrouter_total_usage_monthly}",
                "# HELP ai_openrouter_total_byok_usage Total BYOK spend across all keys (USD, user-owned model keys).",
                "# TYPE ai_openrouter_total_byok_usage gauge",
                f"ai_openrouter_total_byok_usage {self._openrouter_total_byok_usage}",
                "# HELP ai_openrouter_total_byok_usage_daily Aggregated BYOK spend today across all keys (USD).",
                "# TYPE ai_openrouter_total_byok_usage_daily gauge",
                f"ai_openrouter_total_byok_usage_daily {self._openrouter_total_byok_usage_daily}",
                "# HELP ai_openrouter_total_byok_usage_weekly Aggregated BYOK spend this week across all keys (USD).",
                "# TYPE ai_openrouter_total_byok_usage_weekly gauge",
                f"ai_openrouter_total_byok_usage_weekly {self._openrouter_total_byok_usage_weekly}",
                "# HELP ai_openrouter_total_byok_usage_monthly Aggregated BYOK spend this month across all keys (USD).",
                "# TYPE ai_openrouter_total_byok_usage_monthly gauge",
                f"ai_openrouter_total_byok_usage_monthly {self._openrouter_total_byok_usage_monthly}",
                "# HELP ai_openrouter_keys_enabled Number of enabled OpenRouter keys in the organisation.",
                "# TYPE ai_openrouter_keys_enabled gauge",
                f"ai_openrouter_keys_enabled {self._openrouter_keys_enabled}",
                "# HELP ai_exporter_scrape_success Whether the last scrape of each source succeeded.",
                "# TYPE ai_exporter_scrape_success gauge",
                f'ai_exporter_scrape_success{labels(source="codex")} {self._codex_scrape_success}',
                f'ai_exporter_scrape_success{labels(source="openrouter")} {self._openrouter_scrape_success}',
                "# HELP ai_exporter_scrape_duration_seconds Duration of the last scrape for each source.",
                "# TYPE ai_exporter_scrape_duration_seconds gauge",
                f'ai_exporter_scrape_duration_seconds{labels(source="codex")} {self._codex_scrape_duration:.3f}',
                f'ai_exporter_scrape_duration_seconds{labels(source="openrouter")} {self._openrouter_scrape_duration:.3f}',
                "# HELP ai_exporter_last_success_timestamp_seconds Completion time of the last successful source collection.",
                "# TYPE ai_exporter_last_success_timestamp_seconds gauge",
            ]
        )
        if self._codex_last_success is not None:
            lines.append(
                f'ai_exporter_last_success_timestamp_seconds{labels(source="codex")} '
                f"{metric_number(self._codex_last_success)}"
            )
        if self._openrouter_last_success is not None:
            lines.append(
                f'ai_exporter_last_success_timestamp_seconds{labels(source="openrouter")} '
                f"{metric_number(self._openrouter_last_success)}"
            )
        lines.extend(
            [
                "# HELP ai_exporter_poll_interval_seconds Configured source polling interval.",
                "# TYPE ai_exporter_poll_interval_seconds gauge",
                f'ai_exporter_poll_interval_seconds{labels(source="codex")} {self._poll_interval}',
                f'ai_exporter_poll_interval_seconds{labels(source="openrouter")} {self._poll_interval}',
                "# HELP ai_exporter_ready Whether the exporter has completed an initial scrape.",
                "# TYPE ai_exporter_ready gauge",
                "ai_exporter_ready 1",
            ]
        )
        return "\n".join(lines) + "\n"


def run_loop(collector: Collector, stop: Event, interval: int) -> None:
    while not stop.wait(interval):
        try:
            collector._cache.set(collector.collect())
        except Exception:
            LOG.exception("collection cycle failed")


# ---------------------------------------------------------------------------
# Configuration and main
# ---------------------------------------------------------------------------


def parse_env_file(path: str) -> dict[str, str]:
    env = {}
    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI usage metrics exporter")
    parser.add_argument(
        "--codex-socket",
        default="/run/codex-app-server/control.sock",
        help="Path to the local Codex app-server Unix socket",
    )
    parser.add_argument(
        "--openrouter-env-file",
        default=None,
        help="Path to a file containing OPENROUTER_MANAGEMENT_KEY",
    )
    parser.add_argument(
        "--listen-address",
        default="127.0.0.1:9188",
        help="Metrics listen address (default: 127.0.0.1:9188)",
    )
    parser.add_argument(
        "--poll-interval",
        type=positive_int,
        default=DEFAULT_POLL_INTERVAL,
        help=f"Polling interval in seconds (default: {DEFAULT_POLL_INTERVAL})",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args()

    openrouter_key = ""
    if args.openrouter_env_file:
        env = parse_env_file(args.openrouter_env_file)
        openrouter_key = env.get("OPENROUTER_MANAGEMENT_KEY") or env.get("OPENROUTER_API_KEY", "")
        if not openrouter_key:
            LOG.warning("OpenRouter management key is unavailable")
    else:
        LOG.warning("No OpenRouter environment file provided")

    cache = MetricsCache()
    collector = Collector(
        CodexClient(args.codex_socket),
        OpenRouterClient(openrouter_key),
        cache,
        args.poll_interval,
    )
    stop = Event()
    try:
        cache.set(collector.collect())
        LOG.info("initial collection complete")
    except Exception:
        LOG.exception("initial collection failed")
    Thread(target=run_loop, args=(collector, stop, args.poll_interval), daemon=True).start()

    host, port_text = args.listen_address.rsplit(":", 1)
    port = int(port_text)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/metrics":
                self.send_response(404)
                self.end_headers()
                return
            payload = cache.get()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    LOG.info("serving AI usage metrics on %s", args.listen_address)
    try:
        ThreadingHTTPServer((host, port), Handler).serve_forever()
    except OSError as error:
        LOG.error("failed to bind metrics listener: %s", error)
        stop.set()
        raise


if __name__ == "__main__":
    main()
