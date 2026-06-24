## ADDED Requirements

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
