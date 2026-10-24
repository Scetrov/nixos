# Home Assistant on Habiki

## Runtime and access

`src/roles/nixos/files/etc/nixos/modules/home-assistant.nix` owns the
`scetrov.services.home-assistant` options; Habiki enables the service, Matter
and Bluetooth explicitly. Home Assistant uses a version/digest-pinned Podman
image and host networking for multicast discovery. `/var/lib/homeassistant`
is persistent, initially `0750 root:root`; it is not disposable container state.
Locale defaults are Europe/London, GB, GBP, en-GB and elevation 50.

Caddy serves `https://homeassistant.net.scetrov.live` using the existing
certificate and `127.0.0.1:8123` upstream, preserving Host. Authentication is
**native Authentik OIDC**, not Caddy forward-auth: UI, webhook, WebSocket and
`/auth/oidc/callback` requests retain Home Assistant's own protocol handling.
The public OIDC client is `home-assistant`, with discovery under application
slug `home-assistant-oidc` and the exact HTTPS callback above. The existing
proxy application is not a reason to add a second browser authentication gate.
The alias maps to Habiki through shared local networking.

The vendored `hass-oidc-auth` integration is the existing custom-integration
exception. Roles map Authentik Admins to admin and General User to user.
Generated HTTP configuration trusts `127.0.0.1`, `::1` and `10.229.0.0/16`;
review the real proxy path before changing this trust boundary. Discovery opens
UDP 1900 and 5353 only with the service enabled; host networking does not imply
permission to open further application ports.

Activation manages `configuration.yaml`, the reviewed automation/script/scene
includes, the OIDC component and onboarding state. The bootstrap-owner oneshot
creates `scetrov-bootstrap` only when no users exist; its generated password
stays in the mode-0600 `.bootstrap-owner-password` file, never in Git or logs.
Preserve existing authentication and registry state during rebuilds/recovery.

## Configuration ownership

Review live files before replacing managed YAML: deployment installs the
repository versions, so unimported UI changes can be lost. Compare live
`automations.yaml`, `scripts.yaml`, `scenes.yaml`, helpers and dashboards with
`src/roles/nixos/files/etc/nixos/home-assistant/`. Import only reviewed assets;
keep `.storage` authentication, registries and personal runtime data out of Git.
The [original configuration audit](../src/roles/nixos/files/etc/nixos/home-assistant/docs/audit.md)
is a dated inventory, not a current device census or image-version authority.

Define each automation/script's trigger or inputs, preconditions and expected
actions in a small GIVEN/WHEN/THEN example before changing behaviour. Prefer
official integrations and built-in helpers; any new HACS/custom exception needs
a reason, deployment/update ownership and removal/rollback notes. Review entity
availability before deleting disabled entities. Dashboard ownership must be
explicitly chosen before importing UI storage into declarative YAML.

## Matter and Bluetooth

- `matter.enable` runs a separate pinned official Matter Server with persistent
  `/var/lib/matter-server` state and loopback `ws://localhost:5580/ws`. It is
  not a Thread border router. Record the external border router before
  commissioning Thread devices; do not add public Matter ingress. The current
  container uses host networking and an AppArmor-unconfined exception; preserve
  that explicit boundary rather than describing it as fully confined.
- `bluetooth.enable` enables host BlueZ, mounts `/run/dbus:/run/dbus:ro` and adds
  only `NET_ADMIN`/`NET_RAW`, not privileged mode. Disabling it removes those
  Home Assistant-specific additions. Host/controller/D-Bus checks were recorded
  in the Bluetooth rollout, but the official SwitchBot discovery trial and the
  decision whether an ESPHome proxy is needed were left unchecked. Environmental
  dashboards alone do not establish reliable local BLE coverage. Recheck these
  with the operator before claiming the trial complete.

## Private telemetry

The module manages an authenticated `/api/prometheus` endpoint and a local
Prometheus scrape at `127.0.0.1:8123`, labelled `service="home-assistant"`.
Only curated temperature, humidity, CO2, particulate and air-quality entities
are exported; diagnostic/firmware/RSSI series are not a blanket default.

Create a dedicated long-lived token in the Home Assistant profile UI, store it
as `home_assistant_metrics_token` in encrypted `src/secrets.yml`, and deploy
through Vault/agenix. Prometheus reads its mode-0400 credential file; keep
values out of configuration and logs. Rotation replaces the vaulted token and
redeploys the affected secret/service, then checks `up{job="home-assistant"}`.

Use local Prometheus for scrape health and Mimir for retained environmental
history. The service, environmental and house dashboards live in
`terraform/dashboards/`. Indoor/outdoor averages use reviewed entity allowlists,
not assumptions based on sensor names. Traces require separately verified
Home Assistant OTLP configuration; their presence is not implied by metrics.
Journals flow through existing Alloy/Loki collection.

## Deployment, verification and recovery

```sh
./scripts/play.sh --limit habiki --tags nixos
# Propagate changed aliases to the other DNS host only when necessary:
./scripts/play.sh --limit fyne --tags local-dns
```

Review complete Habiki configuration and coordinate downtime: the generic NixOS
lane can restart unrelated Podman services. Verify Home Assistant/container and
bootstrap health, native OIDC login/return, webhook/WebSocket compatibility,
8123 listener and discovery firewall rules, Caddy validation, and local DNS.
When enabled, verify Matter's loopback WebSocket, BlueZ/controller/D-Bus access,
and actual device discovery. Confirm authenticated scrape health, real exported
series through both Prometheus and Mimir, dashboard rendering and Loki delivery.
Deploy dashboard changes only through `scripts/tofu.sh` after telemetry works.

Disable Matter/Bluetooth independently through their options when reverting
those features; retain pairing and application state. Disabling the whole
service must also remove its Caddy route/discovery allowances through automation.
Do not remove persistent directories or restore an old registry as a casual
configuration rollback; no off-host backup/restore certification is implied.
