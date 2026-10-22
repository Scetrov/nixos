## ADDED Requirements

### Requirement: Evidence gates scheduling issue closure
The maintainer SHALL map every acceptance criterion in issue #29 to durable repository evidence and applicable current verification before closing it as completed. Historical native-job execution across restart/rebuild SHALL count only when the relevant deployed configuration remains consistent with that acceptance. The verification SHALL distinguish healthy empty inventory from scheduler failure.

#### Scenario: Existing acceptance remains applicable
- **WHEN** archived lifecycle acceptance matches the deployed scheduling configuration and bounded current checks show advancing healthy metadata
- **THEN** the closure summary links the historical lifecycle evidence and current checks without claiming a new restart/rebuild or inventing scheduled jobs

#### Scenario: Evidence is missing or contradicts acceptance
- **WHEN** a criterion lacks applicable evidence, current health fails, or approved access needed for verification is unavailable
- **THEN** issue #29 remains open and the unmet criterion or verification blocker is recorded without initiating unscoped remediation

### Requirement: Closure preserves security and auditability
The maintainer SHALL use existing approved read-only probes, observability, or operator verification without bypassing Authentik or exposing secrets. A redacted summary SHALL be posted through GitHub tooling before issue #29 is closed, distinguishing historical, newly observed, automated, and operator-confirmed evidence.

#### Scenario: Acceptance is established
- **WHEN** all issue acceptance criteria are supported
- **THEN** a GitHub comment links durable evidence, records any non-blocking limitations accurately, and issue #29 is closed as completed without runtime changes

#### Scenario: Closure is later contradicted
- **WHEN** evidence establishes that the closure was incorrect
- **THEN** the issue can be reopened with the contradictory evidence while preserving the original closure record
