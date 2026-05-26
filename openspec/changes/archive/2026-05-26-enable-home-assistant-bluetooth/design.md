## Context

Home Assistant runs on Habiki as an OCI container using host networking. That gives it LAN discovery behavior for integrations such as mDNS and SSDP, but Bluetooth on Linux is mediated by the host kernel controller, BlueZ, and the system D-Bus API. The current Home Assistant module does not enable the host Bluetooth stack and does not pass `/run/dbus` or Bluetooth-related capabilities into the container.

SwitchBot temperature and humidity sensors advertise over BLE. The official Home Assistant Bluetooth and SwitchBot integrations can consume those advertisements locally when Home Assistant can reach a working BlueZ controller.

## Goals / Non-Goals

**Goals:**

- Add an opt-in `scetrov.services.home-assistant.bluetooth.enable` setting.
- When enabled, make Habiki's local Bluetooth controller available to the Home Assistant container through host BlueZ and D-Bus.
- Enable the option on Habiki for a direct local trial with the existing Bluetooth controller or a host-attached USB adapter.
- Add verification steps that distinguish host Bluetooth failure from container access failure.

**Non-Goals:**

- Do not introduce ESPHome Bluetooth proxies in this change.
- Do not configure SwitchBot entities declaratively inside Home Assistant.
- Do not add a SwitchBot Hub, cloud API integration, or Matter bridge path.
- Do not change the existing Home Assistant OIDC, Matter, ingress, or YAML asset behavior except where verification needs to account for Bluetooth.

## Decisions

### Use host BlueZ with D-Bus passthrough

Home Assistant Container expects the Linux host to run BlueZ and expose the D-Bus socket inside the container. The NixOS module should enable host Bluetooth support when the Home Assistant Bluetooth option is enabled, then mount `/run/dbus:/run/dbus:ro` into the Home Assistant container.

Alternative considered: pass `/dev` or a specific USB controller device directly into the container. That is less aligned with Home Assistant's supported Linux container path because Home Assistant talks to BlueZ over D-Bus, not directly to raw USB device nodes for normal Bluetooth operation.

### Add only the capabilities Home Assistant needs

The Home Assistant container should receive `NET_ADMIN` and `NET_RAW` when Bluetooth is enabled. These match the documented container requirements for Home Assistant Bluetooth support and avoid making the container fully privileged by default.

Alternative considered: run the Home Assistant container privileged. That is broader than necessary for the first implementation and makes the security boundary harder to reason about.

### Keep Bluetooth optional in the service module

Bluetooth should be modeled as a sub-option under the existing Home Assistant service, similar to Matter. Habiki can enable it explicitly, while other hosts that import the module retain the current behavior.

Alternative considered: enable Bluetooth unconditionally whenever Home Assistant is enabled. That would expand host services and container permissions for deployments that do not need BLE integrations.

### Treat ESPHome proxies as a follow-up if range is poor

This change deliberately tries local Habiki Bluetooth first. If SwitchBot sensor coverage is unreliable because of house layout, walls, adapter quality, or radio placement, a later change can add ESPHome Bluetooth proxy management.

## Risks / Trade-offs

- D-Bus exposure increases container reach into host service APIs -> mount `/run/dbus` read-only and only when Bluetooth is explicitly enabled.
- Extra network capabilities broaden container permissions -> gate `NET_ADMIN` and `NET_RAW` behind `bluetooth.enable`.
- Habiki's adapter may not cover all sensors -> verify with discovered SwitchBot devices and defer ESPHome proxy work until the local trial produces evidence.
- BlueZ may see a controller but Home Assistant may fail due to confinement -> inspect Home Assistant and host logs; only add stronger security relaxation if the trial shows a specific denial.

## Migration Plan

1. Add the Bluetooth option and conditional host/container configuration to the Home Assistant module.
2. Enable the option in Habiki's device configuration.
3. Deploy with `./scripts/play.sh --limit habiki --tags nixos`.
4. Verify BlueZ on the host, D-Bus visibility inside the container, Home Assistant Bluetooth integration setup, and SwitchBot discovery.
5. Roll back by disabling `scetrov.services.home-assistant.bluetooth.enable` on Habiki and redeploying the targeted NixOS tag.

## Open Questions

- Does Habiki currently have a reliable internal Bluetooth controller, or will the trial need a known-good USB BLE adapter?
- Is AppArmor or another container policy active enough to require a targeted `--security-opt` exception after D-Bus passthrough is added?
