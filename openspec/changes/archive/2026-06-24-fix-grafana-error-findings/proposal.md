## Why

The last 24 hours of Grafana/Loki logs show recurring service failures and high-volume warning noise that reduce operational confidence and obscure actionable alerts. The most urgent finding is `podman-frontier-indexer.service` repeatedly failing database setup, while kernel PCIe AER spam and Grafana resource-client warnings should be triaged or suppressed only after root cause is understood.

## What Changes

- Add a repeatable operational remediation path for high-priority Grafana/Loki error findings.
- Fix or harden the Frontier Indexer database connection/setup path so the service does not crash-loop when its database dependency or secret material is unavailable.
- Add validation for Frontier Indexer runtime health and telemetry after deployment.
- Triage the recurring PCIe AER correctable error spam and document/apply a host-specific mitigation only if it is safe for the affected hardware.
- Triage Grafana `resource-client-auth-interceptor` warnings and either fix the configuration/plugin behavior or document them as accepted upstream noise with an explicit filter/monitoring decision.
- Leave low-priority Home Assistant Chromecast, Syncthing NAT-PMP, and transient Authentik disconnect warnings as documented follow-up unless investigation reveals a shared dependency or service-impacting failure.

## Capabilities

### New Capabilities
- `grafana-error-remediation`: Defines how recurring Grafana/Loki error findings are investigated, prioritized, fixed, and verified through declarative infrastructure changes.

### Modified Capabilities
- `grafana-operations-portal`: Add requirements for surfacing actionable remediation status for services with recurring error findings, starting with Frontier Indexer.

## Impact

- Affected systems: Grafana/Loki observability, Frontier Indexer service, Habiki host configuration, Grafana dashboards/operations portal.
- Affected code is expected under `src/roles/nixos/files/etc/nixos/modules/`, `src/roles/nixos/files/device-configuration/`, `src/roles/secrets/`, and `terraform/dashboards/` or `terraform/grafana.tf` if dashboard/catalog updates are required.
- Deployment should use targeted automation, e.g. `./scripts/play.sh --limit habiki --tags nixos` and any relevant OpenTofu wrapper flow through `scripts/tofu.sh`.
- No secrets may be hardcoded; any database credentials or tokens must continue to flow through Ansible Vault/agenix/runtime environment files.
