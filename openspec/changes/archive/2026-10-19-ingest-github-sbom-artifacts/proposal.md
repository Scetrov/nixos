## Why

Issue #27 requires ingesting GitHub Actions CycloneDX artifacts into private Dependency-Track without exposing its API or running repository code on the private host. An outbound-only collector separates SBOM production from trusted, least-privilege ingestion.

## What Changes

- Define a versioned producer contract for CycloneDX JSON artifacts from explicitly trusted successful workflows and refs.
- Add a private NixOS oneshot collector/timer that downloads, validates, and submits artifacts to configured Dependency-Track projects.
- Persist accepted-upload checkpoints and returned tokens, with bounded transfer retries and actionable operational status. Dependency-Track owns subsequent processing; the collector does not verify internal ingestion success.
- Deliver first with one trusted repository/workflow/artifact/project while supporting declarative expansion independently of Forgejo mirror selection.
- Authenticate with a dedicated SBOM GitHub App: one App ID/private key, an explicit array of installation IDs across accounts/organisations, and automatically minted repository-scoped Actions-read tokens. Do not reuse or extend the Grafana App.

## Capabilities

### New Capabilities
- `github-sbom-ingestion`: Trusted artifact selection, bounded validation, project mapping, durable ingestion state, and private operations.

### Modified Capabilities
None.

## Impact

Issue #27; collector packaging/module, encrypted runtime credentials, persistent checkpoint state, producer contract/selected workflow integration, Dependency-Track project/team configuration, tests, and existing observability. Any necessary service-internal configuration uses existing automation; OpenTofu operations use `scripts/tofu.sh`. No public ingress, private-network CI runner, collector-side builds, automatic remediation, or mandatory artifact attestations.
