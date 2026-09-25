## ADDED Requirements

### Requirement: Project Zomboid dashboard is available from the operations portal
The system SHALL register the Project Zomboid Server dashboard declaratively in `Operations / Services` and list it in the source-controlled service catalog.

#### Scenario: Service catalog links to Project Zomboid
- **WHEN** an operator opens the operations service catalog
- **THEN** the catalog includes Project Zomboid with a link to its managed service dashboard and an accurate summary of its available metrics and logs

#### Scenario: Dashboard registration remains declarative
- **WHEN** the Project Zomboid service dashboard is provisioned
- **THEN** its dashboard definition and Terraform Grafana registration are stored in source control and not managed only through manual Grafana UI edits
