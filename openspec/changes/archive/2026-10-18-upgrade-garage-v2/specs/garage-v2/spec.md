## ADDED Requirements

### Requirement: Garage 2.4.1 package

The Habiki Garage service SHALL use the NixOS `pkgs.garage_2` package at version 2.4.1. It SHALL NOT use the `pkgs.garage` alias or another Garage version.

#### Scenario: Configuration selects the packaged release

- **WHEN** the Habiki Garage module is evaluated
- **THEN** `services.garage.package` SHALL be `pkgs.garage_2`
- **AND** its version SHALL be `2.4.1`

### Requirement: Existing behaviour remains unchanged

The package change SHALL retain the current loopback listeners, storage paths, replication factor, secret injection, private endpoints, and metrics collection. It SHALL NOT add endpoints, credentials, buckets, administration routes, or data-preservation tooling.

#### Scenario: Upgrade does not redesign the service

- **WHEN** Garage 2.4.1 replaces the current package
- **THEN** the existing service configuration and access paths SHALL remain in place
- **AND** no snapshot, rehearsal, or recovery automation SHALL be introduced

#### Scenario: Incompatible interface needs adjustment

- **WHEN** Garage 2.4.1 rejects an existing setting or layout command
- **THEN** the implementation SHALL make the smallest compatible adjustment
- **AND** the adjustment SHALL preserve the current externally visible behaviour
