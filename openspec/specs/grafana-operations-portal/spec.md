# grafana-operations-portal Specification

## Purpose

TBD - created by archiving change grafana-single-pane-of-glass. Update Purpose after archive.
## Requirements
### Requirement: Grafana provides an operator landing experience

The system SHALL make Grafana the primary operations entrypoint by exposing platform-wide overview dashboards and a service catalog for the managed environment.

#### Scenario: Platform overview is available

- **WHEN** an operator opens the Grafana portal
- **THEN** Grafana presents a platform-wide overview that summarizes host health and observability stack health using the configured Grafana datasources

#### Scenario: Service catalog is available

- **WHEN** an operator needs to inspect an application or infrastructure component
- **THEN** Grafana provides a service catalog or equivalent dashboard index with entries for the managed services and links to their detailed views

### Requirement: Service dashboards support cross-signal drilldown

The system SHALL provide per-service dashboards that let operators navigate from high-level status into metrics, logs, traces, profiles, incidents, and related operational views when those signals exist.

#### Scenario: Cross-signal navigation is available

- **WHEN** an operator selects a service from the platform overview or service catalog
- **THEN** the service dashboard provides drilldowns into the relevant metrics, logs, traces, and profile views using the selected service context

#### Scenario: Partial signal coverage is handled explicitly

- **WHEN** a service does not yet emit one or more advanced signals such as traces or profiles
- **THEN** the service dashboard still provides the available signals and clearly indicates which signal types are not yet available

### Requirement: Managed services meet a minimum observability contract

The system SHALL onboard managed services into Grafana using a common service identity so signals can be correlated across metrics, logs, and traces.

#### Scenario: Signals share service identity

- **WHEN** a managed service emits telemetry into the observability stack
- **THEN** that telemetry includes stable identifiers for at least the service name and host so Grafana can correlate signals across backends

#### Scenario: Service onboarding includes a baseline

- **WHEN** a managed service is added to the Grafana operations portal
- **THEN** it exposes at least one supported operational signal and a defined path for adding the remaining supported signals over time

### Requirement: Dashboard catalog is declaratively managed

The system SHALL manage the operations overview, service catalog, and per-service dashboards from source control using the repository's declarative Grafana workflows.

#### Scenario: Dashboard definitions remain in source control

- **WHEN** observability dashboards are added or updated
- **THEN** their definitions are stored in the repository and applied through the established deployment workflows rather than manual-only Grafana UI edits

#### Scenario: Dashboard organization is stable

- **WHEN** Grafana provisions the dashboard catalog
- **THEN** dashboards are grouped into a stable structure that separates platform-wide views from service-specific views

### Requirement: Home Assistant service dashboard shows live metrics coverage
The system SHALL provide a Home Assistant service dashboard that shows live operational metrics coverage once Home Assistant metrics are onboarded.

#### Scenario: Service dashboard shows scrape health
- **WHEN** an operator opens the Home Assistant service dashboard after metrics onboarding
- **THEN** the dashboard shows Home Assistant scrape health and related operational metrics from the Prometheus and Mimir datasources alongside the existing log view

#### Scenario: Metrics placeholder is removed
- **WHEN** the Home Assistant dashboard definitions are updated for this change
- **THEN** the previous placeholder stating that Home Assistant metrics are not yet enabled is replaced with panels backed by the active telemetry path

### Requirement: Home Assistant environmental telemetry dashboard is available
The system SHALL provide a declaratively managed Grafana dashboard for Home Assistant environmental telemetry so operators can inspect indoor climate and air-quality history.

#### Scenario: Environmental dashboard includes numeric air-quality metrics
- **WHEN** an operator opens the Home Assistant environmental dashboard
- **THEN** the dashboard includes time-series views for the onboarded CO2, PM2.5, and PM10 metrics using the retained metrics datasource path

#### Scenario: Environmental dashboard includes climate metrics
- **WHEN** an operator opens the Home Assistant environmental dashboard
- **THEN** the dashboard includes temperature and humidity panels for the approved Home Assistant entities exported through the managed Prometheus integration

### Requirement: UniFi network logs are listed in the operations portal
The system SHALL add the UniFi network log dashboard to the declaratively managed Grafana operations portal so operators can discover it from the existing catalog flow.

#### Scenario: Service catalog links to UniFi network logs
- **WHEN** an operator opens the operations service catalog
- **THEN** the catalog includes a UniFi network logs entry with a link to the managed UniFi dashboard and notes that the current signals are retained logs for firewall, threat, and warning-or-higher events

#### Scenario: Dashboard registration remains declarative
- **WHEN** the UniFi network dashboard is added to Grafana
- **THEN** its dashboard JSON lives in the repository and its provisioning is managed through the existing Terraform Grafana resources

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

### Requirement: Platform overview exposes house environmental summary
The system SHALL include house-level climate and air-quality summary panels on the Operations Platform Overview dashboard using retained Home Assistant telemetry from the managed metrics datasource path.

#### Scenario: Indoor and outdoor climate averages are visible
- **WHEN** an operator opens the Operations Platform Overview dashboard
- **THEN** the dashboard shows average indoor temperature, average outdoor temperature, average indoor humidity, and average outdoor humidity panels backed by Home Assistant metrics

#### Scenario: Air-quality status is visible
- **WHEN** an operator opens the Operations Platform Overview dashboard
- **THEN** the dashboard shows CO2 and air-quality summary panels backed by numeric Home Assistant environmental telemetry such as CO2 and particulate metrics

#### Scenario: Detailed environmental drilldown remains available
- **WHEN** an operator needs more detail than the platform overview summary provides
- **THEN** the dashboard provides a clear path to the existing Home Assistant environmental or house overview dashboards for detailed history and per-sensor context

#### Scenario: Dashboard remains declaratively managed
- **WHEN** the house environmental summary is added to the Operations Platform Overview dashboard
- **THEN** the dashboard definition remains stored in source control and provisioned through the existing Terraform-managed Grafana workflow

### Requirement: Operations portal exposes active remediation status
The system SHALL make actionable remediation status visible through the Grafana operations workflow for managed services with recurring high-priority log findings.

#### Scenario: Service with active error finding is identifiable
- **WHEN** a managed service has a current recurring error finding that indicates service failure
- **THEN** the operations portal or associated service dashboard identifies the service as needing remediation rather than only showing raw logs

#### Scenario: Frontier Indexer remediation state is visible
- **WHEN** an operator opens the Frontier Indexer operational view after this change
- **THEN** the view provides enough service health, recent error, and metrics context to distinguish a healthy indexer from one failing database setup

#### Scenario: Accepted noise is distinguishable from active failures
- **WHEN** a recurring warning has been reviewed and accepted as benign noise
- **THEN** the operations workflow documents or displays that status separately from unresolved service failures
