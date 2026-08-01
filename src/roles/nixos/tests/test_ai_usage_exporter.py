#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import math
import os
import re
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

TEST_DIR = Path(__file__).resolve().parent
MODULE_PATH = TEST_DIR.parent / "files/etc/nixos/pkgs/ai-usage-exporter.py"
FIXTURE_DIR = TEST_DIR / "fixtures/codex-app-server"
SPEC = importlib.util.spec_from_file_location("ai_usage_exporter", MODULE_PATH)
assert SPEC and SPEC.loader
exporter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = exporter
SPEC.loader.exec_module(exporter)


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def recv_exact(conn: socket.socket, length: int) -> bytes:
    output = bytearray()
    while len(output) < length:
        chunk = conn.recv(length - len(output))
        if not chunk:
            raise ConnectionError("closed")
        output.extend(chunk)
    return bytes(output)


def recv_client_frame(conn: socket.socket) -> tuple[int, bytes]:
    first, second = recv_exact(conn, 2)
    opcode = first & 0x0F
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", recv_exact(conn, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", recv_exact(conn, 8))[0]
    mask = recv_exact(conn, 4) if second & 0x80 else None
    payload = recv_exact(conn, length)
    if mask:
        payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
    return opcode, payload


def send_server_frame(conn: socket.socket, opcode: int, payload: bytes) -> None:
    header = bytearray([0x80 | opcode])
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.extend((126,))
        header.extend(struct.pack("!H", length))
    else:
        header.extend((127,))
        header.extend(struct.pack("!Q", length))
    conn.sendall(bytes(header) + payload)


def send_json(conn: socket.socket, value: dict) -> None:
    send_server_frame(conn, 0x1, json.dumps(value, separators=(",", ":")).encode())


class FakeAppServer:
    def __init__(
        self,
        account: dict,
        rate_limits: dict,
        *,
        overloads: int = 0,
        failure: str | None = None,
        rpc_error_message: str | None = None,
    ):
        self.account = account
        self.rate_limits = rate_limits
        self.overloads = overloads
        self.failure = failure
        self.rpc_error_message = rpc_error_message
        self.methods: list[str] = []
        self._temporary = tempfile.TemporaryDirectory()
        self.path = str(Path(self._temporary.name) / "control.sock")
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def __enter__(self) -> "FakeAppServer":
        self._thread.start()
        if not self._ready.wait(2):
            raise RuntimeError("fake app-server did not start")
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        try:
            wake = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            wake.connect(self.path)
            wake.close()
        except OSError:
            pass
        self._thread.join(2)
        self._temporary.cleanup()

    def _serve(self) -> None:
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(self.path)
        server.listen(5)
        server.settimeout(0.1)
        self._ready.set()
        try:
            while not self._stop.is_set():
                try:
                    conn, _ = server.accept()
                except TimeoutError:
                    continue
                try:
                    self._handle(conn)
                except (ConnectionError, OSError, json.JSONDecodeError):
                    pass
                finally:
                    conn.close()
        finally:
            server.close()

    def _handle(self, conn: socket.socket) -> None:
        headers = bytearray()
        while b"\r\n\r\n" not in headers:
            chunk = conn.recv(4096)
            if not chunk:
                return
            headers.extend(chunk)
        match = re.search(rb"Sec-WebSocket-Key:\s*([^\r\n]+)", headers, re.IGNORECASE)
        if not match:
            return
        accept = base64.b64encode(
            hashlib.sha1(
                match.group(1).strip() + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
            ).digest()
        )
        conn.sendall(
            b"HTTP/1.1 101 Switching Protocols\r\n"
            b"Upgrade: websocket\r\n"
            b"Connection: Upgrade\r\n"
            b"Sec-WebSocket-Accept: "
            + accept
            + b"\r\n\r\n"
        )

        while not self._stop.is_set():
            opcode, payload = recv_client_frame(conn)
            if opcode == 0x8:
                send_server_frame(conn, 0x8, struct.pack("!H", 1000))
                return
            if opcode != 0x1:
                continue
            request = json.loads(payload)
            method = request.get("method")
            if isinstance(method, str):
                self.methods.append(method)
            if "id" not in request:
                continue
            request_id = request["id"]
            if method == "initialize":
                send_json(conn, {"method": "server/ready", "params": {}})
                send_json(conn, {"id": request_id, "result": {"userAgent": "fake"}})
            elif method == "account/read":
                if self.failure == "close":
                    return
                if self.failure == "timeout":
                    time.sleep(0.5)
                    return
                send_json(conn, {"id": request_id, "result": self.account})
            elif method == "account/rateLimits/read":
                if self.failure == "malformed":
                    send_server_frame(conn, 0x1, b"not-json")
                    return
                if self.rpc_error_message is not None:
                    send_json(
                        conn,
                        {
                            "id": request_id,
                            "error": {"code": -32603, "message": self.rpc_error_message},
                        },
                    )
                elif self.overloads > 0:
                    self.overloads -= 1
                    send_json(
                        conn,
                        {
                            "id": request_id,
                            "error": {"code": -32001, "message": "server overloaded"},
                        },
                    )
                    return
                else:
                    send_json(conn, {"id": request_id, "result": self.rate_limits})


class SequenceCodex:
    def __init__(self, *values: object):
        self.values = list(values)

    def poll(self):
        value = self.values.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


class RecordingOpenRouter:
    def __init__(self, value: list[dict] | None = None):
        self.value = value if value is not None else [{"name": "service", "usage": 3.5}]
        self.calls = 0

    def poll(self):
        self.calls += 1
        return self.value


class CodexProtocolTests(unittest.TestCase):
    def test_initializes_reads_account_and_rate_limits(self) -> None:
        fixture = load_fixture("weekly-only.json")
        with FakeAppServer(fixture["account"], fixture["rateLimits"]) as server:
            result = exporter.CodexClient(server.path, timeout=2, retries=0).poll()
        self.assertTrue(result.authenticated)
        self.assertEqual(result.rate_limits, fixture["rateLimits"])
        self.assertEqual(
            server.methods,
            ["initialize", "initialized", "account/read", "account/rateLimits/read"],
        )

    def test_explicit_unauthenticated_account_stops_before_rate_limit_read(self) -> None:
        with FakeAppServer(
            {"account": None, "requiresOpenaiAuth": True},
            {},
        ) as server:
            result = exporter.CodexClient(server.path, timeout=2, retries=0).poll()
        self.assertFalse(result.authenticated)
        self.assertIsNone(result.rate_limits)
        self.assertNotIn("account/rateLimits/read", server.methods)

    def test_retryable_overload_reconnects_once(self) -> None:
        fixture = load_fixture("weekly-only.json")
        with FakeAppServer(
            fixture["account"], fixture["rateLimits"], overloads=1
        ) as server:
            result = exporter.CodexClient(server.path, timeout=3, retries=1).poll()
        self.assertTrue(result.authenticated)
        self.assertEqual(server.methods.count("account/rateLimits/read"), 2)

    def test_connection_loss_timeout_and_malformed_response_are_bounded(self) -> None:
        fixture = load_fixture("weekly-only.json")
        cases = {
            "close": exporter.CodexTransportError,
            "timeout": exporter.CodexTransportError,
            "malformed": exporter.CodexProtocolError,
        }
        for failure, expected in cases.items():
            with self.subTest(failure=failure):
                with FakeAppServer(
                    fixture["account"], fixture["rateLimits"], failure=failure
                ) as server:
                    started = time.monotonic()
                    with self.assertRaises(expected):
                        exporter.CodexClient(server.path, timeout=0.15, retries=0).poll()
                    self.assertLess(time.monotonic() - started, 1)


class CodexNormalizationTests(unittest.TestCase):
    def snapshot(self, fixture_name: str) -> dict:
        return exporter.select_rate_limit_snapshot(load_fixture(fixture_name)["rateLimits"])

    def test_weekly_only_and_null_windows_emit_only_weekly(self) -> None:
        windows, plan, reached = exporter.normalize_codex_snapshot(
            self.snapshot("weekly-only.json")
        )
        self.assertEqual(set(windows), {"weekly"})
        self.assertEqual(windows["weekly"].duration_seconds, 604800)
        self.assertEqual(windows["weekly"].reset_timestamp, 1900000000)
        self.assertEqual(plan, "plus")
        self.assertEqual(reached, 0)

    def test_real_five_hour_and_weekly_windows_are_slot_independent(self) -> None:
        windows, _, _ = exporter.normalize_codex_snapshot(
            self.snapshot("five-hour-weekly.json")
        )
        self.assertEqual(set(windows), {"5h", "weekly"})
        self.assertEqual(windows["5h"].used_percent, 12.5)

    def test_codex_multi_limit_entry_wins_over_fallback(self) -> None:
        snapshot = self.snapshot("multi-limit.json")
        windows, plan, reached = exporter.normalize_codex_snapshot(snapshot)
        self.assertEqual(set(windows), {"weekly"})
        self.assertEqual(plan, "enterprise")
        self.assertEqual(reached, 1)

    def test_backward_compatible_snapshot_and_unknown_plan_are_accepted(self) -> None:
        windows, plan, _ = exporter.normalize_codex_snapshot(
            self.snapshot("backward-compatible.json")
        )
        self.assertEqual(set(windows), {"weekly"})
        self.assertEqual(plan, "new-plan-value")

    def test_null_windows_produce_no_synthetic_series(self) -> None:
        windows, _, _ = exporter.normalize_codex_snapshot(self.snapshot("null-windows.json"))
        self.assertEqual(windows, {})

    def test_unknown_duration_has_deterministic_label_and_optional_reset(self) -> None:
        windows, plan, _ = exporter.normalize_codex_snapshot(
            self.snapshot("unknown-duration-plan.json")
        )
        self.assertEqual(set(windows), {"duration_1440m"})
        self.assertIsNone(windows["duration_1440m"].reset_timestamp)
        self.assertEqual(plan, "future-plan")

    def test_duplicate_duration_is_rejected(self) -> None:
        window = {"usedPercent": 10, "windowDurationMins": 10080, "resetsAt": 1900000000}
        with self.assertRaises(exporter.CodexSchemaError):
            exporter.normalize_codex_snapshot(
                {"primary": window, "secondary": dict(window), "planType": "plus"}
            )

    def test_malformed_windows_are_rejected_and_percentages_are_clamped(self) -> None:
        malformed = [
            {"usedPercent": float("nan"), "windowDurationMins": 10080},
            {"usedPercent": 10, "windowDurationMins": 0},
            {"usedPercent": 10, "windowDurationMins": "10080"},
            {"usedPercent": 10, "windowDurationMins": 10080, "resetsAt": "later"},
        ]
        for window in malformed:
            with self.subTest(window=window):
                with self.assertRaises(exporter.CodexSchemaError):
                    exporter.normalize_codex_snapshot({"primary": window})
        windows, _, _ = exporter.normalize_codex_snapshot(
            {"primary": {"usedPercent": 120, "windowDurationMins": 10080}}
        )
        self.assertEqual(windows["weekly"].used_percent, 100)


class CollectorTests(unittest.TestCase):
    def collector(self, codex: object, openrouter: RecordingOpenRouter | None = None):
        return exporter.Collector(
            codex,
            openrouter or RecordingOpenRouter(),
            exporter.MetricsCache(),
            900,
        )

    def test_semantic_metrics_freshness_and_prometheus_shape(self) -> None:
        fixture = load_fixture("weekly-only.json")
        codex = SequenceCodex(exporter.CodexPollResult(True, fixture["rateLimits"]))
        collector = self.collector(codex)
        with mock.patch.object(exporter.time, "time", return_value=1700000000.0):
            collector._scrape_codex()
            collector._scrape_openrouter()
        metrics = collector._render()
        self.assertIn('ai_codex_window_used_percent{window="weekly"} 37', metrics)
        self.assertIn('ai_codex_window_duration_seconds{window="weekly"} 604800', metrics)
        self.assertIn(
            'ai_codex_window_reset_timestamp_seconds{window="weekly"} 1900000000', metrics
        )
        self.assertIn('ai_codex_window_present{window="weekly"} 1', metrics)
        self.assertNotIn('window="7d"', metrics)
        self.assertNotIn('window="5h"', metrics)
        self.assertNotIn("ai_codex_window_reset_seconds", metrics)
        self.assertIn("ai_codex_authenticated 1", metrics)
        self.assertIn(
            'ai_exporter_last_success_timestamp_seconds{source="codex"} 1700000000', metrics
        )
        self.assertIn('ai_exporter_poll_interval_seconds{source="codex"} 900', metrics)
        self.assertIn('ai_exporter_poll_interval_seconds{source="openrouter"} 900', metrics)
        self.assert_valid_exposition(metrics)

    def test_failure_retains_values_timestamp_and_explicit_auth_state(self) -> None:
        fixture = load_fixture("weekly-only.json")
        codex = SequenceCodex(
            exporter.CodexPollResult(True, fixture["rateLimits"]),
            exporter.CodexTransportError("socket unavailable"),
            exporter.CodexPollResult(False, None),
        )
        collector = self.collector(codex)
        with mock.patch.object(exporter.time, "time", return_value=1700000000.0):
            collector._scrape_codex()
        initial_timestamp = collector._codex_last_success
        collector._scrape_codex()
        self.assertEqual(collector._codex_authenticated, 1)
        self.assertEqual(collector._codex_last_success, initial_timestamp)
        self.assertIn("weekly", collector._codex_windows)
        self.assertEqual(collector._codex_scrape_success, 0)
        collector._scrape_codex()
        self.assertEqual(collector._codex_authenticated, 0)
        self.assertEqual(collector._codex_last_success, initial_timestamp)
        self.assertIn("weekly", collector._codex_windows)

    def test_unknown_auth_is_omitted_before_first_explicit_observation(self) -> None:
        collector = self.collector(SequenceCodex(exporter.CodexTransportError("unreachable")))
        collector._scrape_codex()
        samples = [line for line in collector._render().splitlines() if not line.startswith("#")]
        self.assertFalse(any(line.startswith("ai_codex_authenticated ") for line in samples))

    def test_openrouter_continues_for_every_codex_failure_class(self) -> None:
        malformed = {"rateLimits": {"primary": {"usedPercent": "bad"}}}
        cases = [
            exporter.CodexTransportError("transport"),
            exporter.CodexProtocolError("protocol"),
            exporter.CodexPollResult(False, None),
            exporter.CodexPollResult(True, malformed),
        ]
        for case in cases:
            with self.subTest(case=type(case).__name__):
                openrouter = RecordingOpenRouter()
                collector = self.collector(SequenceCodex(case), openrouter)
                with mock.patch.object(exporter, "CODEX_STAGGER", 0):
                    metrics = collector.collect()
                self.assertEqual(openrouter.calls, 1)
                self.assertIn("ai_openrouter_total_usage 3.5", metrics)
                self.assertIn('ai_exporter_scrape_success{source="openrouter"} 1', metrics)

    def test_error_text_and_unknown_payload_are_not_logged_or_labeled(self) -> None:
        marker = "runtime-generated-marker-not-for-output"
        fixture = load_fixture("weekly-only.json")
        with FakeAppServer(
            fixture["account"],
            fixture["rateLimits"],
            rpc_error_message=marker,
        ) as server:
            collector = self.collector(
                exporter.CodexClient(server.path, timeout=2, retries=0)
            )
            with self.assertLogs("ai-usage-exporter", level="WARNING") as captured:
                collector._scrape_codex()
        rendered = collector._render()
        self.assertNotIn(marker, "\n".join(captured.output))
        self.assertNotIn(marker, rendered)

    def test_fixtures_contain_no_sensitive_payload_fields(self) -> None:
        forbidden = ("access_token", "refresh_token", "authorization", "account_id", "email", "secret")
        for path in FIXTURE_DIR.glob("*.json"):
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=path.name):
                for field in forbidden:
                    self.assertNotIn(field, text)

    def test_no_legacy_codex_oauth_or_private_endpoint_code_remains(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        for legacy in ("OAuthTokenManager", "CODEX_USAGE_URL", "wham/usage", "codex-secret-file"):
            self.assertNotIn(legacy, source)

    def assert_valid_exposition(self, metrics: str) -> None:
        sample_pattern = re.compile(
            r'^[a-zA-Z_:][a-zA-Z0-9_:]*(?:\{(?:[a-zA-Z_][a-zA-Z0-9_]*="(?:[^"\\]|\\.)*"(?:,[a-zA-Z_][a-zA-Z0-9_]*="(?:[^"\\]|\\.)*")*)?\})? [-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?$'
        )
        samples: set[str] = set()
        for line in metrics.splitlines():
            if not line or line.startswith("#"):
                continue
            self.assertRegex(line, sample_pattern)
            identity = line.rsplit(" ", 1)[0]
            self.assertNotIn(identity, samples)
            samples.add(identity)
            value = float(line.rsplit(" ", 1)[1])
            self.assertTrue(math.isfinite(value))


if __name__ == "__main__":
    unittest.main()
