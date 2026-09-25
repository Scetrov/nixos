## ADDED Requirements

### Requirement: Restricted local-LAN gameplay access
The system SHALL permit Project Zomboid gameplay traffic only from explicitly configured local-LAN source CIDRs and only on the minimum UDP ports or range verified for the selected server profile. The firewall SHALL deny gameplay traffic from sources outside those configured LAN CIDRs unless a separately enabled access policy permits it.

#### Scenario: Approved LAN player connects
- **WHEN** a client on an approved local-LAN source CIDR connects using the verified gameplay UDP ports
- **THEN** the firewall SHALL permit the traffic
- **AND** the client SHALL be able to complete the documented LAN join smoke test

#### Scenario: Unapproved network source attempts gameplay access
- **WHEN** a client outside every configured local-LAN and enabled Headscale source policy sends traffic to the gameplay ports
- **THEN** the firewall SHALL deny the traffic
- **AND** no WAN router-forwarding requirement SHALL be introduced by this change

### Requirement: Non-public server admission
The initial server profile SHALL not publicly list the server and SHALL use a configured non-public admission policy. The policy SHALL require a join password, explicit accounts/whitelist membership, or both before an uninvited player can join.

#### Scenario: Server browser listing is evaluated
- **WHEN** the configured server profile is inspected or started
- **THEN** public server-list registration SHALL be disabled
- **AND** the configured non-public admission policy SHALL be active

#### Scenario: Uninvited player attempts to join
- **WHEN** a player reaches the server without satisfying the configured admission policy
- **THEN** the server SHALL reject the join
- **AND** the player SHALL not receive administrative access

### Requirement: Private administration surface
The system SHALL NOT expose RCON or any other Project Zomboid remote-administration listener on LAN, Headscale, or WAN interfaces. Automated save and shutdown control SHALL use the private local control channel owned by the service identity.

#### Scenario: Network listeners are inspected
- **WHEN** Habiki network listeners and firewall policy are inspected after deployment
- **THEN** no Project Zomboid remote-administration port SHALL be reachable from LAN, Headscale, or WAN sources
- **AND** gameplay ingress SHALL remain limited to the approved UDP policy

### Requirement: Disabled-by-default Headscale access path
The system SHALL represent Headscale gameplay access as a separately configurable policy that is disabled by default. Enabling it SHALL require an explicit source/interface policy and a successful invited-peer join test; it SHALL NOT widen the local-LAN rule implicitly.

#### Scenario: Default Headscale policy
- **WHEN** the server is deployed with default access configuration
- **THEN** Headscale peer traffic SHALL not be admitted solely because the peer is on a tailnet
- **AND** the local-LAN policy SHALL remain unchanged

#### Scenario: Explicitly enabled Headscale policy
- **WHEN** an operator explicitly enables the configured Headscale source/interface policy and an invited peer satisfies server admission requirements
- **THEN** the firewall SHALL permit only the verified gameplay UDP traffic for that peer path
- **AND** the peer SHALL be able to complete a documented join test
