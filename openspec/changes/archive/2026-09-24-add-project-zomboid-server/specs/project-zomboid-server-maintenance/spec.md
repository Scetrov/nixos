## ADDED Requirements

### Requirement: Controlled Steam and Workshop updates
The system SHALL NOT download or update the Project Zomboid Steam app or Workshop content during an ordinary service start. It SHALL provide a manually invoked serialized maintenance operation that creates a recovery point, updates and validates Steam content, restarts the server gracefully, and records the operation outcome for review.

#### Scenario: Ordinary restart
- **WHEN** the Project Zomboid service starts after a crash, NixOS rebuild, or planned restart outside a maintenance operation
- **THEN** it SHALL use the already installed Steam app and Workshop content
- **AND** it SHALL NOT run an update or validation download

#### Scenario: Controlled update succeeds
- **WHEN** an operator invokes the controlled maintenance operation
- **THEN** the operation SHALL acquire the shared maintenance lock, create a pre-update recovery point, update and validate the Steam app and configured Workshop content, and restart the server through the graceful lifecycle
- **AND** it SHALL require startup-log review and an administrator join smoke test before the update is accepted

#### Scenario: Controlled update fails
- **WHEN** Steam validation, mod verification, server startup, or smoke testing fails during a controlled maintenance operation
- **THEN** the operation SHALL report failure without deleting the pre-update recovery point
- **AND** the operator SHALL have a documented rollback path to the prior local state

### Requirement: Serialized planned maintenance
Planned restart, backup, restore, profile migration, and controlled update operations SHALL share an exclusive lock and SHALL NOT overlap. Each operation that stops the server SHALL use the graceful save-and-quit lifecycle before mutating or copying game-owned state.

#### Scenario: Concurrent operation request
- **WHEN** a backup, restart, restore, migration, or update is requested while another maintenance operation holds the lock
- **THEN** the new operation SHALL wait or fail deterministically without accessing mutable world state concurrently
- **AND** the running operation's outcome SHALL remain observable

### Requirement: Rotating local full-state recovery points
The system SHALL create timestamped local compressed recovery points of the complete mutable Project Zomboid state while the server is stopped. It SHALL maintain configured bounded retention and preserve a pre-maintenance recovery point until a later controlled update is accepted or the configured retention policy expires.

#### Scenario: Scheduled backup
- **WHEN** the configured backup timer fires and no other maintenance operation holds the lock
- **THEN** it SHALL gracefully stop the server, archive the complete mutable state, apply configured retention, and restart the server
- **AND** the timer status and archive result SHALL be observable to operators

#### Scenario: Backup retention is applied
- **WHEN** creating a recovery point would exceed configured retention
- **THEN** the system SHALL remove only recovery points eligible under the retention policy
- **AND** it SHALL not delete the live world state as part of retention

### Requirement: Documented local restoration
The system SHALL provide an operator runbook for restoring a selected local recovery point into a stopped Project Zomboid service. The runbook SHALL state that the backups protect against accidental world damage only and SHALL include a restore validation procedure.

#### Scenario: Operator restores a recovery point
- **WHEN** an operator follows the documented restore procedure for a selected recovery point
- **THEN** the procedure SHALL stop the server gracefully, preserve or quarantine the damaged live state, restore the selected complete state, and restart the service
- **AND** the operator SHALL be able to validate that the restored world and configured profile load

#### Scenario: Backup scope is reviewed
- **WHEN** the Project Zomboid backup documentation is reviewed
- **THEN** it SHALL state that backups are stored on Habiki and do not provide recovery from loss of Habiki or its storage
- **AND** it SHALL not claim off-host disaster-recovery protection
