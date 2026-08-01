## ADDED Requirements

### Requirement: Operations Platform Overview displays current Codex allowance
The system SHALL display a `Weekly Remaining` stat panel on the Operations Platform Overview dashboard that calculates remaining Codex allowance as `100 - ai_codex_window_used_percent{window="weekly"}` and uses the Mimir datasource with Heart Pumps Neon capacity thresholds: pink below 20%, amber from 20% through 50%, and teal above 50%.

#### Scenario: Fresh authenticated weekly allowance
- **WHEN** a weekly Codex window is present, Codex authentication is explicitly available, the Codex source scrape is successful, and the last successful Codex collection is no older than two configured source poll intervals
- **THEN** the `Weekly Remaining` panel displays the calculated remaining allowance as a percentage

#### Scenario: Codex allowance is not current
- **WHEN** Codex authentication is unavailable, the source scrape is unsuccessful, the weekly window is absent, or the last successful Codex collection is older than two configured source poll intervals
- **THEN** the `Weekly Remaining` panel displays `N/A` and does not display a retained or synthetic usage value

### Requirement: Operations Platform Overview displays Codex weekly reset
The system SHALL display a `Weekly Reset` stat panel on the Operations Platform Overview dashboard that calculates `clamp_min(ai_codex_window_reset_timestamp_seconds{window="weekly"} - time(), 0)` and formats the result as a duration.

#### Scenario: Fresh weekly reset timestamp
- **WHEN** a weekly Codex window has a reset timestamp, Codex authentication is explicitly available, the Codex source scrape is successful, and the last successful Codex collection is no older than two configured source poll intervals
- **THEN** the `Weekly Reset` panel displays the non-negative time remaining until reset

#### Scenario: Codex reset is not current
- **WHEN** Codex authentication is unavailable, the source scrape is unsuccessful, the weekly window or reset timestamp is absent, or the last successful Codex collection is older than two configured source poll intervals
- **THEN** the `Weekly Reset` panel displays `N/A` rather than a stale, negative, or fabricated duration

### Requirement: Operations Platform Overview avoids retired Codex window labels
The system SHALL not query or display fixed Codex `5h` or `7d` window labels in the Operations Platform Overview dashboard.

#### Scenario: Dashboard uses semantic weekly metrics
- **WHEN** the Operations Platform Overview dashboard definition is validated
- **THEN** its Codex allowance and reset cards use `window="weekly"` and contain no `ai_codex_window_used_percent` query using `window="5h"` or `window="7d"`
