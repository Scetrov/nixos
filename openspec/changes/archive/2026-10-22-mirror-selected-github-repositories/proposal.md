## Why

Issue #26 requests local Git mirrors without manually importing each repository or updating configuration for every new matching source. Declarative discovery can populate the existing private Forgejo service while keeping credentials, ownership, and destructive lifecycle decisions controlled.

## What Changes

- Discover repositories matching `Scetrov/*`, `RichardSlater/*`, and `storytold/*craft` through paginated GitHub APIs.
- Reconcile managed Forgejo pull mirrors with deterministic source-owner namespaces and a reviewable report-only mode.
- Define eligibility, visibility, credential, rename/deletion, LFS/submodule, and retry behavior explicitly.
- Schedule reconciliation declaratively and expose failures and stale synchronization through existing observability.

## Capabilities

### New Capabilities
- `forgejo-github-mirroring`: Safe declarative discovery, creation, and ongoing synchronization of selected GitHub Git repositories.

### Modified Capabilities
None. Existing private service, native identity, and inactive Actions requirements remain intact.

## Impact

Issue #26; a focused mirror reconciler, NixOS service/timer, vault-backed runtime credentials, isolated OpenTofu-managed Forgejo identity/organizations, a focused Habiki report-only deployment lane, tests, documentation, and existing Grafana/Loki integration. No runners, platform metadata migration, automatic deletion, public ingress, or shared discovery framework with #27.
