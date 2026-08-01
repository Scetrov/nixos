# ai-usage-metrics Specification

## Purpose

Defines the Prometheus metrics exporter that polls Codex and OpenRouter APIs for AI usage data and exposes structured metrics for Grafana consumption.

## Requirements

### Requirement: Exporter reads Codex rate limits from app-server
The system SHALL obtain Codex subscription rate limits from the local Codex app-server `account/rateLimits/read` JSON-RPC method over the authorized Unix socket and SHALL NOT refresh ChatGPT OAuth tokens or poll the private WHAM usage endpoint directly.

#### Scenario: Successful app-server rate-limit read
- **WHEN** the exporter performs a Codex collection cycle while app-server is authenticated
- **THEN** it completes protocol initialization, calls `account/rateLimits/read`, and parses the Codex rate-limit snapshot into Prometheus metrics

#### Scenario: Multi-limit response
- **WHEN** the response contains `rateLimitsByLimitId.codex`
- **THEN** the exporter uses that entry as the Codex subscription limit snapshot

#### Scenario: Backward-compatible response
- **WHEN** a Codex-specific multi-limit entry is unavailable and the response contains the backward-compatible `rateLimits` snapshot
- **THEN** the exporter uses `rateLimits` without failing on unknown additional response fields

#### Scenario: App-server explicitly reports unauthenticated
- **WHEN** app-server returns a successful account response stating that no ChatGPT account is authenticated
- **THEN** the exporter emits `ai_codex_authenticated` as 0, sets `ai_exporter_scrape_success{source="codex"}` to 0, and continues collecting OpenRouter metrics

#### Scenario: Authentication state cannot be observed
- **WHEN** the container, socket, timeout, or JSON-RPC protocol fails before app-server returns an explicit account state
- **THEN** the exporter sets Codex scrape success to 0 and leaves the last explicit `ai_codex_authenticated` value unchanged, or omits it when no explicit state has ever been observed

#### Scenario: Rate limit reached
- **WHEN** the snapshot includes a non-null reached-limit classification
- **THEN** the exporter emits `ai_codex_limit_reached` as 1

#### Scenario: Plan type detection
- **WHEN** the snapshot includes a plan type
- **THEN** the exporter emits `ai_codex_plan_type` as an info metric without rejecting previously unknown plan values

### Requirement: Exporter identifies Codex windows by reported duration
The system SHALL derive each Codex window's semantic identity from its positive provider-reported duration and SHALL emit metrics only for windows actually present in the response.

#### Scenario: Weekly-only response
- **WHEN** app-server returns one window with `windowDurationMins` equal to 10,080 and a null or absent secondary window
- **THEN** the exporter emits `ai_codex_window_used_percent{window="weekly"}`, `ai_codex_window_duration_seconds{window="weekly"}`, `ai_codex_window_reset_timestamp_seconds{window="weekly"}`, and `ai_codex_window_present{window="weekly"}` without emitting a placeholder 5-hour window

#### Scenario: Real 5-hour window is present
- **WHEN** app-server returns a window with `windowDurationMins` equal to 300
- **THEN** the exporter emits that actual window with `window="5h"` independently of whether it arrived in the primary or secondary slot

#### Scenario: Unknown positive duration
- **WHEN** app-server returns a valid window duration that has no configured semantic name
- **THEN** the exporter emits the window under a deterministic duration-derived label and preserves its exact duration in `ai_codex_window_duration_seconds`

#### Scenario: Window is absent
- **WHEN** a primary or secondary slot is null or missing
- **THEN** the exporter emits no usage, duration, reset, or presence series for that absent window and does not substitute zero

#### Scenario: Duplicate semantic duration
- **WHEN** two returned windows normalize to the same duration-derived label
- **THEN** the exporter rejects the ambiguous Codex snapshot and marks the scrape unsuccessful rather than overwriting or duplicating a Prometheus series

#### Scenario: Malformed window
- **WHEN** a window has a non-finite percentage, non-positive duration, invalid reset timestamp, or unexpected data type
- **THEN** the exporter rejects that window, marks the Codex scrape unsuccessful, and logs a sanitized schema diagnostic without logging credentials or the complete account payload

### Requirement: Exporter exposes source freshness
The system SHALL expose an absolute Unix timestamp for the last successful collection and the configured poll interval for each source so consumers can distinguish retained last-known values from current data and calculate a staleness threshold of two source intervals.

#### Scenario: Successful Codex collection
- **WHEN** a valid Codex rate-limit collection completes
- **THEN** the exporter updates `ai_exporter_last_success_timestamp_seconds{source="codex"}` to the completion time and sets `ai_exporter_scrape_success{source="codex"}` to 1

#### Scenario: Failed Codex collection after prior success
- **WHEN** a Codex collection fails after at least one successful collection
- **THEN** the exporter leaves the last-success timestamp and last-known usage samples unchanged while setting scrape success to 0

#### Scenario: No successful Codex collection
- **WHEN** the exporter has not completed a valid Codex collection since startup
- **THEN** it does not expose last-known Codex usage as current data and reports the Codex source as unsuccessful

#### Scenario: Poll interval is exposed
- **WHEN** the exporter serves metrics
- **THEN** it emits `ai_exporter_poll_interval_seconds{source="codex"}` and the corresponding OpenRouter series with the effective configured source interval

#### Scenario: Prometheus cache is scraped between provider polls
- **WHEN** Alloy scrapes `/metrics` between Codex source polls
- **THEN** the absolute last-success and reset timestamps plus `ai_exporter_poll_interval_seconds` allow PromQL to calculate current data age, the two-interval staleness threshold, and reset countdown without relying on a cached relative duration

### Requirement: Exporter polls OpenRouter credits endpoint with API key
The system SHALL poll the `https://openrouter.ai/api/v1/credits` endpoint using the existing OpenRouter API key and SHALL expose credit balance metrics as Prometheus gauges.

#### Scenario: Successful OpenRouter credits scrape
- **WHEN** the exporter performs an OpenRouter scrape cycle
- **THEN** it reads the OpenRouter API key from the runtime environment, sends an authenticated GET request to the /credits endpoint, and parses `total_credits` and `total_usage` into Prometheus gauge metrics

#### Scenario: OpenRouter scrape failure
- **WHEN** the /credits endpoint returns a non-200 status or the request times out after 10 seconds
- **THEN** the exporter SHALL set `ai_exporter_scrape_success{source="openrouter"}` to 0 and leave existing OpenRouter metrics at their last known values

### Requirement: Exporter exposes Prometheus metrics on a configurable port
The system SHALL expose all AI usage metrics via an HTTP `/metrics` endpoint on a configurable port with the standard Prometheus text format.

#### Scenario: Metrics endpoint is reachable
- **WHEN** the exporter is running and Alloy scrapes its `/metrics` endpoint
- **THEN** the response contains all Codex and OpenRouter metrics in valid Prometheus exposition format

#### Scenario: Port conflicts are detectable
- **WHEN** the configured port is already in use
- **THEN** the exporter SHALL fail to start with a clear error message indicating the port conflict

### Requirement: Exporter follows existing scrape interval and timeout conventions
The system SHALL poll Codex app-server and OpenRouter on a configurable interval that defaults to 900 seconds, SHALL retain a 10-second per-request timeout unless the local protocol requires a stricter bound, and SHALL expose scrape duration, success, and last-success metrics.

#### Scenario: Scrape interval timing
- **WHEN** the exporter runs with default configuration
- **THEN** it polls Codex app-server and OpenRouter every 900 seconds, staggered so the two source requests are not initiated simultaneously

#### Scenario: Configured scrape interval
- **WHEN** a positive non-default source poll interval is configured
- **THEN** the exporter applies that interval consistently and exposes enough configuration or timestamp data for consumers to use a staleness threshold of two source intervals

#### Scenario: Scrape duration tracking
- **WHEN** a scrape cycle completes successfully or unsuccessfully
- **THEN** the exporter updates `ai_exporter_scrape_duration_seconds` with the observed request duration for that source

### Requirement: Exporter runs as a systemd service on habiki
The system SHALL run the exporter as a hardened systemd service on Habiki, configured through a NixOS module, ordered after the Codex app-server workload, authorized to access only its local Unix socket and existing OpenRouter secret, and independent enough to continue serving OpenRouter metrics during Codex failure.

#### Scenario: Service starts on boot
- **WHEN** Habiki boots
- **THEN** the `ai-usage-exporter.service` systemd unit starts automatically after the app-server workload has been requested and begins serving metrics

#### Scenario: Service restarts on failure
- **WHEN** the exporter process exits with a non-zero code
- **THEN** systemd restarts it automatically after a short delay

#### Scenario: App-server is temporarily unavailable
- **WHEN** the exporter cannot open the app-server Unix socket or complete JSON-RPC initialization
- **THEN** it marks only the Codex source unsuccessful, retries on a later cycle, and continues serving OpenRouter and exporter health metrics

#### Scenario: Runtime access is least privilege
- **WHEN** service permissions and mounts are inspected
- **THEN** the exporter can access the app-server control socket and OpenRouter secret but cannot read the app-server OAuth state or the retired Codex OAuth secret
