# ai-usage-dashboard Specification

## Purpose

Defines the Grafana dashboard for visualizing AI usage metrics including Codex usage windows, OpenRouter credit balance, and usage trends over time.

## Requirements

### Requirement: Dashboard displays Codex 5-hour and 7-day window usage
The system SHALL display Codex usage window percentages as stat panels showing the percentage of each window currently used, with threshold-based coloring.

#### Scenario: 5-hour window stat panel
- **WHEN** the dashboard renders and Codex metrics are available
- **THEN** a stat panel displays the 5-hour window `ai_codex_window_used_percent{window="5h"}` value with green (0-50%), yellow (50-80%), and red (80-100%) thresholds

#### Scenario: 7-day window stat panel
- **WHEN** the dashboard renders and Codex metrics are available
- **THEN** a stat panel displays the 7-day window `ai_codex_window_used_percent{window="7d"}` value with green (0-50%), yellow (50-80%), and red (80-100%) thresholds

#### Scenario: Metrics unavailable
- **WHEN** Codex metrics have not been scraped for more than 5 minutes
- **THEN** stat panels display "N/A" rather than stale values

### Requirement: Dashboard displays OpenRouter credit balance
The system SHALL display OpenRouter credit usage as a stat panel showing remaining credits and percentage consumed.

#### Scenario: Credit balance stat panel
- **WHEN** the dashboard renders and OpenRouter metrics are available
- **THEN** a stat panel displays the remaining credits calculated as `ai_openrouter_credits_total - ai_openrouter_credits_used` and the percentage consumed

### Requirement: Dashboard displays usage trends over time
The system SHALL include time-series panels showing historical usage data for both Codex windows and OpenRouter credits.

#### Scenario: Codex usage over time
- **WHEN** viewing the dashboard over a 7-day time range
- **THEN** a time-series panel shows `ai_codex_window_used_percent` for both 5h and 7d windows over the selected time range

#### Scenario: OpenRouter credit consumption over time
- **WHEN** viewing the dashboard over a 7-day time range
- **THEN** a time-series panel shows `ai_openrouter_credits_used` over the selected time range

### Requirement: Dashboard displays rate-limit and status indicators
The system SHALL display rate-limit status and window reset countdowns for both Codex windows.

#### Scenario: Rate-limit status
- **WHEN** `ai_codex_limit_reached` is 1
- **THEN** a status indicator panel displays "Rate Limited" in red

#### Scenario: Window reset countdowns
- **WHEN** Codex metrics are available
- **THEN** the dashboard displays remaining time until window reset using `ai_codex_window_reset_seconds` formatted as hours and minutes

### Requirement: Dashboard is provisioned declaratively via Terraform
The system SHALL provision the dashboard as a `grafana_dashboard` resource in Terraform, placed in the `ops-services` folder, following the existing 13-dashboard pattern.

#### Scenario: Dashboard is created on terraform apply
- **WHEN** `terraform apply` runs with the dashboard JSON file present
- **THEN** the dashboard appears in Grafana under the `ops-services` folder

#### Scenario: Dashboard updates are declarative
- **WHEN** the dashboard JSON source file is modified and `terraform apply` runs
- **THEN** the Grafana dashboard is updated to match the source of truth

#### Scenario: Dashboard uses approved color palette
- **WHEN** the dashboard renders in Grafana dark mode
- **THEN** all time-series and stat panel colors use the Heart Pumps Neon palette defined in AGENTS.md

### Requirement: Dashboard includes scrape health indicators
The system SHALL display whether each data source is being successfully scraped.

#### Scenario: Codex scrape healthy
- **WHEN** `ai_exporter_scrape_success{source="codex"}` is 1
- **THEN** a health indicator shows the Codex data source as green

#### Scenario: OpenRouter scrape healthy
- **WHEN** `ai_exporter_scrape_success{source="openrouter"}` is 1
- **THEN** a health indicator shows the OpenRouter data source as green

#### Scenario: Scrape failure
- **WHEN** `ai_exporter_scrape_success` for a source is 0
- **THEN** the corresponding health indicator shows red and the affected stat panels display "N/A"
