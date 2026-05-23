## Context

Home Assistant runs on Habiki as a Podman container with host networking and repository-managed configuration. That deployment model does not include Home Assistant Supervisor, so the normal add-on path for Matter is unavailable even though the Home Assistant UI still suggests the default Matter websocket endpoint `ws://localhost:5580/ws`.

The current repository state already documents that Thread exists in live Home Assistant state while Matter does not. The Home Assistant platform spec also prefers official integrations and explicit review of protocol dependencies before introducing new runtime services.

## Goals / Non-Goals

**Goals:**

- Provide a declarative Matter Server runtime on Habiki for the existing Home Assistant container deployment.
- Preserve the default Home Assistant controller endpoint contract at `ws://localhost:5580/ws` so the integration works without extra host indirection.
- Persist Matter state outside Git and manage it through the existing NixOS workflow.
- Keep Thread border-router responsibilities explicit so Matter enablement does not imply Thread infrastructure exists.
- Add focused deployment verification for the Matter websocket endpoint and service health.

**Non-Goals:**

- Provision a second Home Assistant instance or move Home Assistant off Habiki.
- Expose the Matter websocket publicly through Caddy or Authentik.
- Introduce HACS or additional custom integrations for Matter.
- Solve Thread border-router deployment in the same change.
- Commit Matter pairing credentials or runtime state into the repository.

## Decisions

- Extend the existing Home Assistant module instead of creating a separate Habiki-only service module.
  - Rationale: the owning abstraction is already `src/roles/nixos/files/etc/nixos/modules/home-assistant.nix`, which manages the Home Assistant container, its declarative state, and related local-protocol firewall behavior.
  - Alternative considered: a standalone `matter-server.nix` module imported only on Habiki. This would add another service boundary for behavior that exists only to support the Home Assistant platform.

- Add an explicit Matter sub-option under the Home Assistant service and enable it on Habiki.
  - Rationale: Matter introduces a new stateful runtime and troubleshooting surface, so it should be opt-in at the module level even if Habiki enables it immediately.
  - Alternative considered: always run Matter whenever Home Assistant is enabled. This is simpler but makes every Home Assistant deployment carry an unnecessary daemon.

- Run the Matter Server on the same host as Home Assistant and keep the endpoint contract at loopback port `5580`.
  - Rationale: the Home Assistant container already uses `--network=host`, so `ws://localhost:5580/ws` resolves on Habiki exactly where the integration expects it.
  - Alternative considered: run Matter on another host or a bridged container network and override the UI prompt. This works, but it adds routing and configuration drift for no benefit on this single-host deployment.

- Persist Matter state in a dedicated host directory rather than inside `/var/lib/homeassistant`.
  - Rationale: a separate state path keeps Matter credentials and storage isolated from Home Assistant configuration while still remaining declarative and persistent.
  - Alternative considered: store Matter state under Home Assistant's existing config directory. This would reduce path count but mixes independent service state and makes rollback less clear.

- Treat Thread border-router ownership as a documented prerequisite, not as part of the Matter server runtime.
  - Rationale: Matter over Wi-Fi and Ethernet can work without Thread, while Matter over Thread requires additional hardware or an external border router that this repository does not currently declare.
  - Alternative considered: bundle Thread border-router provisioning into the same change. This would broaden scope into hardware-specific networking decisions before the Matter backend itself is in place.

## Risks / Trade-offs

- Runtime packaging may differ between what Nixpkgs exposes and what the official Home Assistant Matter Server image supports best. -> Keep the endpoint and persistence contract fixed, and choose the implementation form during coding based on what the repo can reliably deploy.
- Matter state is sensitive operational data even if it is not a long-lived secret in Git terms. -> Store it in a persistent host directory with restricted permissions and never commit runtime artifacts.
- Users may still fail to commission Thread-based Matter devices if no Thread border router is present. -> Document the requirement explicitly and keep it separate from Matter server health checks.
- Host-network deployment can make services easier to reach than necessary. -> Prefer loopback binding when the runtime allows it, and do not add any public reverse proxy or extra ingress.

## Migration Plan

1. Extend `home-assistant.nix` with a Matter-specific option, runtime declaration, and persistent state directory.
2. Enable the Matter option on Habiki through the existing device configuration.
3. Deploy narrowly with `./scripts/play.sh --limit habiki --tags nixos` and verify the Matter websocket listener is present on port `5580`.
4. Add the Matter integration in Home Assistant using `ws://localhost:5580/ws` and confirm the websocket connection succeeds.
5. If rollback is needed, disable the Matter option to remove the runtime while preserving state until explicit cleanup is requested.

## Open Questions

- Should implementation prefer a Nixpkgs-provided package/service or an OCI container for the official Matter Server runtime in this repository?
- Does the chosen runtime require additional multicast, IPv6, or Bluetooth permissions for the device mix expected on Habiki?
