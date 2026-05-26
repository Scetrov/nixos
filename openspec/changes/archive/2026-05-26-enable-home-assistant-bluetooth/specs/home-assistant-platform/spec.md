## ADDED Requirements

### Requirement: Declarative Home Assistant Bluetooth Access

The system SHALL provide an opt-in Bluetooth access mode for the container-based Home Assistant deployment.

#### Scenario: Bluetooth access disabled

- **WHEN** `scetrov.services.home-assistant.bluetooth.enable` is false or unset
- **THEN** the module does not enable host Bluetooth support for Home Assistant, does not mount `/run/dbus` into the Home Assistant container, and does not add Bluetooth-specific container capabilities

#### Scenario: Bluetooth access enabled

- **WHEN** `scetrov.services.home-assistant.bluetooth.enable` is true
- **THEN** the module enables the host Bluetooth stack, makes the host system D-Bus socket available to the Home Assistant container as `/run/dbus:ro`, and adds the `NET_ADMIN` and `NET_RAW` capabilities to the Home Assistant container

### Requirement: Habiki Bluetooth Trial Assignment

The system SHALL enable Home Assistant Bluetooth access on the `habiki` node for a local SwitchBot BLE sensor trial.

#### Scenario: Habiki enables Bluetooth access

- **WHEN** `src/roles/nixos/files/device-configuration/habiki.nix` is evaluated
- **THEN** it sets `scetrov.services.home-assistant.bluetooth.enable = true`

### Requirement: Bluetooth Runtime Verification

The system SHALL verify the Bluetooth access path after deploying Home Assistant Bluetooth support.

#### Scenario: Host Bluetooth is available

- **WHEN** Home Assistant Bluetooth access is deployed to `habiki`
- **THEN** verification confirms the host Bluetooth service is active and a Bluetooth controller is visible to BlueZ

#### Scenario: Container can access BlueZ over D-Bus

- **WHEN** Home Assistant Bluetooth access is deployed to `habiki`
- **THEN** verification confirms the Home Assistant container has access to `/run/dbus` and Home Assistant logs do not report a missing BlueZ D-Bus service for the Bluetooth integration

#### Scenario: SwitchBot discovery is trialed

- **WHEN** Home Assistant Bluetooth access is deployed to `habiki`
- **THEN** the operator can add the official Home Assistant SwitchBot Bluetooth integration and assess whether local Habiki Bluetooth coverage is sufficient for nearby SwitchBot temperature and humidity sensors
