#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError

TEST_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location(
    "github_main_exporter", TEST_DIR.parent / "files/etc/nixos/pkgs/github-repository-observability-exporter.py",
)
assert SPEC and SPEC.loader
exporter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = exporter
SPEC.loader.exec_module(exporter)
SHA = "a" * 40


def commit_status(identifier: int, context: str = "external-ci", state: str = "failure") -> dict:
    return {"id": identifier, "context": context, "state": state}


def check_run(identifier: int, name: str = "build", conclusion: str | None = "failure", *,
              state: str = "completed", app_id: int = 1, sha: str = SHA) -> dict:
    return {"id": identifier, "name": name, "conclusion": conclusion,
            "status": state, "app": {"id": app_id}, "head_sha": sha}


def pages(statuses: list[dict], checks: list[dict]) -> tuple[list[dict], list[dict]]:
    return ([{"sha": SHA, "total_count": len(statuses), "statuses": statuses}],
            [{"total_count": len(checks), "check_runs": checks}])


class MainFailureNormalizationTests(unittest.TestCase):
    def test_counts_failures_not_pending_cancelled_skipped_neutral_or_stale(self) -> None:
        statuses = [commit_status(i, str(i), state) for i, state in enumerate(
            ("failure", "error", "pending", "success"), 1,
        )]
        conclusions = ("failure", "timed_out", "action_required", "startup_failure",
                       "success", "neutral", "cancelled", "skipped", "stale")
        checks = [check_run(i, str(i), conclusion) for i, conclusion in enumerate(conclusions, 1)]
        checks.append(check_run(10, "pending", None, state="queued"))
        self.assertEqual(exporter.count_main_failures(*pages(statuses, checks), SHA), 6)

    def test_successful_and_pending_reruns_replace_old_failures(self) -> None:
        statuses = [commit_status(1), commit_status(2, state="success")]
        checks = [check_run(1), check_run(2, conclusion="success"),
                  check_run(3, "test"), check_run(4, "test", None, state="in_progress"),
                  check_run(5, app_id=2)]
        self.assertEqual(exporter.count_main_failures(*pages(statuses, checks), SHA), 1)

    def test_empty_statuses_and_checks_are_a_real_zero(self) -> None:
        self.assertEqual(exporter.count_main_failures(*pages([], []), SHA), 0)

    def test_all_pages_are_counted_and_identical_duplicate_ids_are_deduplicated(self) -> None:
        first, second = commit_status(1, "one"), commit_status(2, "two")
        statuses = [{"sha": SHA, "total_count": 2, "statuses": [first]},
                    {"sha": SHA, "total_count": 2, "statuses": [first, second]}]
        checks = [{"total_count": 2, "check_runs": [check_run(1, "one")]},
                  {"total_count": 2, "check_runs": [check_run(2, "two")]}]
        self.assertEqual(exporter.count_main_failures(statuses, checks, SHA), 4)

    def test_incomplete_changing_or_malformed_pages_are_rejected(self) -> None:
        invalid = [[], [None], [{"total_count": 0, "check_runs": None}],
                   [{"total_count": True, "check_runs": []}],
                   [{"total_count": 2, "check_runs": [check_run(1)]}],
                   [{"total_count": 1, "check_runs": [check_run(1)]},
                    {"total_count": 2, "check_runs": [check_run(2)]}],
                   [{"total_count": 1, "check_runs": [check_run(1)]},
                    {"total_count": 1, "check_runs": [check_run(1, conclusion="success")]}],
                   [{"total_count": 1, "check_runs": [{"id": True}]}]]
        for check_pages in invalid:
            with self.subTest(check_pages=check_pages):
                with self.assertRaises(ValueError):
                    exporter.count_main_failures(pages([], [])[0], check_pages, SHA)

    def test_mismatched_commit_references_are_rejected(self) -> None:
        statuses, checks = pages([], [check_run(1, sha="b" * 40)])
        with self.assertRaises(ValueError):
            exporter.count_main_failures(statuses, checks, SHA)
        statuses, checks = pages([], [])
        statuses[0]["sha"] = "b" * 40
        with self.assertRaises(ValueError):
            exporter.count_main_failures(statuses, checks, SHA)

    def test_unknown_or_inconsistent_statuses_are_rejected_without_echoing_text(self) -> None:
        marker = "synthetic-sensitive-check-name"
        bad_checks = [check_run(1, marker, "future-conclusion"),
                      check_run(1, marker, None),
                      check_run(1, marker, state="future-state"),
                      check_run(1, marker, state="queued"),
                      check_run(1, marker, app_id=True),
                      {**check_run(1), "app": None}]
        for check in bad_checks:
            with self.subTest(check=check):
                with self.assertRaises(ValueError) as raised:
                    exporter.count_main_failures(*pages([], [check]), SHA)
                self.assertNotIn(marker, str(raised.exception))
        for status in (commit_status(1, state="unknown"), commit_status(1, context="")):
            with self.assertRaises(ValueError):
                exporter.count_main_failures(*pages([status], []), SHA)


class MainFailureCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.collector = object.__new__(exporter.Collector)
        self.client = self.collector.client = mock.Mock()
        self.repo = exporter.Repo("Scetrov", "synthetic-repository", False, False)
        self.client.request.return_value = ({"name": "main", "commit": {"sha": SHA}}, {})

    def collect(self) -> list[str]:
        lines: list[str] = []
        self.collector.collect_main_statuses(lines, self.repo, "synthetic-token")
        return lines

    def test_fetches_literal_main_and_pins_both_status_apis_to_same_sha(self) -> None:
        self.client.paged.side_effect = pages([commit_status(1)], [check_run(1)])
        lines = self.collect()
        self.client.request.assert_called_once_with(
            "/repos/Scetrov/synthetic-repository/branches/main", token="synthetic-token",
        )
        calls = [call.args[0] for call in self.client.paged.call_args_list]
        self.assertIn(f"/commits/{SHA}/status?", calls[0])
        self.assertIn(f"/commits/{SHA}/check-runs?filter=latest", calls[1])
        self.assertIn('github_repository_main_failing_statuses{owner="Scetrov",repository="synthetic-repository"} 2', lines)
        self.assertIn('github_repository_main_branch_present{owner="Scetrov",repository="synthetic-repository"} 1', lines)
        self.assertIn('signal="main_statuses",status="ok"} 1', lines[-1])
        self.assertNotIn("external-ci", "\n".join(lines))
        self.assertNotIn(SHA, "\n".join(lines))

    def test_missing_main_requires_successful_branch_listing_and_never_falls_back(self) -> None:
        self.client.request.side_effect = HTTPError("https://api.github.com", 404, "synthetic", {}, None)
        self.client.paged.return_value = [{"name": "master"}, {"name": "develop"}]
        lines = self.collect()
        self.assertIn('github_repository_main_branch_present{owner="Scetrov",repository="synthetic-repository"} 0', lines)
        self.assertIn('github_repository_main_failing_statuses{owner="Scetrov",repository="synthetic-repository"} 0', lines)
        self.assertIn('signal="main_statuses",status="no_main"} 1', lines[-1])
        self.client.paged.assert_called_once_with(
            "/repos/Scetrov/synthetic-repository/branches?per_page=100", "synthetic-token", require_list=True,
        )

    def test_inaccessible_branch_listing_does_not_masquerade_as_no_main(self) -> None:
        self.client.request.side_effect = HTTPError("https://api.github.com", 404, "synthetic", {}, None)
        self.client.paged.side_effect = HTTPError("https://api.github.com", 403, "synthetic", {}, None)
        lines = self.collect()
        self.assertEqual(len(lines), 1)
        self.assertIn('signal="main_statuses",status="http_403"} 0', lines[0])

    def test_inconsistent_main_lookup_and_alias_branch_are_unknown(self) -> None:
        self.client.request.side_effect = HTTPError("https://api.github.com", 404, "synthetic", {}, None)
        self.client.paged.return_value = [{"name": "main"}]
        self.assertIn('status="invalid_response"} 0', self.collect()[0])
        self.client.request.side_effect = None
        self.client.request.return_value = ({"name": "master", "commit": {"sha": SHA}}, {})
        self.assertIn('status="invalid_response"} 0', self.collect()[0])

    def test_partial_status_reads_emit_unknown_not_partial_failure_count(self) -> None:
        statuses = pages([commit_status(1)], [])[0]
        for error, status in (
            (HTTPError("https://api.github.com", 403, "synthetic", {}, None), "http_403"),
            (HTTPError("https://api.github.com", 429, "synthetic", {}, None), "http_429"),
            (URLError("synthetic"), "request_failed"),
            (TimeoutError(), "request_failed"),
        ):
            with self.subTest(status=status):
                self.client.paged.side_effect = [statuses, error]
                lines = self.collect()
                self.assertEqual(len(lines), 1)
                self.assertIn(f'status="{status}"}} 0', lines[0])

    def test_malformed_sha_is_rejected_before_requesting_commit_data(self) -> None:
        self.client.request.return_value = ({"name": "main", "commit": {"sha": "../not-a-sha"}}, {})
        self.assertIn('status="invalid_response"} 0', self.collect()[0])
        self.client.paged.assert_not_called()


class MainAndIssueDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.overview = json.loads((REPO_ROOT / "terraform/dashboards/platform-overview.json").read_text())
        cls.health = json.loads((REPO_ROOT / "terraform/dashboards/github-repository-health.json").read_text())

    def test_overview_main_card_is_left_of_issues_and_requires_full_fresh_coverage(self) -> None:
        panels = {panel["id"]: panel for panel in self.overview["panels"]}
        main, issues = panels[39], panels[38]
        self.assertEqual(main["title"], "GitHub Main Failures")
        self.assertEqual(main["gridPos"], {"h": 4, "w": 4, "x": 4, "y": 8})
        self.assertEqual(main["gridPos"]["x"] + main["gridPos"]["w"], issues["gridPos"]["x"])
        self.assertEqual(main["fieldConfig"]["defaults"]["noValue"], "N/A")
        self.assertEqual(main["fieldConfig"]["defaults"]["thresholds"]["steps"], [
            {"color": "#008791", "value": None}, {"color": "#FF3E8D", "value": 1},
        ])
        expr = main["targets"][0]["expr"]
        for fragment in ("github_repository_main_failing_statuses", 'signal="main_statuses"',
                         "github_repository_observability_collection_success == 1",
                         "github_repository_observability_last_success_timestamp_seconds",
                         "github_repository_observability_collection_interval_seconds",
                         'count(count by (owner) (github_repository_info{owner=~"RichardSlater|Scetrov"})) == 2'):
            self.assertIn(fragment, expr)
        self.assertNotIn("or vector(0)", expr)

    def test_repository_table_has_fresh_issue_main_counts_and_main_presence(self) -> None:
        panel = next(panel for panel in self.health["panels"] if panel["id"] == 14)
        self.assertEqual(panel["type"], "table")
        self.assertEqual(panel["gridPos"], {"x": 0, "y": 20, "w": 24, "h": 16})
        self.assertEqual(panel["fieldConfig"]["defaults"]["noValue"], "N/A")
        self.assertEqual(len(panel["targets"]), 4)
        for target in panel["targets"]:
            self.assertTrue(target["instant"])
            self.assertFalse(target["range"])
            self.assertEqual(target["format"], "table")
            self.assertEqual(target["datasource"]["uid"], "mimir")
            self.assertIn("github_repository_observability_collection_success == 1", target["expr"])
            self.assertIn("github_repository_observability_last_success_timestamp_seconds", target["expr"])
            self.assertIn('"repo", "/", "owner", "repository"', target["expr"])
        self.assertIn("github_repository_issues_created_last_7_days", panel["targets"][1]["expr"])
        self.assertIn('signal="issues"', panel["targets"][1]["expr"])
        self.assertIn("github_repository_main_failing_statuses", panel["targets"][2]["expr"])
        self.assertIn('signal="main_statuses"', panel["targets"][2]["expr"])
        self.assertIn("github_repository_main_branch_present", panel["targets"][3]["expr"])
        names = panel["transformations"][-1]["options"]["renameByName"]
        self.assertEqual(names, {"repo": "Repository", "Value #B": "Issues 7d",
                                 "Value #C": "Failing main", "Value #D": "Has main"})

    def test_both_dashboards_have_unique_ids_and_non_overlapping_layouts(self) -> None:
        for dashboard in (self.overview, self.health):
            panels = dashboard["panels"]
            self.assertEqual(len(panels), len({panel["id"] for panel in panels}))
            for index, panel in enumerate(panels):
                a = panel["gridPos"]
                self.assertLessEqual(a["x"] + a["w"], 24)
                for other in panels[index + 1:]:
                    b = other["gridPos"]
                    overlap = a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]
                    self.assertFalse(overlap, (panel["title"], other["title"]))


if __name__ == "__main__":
    unittest.main()
