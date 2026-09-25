# project-zomboid-server-runtime Specification

## Purpose
TBD - created by archiving change add-project-zomboid-server. Update Purpose after archive.
## Requirements
### Requirement: Persistent unprivileged dedicated-server runtime
The system SHALL run one Project Zomboid Build 42 dedicated-server instance on Habiki under a dedicated non-root system identity. The server executable, Steam/Workshop cache, generated configuration, world saves, player data, and logs SHALL reside in persistent service-owned storage outside `/nix/store` and SHALL survive NixOS rebuilds and service restarts.

#### Scenario: Rebuild preserves an existing world
- **WHEN** Habiki is rebuilt or the Project Zomboid service is restarted
- **THEN** the service SHALL use its pre-existing persistent state
- **AND** the previously created world and server profile SHALL remain available

#### Scenario: Service process identity is inspected
- **WHEN** the Project Zomboid service is running
- **THEN** it SHALL run as its dedicated non-root system identity
- **AND** its persistent state SHALL not be writable by unrelated unprivileged users

### Requirement: Declarative desired server profile
The system SHALL declare the intended initial Build 42 server profile in repository-managed NixOS configuration while preserving game-owned mutable state. Profile reconciliation or initialization SHALL occur only while the server is stopped and SHALL NOT replace an existing world without an explicit operator migration action.

#### Scenario: First service initialization
- **WHEN** the service state contains no initialized server profile
- **THEN** the system SHALL create the configured initial profile in persistent service-owned storage
- **AND** subsequent starts SHALL use that profile rather than a transient home-directory default

#### Scenario: Existing world is present during rebuild
- **WHEN** a NixOS rebuild applies a changed desired profile while an existing world is present
- **THEN** the rebuild SHALL NOT silently delete or replace the world
- **AND** the operator SHALL be required to use the defined stopped-service migration workflow for destructive profile changes

### Requirement: Secret-backed admission and administration configuration
The system SHALL obtain administrative and configured admission credentials through the existing encrypted agenix and Ansible Vault workflow. Plaintext administrative, join, or remote-administration credentials SHALL NOT be stored in Nix expressions, generated repository files, or OpenSpec artifacts.

#### Scenario: Configuration is reviewed
- **WHEN** the Project Zomboid NixOS configuration and OpenSpec artifacts are inspected
- **THEN** no plaintext administrative or admission credential SHALL be present
- **AND** runtime credential material SHALL be sourced from encrypted secret paths

### Requirement: Build 42 Skill Recovery Journal mod manifest
The initial desired mod manifest SHALL include Skill Recovery Journal only after its current Build 42 compatibility, Workshop item identifier, internal mod identifier, and declared dependencies have been verified from installed metadata. The manifest SHALL distinguish Workshop download identifiers from internal mod load identifiers and preserve dependency-first load order.

#### Scenario: Mod metadata matches the declared manifest
- **WHEN** a controlled initialization or maintenance operation downloads the configured Workshop content
- **THEN** the operation SHALL verify that each declared internal mod identifier exists in installed Build 42-compatible metadata
- **AND** it SHALL fail rather than start the server with an unresolved configured mod dependency

#### Scenario: Skill Recovery Journal starts successfully
- **WHEN** the server starts with the verified Skill Recovery Journal manifest
- **THEN** its startup log SHALL show the configured mod loading without an unresolved-mod error
- **AND** an administrator SHALL be able to perform the documented in-game smoke test before the world is opened to players

### Requirement: Graceful lifecycle and crash recovery
The system SHALL provide a private local control channel for Project Zomboid console commands. Planned stop, restart, backup, and maintenance operations SHALL request `save`, wait for the configured bounded flush period, and request `quit` before process termination. Unexpected service failures SHALL use bounded systemd automatic restart behavior and SHALL NOT require an interactive terminal.

#### Scenario: Planned restart
- **WHEN** an operator or scheduled maintenance action restarts the Project Zomboid service
- **THEN** the service SHALL issue the configured graceful save-and-quit sequence before stopping
- **AND** systemd SHALL start the service again only after the previous process exits

#### Scenario: Unexpected service failure
- **WHEN** the dedicated-server process exits unexpectedly
- **THEN** systemd SHALL restart it after the configured delay within configured start-rate limits
- **AND** the restart outcome SHALL be observable through systemd logs/status

### Requirement: Declarative character-creation and multi-hit settings
The system SHALL configure 100 free character-creation points and enable multi-hit melee combat in the persistent Build 42 sandbox profile. It SHALL reconcile only these specific settings while the game service is stopped, preserving all other game-owned world and profile state.

#### Scenario: Existing profile receives changed gameplay settings
- **WHEN** the Project Zomboid service starts with an existing sandbox profile
- **THEN** `CharacterFreePoints` SHALL equal `100` and `MultiHitZombies` SHALL equal `true`
- **AND** other sandbox keys and the world saves SHALL remain unchanged

### Requirement: New multiplayer characters receive the family co-op kit once
The system SHALL grant each newly created multiplayer character one duffel bag, one shelf-stable food item, one can opener, one potable water bottle, and one hatchet using item identifiers present in the installed Build 42 game. The system SHALL NOT enable the game's separate default starter kit or re-grant these items to the same character on reconnect. Existing characters SHALL NOT be retroactively modified.

#### Scenario: An approved player creates a character
- **WHEN** a newly created multiplayer character joins the server
- **THEN** that character receives `Base.Bag_DuffelBag`, `Base.CannedChili`, `Base.TinOpener`, `Base.WaterBottle` containing drinkable water, and `Base.HandAxe` exactly once
- **AND** the separate default schoolbag/baseball-bat starter kit is not also added

#### Scenario: A character reconnects
- **WHEN** an existing character disconnects and reconnects
- **THEN** the server SHALL NOT grant another co-op kit

#### Scenario: A player creates a replacement character
- **WHEN** a player creates a new character after death
- **THEN** the new character receives its own one-time kit without modifying the previous character's saved state

### Requirement: Co-op sandbox rules are reconciled without a world reset
The system SHALL enable the in-game minimap, set zombie infection transmission to saliva only, and apply a global 1.5× skill XP multiplier while retaining the global multiplier toggle. It SHALL reconcile only these explicit sandbox settings while the server is stopped and preserve saved worlds, character data, and unrelated sandbox values.

#### Scenario: Existing sandbox profile is reconciled
- **WHEN** the managed server starts with an existing Build 42 sandbox profile
- **THEN** `Map.AllowMiniMap` SHALL be `true`, `ZombieLore.Transmission` SHALL be `2`, `MultiplierConfig.Global` SHALL be `1.5`, and `MultiplierConfig.GlobalToggle` SHALL remain `true`
- **AND** unrelated sandbox keys and persistent world files SHALL remain unchanged

#### Scenario: Sandbox profile has an ambiguous nested structure
- **WHEN** a nested table or key cannot be identified uniquely during reconciliation
- **THEN** initialization SHALL fail safely rather than changing a similarly named key in another table or replacing the whole profile

### Requirement: Managed reset preserves only the requested whitelist approvals
The system SHALL support the requested managed full-state reset without retaining the prior world or character data. While the service is stopped, it SHALL preserve exactly one existing Build 42 whitelist record for each of `Scetrov` and `FlyingFire`, restore only those records after the fresh server profile creates its database, and securely remove temporary preservation data. It SHALL fail without resetting if a requested record is absent or duplicated, and SHALL NOT print or commit any authentication data.

#### Scenario: Requested whitelist entries are migrated through a reset
- **WHEN** the managed reset is run and each requested username has exactly one whitelist record
- **THEN** the reset SHALL replace the old profile and saved world while restoring exactly the `Scetrov` and `FlyingFire` whitelist records to the fresh server database
- **AND** no other former whitelist, player, or world record SHALL be restored

#### Scenario: Whitelist preservation cannot be verified
- **WHEN** either requested username has zero or more than one whitelist record
- **THEN** the managed reset SHALL fail before replacing the live profile
