## Why

Home Assistant on Habiki currently runs with host networking but does not have access to the host Bluetooth stack, so BLE-only SwitchBot temperature and humidity sensors cannot be discovered reliably through the official Bluetooth/SwitchBot integrations. Enabling local Bluetooth access lets us try the simplest fully local path before introducing ESPHome Bluetooth proxies or vendor hubs.

## What Changes

- Add a declarative Home Assistant Bluetooth option for the container deployment.
- When enabled, configure Habiki's host Bluetooth stack so BlueZ exposes the local controller over system D-Bus.
- Pass the host D-Bus socket and required network capabilities into the Home Assistant container.
- Enable the option on Habiki for an initial local Bluetooth trial.
- Extend runtime verification to confirm the host controller, BlueZ service, and Home Assistant container access path are present.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `home-assistant-platform`: Add declarative Bluetooth controller access for Home Assistant on Habiki.

## Impact

- Affected NixOS module: `src/roles/nixos/files/etc/nixos/modules/home-assistant.nix`
- Affected host configuration: `src/roles/nixos/files/device-configuration/habiki.nix`
- Affected validation: Home Assistant runtime checks and deployment verification
- Runtime dependencies: host BlueZ/Bluetooth service, system D-Bus socket, Home Assistant Bluetooth and SwitchBot integrations
- Security impact: the Home Assistant container receives read-only access to `/run/dbus` and additional capabilities needed by Home Assistant's Bluetooth integration
