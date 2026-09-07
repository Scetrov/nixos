## ADDED Requirements

### Requirement: Operations Platform Overview displays current Codex five-hour allowance
The system SHALL display a `5-Hour Remaining` stat panel on the Operations Platform Overview dashboard that calculates remaining Codex allowance as `100 - ai_codex_window_used_percent{window="5h"}` and uses the Mimir datasource with Heart Pumps Neon capacity thresholds: pink below 20%, amber from 20% through 50%, and teal above 50%.

#### Scenario: Fresh authenticated five-hour allowance
- **WHEN** a 5-hour Codex window is present, Codex authentication is explicitly available, the Codex source scrape is successful, and the last successful Codex collection is no older than two configured source poll intervals
- **THEN** the `5-Hour Remaining` panel displays the calculated remaining allowance as a percentage

#### Scenario: Five-hour allowance is not current
- **WHEN** Codex authentication is unavailable, the source scrape is unsuccessful, the 5-hour window is absent, or the last successful collection is older than two configured source poll intervals
- **THEN** the `5-Hour Remaining` panel displays `N/A` and does not display a retained or synthetic usage value

### Requirement: Operations Platform Overview displays Codex five-hour reset
The system SHALL display a `5-Hour Reset` stat panel on the Operations Platform Overview dashboard that calculates `clamp_min(ai_codex_window_reset_timestamp_seconds{window="5h"} - time(), 0)` and formats the result as a duration.

#### Scenario: Fresh five-hour reset timestamp
- **WHEN** a 5-hour Codex window has a reset timestamp, Codex authentication is explicitly available, the Codex source scrape is successful, and the last successful Codex collection is no older than two configured source poll intervals
- **THEN** the `5-Hour Reset` panel displays the non-negative time remaining until reset

#### Scenario: Five-hour reset is not current
- **WHEN** Codex authentication is unavailable, the source scrape is unsuccessful, the 5-hour window or reset timestamp is absent, or the last successful collection is older than two configured source poll intervals
- **THEN** the `5-Hour Reset` panel displays `N/A` rather than a stale, negative, or fabricated duration

## MODIFIED Requirements

### Requirement: Operations Platform Overview avoids retired Codex window labels
The system SHALL query or display the semantic `5h` label only for provider-reported 300-minute Codex windows and SHALL not query or display the retired `7d` label.

#### Scenario: Dashboard uses actual semantic window metrics
- **WHEN** the Operations Platform Overview dashboard definition is validated
- **THEN** its Codex allowance and reset cards use `window="5h"` and `window="weekly"`, contain no query using `window="7d"`, and have presence, authentication, scrape-success, and two-poll freshness gates for each window
