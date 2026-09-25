## ADDED Requirements

### Requirement: Declarative character-creation and multi-hit settings
The system SHALL configure 100 free character-creation points and enable multi-hit melee combat in the persistent Build 42 sandbox profile. It SHALL reconcile only these specific settings while the game service is stopped, preserving all other game-owned world and profile state.

#### Scenario: Existing profile receives changed gameplay settings
- **WHEN** the Project Zomboid service starts with an existing sandbox profile
- **THEN** `CharacterFreePoints` SHALL equal `100` and `MultiHitZombies` SHALL equal `true`
- **AND** other sandbox keys and the world saves SHALL remain unchanged
