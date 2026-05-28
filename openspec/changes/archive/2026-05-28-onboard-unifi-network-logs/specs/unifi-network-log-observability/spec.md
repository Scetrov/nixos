## ADDED Requirements

### Requirement: Declarative UniFi syslog receiver is available
The system SHALL provide a declaratively managed UniFi-specific remote syslog receiver on `habiki` that listens on UDP port `5514` and is isolated from the existing Alloy host log path.

#### Scenario: Receiver is enabled on habiki
- **WHEN** the UniFi network log receiver is enabled for `habiki`
- **THEN** NixOS provisions a dedicated Vector service that listens for remote syslog on UDP port `5514` and forwards retained events into the local Loki instance without changing the existing Alloy journal and file-log configuration

#### Scenario: Receiver access is source-restricted
- **WHEN** firewall rules are rendered for the UniFi network log receiver
- **THEN** only the UCG Ultra source address `10.229.0.1` is allowed to send UDP syslog traffic to port `5514` on `habiki`

### Requirement: UniFi events are filtered to high-signal network activity
The system SHALL retain only firewall events, threat or IDS events, and warning-or-higher non-firewall UniFi events before pushing them to Loki.

#### Scenario: Firewall and threat events are kept
- **WHEN** the receiver ingests UniFi firewall or threat-related syslog messages
- **THEN** the pipeline keeps those events and forwards them to Loki even if they are not tagged with a warning-or-higher severity

#### Scenario: Low-signal events are dropped
- **WHEN** the receiver ingests UniFi messages that are neither firewall events, nor threat or IDS events, nor warning-or-higher events
- **THEN** the pipeline drops those messages before Loki ingestion

### Requirement: Retained UniFi logs are normalized for Grafana queries
The system SHALL transform retained UniFi events into structured Loki entries with stable service identity and searchable network fields.

#### Scenario: Stable service identity is attached
- **WHEN** a retained UniFi event is written to Loki
- **THEN** the log entry includes labels for at least `service="unifi-network"` and `host="ucg-ultra"`

#### Scenario: Network fields are queryable
- **WHEN** a retained UniFi firewall or threat event reaches Loki
- **THEN** the structured log payload includes the parsed event class plus available source IP, destination IP, source port, destination port, protocol, action, interface, severity, and threat metadata fields needed for dashboard queries

### Requirement: UniFi network log dashboard is available
The system SHALL provide a declaratively managed Grafana dashboard for retained UniFi network logs.

#### Scenario: Dashboard shows key UniFi views
- **WHEN** an operator opens the UniFi network log dashboard
- **THEN** the dashboard provides panels or views for recent firewall actions, allow versus block trends, top source and destination endpoints, protocol or port breakdowns, threat or IDS events, and recent warning or error events

#### Scenario: Dashboard queries use retained UniFi labels
- **WHEN** Grafana renders the UniFi network log dashboard
- **THEN** its Loki queries target the retained UniFi label set and structured fields emitted by the managed Vector pipeline rather than relying on ad hoc free-text matching alone

### Requirement: UniFi remote logging setup is documented
The system SHALL document the UniFi Network Application remote logging settings required for this integration.

#### Scenario: Operator configuration steps are documented
- **WHEN** an operator configures the UCG Ultra remote logging target
- **THEN** the repository documentation states the host, UDP port `5514`, transport expectation, and event scope required for the managed receiver

#### Scenario: Validation steps are documented
- **WHEN** the remote logging setup is complete
- **THEN** the repository documentation describes how to confirm that UniFi logs arrive in Loki and appear in the Grafana dashboard
