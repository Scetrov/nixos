## Purpose

Provide a private, persistent S3-compatible backup target on Habiki for authorized tailnet clients.

## Requirements

### Requirement: Persistent S3-compatible backup storage

The system SHALL run a Garage S3-compatible object-storage service on Habiki. Object data and service configuration SHALL reside in persistent, service-owned host storage and SHALL survive service restarts and NixOS rebuilds.

#### Scenario: Service restart preserves backup objects

- **WHEN** the MinIO service is restarted or Habiki is rebuilt
- **THEN** the service SHALL start using its existing persistent storage
- **AND** objects previously written to an authorized bucket SHALL remain available

### Requirement: Tailnet-only HTTPS endpoint

The S3 API SHALL be reachable only over HTTPS from Habiki's Headscale tailnet and required Habiki-local management paths. The service API and, if enabled, its management console SHALL NOT be reachable through a WAN listener or router port-forward.

#### Scenario: Authorized tailnet client accesses S3

- **WHEN** a tailnet client resolves the dedicated S3 endpoint hostname and presents valid credentials
- **THEN** the hostname SHALL resolve to Habiki's tailnet address
- **AND** the client SHALL be able to establish a trusted HTTPS connection to the S3 API

#### Scenario: Non-tailnet network client attempts access

- **WHEN** a client outside the Headscale tailnet attempts to connect to the S3 API or management console
- **THEN** firewall and service binding policy SHALL deny access
- **AND** no public S3 route or router port-forward SHALL provide an alternate path

### Requirement: Isolated least-privilege project access

The system SHALL use distinct administrative and project credentials. Each provisioned project bucket SHALL have a dedicated credential and policy that permits only the operations required for that bucket. Anonymous access SHALL be disabled.

#### Scenario: Project backup credential writes its bucket

- **WHEN** a backup client uses its project credential to write an object to its assigned bucket
- **THEN** the S3 service SHALL allow the authorized operation

#### Scenario: Project backup credential crosses bucket boundary

- **WHEN** a backup client uses a project credential to access a bucket not assigned to that credential
- **THEN** the S3 service SHALL deny the operation

### Requirement: Encrypted secret management

The system SHALL obtain Garage administrative credentials, project credentials, and private certificate material through the existing agenix and Ansible Vault secret-management workflow. The repository SHALL NOT contain plaintext secret material for the S3 service.

#### Scenario: Service configuration is reviewed

- **WHEN** the NixOS and OpenSpec configuration is inspected
- **THEN** no plaintext Garage credential or private certificate key SHALL be present
- **AND** the runtime service SHALL receive required secrets from encrypted secret paths

### Requirement: Storage observability

The system SHALL collect Garage availability and supported capacity/health metrics through the existing Grafana-based observability stack. The system SHALL alert or visibly signal when available persistent storage reaches the configured reserve threshold.

#### Scenario: Storage reserve is reached

- **WHEN** available storage falls below the configured reserve threshold
- **THEN** observability tooling SHALL expose the low-capacity condition
- **AND** operators SHALL be able to identify that the S3 backup target requires capacity action
