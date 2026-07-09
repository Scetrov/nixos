#!/usr/bin/env python3
"""Prometheus exporter for AI usage metrics.

Polls the Codex (ChatGPT) wham/usage endpoint and the OpenRouter /credits
endpoint, exposing Prometheus gauges for subscription window usage, credit
balances, and rate-limit status.

Codex auth: reads an age-decrypted JSON file containing the full OAuth
credential (access, refresh, expires, accountId).  Refreshes the access
token in-process when within 5 minutes of expiry or on 401.

OpenRouter auth: reads a KEY=VALUE environment file for OPENROUTER_API_KEY.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Lock, Thread
from typing import Any

LOG = logging.getLogger("ai-usage-exporter")
DEFAULT_POLL_INTERVAL = 60
CODEX_STAGGER = 5
REQUEST_TIMEOUT = 10
TOKEN_REFRESH_MARGIN = 300  # 5 minutes in seconds

CODEX_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
OPENROUTER_KEYS_URL = "https://openrouter.ai/api/v1/keys"


# ---------------------------------------------------------------------------
# Prometheus text helpers
# ---------------------------------------------------------------------------

def prom_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def labels(**values: str | int | bool) -> str:
    parts = []
    for k, v in values.items():
        escaped = prom_escape(str(v).lower() if isinstance(v, bool) else str(v))
        parts.append(f'{k}="{escaped}"')
    return "{" + ",".join(parts) + "}"


# ---------------------------------------------------------------------------
# OAuth token manager
# ---------------------------------------------------------------------------

@dataclass
class OAuthCredential:
    access_token: str
    refresh_token: str
    expires_ms: int  # milliseconds epoch
    account_id: str

    @property
    def expires_s(self) -> float:
        return self.expires_ms / 1000.0

    def needs_refresh(self) -> bool:
        return time.time() >= self.expires_s - TOKEN_REFRESH_MARGIN


class OAuthTokenManager:
    """Manages Codex OAuth credentials with in-process token refresh."""

    def __init__(self, secret_file: str):
        self._secret_file = secret_file
        self._lock = Lock()
        self._cred = self._load_credential()
        LOG.info("loaded OAuth credential for account %s (expires %s)",
                 self._cred.account_id,
                 time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._cred.expires_s)))

    def _load_credential(self) -> OAuthCredential:
        """Load OAuth credential from the age-decrypted JSON secret file."""
        with open(self._secret_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return OAuthCredential(
            access_token=data["access"],
            refresh_token=data["refresh"],
            expires_ms=int(data["expires"]),
            account_id=data["accountId"],
        )

    @property
    def credential(self) -> OAuthCredential:
        with self._lock:
            return self._cred

    @property
    def account_id(self) -> str:
        return self._cred.account_id

    def ensure_fresh(self) -> None:
        """Refresh the access token if it's within the refresh margin of expiry."""
        with self._lock:
            if not self._cred.needs_refresh():
                return
            LOG.info("access token near expiry, refreshing...")
            self._do_refresh()

    def handle_401(self) -> bool:
        """Called on HTTP 401 from the API. Forces a token refresh.

        Returns True if the token was refreshed, False if refresh failed.
        """
        with self._lock:
            LOG.warning("received 401, forcing token refresh")
            try:
                self._do_refresh()
                return True
            except Exception:
                LOG.exception("token refresh after 401 failed")
                return False

    def _do_refresh(self) -> None:
        """Perform the actual token refresh. Must be called with self._lock held."""
        # We need the token URL; extract from the credential or use a default.
        # The auth.json doesn't contain a token URL, so we derive it.
        # OpenAI's OAuth token endpoint:
        token_url = "https://auth.openai.com/oauth/token"

        payload = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": self._cred.refresh_token,
            "client_id": "app_chatgpt",
        }).encode("utf-8")

        req = urllib.request.Request(
            token_url,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "ai-usage-exporter/1.0",
            },
        )

        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=ctx) as resp:
            data = json.loads(resp.read())

        self._cred = OAuthCredential(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", self._cred.refresh_token),
            expires_ms=int(data.get("expires_in", 3600)) * 1000 + int(time.time() * 1000),
            account_id=self._cred.account_id,
        )
        LOG.info("access token refreshed (new expiry %s)",
                 time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._cred.expires_s)))


# ---------------------------------------------------------------------------
# API clients
# ---------------------------------------------------------------------------

def http_get_json(url: str, headers: dict[str, str], timeout: int = REQUEST_TIMEOUT) -> dict:
    """Perform an HTTP GET and return the parsed JSON response."""
    req = urllib.request.Request(url, headers=headers, method="GET")
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read())


class CodexClient:
    """Polls the Codex wham/usage endpoint."""

    def __init__(self, token_mgr: OAuthTokenManager):
        self._token_mgr = token_mgr

    def poll(self) -> dict[str, Any] | None:
        """Poll the usage endpoint. Returns parsed response or None on failure.

        Handles token refresh on expiry/401.
        """
        self._token_mgr.ensure_fresh()

        cred = self._token_mgr.credential
        headers = {
            "Authorization": f"Bearer {cred.access_token}",
            "Chatgpt-Account-Id": self._token_mgr.account_id,
            "User-Agent": "ai-usage-exporter/1.0",
            "Accept": "application/json",
        }

        try:
            data = http_get_json(CODEX_USAGE_URL, headers)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 401:
                if self._token_mgr.handle_401():
                    # Retry once with the new token
                    cred = self._token_mgr.credential
                    headers["Authorization"] = f"Bearer {cred.access_token}"
                    try:
                        return http_get_json(CODEX_USAGE_URL, headers)
                    except Exception:
                        LOG.exception("codex retry after 401 failed")
                        return None
            else:
                LOG.warning("codex wham/usage returned HTTP %d", e.code)
            return None
        except Exception:
            LOG.exception("codex wham/usage request failed")
            return None


class OpenRouterClient:
    """Polls the OpenRouter /keys endpoint using a management key.

    A management key (as opposed to a regular API key) grants access to
    the keys-management API, which lists *all* keys in the organisation
    with per-key usage breakdowns, spend limits, and enabled status.
    This gives a complete picture of OpenRouter consumption across all
    workstations and services, not just the single key used to make the request.
    """

    def __init__(self, management_key: str):
        self._management_key = management_key

    def poll(self) -> list[dict[str, Any]] | None:
        """Poll the /keys endpoint. Returns list of key dicts or None on failure."""
        headers = {
            "Authorization": f"Bearer {self._management_key}",
            "User-Agent": "ai-usage-exporter/1.0",
            "Accept": "application/json",
        }
        try:
            data = http_get_json(OPENROUTER_KEYS_URL, headers)
            # Response shape: {"data": [key1, key2, ...]}
            return data.get("data") if isinstance(data, dict) else None
        except Exception:
            LOG.exception("openrouter /keys request failed")
            return None


# ---------------------------------------------------------------------------
# Metrics cache
# ---------------------------------------------------------------------------

@dataclass
class MetricsCache:
    """Thread-safe cache for rendered Prometheus metrics text."""
    text: str = "# HELP ai_exporter_ready Whether the exporter has completed an initial scrape.\n# TYPE ai_exporter_ready gauge\nai_exporter_ready 0\n"
    lock: Lock = field(default_factory=Lock)

    def get(self) -> bytes:
        with self.lock:
            return self.text.encode()

    def set(self, text: str) -> None:
        with self.lock:
            self.text = text


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

class Collector:
    """Collects metrics from Codex and OpenRouter, renders Prometheus text."""

    def __init__(self, codex: CodexClient, openrouter: OpenRouterClient, cache: MetricsCache):
        self._codex = codex
        self._openrouter = openrouter
        self._cache = cache

        # Last known values (kept on scrape failure)
        self._codex_5h_pct: float = 0.0
        self._codex_7d_pct: float = 0.0
        self._codex_5h_reset: float = 0.0
        self._codex_7d_reset: float = 0.0
        self._codex_limit_reached: int = 0
        self._codex_plan_type: str = "unknown"
        # OpenRouter per-key state: list of dicts {name, usage, usage_daily, ...}
        self._openrouter_keys: list[dict[str, Any]] = []
        self._openrouter_total_usage: float = 0.0
        self._openrouter_total_usage_daily: float = 0.0
        self._openrouter_total_usage_weekly: float = 0.0
        self._openrouter_total_usage_monthly: float = 0.0
        self._openrouter_total_byok_usage: float = 0.0
        self._openrouter_total_byok_usage_daily: float = 0.0
        self._openrouter_total_byok_usage_weekly: float = 0.0
        self._openrouter_total_byok_usage_monthly: float = 0.0
        self._openrouter_keys_enabled: int = 0
        self._codex_scrape_success: int = 0
        self._openrouter_scrape_success: int = 0
        self._codex_scrape_duration: float = 0.0
        self._openrouter_scrape_duration: float = 0.0

    def collect(self) -> str:
        """Perform a full scrape cycle and return rendered metrics."""
        # Scrape Codex
        self._scrape_codex()

        # Stagger OpenRouter by 5 seconds
        time.sleep(CODEX_STAGGER)

        # Scrape OpenRouter
        self._scrape_openrouter()

        return self._render()

    def _scrape_codex(self) -> None:
        started = time.time()
        try:
            data = self._codex.poll()
            if data is None:
                self._codex_scrape_success = 0
                self._codex_scrape_duration = time.time() - started
                return

            self._codex_scrape_success = 1

            # Parse rate limit info
            rl = data.get("rate_limit") or {}
            self._codex_limit_reached = 1 if rl.get("limit_reached") else 0
            if not rl.get("allowed", True):
                self._codex_limit_reached = 1

            # Parse primary window (5h) — nested under rate_limit
            pw = rl.get("primary_window") or {}
            self._codex_5h_pct = float(pw.get("used_percent", 0))
            reset_s = pw.get("reset_after_seconds") or pw.get("reset_at")
            if reset_s is not None:
                # If it's a Unix timestamp (large number), convert to seconds-until-reset
                if isinstance(reset_s, (int, float, str)) and float(reset_s) > 1e9:
                    self._codex_5h_reset = max(0.0, float(reset_s) - time.time())
                else:
                    self._codex_5h_reset = max(0.0, float(reset_s))

            # Parse secondary window (7d) — nested under rate_limit
            sw = rl.get("secondary_window") or {}
            self._codex_7d_pct = float(sw.get("used_percent", 0))
            reset_s2 = sw.get("reset_after_seconds") or sw.get("reset_at")
            if reset_s2 is not None:
                if isinstance(reset_s2, (int, float, str)) and float(reset_s2) > 1e9:
                    self._codex_7d_reset = max(0.0, float(reset_s2) - time.time())
                else:
                    self._codex_7d_reset = max(0.0, float(reset_s2))

            # Parse plan type
            self._codex_plan_type = str(data.get("plan_type", "unknown"))

        except Exception:
            self._codex_scrape_success = 0
            LOG.exception("codex scrape failed")
        finally:
            self._codex_scrape_duration = time.time() - started

    def _scrape_openrouter(self) -> None:
        started = time.time()
        try:
            keys = self._openrouter.poll()
            if keys is None:
                self._openrouter_scrape_success = 0
                self._openrouter_scrape_duration = time.time() - started
                return

            self._openrouter_scrape_success = 1
            self._openrouter_keys = keys

            # Compute account-level aggregates from per-key data
            self._openrouter_total_usage = sum(float(k.get("usage") or 0) for k in keys)
            self._openrouter_total_usage_daily = sum(float(k.get("usage_daily") or 0) for k in keys)
            self._openrouter_total_usage_weekly = sum(float(k.get("usage_weekly") or 0) for k in keys)
            self._openrouter_total_usage_monthly = sum(float(k.get("usage_monthly") or 0) for k in keys)
            self._openrouter_total_byok_usage = sum(float(k.get("byok_usage") or 0) for k in keys)
            self._openrouter_total_byok_usage_daily = sum(float(k.get("byok_usage_daily") or 0) for k in keys)
            self._openrouter_total_byok_usage_weekly = sum(float(k.get("byok_usage_weekly") or 0) for k in keys)
            self._openrouter_total_byok_usage_monthly = sum(float(k.get("byok_usage_monthly") or 0) for k in keys)
            self._openrouter_keys_enabled = sum(1 for k in keys if not k.get("disabled"))

        except Exception:
            self._openrouter_scrape_success = 0
            LOG.exception("openrouter scrape failed")
        finally:
            self._openrouter_scrape_duration = time.time() - started

    def _render(self) -> str:
        lines = [
            "# HELP ai_codex_window_used_percent Percentage of the Codex usage window consumed.",
            "# TYPE ai_codex_window_used_percent gauge",
            f'ai_codex_window_used_percent{labels(window="5h")} {self._codex_5h_pct}',
            f'ai_codex_window_used_percent{labels(window="7d")} {self._codex_7d_pct}',

            "# HELP ai_codex_window_reset_seconds Seconds until the Codex usage window resets.",
            "# TYPE ai_codex_window_reset_seconds gauge",
            f'ai_codex_window_reset_seconds{labels(window="5h")} {self._codex_5h_reset:.0f}',
            f'ai_codex_window_reset_seconds{labels(window="7d")} {self._codex_7d_reset:.0f}',

            "# HELP ai_codex_limit_reached 1 if the Codex rate limit has been reached, 0 otherwise.",
            "# TYPE ai_codex_limit_reached gauge",
            f"ai_codex_limit_reached {self._codex_limit_reached}",

            "# HELP ai_codex_plan_type Codex subscription plan type.",
            "# TYPE ai_codex_plan_type gauge",
            f'ai_codex_plan_type{labels(plan_type=self._codex_plan_type)} 1',

            # OpenRouter per-key metrics
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

        # Per-key series (only emitted when we have data)
        for k in self._openrouter_keys:
            name = prom_escape(str(k.get("name") or "unknown"))
            lbl = labels(key=name)
            lines.extend([
                f"ai_openrouter_key_usage{lbl} {float(k.get('usage') or 0)}",
                f"ai_openrouter_key_usage_daily{lbl} {float(k.get('usage_daily') or 0)}",
                f"ai_openrouter_key_usage_weekly{lbl} {float(k.get('usage_weekly') or 0)}",
                f"ai_openrouter_key_usage_monthly{lbl} {float(k.get('usage_monthly') or 0)}",
                f"ai_openrouter_key_byok_usage{lbl} {float(k.get('byok_usage') or 0)}",
                f"ai_openrouter_key_limit{lbl} {float(k.get('limit') or 0)}",
                f"ai_openrouter_key_limit_remaining{lbl} {float(k.get('limit_remaining') or 0)}",
                f"ai_openrouter_key_enabled{lbl} {0 if k.get('disabled') else 1}",
            ])

        # Account-level aggregates (sum across all keys)
        lines.extend([
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
        ])
        return "\n".join(lines) + "\n"


def run_loop(collector: Collector, stop: Event, interval: int) -> None:
    """Background polling loop."""
    while not stop.is_set():
        try:
            metrics = collector.collect()
            collector._cache.set(metrics)
        except Exception:
            LOG.exception("collection cycle failed")
        stop.wait(interval)


# ---------------------------------------------------------------------------
# Env file parser
# ---------------------------------------------------------------------------

def parse_env_file(path: str) -> dict[str, str]:
    """Parse a KEY=VALUE environment file."""
    env = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AI usage metrics exporter")
    p.add_argument("--codex-secret-file", required=True,
                   help="Path to age-decrypted Codex OAuth JSON credential file")
    p.add_argument("--openrouter-env-file", required=False, default=None,
                   help="Path to file containing OPENROUTER_MANAGEMENT_KEY=<key>")
    p.add_argument("--listen-address", default="127.0.0.1:9188",
                   help="Metrics listen address (default: 127.0.0.1:9188)")
    p.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL,
                   help=f"Polling interval in seconds (default: {DEFAULT_POLL_INTERVAL})")
    return p.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args()

    # Load Codex OAuth credential
    token_mgr = OAuthTokenManager(args.codex_secret_file)

    # Load OpenRouter management key
    openrouter_key = ""
    if args.openrouter_env_file:
        env = parse_env_file(args.openrouter_env_file)
        # Prefer the management key; fall back to regular API key for backward compat
        openrouter_key = env.get("OPENROUTER_MANAGEMENT_KEY") or env.get("OPENROUTER_API_KEY", "")
        if not openrouter_key:
            LOG.warning("OPENROUTER_MANAGEMENT_KEY not found in %s; OpenRouter metrics will fail",
                        args.openrouter_env_file)
    else:
        LOG.warning("No OpenRouter env file provided; OpenRouter metrics will be unavailable")

    # Create clients and collector
    codex = CodexClient(token_mgr)
    openrouter = OpenRouterClient(openrouter_key)
    cache = MetricsCache()
    collector = Collector(codex, openrouter, cache)

    # Start background polling
    stop = Event()
    Thread(target=run_loop, args=(collector, stop, args.poll_interval), daemon=True).start()

    # Initial collection
    try:
        cache.set(collector.collect())
        LOG.info("initial collection complete")
    except Exception:
        LOG.exception("initial collection failed")

    # Serve metrics
    host, port_s = args.listen_address.rsplit(":", 1)
    port = int(port_s)

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

        def log_message(self, fmt: str, *a: Any) -> None:
            return

    LOG.info("serving AI usage metrics on %s", args.listen_address)
    try:
        ThreadingHTTPServer((host, port), Handler).serve_forever()
    except OSError as e:
        LOG.error("failed to bind %s: %s", args.listen_address, e)
        stop.set()
        raise


if __name__ == "__main__":
    main()
