#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DASHBOARD_PATH = REPO_ROOT / "terraform/dashboards/ai-usage.json"
GRAFANA_TF_PATH = REPO_ROOT / "terraform/grafana.tf"


class AIUsageDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dashboard = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
        cls.panels = {panel["id"]: panel for panel in cls.dashboard["panels"]}

    def expressions(self, panel_id: int) -> list[str]:
        return [target["expr"] for target in self.panels[panel_id].get("targets", [])]

    def test_weekly_remaining_is_freshness_gated_with_approved_thresholds(self) -> None:
        panel = self.panels[1]
        self.assertEqual(panel["title"], "Weekly Remaining")
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
        self.assertIn('100 - ai_codex_window_used_percent{window="weekly"}', expression)
        self.assert_freshness_gated(expression)
        self.assertIn('ai_codex_window_present{window="weekly"}', expression)

    def test_weekly_reset_uses_absolute_non_negative_countdown(self) -> None:
        panel = self.panels[6]
        self.assertEqual(panel["title"], "Weekly Reset")
        self.assertEqual(panel["fieldConfig"]["defaults"]["unit"], "s")
        self.assertEqual(panel["fieldConfig"]["defaults"]["noValue"], "N/A")
        self.assertEqual(len(panel["targets"]), 1)
        expression = self.expressions(6)[0]
        self.assertIn(
            'clamp_min(ai_codex_window_reset_timestamp_seconds{window="weekly"} - time(), 0)',
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

    def test_old_fixed_window_and_relative_reset_queries_are_absent(self) -> None:
        expressions = "\n".join(
            target["expr"]
            for panel in self.dashboard["panels"]
            for target in panel.get("targets", [])
            if "expr" in target
        )
        self.assertNotIn('ai_codex_window_used_percent{window="5h"}', expressions)
        self.assertNotIn('ai_codex_window_used_percent{window="7d"}', expressions)
        self.assertNotIn("ai_codex_window_reset_seconds", expressions)

    def test_openrouter_panels_and_queries_are_unchanged(self) -> None:
        expected = {
            3: (
                "Monthly Spend (All Keys)",
                {"x": 8, "y": 0, "w": 4, "h": 5},
                ["ai_openrouter_total_usage_monthly"],
            ),
            4: (
                "This Week (All Keys)",
                {"x": 12, "y": 0, "w": 4, "h": 5},
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
        codex_colors = json.dumps([self.panels[index] for index in (1, 2, 5, 6, 7, 10, 16, 17, 18)])
        for color in ("#FF3E8D", "#E6C65B", "#008791"):
            self.assertIn(color, codex_colors)

    def assert_freshness_gated(self, expression: str) -> None:
        self.assertIn('ai_codex_authenticated == 1', expression)
        self.assertIn('ai_exporter_scrape_success{source="codex"} == 1', expression)
        self.assertIn('ai_exporter_last_success_timestamp_seconds{source="codex"}', expression)
        self.assertIn('ai_exporter_poll_interval_seconds{source="codex"}', expression)
        self.assertIn("2 * ai_exporter_poll_interval_seconds", expression)


if __name__ == "__main__":
    unittest.main()
