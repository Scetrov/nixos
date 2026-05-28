## ADDED Requirements

### Requirement: UniFi network logs are listed in the operations portal
The system SHALL add the UniFi network log dashboard to the declaratively managed Grafana operations portal so operators can discover it from the existing catalog flow.

#### Scenario: Service catalog links to UniFi network logs
- **WHEN** an operator opens the operations service catalog
- **THEN** the catalog includes a UniFi network logs entry with a link to the managed UniFi dashboard and notes that the current signals are retained logs for firewall, threat, and warning-or-higher events

#### Scenario: Dashboard registration remains declarative
- **WHEN** the UniFi network dashboard is added to Grafana
- **THEN** its dashboard JSON lives in the repository and its provisioning is managed through the existing Terraform Grafana resources
