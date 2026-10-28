#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

TEST_DIR = Path(__file__).resolve().parent
REPO_ROOT = TEST_DIR.parents[3]
MODULE_PATH = TEST_DIR.parent / "files/etc/nixos/pkgs/github-repository-observability-exporter.py"
SPEC = importlib.util.spec_from_file_location("github_repository_exporter", MODULE_PATH)
assert SPEC and SPEC.loader
exporter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = exporter
SPEC.loader.exec_module(exporter)
NOW = 1793218000
CUTOFF = NOW - 7 * 86400


def issue(number: int, created: int, **extra: object) -> dict:
    return {
        "number": number,
        "created_at": datetime.fromtimestamp(created, timezone.utc).isoformat(),
        **extra,
    }


class GitHubIssueCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = mock.Mock()
        cfg = exporter.Config(
            "unused-app-id", "unused-private-key", ["RichardSlater", "Scetrov"],
            False, False, set(), 900, "127.0.0.1:9177",
        )
        with mock.patch.object(exporter, "GitHubClient", return_value=self.client):
            self.collector = exporter.Collector(cfg, exporter.Cache())
        self.repo = exporter.Repo("Scetrov", "synthetic-repository", False, False)

    def collect(self, rows: list) -> list[str]:
        self.client.paged.return_value = rows
        lines: list[str] = []
        self.collector.collect_issues(lines, self.repo, "synthetic-token", NOW)
        return lines

    def assert_count(self, lines: list[str], count: int) -> None:
        self.assertIn(
            'github_repository_issues_created_last_7_days{owner="Scetrov",repository="synthetic-repository"} '
            + str(count), lines,
        )
        self.assertIn(
            'github_repository_signal_available{owner="Scetrov",repository="synthetic-repository",signal="issues",status="ok"} 1',
            lines,
        )

    def test_counts_created_time_including_closed_and_exact_boundary_not_prs(self) -> None:
        lines = self.collect([
            issue(1, CUTOFF, state="closed"),
            issue(2, NOW, state="open"),
            issue(3, CUTOFF - 1, updated_at=datetime.fromtimestamp(NOW, timezone.utc).isoformat()),
            issue(4, NOW + 1),
            issue(5, NOW - 10, pull_request={"url": "synthetic-pr"}),
            issue(6, NOW - 10, pull_request=None),
            issue(2, NOW, state="open"),
        ])
        self.assert_count(lines, 2)
        path, token = self.client.paged.call_args.args
        self.assertEqual(token, "synthetic-token")
        self.assertEqual(urlsplit(path).path, "/repos/Scetrov/synthetic-repository/issues")
        query = parse_qs(urlsplit(path).query)
        self.assertEqual(query["state"], ["all"])
        self.assertEqual(query["per_page"], ["100"])
        self.assertEqual(query["sort"], ["created"])
        since = datetime.fromisoformat(query["since"][0].replace("Z", "+00:00")).timestamp()
        self.assertEqual(since, CUTOFF - 1)

    def test_empty_success_is_a_real_zero(self) -> None:
        self.assert_count(self.collect([]), 0)

    def test_http_and_transport_failures_emit_unavailable_not_zero(self) -> None:
        failures = [(HTTPError("https://api.github.com", code, "synthetic", {}, None), f"http_{code}")
                    for code in (403, 404, 410, 429, 503)]
        failures.extend([(URLError("synthetic"), "request_failed"), (TimeoutError(), "request_failed")])
        for error, status in failures:
            with self.subTest(status=status):
                self.client.paged.side_effect = error
                lines: list[str] = []
                self.collector.collect_issues(lines, self.repo, "synthetic-token", NOW)
                self.assertEqual(len(lines), 1)
                self.assertIn(f'status="{status}"}} 0', lines[0])
                self.assertNotIn("github_repository_issues_created_last_7_days", lines[0])

    def test_malformed_rows_fail_closed_without_issue_text_or_urls(self) -> None:
        marker = "synthetic-sensitive-issue-title"
        rows = [None, {}, {"created_at": marker}, {"created_at": 42},
                {"created_at": "2026-10-28T00:00:00"},
                issue(True, NOW), issue(0, NOW), issue("bad", NOW)]
        for row in rows:
            with self.subTest(row=row):
                lines = self.collect([issue(1, NOW, title=marker), row])
                self.assertEqual(len(lines), 1)
                self.assertIn('signal="issues",status="invalid_response"} 0', lines[0])
                self.assertNotIn(marker, "\n".join(lines))

    def test_follows_all_issue_pages_before_emitting_count(self) -> None:
        client = object.__new__(exporter.GitHubClient)
        client.request = mock.Mock(side_effect=[
            ([issue(1, NOW)], {"link": '<https://api.github.com/repos/Scetrov/synthetic-repository/issues?page=2>; rel="next"'}),
            ([issue(2, NOW - 1)], {}),
        ])
        self.collector.client = client
        lines: list[str] = []
        self.collector.collect_issues(lines, self.repo, "synthetic-token", NOW)
        self.assert_count(lines, 2)
        self.assertEqual(client.request.call_count, 2)

    def test_malformed_page_is_unavailable_not_a_healthy_zero(self) -> None:
        for payload in (None, {}, "synthetic-invalid-page"):
            with self.subTest(payload=payload):
                client = object.__new__(exporter.GitHubClient)
                client.request = mock.Mock(return_value=(payload, {}))
                self.collector.client = client
                lines: list[str] = []
                self.collector.collect_issues(lines, self.repo, "synthetic-token", NOW)
                self.assertEqual(len(lines), 1)
                self.assertIn('signal="issues",status="invalid_response"} 0', lines[0])

    def test_collection_uses_one_window_anchor_and_emits_interval(self) -> None:
        self.client.installations.return_value = [{"id": 1, "account": {"login": "Scetrov"}}]
        self.client.installation_token.return_value = "synthetic-token"
        self.client.rate_remaining = 1000
        self.client.rate_reset = NOW + 3600
        self.client.paged.side_effect = [
            [{"repositories": [
                {"full_name": "Scetrov/one"}, {"full_name": "Scetrov/two"},
                {"full_name": "Scetrov/fork", "fork": True},
                {"full_name": "Scetrov/archive", "archived": True},
            ]}],
            [], [],
        ]
        with (
            mock.patch.object(exporter.time, "time", return_value=NOW),
            mock.patch.object(self.collector, "collect_prs"),
            mock.patch.object(self.collector, "collect_main_statuses"),
            mock.patch.object(self.collector, "collect_dependabot"),
            mock.patch.object(self.collector, "collect_code_scanning"),
        ):
            metrics = self.collector.collect()
        self.assertEqual(metrics.count('signal="issues",status="ok"} 1'), 2)
        self.assertIn("github_repository_observability_collection_interval_seconds 900", metrics)
        self.assertIn("github_repository_observability_collection_success 1", metrics)
        queries = [parse_qs(urlsplit(call.args[0]).query) for call in self.client.paged.call_args_list[1:]]
        self.assertEqual(queries[0]["since"], queries[1]["since"])


class GitHubIssueDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dashboard = json.loads((REPO_ROOT / "terraform/dashboards/platform-overview.json").read_text())
        cls.panels = {panel["id"]: panel for panel in cls.dashboard["panels"]}

    def test_card_is_immediately_left_of_open_prs_and_uses_count_units(self) -> None:
        card = self.panels[38]
        prs = self.panels[28]
        self.assertEqual(card["title"], "GitHub Issues 7d")
        self.assertEqual(card["gridPos"], {"h": 4, "w": 4, "x": 8, "y": 8})
        self.assertEqual(card["gridPos"]["x"] + card["gridPos"]["w"], prs["gridPos"]["x"])
        self.assertEqual(card["gridPos"]["y"], prs["gridPos"]["y"])
        self.assertEqual(card["fieldConfig"]["defaults"]["noValue"], "N/A")
        self.assertEqual(card["fieldConfig"]["defaults"]["decimals"], 0)
        self.assertEqual(card["fieldConfig"]["defaults"]["unit"], "short")
        self.assertTrue(card["targets"][0]["instant"])
        self.assertFalse(card["targets"][0]["range"])
        self.assertEqual(card["targets"][0]["datasource"]["uid"], "mimir")

    def test_count_requires_both_owners_complete_coverage_and_fresh_collection(self) -> None:
        expression = self.panels[38]["targets"][0]["expr"]
        self.assertIn('github_repository_issues_created_last_7_days{owner=~"RichardSlater|Scetrov"}', expression)
        self.assertIn('signal="issues"', expression)
        self.assertIn("github_repository_observability_collection_success == 1", expression)
        self.assertIn("github_repository_observability_last_success_timestamp_seconds", expression)
        self.assertIn("2 * github_repository_observability_collection_interval_seconds", expression)
        self.assertIn('count(count by (owner) (github_repository_info{owner=~"RichardSlater|Scetrov"})) == 2', expression)
        self.assertIn('count(github_repository_issues_created_last_7_days{owner=~"RichardSlater|Scetrov"}) == count(github_repository_info{owner=~"RichardSlater|Scetrov"})', expression)
        self.assertNotIn("increase(", expression)
        self.assertNotIn("or vector(0)", expression)
        self.assertNotIn("or on() vector(0)", expression)


if __name__ == "__main__":
    unittest.main()
