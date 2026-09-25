## ADDED Requirements

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
