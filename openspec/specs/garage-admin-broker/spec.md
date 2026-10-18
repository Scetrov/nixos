# garage-admin-broker Specification

## Purpose
TBD - created by archiving change add-garage-admin-credential-broker. Update Purpose after archive.
## Requirements
### Requirement: Private management route

The system SHALL provide `https://garage-admin.net.scetrov.live` with declarative internal discovery and trusted TLS using existing Caddy conventions. Admission SHALL use actual socket peers in `10.229.0.0/16`, `127.0.0.0/24` or `100.64.0.0/10`; forwarded headers SHALL NOT grant admission. Other peers, including IPv6, SHALL be denied. Garage direct listeners SHALL remain loopback-only, and existing S3 endpoints SHALL remain unchanged.

#### Scenario: Unapproved source requests management access
- **WHEN** a peer outside the allowed ranges requests the endpoint, with or without spoofed forwarding headers
- **THEN** Caddy SHALL reject the request before it reaches Garage

#### Scenario: Existing S3 client continues operating
- **WHEN** an existing authorised client uses either S3 endpoint after deployment
- **THEN** its signed requests SHALL continue working without Authentik login

### Requirement: Authentik-authorised credential broker

The management route SHALL require a valid Authentik bearer token for a dedicated authorised machine identity/application. Only after successful authorisation SHALL Caddy substitute a server-side Garage credential supplied through Vault/agenix and forward to the fixed loopback API. Missing, invalid, expired or unauthorised credentials and Authentik failures SHALL NOT grant access. Clients, including OpenTofu and its wrapper, SHALL NOT receive the native Garage automation token. The wrapper SHALL authenticate using a dedicated Vault-backed Authentik machine credential without interactive browser login or an operator MFA challenge. Management access SHALL use the Caddy broker, not an SSH tunnel or Authentik-backed SSH integration.

#### Scenario: Authorised automation uses the API
- **WHEN** the actual OpenTofu provider sends a valid machine token from an allowed peer
- **THEN** Authentik SHALL authorise it and Garage SHALL receive Caddy's native credential rather than the client token

#### Scenario: Wrapper authenticates without an interactive session
- **WHEN** the wrapper provisions Garage resources
- **THEN** it SHALL obtain an Authentik machine token without browser login or an operator MFA challenge and supply only that token to the Garage provider
- **AND** the native Garage credential SHALL remain server-side, without retrieval by the wrapper

#### Scenario: Authentication fails
- **WHEN** the client lacks a valid authorised token or the Authentik outpost is unavailable
- **THEN** the request SHALL fail without reaching Garage

### Requirement: Bounded credential exposure

The broker SHALL use a dedicated Garage automation token with resource-operation scopes where supported. If the installed version cannot scope tokens, broader authority SHALL require explicit approval before deployment. Documentation SHALL identify that management access is not limited to the Minecraft bucket. Cross-bucket administrative authority is accepted only for the dedicated infrastructure-administration identity; its credentials SHALL NOT be distributed to the Minecraft server or any client. This acceptance SHALL NOT waive explicit approval of an unscoped native token. Existing logging SHALL NOT expose bearer credentials or secret-bearing request/response bodies.

#### Scenario: Native token authority is selected
- **WHEN** implementation verifies the installed Garage version
- **THEN** it SHALL use supported operation scopes or pause for approval of broader authority rather than silently using a root token

#### Scenario: Management traffic is logged
- **WHEN** successful and rejected requests are inspected through existing logging
- **THEN** the logs SHALL contain no machine, Garage or S3 secret material
