## Context

`garage.nix` enables the NixOS Garage service and sets `package = pkgs.garage`. On `nixos-26.05`, that alias is Garage 1.3.1, while `pkgs.garage_2` is 2.4.1. The module already uses `replication_factor`, loopback listeners, the existing storage directories, and agenix environment files. Caddy, Prometheus, and the layout task sit around that service.

The operator has confirmed that Garage currently holds nothing worth preserving.

## Goals / Non-Goals

**Goals:**

- Run Garage 2.4.1 by selecting the existing NixOS package.
- Leave the current service behaviour and surrounding configuration unchanged.
- Change another file only when required for 2.4.1 to evaluate, start, or accept the existing layout task.

**Non-Goals:**

- Snapshots, upgrade rehearsal, recovery automation, or off-host replication.
- Admin API clients, scoped tokens, Authentik, or the separate broker change.
- New endpoints, buckets, credentials, dashboards, or deployment-workflow refactors.
- Pinning the NixOS channel or changing metadata engines.

## Decisions

### 1. Change the package selection

Set `services.garage.package` to `pkgs.garage_2`. Do not overlay, vendor, or fetch a Garage binary. The NixOS module continues to generate the configuration and systemd service.

Alternative considered: pin a nixpkgs revision or upstream binary. Rejected because the requested version is already packaged and a second delivery path adds supply-chain and update work.

### 2. Keep the current configuration

Do not edit listeners, paths, replication, secrets, Caddy, Prometheus, or provisioning preemptively. The current settings already use `replication_factor` rather than the removed `replication_mode`.

If evaluation or the running 2.4.1 service rejects one existing setting or command, make the smallest compatible adjustment and leave its externally visible behaviour unchanged.

### 3. Assert the requested version locally

Extend the existing Garage evaluation test to require package version `2.4.1`. This catches channel drift without adding a deployment or migration harness.

### 4. Treat stored state as disposable

Do not copy or snapshot `/var/lib/garage`. Do not add a wipe task. If 2.4.1 cannot start because of existing empty state, or a package rollback cannot read state written by 2.4.1, the operator may discard that state and allow the existing provisioning task to recreate the single-node layout.

## Risks / Trade-offs

- [Channel updates `garage_2` beyond 2.4.1] → The evaluation assertion fails until the version decision is revisited.
- [2.4.1 rejects a current setting or CLI command] → Adjust only the rejected interface; do not redesign provisioning.
- [Rollback cannot read upgraded metadata] → Discard the disposable state rather than building a restoration procedure.
- [Targeted NixOS deployment still rebuilds Habiki] → Accept the existing deployment path; do not refactor it for this package change.

## Migration Plan

1. Select `pkgs.garage_2` and assert version 2.4.1.
2. Run the existing Garage evaluation test.
3. Deploy through the existing targeted Habiki NixOS path and confirm the service is active.
4. If startup fails, revert the package selection. Discard `/var/lib/garage` only if the prior version cannot start from the new state.

## Open Questions

None. Command compatibility is an implementation checkpoint, not a reason to add tooling.
