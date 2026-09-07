## ADDED Requirements

### Requirement: Dashboard displays current Codex five-hour usage
The system SHALL display the current five-hour Codex allowance and reset countdown only when a fresh `ai_codex_window_used_percent{window="5h"}` series is actually present, and SHALL clearly distinguish percentage consumed from percentage remaining.

#### Scenario: Five-hour remaining stat panel
- **WHEN** a 5-hour window is present, Codex is authenticated, the Codex scrape succeeds, and the last successful collection is no older than two configured source poll intervals
- **THEN** a stat panel titled `5-Hour Remaining` displays `100 - ai_codex_window_used_percent{window="5h"}` from 0% to 100% with pink below 20%, amber from 20% to 50%, and teal from 50% to 100%

#### Scenario: Five-hour reset countdown
- **WHEN** a fresh 5-hour window includes `ai_codex_window_reset_timestamp_seconds{window="5h"}`
- **THEN** a stat panel titled `5-Hour Reset` displays `clamp_min(ai_codex_window_reset_timestamp_seconds{window="5h"} - time(), 0)` formatted as a duration

#### Scenario: Five-hour window is unavailable
- **WHEN** the 5-hour window is absent, Codex is unauthenticated, the Codex scrape is unsuccessful, or the last successful collection is older than two configured source poll intervals
- **THEN** the 5-hour allowance and reset panels display `N/A` and do not display a retained, zero-used, or synthetic value
