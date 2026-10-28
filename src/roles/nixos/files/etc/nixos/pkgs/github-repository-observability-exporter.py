#!/usr/bin/env python3
"""Prometheus exporter for GitHub repository maintenance and supply-chain risk.

Authentication is GitHub App only. The exporter reads the app id and private key
from runtime secret files, creates short-lived installation tokens, collects in a
background loop, and serves the latest cached metrics on /metrics.
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Lock, Thread
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

LOG = logging.getLogger("github-repository-observability-exporter")
API = "https://api.github.com"
SEVERITIES = ("critical", "high", "medium", "low", "warning", "note", "error", "unknown")
SIGNALS = ("repository", "pull_requests", "issues", "main_statuses", "dependabot", "code_scanning")
FAILING_CHECK_CONCLUSIONS = {"failure", "timed_out", "action_required", "startup_failure"}
CHECK_CONCLUSIONS = FAILING_CHECK_CONCLUSIONS | {"success", "neutral", "cancelled", "skipped", "stale"}
CHECK_STATES = {"queued", "in_progress", "completed", "waiting", "requested", "pending"}


def now_ts() -> int:
    return int(time.time())


def parse_github_time(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def prom_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def labels(**values: str | int | bool) -> str:
    return "{" + ",".join(f'{k}="{prom_escape(str(v).lower() if isinstance(v, bool) else str(v))}"' for k, v in values.items()) + "}"


def complete_page_rows(pages: list[Any], field_name: str) -> list[dict[str, Any]]:
    """Reject truncated or changing result sets instead of emitting partial counts."""
    expected: int | None = None
    rows: dict[int, dict[str, Any]] = {}
    if not pages:
        raise ValueError("missing result page")
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get(field_name), list):
            raise ValueError("invalid result page")
        total = page.get("total_count")
        if isinstance(total, bool) or not isinstance(total, int) or total < 0:
            raise ValueError("invalid result count")
        if expected is not None and expected != total:
            raise ValueError("result count changed during pagination")
        expected = total
        for row in page[field_name]:
            if not isinstance(row, dict):
                raise ValueError("invalid result row")
            row_id = row.get("id")
            if isinstance(row_id, bool) or not isinstance(row_id, int) or row_id <= 0:
                raise ValueError("invalid result identifier")
            if row_id in rows and rows[row_id] != row:
                raise ValueError("result changed during pagination")
            rows[row_id] = row
    if len(rows) != expected:
        raise ValueError("incomplete result pages")
    return list(rows.values())


def count_main_failures(status_pages: list[Any], check_pages: list[Any], sha: str) -> int:
    statuses = complete_page_rows(status_pages, "statuses")
    checks = complete_page_rows(check_pages, "check_runs")
    if any(page.get("sha") != sha for page in status_pages):
        raise ValueError("status reference mismatch")
    latest_statuses: dict[str, dict[str, Any]] = {}
    latest_checks: dict[tuple[int, str], dict[str, Any]] = {}
    for status in statuses:
        context = status.get("context")
        if not isinstance(context, str) or not context or status.get("state") not in ("failure", "error", "pending", "success"):
            raise ValueError("invalid commit status")
        if context not in latest_statuses or status["id"] > latest_statuses[context]["id"]:
            latest_statuses[context] = status
    for check in checks:
        app = check.get("app")
        app_id = app.get("id") if isinstance(app, dict) else None
        name = check.get("name")
        state = check.get("status")
        conclusion = check.get("conclusion")
        if isinstance(app_id, bool) or not isinstance(app_id, int) or app_id <= 0 or not isinstance(name, str) or not name:
            raise ValueError("invalid check identity")
        if check.get("head_sha") != sha or not isinstance(state, str) or state not in CHECK_STATES:
            raise ValueError("invalid check reference or state")
        if state == "completed":
            if not isinstance(conclusion, str) or conclusion not in CHECK_CONCLUSIONS:
                raise ValueError("invalid check conclusion")
        elif conclusion is not None:
            raise ValueError("unfinished check has a conclusion")
        key = (app_id, name)
        if key not in latest_checks or check["id"] > latest_checks[key]["id"]:
            latest_checks[key] = check
    return sum(status["state"] in ("failure", "error") for status in latest_statuses.values()) + sum(
        check["status"] == "completed" and check["conclusion"] in FAILING_CHECK_CONCLUSIONS
        for check in latest_checks.values()
    )


@dataclass
class Repo:
    owner: str
    name: str
    archived: bool
    fork: bool
    default_branch: str | None = None


@dataclass
class Config:
    app_id_file: str
    private_key_file: str
    owners: list[str]
    include_archived: bool
    include_forks: bool
    exclude_repositories: set[str]
    interval_seconds: int
    listen_address: str
    user_agent: str = "scetrov-github-repository-observability-exporter/1.0"


@dataclass
class Cache:
    text: str = "# HELP github_repository_observability_cache_ready Whether the exporter has completed an initial collection.\n# TYPE github_repository_observability_cache_ready gauge\ngithub_repository_observability_cache_ready 0\n"
    lock: Lock = field(default_factory=Lock)

    def get(self) -> bytes:
        with self.lock:
            return self.text.encode()

    def set(self, text: str) -> None:
        with self.lock:
            self.text = text


class GitHubClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.app_id = open(cfg.app_id_file, "r", encoding="utf-8").read().strip()
        key_bytes = open(cfg.private_key_file, "rb").read()
        self.private_key = serialization.load_pem_private_key(key_bytes, password=None)
        self.installation_tokens: dict[int, tuple[str, int]] = {}
        self.rate_remaining = -1
        self.rate_reset = 0

    def app_jwt(self) -> str:
        header = {"alg": "RS256", "typ": "JWT"}
        issued = now_ts() - 60
        payload = {"iat": issued, "exp": issued + 540, "iss": self.app_id}
        signing_input = f"{b64url(json.dumps(header, separators=(',', ':')).encode())}.{b64url(json.dumps(payload, separators=(',', ':')).encode())}".encode()
        # GitHub App JWTs must be RS256, which mandates PKCS1v15 padding.
        signature = self.private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())  # nosemgrep: python.cryptography.cryptography-rsa-pkcs1-signature -- RS256 mandates PKCS1v15; offline JWT generation, no oracle exposure
        return signing_input.decode() + "." + b64url(signature)

    def request(self, path: str, token: str | None = None, method: str = "GET", body: bytes | None = None) -> tuple[Any, dict[str, str]]:
        url = path if path.startswith("https://") else API + path
        if not url.startswith("https://"):
            raise ValueError(f"non-https GitHub URL refused: {url.split('://', 1)[0]}://")
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": self.cfg.user_agent,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = Request(url, data=body, method=method, headers=headers)
        with urlopen(req, timeout=30) as resp:  # nosemgrep: dynamic-urllib-use-detected
            self.rate_remaining = int(resp.headers.get("x-ratelimit-remaining", self.rate_remaining))
            self.rate_reset = int(resp.headers.get("x-ratelimit-reset", self.rate_reset))
            raw = resp.read()
            return (json.loads(raw) if raw else None), {k.lower(): v for k, v in resp.headers.items()}

    def paged(self, path: str, token: str, *, require_list: bool = False) -> list[Any]:
        results: list[Any] = []
        next_path: str | None = path
        while next_path:
            data, headers = self.request(next_path, token=token)
            if require_list and not isinstance(data, list):
                raise ValueError("GitHub paginated response is not an array")
            if isinstance(data, list):
                results.extend(data)
            elif data is not None:
                results.append(data)
            next_path = None
            for part in headers.get("link", "").split(","):
                if 'rel="next"' in part:
                    next_path = part.split(";", 1)[0].strip()[1:-1]
        return results

    def installations(self) -> list[dict[str, Any]]:
        data = self.paged("/app/installations?per_page=100", token=self.app_jwt())
        return [i for i in data if i.get("account", {}).get("login") in set(self.cfg.owners)]

    def installation_token(self, installation_id: int) -> str:
        cached = self.installation_tokens.get(installation_id)
        if cached and cached[1] > now_ts() + 300:
            return cached[0]
        data, _ = self.request(f"/app/installations/{installation_id}/access_tokens", token=self.app_jwt(), method="POST", body=b"{}")
        token = data["token"]
        expires = parse_github_time(data.get("expires_at")) or (now_ts() + 3300)
        self.installation_tokens[installation_id] = (token, int(expires))
        return token


class Collector:
    def __init__(self, cfg: Config, cache: Cache):
        self.cfg = cfg
        self.cache = cache
        self.client = GitHubClient(cfg)

    def safe_signal(self, lines: list[str], repo: Repo, signal: str, status: str, available: int) -> None:
        lines.append(f"github_repository_signal_available{labels(owner=repo.owner, repository=repo.name, signal=signal, status=status)} {available}")

    def collect(self) -> str:
        started = time.time()
        lines: list[str] = [
            "# HELP github_repository_info Repository inventory visible to the GitHub App after policy filtering.",
            "# TYPE github_repository_info gauge",
            "# HELP github_repository_signal_available Signal coverage status by repository.",
            "# TYPE github_repository_signal_available gauge",
            "# HELP github_repository_open_pull_requests Open pull request count by repository.",
            "# TYPE github_repository_open_pull_requests gauge",
            "# HELP github_repository_issues_created_last_7_days Issues created in the last seven days, open or closed, excluding pull requests.",
            "# TYPE github_repository_issues_created_last_7_days gauge",
            "# HELP github_repository_main_failing_statuses Failing checks and commit-status contexts on main's current commit; zero when main is absent.",
            "# TYPE github_repository_main_failing_statuses gauge",
            "# HELP github_repository_main_branch_present Whether a literal main branch exists.",
            "# TYPE github_repository_main_branch_present gauge",
            "# HELP github_repository_oldest_open_pull_request_age_seconds Age of the oldest open pull request.",
            "# TYPE github_repository_oldest_open_pull_request_age_seconds gauge",
            "# HELP github_repository_dependabot_open_alerts Open Dependabot alerts by severity.",
            "# TYPE github_repository_dependabot_open_alerts gauge",
            "# HELP github_repository_dependabot_oldest_open_alert_age_seconds Age of oldest open Dependabot alert by severity.",
            "# TYPE github_repository_dependabot_oldest_open_alert_age_seconds gauge",
            "# HELP github_repository_code_scanning_open_alerts Open code scanning alerts by severity and tool.",
            "# TYPE github_repository_code_scanning_open_alerts gauge",
            "# HELP github_repository_code_scanning_oldest_open_alert_age_seconds Age of oldest open code scanning alert by severity and tool.",
            "# TYPE github_repository_code_scanning_oldest_open_alert_age_seconds gauge",
        ]
        repos_seen = 0
        success = 1
        try:
            for inst in self.client.installations():
                token = self.client.installation_token(int(inst["id"]))
                owner = inst.get("account", {}).get("login", "")
                for raw in self.client.paged("/installation/repositories?per_page=100", token):
                    for item in raw.get("repositories", []) if isinstance(raw, dict) else []:
                        full_name = item["full_name"]
                        repo_owner, repo_name = full_name.split("/", 1)
                        if repo_owner not in self.cfg.owners or full_name in self.cfg.exclude_repositories:
                            continue
                        repo = Repo(repo_owner, repo_name, bool(item.get("archived")), bool(item.get("fork")), item.get("default_branch"))
                        if repo.archived and not self.cfg.include_archived:
                            continue
                        if repo.fork and not self.cfg.include_forks:
                            continue
                        repos_seen += 1
                        lines.append(f"github_repository_info{labels(owner=repo.owner, repository=repo.name, archived=repo.archived, fork=repo.fork, default_branch=repo.default_branch or '')} 1")
                        self.safe_signal(lines, repo, "repository", "ok", 1)
                        self.collect_prs(lines, repo, token)
                        self.collect_issues(lines, repo, token, int(started))
                        self.collect_main_statuses(lines, repo, token)
                        self.collect_dependabot(lines, repo, token)
                        self.collect_code_scanning(lines, repo, token)
        except Exception:
            success = 0
            LOG.exception("collection failed")
        duration = time.time() - started
        lines.extend([
            "# HELP github_repository_observability_collection_success Whether the last collection cycle succeeded.",
            "# TYPE github_repository_observability_collection_success gauge",
            f"github_repository_observability_collection_success {success}",
            "# HELP github_repository_observability_last_success_timestamp_seconds Unix timestamp of the last successful collection.",
            "# TYPE github_repository_observability_last_success_timestamp_seconds gauge",
            f"github_repository_observability_last_success_timestamp_seconds {now_ts() if success else 0}",
            "# HELP github_repository_observability_repositories_seen Repositories emitted in the last collection.",
            "# TYPE github_repository_observability_repositories_seen gauge",
            f"github_repository_observability_repositories_seen {repos_seen}",
            "# HELP github_repository_observability_collection_interval_seconds Configured background collection interval.",
            "# TYPE github_repository_observability_collection_interval_seconds gauge",
            f"github_repository_observability_collection_interval_seconds {self.cfg.interval_seconds}",
            "# HELP github_repository_observability_collection_duration_seconds Duration of the last collection.",
            "# TYPE github_repository_observability_collection_duration_seconds gauge",
            f"github_repository_observability_collection_duration_seconds {duration:.3f}",
            "# HELP github_repository_observability_rate_limit_remaining GitHub API rate limit remaining from last response.",
            "# TYPE github_repository_observability_rate_limit_remaining gauge",
            f"github_repository_observability_rate_limit_remaining {self.client.rate_remaining}",
            "# HELP github_repository_observability_rate_limit_reset_timestamp_seconds GitHub API rate limit reset timestamp from last response.",
            "# TYPE github_repository_observability_rate_limit_reset_timestamp_seconds gauge",
            f"github_repository_observability_rate_limit_reset_timestamp_seconds {self.client.rate_reset}",
        ])
        return "\n".join(lines) + "\n"

    def collect_prs(self, lines: list[str], repo: Repo, token: str) -> None:
        try:
            prs = self.client.paged(f"/repos/{repo.owner}/{repo.name}/pulls?state=open&per_page=100", token)
            oldest = min([parse_github_time(pr.get("created_at")) for pr in prs if parse_github_time(pr.get("created_at"))] or [None])
            lines.append(f"github_repository_open_pull_requests{labels(owner=repo.owner, repository=repo.name)} {len(prs)}")
            lines.append(f"github_repository_oldest_open_pull_request_age_seconds{labels(owner=repo.owner, repository=repo.name)} {max(0, now_ts() - int(oldest)) if oldest else 0}")
            self.safe_signal(lines, repo, "pull_requests", "ok", 1)
        except HTTPError as e:
            self.safe_signal(lines, repo, "pull_requests", f"http_{e.code}", 0)

    def collect_issues(self, lines: list[str], repo: Repo, token: str, collected_at: int) -> None:
        cutoff = collected_at - 7 * 86400
        # GitHub's since filter uses UPDATED time, not creation time. Widen its
        # exclusive boundary by one second, then filter created_at locally.
        since = datetime.fromtimestamp(cutoff - 1, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        query = urlencode({"state": "all", "since": since, "sort": "created", "direction": "desc", "per_page": 100})
        try:
            issues = self.client.paged(f"/repos/{repo.owner}/{repo.name}/issues?{query}", token, require_list=True)
            numbers: set[int] = set()
            for issue in issues:
                if not isinstance(issue, dict):
                    raise ValueError("invalid issue row")
                if "pull_request" in issue:
                    continue
                raw_created = issue.get("created_at")
                if not isinstance(raw_created, str):
                    raise ValueError("missing issue creation time")
                created = datetime.fromisoformat(raw_created.replace("Z", "+00:00"))
                if created.tzinfo is None:
                    raise ValueError("issue creation time has no timezone")
                if cutoff <= created.timestamp() <= collected_at:
                    number = issue.get("number")
                    if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
                        raise ValueError("invalid issue number")
                    numbers.add(number)
            lines.append(f"github_repository_issues_created_last_7_days{labels(owner=repo.owner, repository=repo.name)} {len(numbers)}")
            self.safe_signal(lines, repo, "issues", "ok", 1)
        except HTTPError as error:
            self.safe_signal(lines, repo, "issues", f"http_{error.code}", 0)
        except (URLError, TimeoutError):
            self.safe_signal(lines, repo, "issues", "request_failed", 0)
        except (TypeError, ValueError, OverflowError):
            self.safe_signal(lines, repo, "issues", "invalid_response", 0)

    def collect_main_statuses(self, lines: list[str], repo: Repo, token: str) -> None:
        path = f"/repos/{repo.owner}/{repo.name}"
        try:
            present = 1
            try:
                branch, _ = self.client.request(f"{path}/branches/main", token=token)
            except HTTPError as error:
                if error.code != 404:
                    raise
                # A 404 alone can also mean insufficient access. Only a
                # successful branch listing can establish that main is absent.
                branches = self.client.paged(f"{path}/branches?per_page=100", token, require_list=True)
                if any(not isinstance(item, dict) or not isinstance(item.get("name"), str) for item in branches):
                    raise ValueError("invalid branch listing")
                if any(item["name"] == "main" for item in branches):
                    raise ValueError("inconsistent main branch lookup")
                present = 0
            failures = 0
            if present:
                if not isinstance(branch, dict) or branch.get("name") != "main" or not isinstance(branch.get("commit"), dict):
                    raise ValueError("invalid main branch")
                sha = branch["commit"].get("sha")
                if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha):
                    raise ValueError("invalid main commit")
                # Pin both APIs to one SHA so a moving main cannot mix commits.
                statuses = self.client.paged(f"{path}/commits/{sha}/status?per_page=100", token)
                checks = self.client.paged(f"{path}/commits/{sha}/check-runs?filter=latest&per_page=100", token)
                failures = count_main_failures(statuses, checks, sha)
            lines.append(f"github_repository_main_branch_present{labels(owner=repo.owner, repository=repo.name)} {present}")
            lines.append(f"github_repository_main_failing_statuses{labels(owner=repo.owner, repository=repo.name)} {failures}")
            self.safe_signal(lines, repo, "main_statuses", "ok" if present else "no_main", 1)
        except HTTPError as error:
            self.safe_signal(lines, repo, "main_statuses", f"http_{error.code}", 0)
        except (URLError, TimeoutError):
            self.safe_signal(lines, repo, "main_statuses", "request_failed", 0)
        except (TypeError, ValueError, OverflowError):
            self.safe_signal(lines, repo, "main_statuses", "invalid_response", 0)

    def collect_dependabot(self, lines: list[str], repo: Repo, token: str) -> None:
        counts: dict[str, int] = {s: 0 for s in ("critical", "high", "medium", "low", "unknown")}
        oldest: dict[str, float | None] = {s: None for s in counts}
        try:
            alerts = self.client.paged(f"/repos/{repo.owner}/{repo.name}/dependabot/alerts?state=open&per_page=100", token)
            for alert in alerts:
                sev = alert.get("security_advisory", {}).get("severity", "unknown")
                if sev not in counts:
                    sev = "unknown"
                counts[sev] += 1
                ts = parse_github_time(alert.get("created_at"))
                oldest[sev] = ts if ts and (oldest[sev] is None or ts < oldest[sev]) else oldest[sev]
            for sev, count in counts.items():
                lines.append(f"github_repository_dependabot_open_alerts{labels(owner=repo.owner, repository=repo.name, severity=sev)} {count}")
                lines.append(f"github_repository_dependabot_oldest_open_alert_age_seconds{labels(owner=repo.owner, repository=repo.name, severity=sev)} {max(0, now_ts() - int(oldest[sev])) if oldest[sev] else 0}")
            self.safe_signal(lines, repo, "dependabot", "ok", 1)
        except HTTPError as e:
            self.safe_signal(lines, repo, "dependabot", f"http_{e.code}", 0)

    def collect_code_scanning(self, lines: list[str], repo: Repo, token: str) -> None:
        counts: dict[tuple[str, str], int] = {}
        oldest: dict[tuple[str, str], float | None] = {}
        try:
            alerts = self.client.paged(f"/repos/{repo.owner}/{repo.name}/code-scanning/alerts?state=open&per_page=100", token)
            for alert in alerts:
                sev = alert.get("rule", {}).get("security_severity_level") or alert.get("rule", {}).get("severity") or "unknown"
                if sev not in SEVERITIES:
                    sev = "unknown"
                tool = (alert.get("tool", {}) or {}).get("name") or "unknown"
                tool = "".join(ch for ch in tool.lower() if ch.isalnum() or ch in ("-", "_", "."))[:40] or "unknown"
                key = (sev, tool)
                counts[key] = counts.get(key, 0) + 1
                ts = parse_github_time(alert.get("created_at"))
                oldest[key] = ts if ts and (oldest.get(key) is None or ts < oldest[key]) else oldest.get(key)
            if not counts:
                counts[("unknown", "none")] = 0
                oldest[("unknown", "none")] = None
            for (sev, tool), count in counts.items():
                lines.append(f"github_repository_code_scanning_open_alerts{labels(owner=repo.owner, repository=repo.name, severity=sev, tool=tool)} {count}")
                lines.append(f"github_repository_code_scanning_oldest_open_alert_age_seconds{labels(owner=repo.owner, repository=repo.name, severity=sev, tool=tool)} {max(0, now_ts() - int(oldest[(sev, tool)])) if oldest[(sev, tool)] else 0}")
            self.safe_signal(lines, repo, "code_scanning", "ok", 1)
        except HTTPError as e:
            self.safe_signal(lines, repo, "code_scanning", f"http_{e.code}", 0)


def run_loop(collector: Collector, stop: Event) -> None:
    while not stop.is_set():
        collector.cache.set(collector.collect())
        stop.wait(collector.cfg.interval_seconds)


def parse_args() -> Config:
    p = argparse.ArgumentParser()
    p.add_argument("--github-app-id-file", required=True)
    p.add_argument("--github-private-key-file", required=True)
    p.add_argument("--owner", action="append", required=True)
    p.add_argument("--include-archived", action="store_true")
    p.add_argument("--include-forks", action="store_true")
    p.add_argument("--exclude-repository", action="append", default=[])
    p.add_argument("--collection-interval-seconds", type=int, default=900)
    p.add_argument("--listen-address", default="127.0.0.1:9177")
    args = p.parse_args()
    return Config(args.github_app_id_file, args.github_private_key_file, args.owner, args.include_archived, args.include_forks, set(args.exclude_repository), args.collection_interval_seconds, args.listen_address)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = parse_args()
    cache = Cache()
    collector = Collector(cfg, cache)
    stop = Event()
    Thread(target=run_loop, args=(collector, stop), daemon=True).start()
    host, port_s = cfg.listen_address.rsplit(":", 1)

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

        def log_message(self, fmt: str, *args: Any) -> None:
            return

    LOG.info("serving cached metrics on %s", cfg.listen_address)
    ThreadingHTTPServer((host, int(port_s)), Handler).serve_forever()


if __name__ == "__main__":
    main()
