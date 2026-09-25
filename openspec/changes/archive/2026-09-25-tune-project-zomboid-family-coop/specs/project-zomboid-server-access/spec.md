## ADDED Requirements

### Requirement: Private co-op gameplay prevents player-versus-player damage
The system SHALL disable PvP for the managed Build 42 server while preserving its existing whitelist-only LAN admission, join password, disabled RCON, and non-public server listing.

#### Scenario: Two approved players play together
- **WHEN** two approved players are connected and the managed profile is active
- **THEN** `PVP` SHALL be `false`, so players cannot deal PvP damage through the server setting

#### Scenario: Access controls are reviewed after deployment
- **WHEN** the updated server is inspected
- **THEN** unapproved users SHALL remain unable to join, the server SHALL remain non-public, and no RCON listener or new external port SHALL be exposed

### Requirement: Approved players can locate teammates on the in-game map
The system SHALL enable the in-game minimap and configure remote-player map visibility for everyone on the server. This visibility SHALL be limited by the existing authenticated gameplay admission controls and SHALL NOT publish player positions through any new unauthenticated route or telemetry endpoint.

#### Scenario: Approved players open the map
- **WHEN** two approved players are connected to the server and open their in-game map or minimap
- **THEN** `MapRemotePlayerVisibility` SHALL be `4` and the game SHALL show the other connected player's position to each of them

#### Scenario: Unapproved user attempts to see player locations
- **WHEN** a user who is not admitted to the private server attempts to access player positions
- **THEN** the change SHALL NOT add a public map, API, listener, or admission bypass that reveals their locations
