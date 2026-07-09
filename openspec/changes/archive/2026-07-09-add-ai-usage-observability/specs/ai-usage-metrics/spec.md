# ai-usage-metrics Specification

## Purpose

Defines the Prometheus metrics exporter that polls Codex and OpenRouter APIs for AI usage data and exposes structured metrics for Grafana consumption.

## Requirements

### Requirement: Exporter polls Codex wham/usage endpoint with OAuth
The system SHALL poll the `https://chatgpt.com/backend-api/wham/usage` endpoint using OAuth Bearer token authentication from a deployed age-encrypted credential file and SHALL expose Codex usage window metrics as Prometheus gauges.

#### Scenario: Successful Codex usage scrape
- **WHEN** the exporter performs a Codex scrape cycle
- **THEN** it reads the OAuth access token and account ID from the runtime secret file, sends an authenticated GET request to the wham/usage endpoint, and parses `primary_window.used_percent` and `secondary_window.used_percent` into Prometheus gauge metrics

#### Scenario: OAuth token refresh
- **WHEN** the access token is within 5 minutes of expiry or a scrape returns HTTP 401
- **THEN** the exporter SHALL POST to the token refresh URL with the refresh token to obtain a new access token before retrying the scrape

#### Scenario: Codex scrape failure
- **WHEN** the wham/usage endpoint returns a non-200 status or the request times out after 10 seconds
- **THEN** the exporter SHALL set `ai_exporter_scrape_success{source="codex"}` to 0 and leave existing Codex metrics at their last known values

#### Scenario: Rate limit reached
- **WHEN** the wham/usage response indicates `limit_reached: true` or `allowed: false`
- **THEN** the exporter SHALL emit `ai_codex_limit_reached` as 1

#### Scenario: Plan type detection
- **WHEN** the wham/usage response includes `plan_type`
- **THEN** the exporter SHALL emit `ai_codex_plan_type` as an info metric with the plan type value

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
The system SHALL poll both data sources every 60 seconds with a 10-second per-request timeout and SHALL expose scrape duration and success metrics.

#### Scenario: Scrape interval timing
- **WHEN** the exporter is running
- **THEN** it polls the Codex endpoint and the OpenRouter endpoint at a 60-second interval, staggered by 5 seconds to avoid simultaneous requests

#### Scenario: Scrape duration tracking
- **WHEN** a scrape cycle completes (success or failure)
- **THEN** the exporter SHALL update `ai_exporter_scrape_duration_seconds` with the observed request duration for that source

### Requirement: Exporter runs as a systemd service on habiki
The system SHALL run the exporter as a systemd service on the habiki host, configured via a NixOS module, with secret files mounted from age-encrypted paths.

#### Scenario: Service starts on boot
- **WHEN** habiki boots
- **THEN** the `ai-usage-exporter.service` systemd unit starts automatically and begins serving metrics

#### Scenario: Service restarts on failure
- **WHEN** the exporter process exits with a non-zero code
- **THEN** systemd restarts it automatically after a short delay

#### Scenario: Secret files are readable only by the service
- **WHEN** the exporter service starts
- **THEN** the Codex OAuth secret file is mounted with permissions restricted to the service user (mode 0400)
