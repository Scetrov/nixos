# forgejo-private-service Specification

## Purpose
TBD - created by archiving change add-private-forgejo. Update Purpose after archive.
## Requirements
### Requirement: Private HTTPS service
The system SHALL serve Forgejo at `https://source.net.scetrov.live/` on Habiki through Caddy with a trusted certificate, a loopback-only backend listener, and correct external URLs. The system MUST restrict access to approved private LAN/VPN paths without changing unrelated Caddy sites or creating public DNS records or router forwards.

#### Scenario: Private client opens Forgejo
- **WHEN** an approved LAN, Teleport, or Headscale client opens the service
- **THEN** it receives the Forgejo application over trusted HTTPS and generated links use `https://source.net.scetrov.live/`

#### Scenario: Unapproved source supplies the hostname
- **WHEN** an unapproved source attempts the Forgejo virtual host on the shared HTTPS listener
- **THEN** access is denied even if the request supplies the correct hostname

#### Scenario: Backend port is contacted directly
- **WHEN** a remote client attempts the internal Forgejo HTTP port
- **THEN** it cannot access the loopback-only backend

### Requirement: Shared local DNS registration
The system SHALL add `source.net.scetrov.live` to Habiki's `10.229.10.2` entry in `local-networking.nix` and deploy that alias to both local Blocky hosts without deploying Forgejo on Fyne.

#### Scenario: Both DNS servers answer
- **WHEN** a client queries either `10.229.53.1` or `10.229.53.2` after deployment
- **THEN** `source.net.scetrov.live` resolves to `10.229.10.2`

#### Scenario: VPN uses existing LAN connectivity
- **WHEN** a Teleport or Headscale client with existing LAN/DNS access resolves and connects to the hostname
- **THEN** Forgejo is reachable without a new public record or a change to Headscale routing policy

### Requirement: Dedicated Git SSH
The system SHALL provide Git SSH at `source.net.scetrov.live` on TCP 2222 for approved private paths, advertise that port in clone URLs, preserve its host key, and leave administrative SSH unchanged.

#### Scenario: Owner clones and pushes over SSH
- **WHEN** the owner uses a key registered in Forgejo and a port-2222 clone URL
- **THEN** repository clone and push succeed according to Forgejo permissions

#### Scenario: Unknown key attempts access
- **WHEN** a client attempts Git SSH with an unregistered key
- **THEN** Forgejo denies repository access

#### Scenario: Rebuild preserves SSH identity
- **WHEN** Habiki is rebuilt without intentional key rotation
- **THEN** the Git SSH host key remains unchanged and administrative SSH still works

### Requirement: Lightweight persistent storage
The system SHALL use SQLite and persistent service-owned storage for repositories, enabled attachments/LFS, database state, and service keys. Ordinary rebuild, restart, or disable operations MUST NOT delete that state. The service SHALL NOT require HA or a formal backup service.

#### Scenario: Service restarts after rebuild
- **WHEN** Forgejo restarts after an ordinary configuration rebuild
- **THEN** previously created repositories and accounts remain usable

#### Scenario: Service is disabled
- **WHEN** the operator disables Forgejo through automation
- **THEN** its listeners stop while its persistent data remains available for deliberate recovery or removal

### Requirement: Actions is deferred and inactive
The system SHALL disable Forgejo Actions and leave any retained experimental runner code inactive on Habiki. Enabling the private Forgejo service MUST NOT provision a runner account, runtime, registration, job cleanup, or runner-specific egress policy.

#### Scenario: Private Forgejo is enabled
- **WHEN** the current private Forgejo configuration is evaluated or deployed
- **THEN** Actions is disabled and no runner account, runtime/daemon/cleanup units, timer, registration command, or runner egress rules are enabled

### Requirement: Declarative and targeted lifecycle
The system SHALL provision Forgejo through NixOS/Ansible automation with targeted Habiki execution, verified dependency integrity, and documented enable/disable and upgrade procedures. Deployment MUST NOT unintentionally enable Forgejo on other hosts or introduce unrelated routes/listeners.

#### Scenario: Targeted deployment is repeated
- **WHEN** the documented Forgejo deployment is run twice for Habiki
- **THEN** both runs converge on the same service configuration without losing existing data or creating duplicate service instances

#### Scenario: Upgrade changes the database schema
- **WHEN** an upgrade requires a database migration
- **THEN** the documented upgrade process provides a consistent pre-upgrade snapshot procedure and warns against an incompatible binary-only downgrade
