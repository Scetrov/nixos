# ai-usage-dashboard Specification

## Purpose

Defines the Grafana dashboard for visualizing AI usage metrics including Codex usage windows, OpenRouter credit balance, and usage trends over time.

## Requirements

### Requirement: Dashboard displays current Codex weekly usage
The system SHALL display the current weekly Codex allowance using only a fresh `ai_codex_window_used_percent{window="weekly"}` series and SHALL clearly distinguish percentage consumed from percentage remaining.

#### Scenario: Weekly remaining stat panel
- **WHEN** a weekly window is present, Codex is authenticated, and the last successful collection is no older than two configured source poll intervals
- **THEN** a stat panel titled "Weekly Remaining" displays `100 - ai_codex_window_used_percent{window="weekly"}` from 0% to 100% with pink below 20%, amber from 20% to 50%, and teal from 50% to 100%

#### Scenario: Weekly window is absent
- **WHEN** a fresh successful Codex response contains no weekly window
- **THEN** the weekly stat and reset panels display "N/A" rather than substituting a zero-used or 100%-remaining value

#### Scenario: Codex data is stale
- **WHEN** `time() - ai_exporter_last_success_timestamp_seconds{source="codex"}` exceeds twice `ai_exporter_poll_interval_seconds{source="codex"}`
- **THEN** weekly quota and reset panels display "N/A" and a stale-data indicator identifies the condition

#### Scenario: Codex is unauthenticated
- **WHEN** `ai_codex_authenticated` is 0
- **THEN** weekly quota and reset panels display "N/A" and the authentication indicator displays a failure state

### Requirement: Dashboard displays OpenRouter credit balance
The system SHALL display OpenRouter credit usage as a stat panel showing remaining credits and percentage consumed.

#### Scenario: Credit balance stat panel
- **WHEN** the dashboard renders and OpenRouter metrics are available
- **THEN** a stat panel displays the remaining credits calculated as `ai_openrouter_credits_total - ai_openrouter_credits_used` and the percentage consumed

### Requirement: Dashboard displays usage trends over time
The system SHALL include time-series panels showing historical Codex usage for semantic windows actually returned by the provider and the existing OpenRouter usage history.

#### Scenario: Codex weekly usage over time
- **WHEN** viewing the dashboard over a selected time range and weekly samples exist
- **THEN** a time-series panel shows `ai_codex_window_used_percent{window="weekly"}` as percentage consumed and does not require a synthetic 5-hour series

#### Scenario: Additional Codex window appears
- **WHEN** Codex returns another valid duration-derived window
- **THEN** the Codex trend panel can display that actual semantic window as a separate series without relabeling primary or secondary provider slots

#### Scenario: OpenRouter credit consumption over time
- **WHEN** viewing the dashboard over a selected time range
- **THEN** the existing OpenRouter usage time-series behavior remains unchanged

### Requirement: Dashboard displays rate-limit and status indicators
The system SHALL display Codex limit state, weekly reset time, authentication state, source scrape health, and data freshness as distinct indicators.

#### Scenario: Rate-limit status
- **WHEN** fresh `ai_codex_limit_reached` is 1
- **THEN** a status indicator panel displays "Rate Limited" in pink/red

#### Scenario: Weekly reset countdown
- **WHEN** a fresh weekly window includes `ai_codex_window_reset_timestamp_seconds{window="weekly"}`
- **THEN** the dashboard displays the non-negative difference between that timestamp and `time()` formatted as a duration

#### Scenario: Reset timestamp is unavailable
- **WHEN** the fresh weekly window has no valid reset timestamp
- **THEN** the reset panel displays "N/A" without marking the entire exporter target down

#### Scenario: Authentication status
- **WHEN** app-server authentication is unavailable
- **THEN** a dedicated authentication indicator displays a failure distinct from exporter target or OpenRouter health

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
The system SHALL display exporter target health, per-source scrape success, Codex authentication, and per-source freshness without allowing retained samples to mask an outage.

#### Scenario: Codex scrape healthy and fresh
- **WHEN** `ai_exporter_scrape_success{source="codex"}` and `ai_codex_authenticated` are 1 and the last-success timestamp is within two configured poll intervals
- **THEN** Codex scrape, authentication, and freshness indicators display healthy teal states

#### Scenario: OpenRouter scrape healthy
- **WHEN** `ai_exporter_scrape_success{source="openrouter"}` is 1 and its last-success timestamp is within two configured poll intervals
- **THEN** the OpenRouter health indicator displays a healthy teal state

#### Scenario: Source scrape failure
- **WHEN** `ai_exporter_scrape_success` for a source is 0
- **THEN** the corresponding scrape indicator displays pink/red and affected current-value panels display "N/A"

#### Scenario: Source value is retained but stale
- **WHEN** a source's usage series remains in Mimir but its last-success timestamp exceeds two configured poll intervals
- **THEN** the freshness indicator displays stale and current-value panels display "N/A"
