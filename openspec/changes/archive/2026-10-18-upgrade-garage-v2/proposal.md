## Why

Habiki selects `pkgs.garage`, which is Garage 1.3.1. NixOS 26.05 already provides Garage 2.4.1 as `pkgs.garage_2`, including the Admin API needed by later administration work. The current store contains no data that must be preserved.

## What Changes

- Select `pkgs.garage_2` so the Garage service and CLI use version 2.4.1.
- Retain the current listeners, storage paths, replication factor, secret injection, endpoints, and monitoring.
- Adjust an existing command or setting only if Garage 2.4.1 rejects it.
- Do not add snapshots, recovery rehearsal, data migration tooling, new endpoints, or administration features.

## Capabilities

### New Capabilities

- `garage-v2`: Run the existing Habiki Garage service on the NixOS Garage 2.4.1 package without changing its current behaviour.

### Modified Capabilities

- None. Existing S3 endpoint and storage requirements remain unchanged.

## Impact

- `src/roles/nixos/files/etc/nixos/modules/garage.nix`
- `src/roles/nixos/tests/garage-eval.nix`
- Existing Garage provisioning only if its current commands are incompatible with 2.4.1
- Garage restarts when the targeted Habiki NixOS configuration is deployed; no other service redesign is in scope
