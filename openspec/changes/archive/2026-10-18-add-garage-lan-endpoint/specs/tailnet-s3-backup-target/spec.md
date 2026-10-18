## MODIFIED Requirements

### Requirement: Tailnet-only HTTPS endpoint

The existing `s3.tailnet.net.scetrov.live` endpoint SHALL remain restricted to Habiki's Headscale tailnet, retain trusted HTTPS and its current DNS mapping, and continue serving existing backup clients without configuration changes. This restriction SHALL apply to that hostname, not prohibit the complementary internal endpoint. Garage's direct S3, administration, metrics and RPC listeners SHALL remain loopback-only and SHALL NOT gain firewall openings or public router port-forwards.

#### Scenario: Authorized tailnet client accesses S3

- **WHEN** a tailnet client resolves the dedicated tailnet S3 endpoint hostname and presents valid credentials
- **THEN** the hostname SHALL resolve to Habiki's tailnet address
- **AND** the client SHALL be able to establish a trusted HTTPS connection to the S3 API using existing bucket permissions

#### Scenario: Non-tailnet network client attempts tailnet endpoint access

- **WHEN** a client outside the Headscale IPv4 range `100.64.0.0/10` requests the tailnet endpoint
- **THEN** Caddy SHALL deny the request before proxying to Garage
- **AND** no direct Garage port or router port-forward SHALL provide an alternate path

## ADDED Requirements

### Requirement: Complementary internal S3 endpoint

The system SHALL provide `https://s3.net.scetrov.live` through Caddy to the existing Garage S3 listener, with a trusted certificate. Caddy SHALL allow only socket peers in `10.229.0.0/16`, `127.0.0.0/24`, or `100.64.0.0/10`, and SHALL reject all other sources before proxying. Forwarded headers SHALL NOT grant access. Garage SHALL continue enforcing its existing signed authentication and bucket permissions; the endpoint SHALL NOT add browser SSO or anonymous access.

#### Scenario: Allowed client accesses its bucket

- **WHEN** a reachable client from any of the three allowed ranges uses valid Garage credentials at the new hostname
- **THEN** Caddy SHALL permit access to the S3 upstream over trusted HTTPS
- **AND** Garage SHALL permit only operations authorized for that credential

#### Scenario: Untrusted source attempts bypass

- **WHEN** a source outside the allowed ranges, including an IPv6 source, requests the new hostname through any reachable server address, with or without spoofed forwarded headers
- **THEN** Caddy SHALL reject the request before it reaches Garage

#### Scenario: Allowed source lacks valid S3 credentials

- **WHEN** an allowed client requests a protected bucket operation without valid S3 credentials
- **THEN** Garage SHALL deny the operation

### Requirement: Internal discovery and compatible S3 requests

The existing declarative local DNS/hosts mapping SHALL resolve `s3.net.scetrov.live` to `10.229.10.2`. Clients SHALL be documented to use region `garage` and path-style addressing. The proxy SHALL preserve signed Host, URI, query and relevant headers, and support signed listing, object PUT/GET/DELETE and multipart transfer without introducing arbitrary upload limits. Existing storage, credentials and Garage monitoring SHALL remain unchanged.

#### Scenario: LAN client discovers and uses the endpoint

- **WHEN** a LAN client uses the existing internal DNS service and the documented S3 settings
- **THEN** the new hostname SHALL resolve to Habiki's private LAN address and present a valid certificate
- **AND** authorized signed listing, object PUT/GET/DELETE and multipart transfer SHALL succeed without proxy-induced signature errors

#### Scenario: Existing backup client remains independent of LAN routing

- **WHEN** a tailnet backup client continues using its existing hostname and credentials after a rebuild or restart
- **THEN** it SHALL retain access to existing objects without a LAN route, credential rotation or data migration
