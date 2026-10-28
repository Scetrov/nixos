#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DASHBOARD_PATH = REPO_ROOT / "terraform/dashboards/ai-usage.json"
PLATFORM_OVERVIEW_PATH = REPO_ROOT / "terraform/dashboards/platform-overview.json"
GRAFANA_TF_PATH = REPO_ROOT / "terraform/grafana.tf"


class AIUsageDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dashboard = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
        cls.panels = {panel["id"]: panel for panel in cls.dashboard["panels"]}

    def expressions(self, panel_id: int) -> list[str]:
        return [target["expr"] for target in self.panels[panel_id].get("targets", [])]

    def test_five_hour_remaining_is_freshness_gated_with_approved_thresholds(self) -> None:
        panel = self.panels[1]
        self.assertEqual(panel["title"], "5-Hour Remaining")
        self.assertEqual(panel["fieldConfig"]["defaults"]["unit"], "percent")
        self.assertEqual(panel["fieldConfig"]["defaults"]["noValue"], "N/A")
        self.assertEqual(
            panel["fieldConfig"]["defaults"]["thresholds"]["steps"],
            [
                {"color": "#FF3E8D", "value": None},
                {"color": "#E6C65B", "value": 20},
                {"color": "#008791", "value": 50},
            ],
        )
        expression = self.expressions(1)[0]
        self.assertIn('100 - ai_codex_window_used_percent{window="5h"}', expression)
        self.assert_freshness_gated(expression)
        self.assertIn('ai_codex_window_present{window="5h"}', expression)

    def test_five_hour_reset_uses_absolute_non_negative_countdown(self) -> None:
        panel = self.panels[6]
        self.assertEqual(panel["title"], "5-Hour Reset")
        self.assertEqual(panel["fieldConfig"]["defaults"]["unit"], "s")
        self.assertEqual(panel["fieldConfig"]["defaults"]["noValue"], "N/A")
        self.assertEqual(len(panel["targets"]), 1)
        expression = self.expressions(6)[0]
        self.assertIn(
            'clamp_min(ai_codex_window_reset_timestamp_seconds{window="5h"} - time(), 0)',
            expression,
        )
        self.assert_freshness_gated(expression)

    def test_codex_trend_uses_actual_semantic_windows_and_is_freshness_gated(self) -> None:
        panel = self.panels[7]
        self.assertEqual(len(panel["targets"]), 1)
        target = panel["targets"][0]
        self.assertIn("ai_codex_window_used_percent", target["expr"])
        self.assertNotIn('window="5h"', target["expr"])
        self.assertNotIn('window="7d"', target["expr"])
        self.assertEqual(target["legendFormat"], "{{window}} consumed")
        self.assert_freshness_gated(target["expr"])

    def test_distinct_target_auth_scrape_freshness_and_presence_indicators(self) -> None:
        expected = {
            16: ("Exporter Target", 'up{job="ai-usage",host="habiki"}'),
            2: ("Codex Authentication", "ai_codex_authenticated"),
            10: ("Codex Scrape", 'ai_exporter_scrape_success{source="codex"}'),
            17: ("Codex Freshness", "ai_exporter_last_success_timestamp_seconds"),
            18: ("Weekly Window", 'ai_codex_window_present{window="weekly"}'),
        }
        for panel_id, (title, expression_fragment) in expected.items():
            with self.subTest(panel_id=panel_id):
                panel = self.panels[panel_id]
                self.assertEqual(panel["title"], title)
                self.assertIn(expression_fragment, self.expressions(panel_id)[0])
                self.assertEqual(panel["fieldConfig"]["defaults"]["noValue"], "N/A")
        self.assertIn("<= bool", self.expressions(17)[0])
        self.assertIn("or on() vector(0)", self.expressions(18)[0])
        self.assert_freshness_gated(self.expressions(18)[0])

    def test_rate_limit_is_freshness_gated(self) -> None:
        expression = self.expressions(5)[0]
        self.assertIn("ai_codex_limit_reached", expression)
        self.assert_freshness_gated(expression)

    def test_weekly_cards_are_independently_presence_and_freshness_gated(self) -> None:
        for panel_id, title, metric in (
            (19, "Weekly Remaining", '100 - ai_codex_window_used_percent{window="weekly"}'),
            (20, "Weekly Reset", 'ai_codex_window_reset_timestamp_seconds{window="weekly"}'),
        ):
            with self.subTest(panel_id=panel_id):
                panel = self.panels[panel_id]
                expression = self.expressions(panel_id)[0]
                self.assertEqual(panel["title"], title)
                self.assertEqual(panel["fieldConfig"]["defaults"]["noValue"], "N/A")
                self.assertIn(metric, expression)
                self.assertIn('ai_codex_window_present{window="weekly"}', expression)
                self.assert_freshness_gated(expression)

    def test_retired_fixed_window_and_relative_reset_queries_are_absent(self) -> None:
        expressions = "\n".join(
            target["expr"]
            for panel in self.dashboard["panels"]
            for target in panel.get("targets", [])
            if "expr" in target
        )
        self.assertNotIn('window="7d"', expressions)
        self.assertNotIn("ai_codex_window_reset_seconds", expressions)

    def test_openrouter_panels_and_queries_are_unchanged(self) -> None:
        expected = {
            3: (
                "Monthly Spend (All Keys)",
                {"x": 18, "y": 0, "w": 3, "h": 5},
                ["ai_openrouter_total_usage_monthly"],
            ),
            4: (
                "This Week (All Keys)",
                {"x": 21, "y": 0, "w": 3, "h": 5},
                ["ai_openrouter_total_usage_weekly"],
            ),
            8: (
                "OpenRouter Per-Key Usage (Daily)",
                {"x": 12, "y": 8, "w": 12, "h": 8},
                ["sum by (key) (clamp_min(delta(ai_openrouter_key_usage[1d]), 0))"],
            ),
            11: (
                "OpenRouter Scrape",
                {"x": 6, "y": 5, "w": 6, "h": 3},
                ['ai_exporter_scrape_success{source="openrouter"}'],
            ),
            12: (
                "Scrape Duration",
                {"x": 0, "y": 16, "w": 12, "h": 8},
                [
                    'ai_exporter_scrape_duration_seconds{source="codex"}',
                    'ai_exporter_scrape_duration_seconds{source="openrouter"}',
                ],
            ),
            13: (
                "Keys Enabled",
                {"x": 12, "y": 5, "w": 6, "h": 3},
                ["ai_openrouter_keys_enabled"],
            ),
            14: (
                "Lifetime Total (All Keys)",
                {"x": 18, "y": 5, "w": 6, "h": 3},
                ["ai_openrouter_total_usage"],
            ),
            15: (
                "OpenRouter Keys (All Workstations)",
                {"x": 12, "y": 16, "w": 12, "h": 8},
                ["ai_openrouter_key_usage"],
            ),
        }
        for panel_id, (title, grid, expressions) in expected.items():
            with self.subTest(panel_id=panel_id):
                panel = self.panels[panel_id]
                self.assertEqual(panel["title"], title)
                self.assertEqual(panel["gridPos"], grid)
                self.assertEqual(self.expressions(panel_id), expressions)

    def test_datasource_folder_units_and_palette(self) -> None:
        for panel in self.dashboard["panels"]:
            for target in panel.get("targets", []):
                self.assertEqual(target["datasource"]["uid"], "mimir")
        grafana_tf = GRAFANA_TF_PATH.read_text(encoding="utf-8")
        resource = grafana_tf.split('resource "grafana_dashboard" "ai_usage"', 1)[1].split("}", 1)[0]
        self.assertIn("grafana_folder.operations_services.uid", resource)
        codex_colors = json.dumps([self.panels[index] for index in (1, 2, 5, 6, 7, 10, 16, 17, 18, 19, 20)])
        for color in ("#FF3E8D", "#E6C65B", "#008791"):
            self.assertIn(color, codex_colors)

    def assert_freshness_gated(self, expression: str) -> None:
        self.assertIn('ai_codex_authenticated == 1', expression)
        self.assertIn('ai_exporter_scrape_success{source="codex"} == 1', expression)
        self.assertIn('ai_exporter_last_success_timestamp_seconds{source="codex"}', expression)
        self.assertIn('ai_exporter_poll_interval_seconds{source="codex"}', expression)
        self.assertIn("2 * ai_exporter_poll_interval_seconds", expression)


class PlatformOverviewAIUsageDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        dashboard = json.loads(PLATFORM_OVERVIEW_PATH.read_text(encoding="utf-8"))
        cls.panels = {panel["id"]: panel for panel in dashboard["panels"]}

    def assert_freshness_gated(self, expression: str, window: str) -> None:
        self.assertIn('ai_codex_authenticated == 1', expression)
        self.assertIn('ai_exporter_scrape_success{source="codex"} == 1', expression)
        self.assertIn('ai_exporter_last_success_timestamp_seconds{source="codex"}', expression)
        self.assertIn('ai_exporter_poll_interval_seconds{source="codex"}', expression)
        self.assertIn("2 * ai_exporter_poll_interval_seconds", expression)
        self.assertIn(f'ai_codex_window_present{{window="{window}"}} == 1', expression)

    def test_overview_omits_disk_and_network_pressure_panels(self) -> None:
        retired_ids = {11, 12, 13, 14, 15}
        self.assertTrue(retired_ids.isdisjoint(self.panels))
        for panel in self.panels.values():
            self.assertFalse(panel["title"].startswith(("Disk ", "Root Disk ", "Network Errors")))

    def test_cpu_occupies_former_root_disk_position(self) -> None:
        panel = self.panels[8]
        self.assertEqual(panel["title"], "CPU Used by Host")
        self.assertEqual(panel["gridPos"], {"h": 8, "w": 6, "x": 0, "y": 12})
        self.assertIn('node_cpu_seconds_total{mode="idle"}', panel["targets"][0]["expr"])

    def test_overview_panels_do_not_overlap(self) -> None:
        panels = list(self.panels.values())
        for index, panel in enumerate(panels):
            a = panel["gridPos"]
            self.assertLessEqual(a["x"] + a["w"], 24)
            for other in panels[index + 1:]:
                b = other["gridPos"]
                overlaps = (
                    a["x"] < b["x"] + b["w"]
                    and b["x"] < a["x"] + a["w"]
                    and a["y"] < b["y"] + b["h"]
                    and b["y"] < a["y"] + a["h"]
                )
                self.assertFalse(overlaps, (panel["title"], other["title"]))

    def test_remaining_panels_use_semantic_freshness_gated_usage(self) -> None:
        for panel_id, title, window in (
            (33, "5-Hour Remaining", "5h"),
            (35, "Weekly Remaining", "weekly"),
        ):
            with self.subTest(panel_id=panel_id):
                panel = self.panels[panel_id]
                self.assertEqual(panel["title"], title)
                self.assertEqual(panel["fieldConfig"]["defaults"]["unit"], "percent")
                self.assertEqual(panel["fieldConfig"]["defaults"]["noValue"], "N/A")
                self.assertEqual(panel["targets"][0]["datasource"]["uid"], "mimir")
                self.assertEqual(panel["fieldConfig"]["defaults"]["thresholds"]["steps"], [{"color": "#FF3E8D", "value": 0}, {"color": "#E6C65B", "value": 20}, {"color": "#008791", "value": 50}])
                expression = panel["targets"][0]["expr"]
                self.assertIn(f'ai_codex_window_used_percent{{window="{window}"}}', expression)
                self.assert_freshness_gated(expression, window)

    def test_reset_panels_use_non_negative_freshness_gated_countdowns(self) -> None:
        for panel_id, title, window in (
            (34, "5-Hour Reset", "5h"),
            (36, "Weekly Reset", "weekly"),
        ):
            with self.subTest(panel_id=panel_id):
                panel = self.panels[panel_id]
                self.assertEqual(panel["title"], title)
                self.assertEqual(panel["fieldConfig"]["defaults"]["unit"], "s")
                self.assertEqual(panel["fieldConfig"]["defaults"]["noValue"], "N/A")
                self.assertEqual(panel["targets"][0]["datasource"]["uid"], "mimir")
                expression = panel["targets"][0]["expr"]
                self.assertIn(f'ai_codex_window_reset_timestamp_seconds{{window="{window}"}} - time()', expression)
                self.assert_freshness_gated(expression, window)

    def test_banked_reset_expiry_card_matches_five_hour_size_and_is_freshness_gated(self) -> None:
        panel = self.panels[37]
        self.assertEqual(panel["title"], "Banked Reset Expires")
        self.assertEqual(panel["gridPos"], {"h": 4, "w": 4, "x": 0, "y": 8})
        for dimension in ("h", "w"):
            self.assertEqual(panel["gridPos"][dimension], self.panels[34]["gridPos"][dimension])
        self.assertEqual(panel["type"], "stat")
        self.assertEqual(panel["fieldConfig"]["defaults"]["unit"], "clocks")
        self.assertEqual(panel["fieldConfig"]["defaults"]["decimals"], 0)
        self.assertEqual(panel["fieldConfig"]["defaults"]["noValue"], "N/A")
        self.assertEqual(panel["options"]["graphMode"], "none")
        self.assertEqual(len(panel["targets"]), 1)
        target = panel["targets"][0]
        self.assertEqual(target["datasource"]["uid"], "mimir")
        self.assertTrue(target["instant"])
        self.assertFalse(target["range"])
        expression = target["expr"]
        self.assertIn("ai_codex_banked_reset_next_expiry_timestamp_seconds - time()", expression)
        self.assertIn("ai_codex_banked_reset_next_expiry_timestamp_seconds > time()", expression)
        self.assertIn("ai_codex_banked_reset_details_complete == 1", expression)
        self.assertIn("ai_codex_authenticated == 1", expression)
        self.assertIn('ai_exporter_scrape_success{source="codex"} == 1', expression)
        self.assertIn('time() - ai_exporter_last_success_timestamp_seconds{source="codex"}', expression)
        self.assertIn('2 * ai_exporter_poll_interval_seconds{source="codex"}', expression)
        self.assertNotIn("ai_codex_window_reset_timestamp_seconds", expression)
        self.assertNotIn("or on() vector(0)", expression)

    def test_retired_fixed_window_labels_are_absent(self) -> None:
        expressions = "\n".join(
            target["expr"]
            for panel in self.panels.values()
            for target in panel.get("targets", [])
            if "expr" in target
        )
        self.assertNotIn('window="7d"', expressions)


if __name__ == "__main__":
    unittest.main()
