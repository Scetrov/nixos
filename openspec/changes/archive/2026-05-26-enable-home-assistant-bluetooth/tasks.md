## 1. Module Configuration

- [x] 1.1 Add `scetrov.services.home-assistant.bluetooth.enable` to `src/roles/nixos/files/etc/nixos/modules/home-assistant.nix`
- [x] 1.2 When Bluetooth is enabled, configure host Bluetooth/BlueZ support declaratively in the Home Assistant module
- [x] 1.3 When Bluetooth is enabled, mount `/run/dbus:/run/dbus:ro` into the Home Assistant container
- [x] 1.4 When Bluetooth is enabled, add `--cap-add=NET_ADMIN` and `--cap-add=NET_RAW` to the Home Assistant container options
- [x] 1.5 Keep Bluetooth-related host services, mounts, and capabilities absent when `bluetooth.enable` is false

## 2. Habiki Trial Enablement

- [x] 2.1 Enable `scetrov.services.home-assistant.bluetooth.enable = true` in `src/roles/nixos/files/device-configuration/habiki.nix`
- [x] 2.2 Confirm the Home Assistant container declaration still preserves existing host networking, state volume, OIDC configuration, Matter configuration, and discovery firewall behavior

## 3. Verification

- [x] 3.1 Run a local Nix evaluation/build check for Habiki or the relevant NixOS configuration
- [x] 3.2 Deploy with `./scripts/play.sh --limit habiki --tags nixos`
- [x] 3.3 Verify on Habiki that the Bluetooth service is active and BlueZ sees a controller
- [x] 3.4 Verify inside the Home Assistant container that `/run/dbus` is present
- [x] 3.5 Check Home Assistant logs for Bluetooth setup errors such as missing BlueZ D-Bus service or D-Bus access denial
- [ ] 3.6 Add the official SwitchBot Bluetooth integration in Home Assistant and record whether local Habiki coverage discovers the target temperature and humidity sensors

## 4. Sign-off

- [x] 4.1 Run `openspec status --change enable-home-assistant-bluetooth`
- [x] 4.2 Stage the OpenSpec artifacts and implementation files for commit
- [x] 4.3 Confirm no secrets, keys, tokens, or sensitive material were introduced
- [ ] 4.4 Decide whether local Bluetooth is sufficient or whether a follow-up ESPHome Bluetooth proxy change is needed
