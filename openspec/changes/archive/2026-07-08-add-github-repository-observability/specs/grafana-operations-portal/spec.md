## ADDED Requirements

### Requirement: Operations portal exposes GitHub repository risk summary
The system SHALL expose GitHub repository maintenance and supply-chain risk summary panels on the Operations Platform Overview dashboard using metrics collected through the managed Prometheus/Mimir telemetry path.

#### Scenario: Repository risk summary is visible
- **WHEN** an operator opens the Operations Platform Overview dashboard
- **THEN** the dashboard shows summary panels for GitHub repository risk such as open pull requests, stale pull requests, Dependabot alerts, and code scanning alerts

#### Scenario: Summary uses collector health context
- **WHEN** the Operations Platform Overview dashboard shows GitHub repository risk summary panels
- **THEN** the dashboard also indicates whether the GitHub repository observability collector is healthy enough for the summary values to be trusted

#### Scenario: Repository risk summary links to detail
- **WHEN** an operator needs more detail than the platform overview summary provides
- **THEN** the dashboard provides a clear path to the dedicated GitHub repository or software supply-chain health dashboard

### Requirement: Operations portal provides GitHub repository health drilldown
The system SHALL provide a declaratively managed Grafana dashboard for GitHub repository health covering repositories under the `Scetrov` and `RichardSlater` owners.

#### Scenario: Repository health dashboard is available
- **WHEN** Grafana provisions the operations portal dashboards
- **THEN** a GitHub repository health or software supply-chain health dashboard is available from the managed dashboard catalog

#### Scenario: Repository table supports triage
- **WHEN** an operator opens the GitHub repository health dashboard
- **THEN** the dashboard includes a repository-level view of open pull requests, stale pull request age, Dependabot alert counts, code scanning alert counts, and collector coverage status

#### Scenario: Owner-level grouping is visible
- **WHEN** repositories from both configured owners are present
- **THEN** the dashboard allows operators to distinguish or group repository risk for `Scetrov` and `RichardSlater`

#### Scenario: GitHub remediation links are available
- **WHEN** an operator inspects a repository on the GitHub repository health dashboard
- **THEN** the dashboard provides links or data links to the repository's GitHub pull request, Dependabot, and code scanning views where practical

### Requirement: Operations portal distinguishes zero findings from unknown coverage
The system SHALL distinguish repositories with zero findings from repositories whose Dependabot or code scanning coverage is disabled, unavailable, forbidden, or otherwise unknown.

#### Scenario: Zero findings are trusted only when collection succeeded
- **WHEN** a repository has zero Dependabot or code scanning findings and the exporter successfully queried that signal
- **THEN** the Grafana dashboard presents the signal as a collected zero rather than an unknown value

#### Scenario: Unknown coverage is visible
- **WHEN** a repository's Dependabot or code scanning signal cannot be queried or is not enabled
- **THEN** the Grafana dashboard shows the signal as unavailable or unknown rather than silently treating it as zero findings

#### Scenario: Collector failures are visible
- **WHEN** the GitHub repository observability exporter fails collection or serves stale data
- **THEN** the Grafana dashboard shows collector health or freshness indicators so operators know the repository risk data may be stale

### Requirement: GitHub repository dashboards remain declaratively managed
The system SHALL manage GitHub repository observability dashboards through the existing source-controlled Grafana workflow.

#### Scenario: Dashboard definitions live in source control
- **WHEN** GitHub repository health dashboard panels are added or updated
- **THEN** their dashboard definitions are stored under the repository's dashboard source tree and applied through the established Terraform Grafana workflow

#### Scenario: Dashboard organization follows operations portal conventions
- **WHEN** the GitHub repository health dashboard is registered in Grafana
- **THEN** it is grouped within the operations portal structure using stable dashboard naming and UID conventions
