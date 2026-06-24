## ADDED Requirements

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
