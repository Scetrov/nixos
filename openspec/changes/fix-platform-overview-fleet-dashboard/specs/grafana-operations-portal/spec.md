## ADDED Requirements

### Requirement: Platform overview shows accurate fleet host reporting
The system SHALL show active fleet host reporting on the Operations Platform Overview dashboard using the active Mimir-backed Unix host telemetry path.

#### Scenario: Hosts reporting uses active fleet telemetry
- **WHEN** an operator opens the Operations Platform Overview dashboard
- **THEN** the Hosts Reporting panel reports hosts from active fleet telemetry labelled by `host` rather than stale or local-only node scrape targets

#### Scenario: All reporting hosts are counted
- **WHEN** the active Unix integration scrape is up for `fyne`, `habiki`, and `bullit`
- **THEN** the Hosts Reporting panel shows a reporting host count of `3`

### Requirement: Platform overview exposes fleet storage and disk pressure
The system SHALL include fleet-level storage and disk pressure panels on the Operations Platform Overview dashboard so operators can detect host disk capacity, throughput, I/O, busy-time, and queue-depth risks without opening per-host dashboards first.

#### Scenario: Root disk usage is visible by host
- **WHEN** an operator opens the Fleet Health section
- **THEN** the dashboard shows root filesystem utilization grouped by host using Mimir-backed node filesystem metrics

#### Scenario: Disk activity is visible by host and device
- **WHEN** an operator opens the Fleet Health section
- **THEN** the dashboard shows disk throughput and disk I/O operation rates grouped by host and device using Mimir-backed node disk metrics

#### Scenario: Disk pressure is visible by host and device
- **WHEN** an operator opens the Fleet Health section
- **THEN** the dashboard shows disk busy-time or average queue-depth pressure grouped by host and device using Mimir-backed node disk metrics

### Requirement: Platform overview exposes fleet network error signals
The system SHALL include fleet-level network error or drop panels on the Operations Platform Overview dashboard so operators can detect host network degradation from the landing dashboard.

#### Scenario: Network errors and drops are visible by host and device
- **WHEN** an operator opens the Fleet Health section
- **THEN** the dashboard shows network receive/transmit error or drop rates grouped by host and device using Mimir-backed node network metrics

### Requirement: Platform overview top row uses the full dashboard grid
The system SHALL use the available top-row dashboard space for observability stack health instead of leaving an empty grid area beside Hosts Reporting.

#### Scenario: Observability stack health row is fully populated
- **WHEN** an operator opens the Operations Platform Overview dashboard
- **THEN** the Observability Stack Health row fills the 24-column Grafana grid with useful health stats for the observability stack and host reporting
