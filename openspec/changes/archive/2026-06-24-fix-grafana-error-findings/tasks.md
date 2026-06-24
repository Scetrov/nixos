## 1. Runtime Investigation

- [x] 1.1 Query recent Loki logs for Frontier Indexer, TimescaleDB, PCIe AER, and Grafana resource-client warnings to confirm current frequency and affected units.
- [x] 1.2 Inspect `habiki` Frontier Indexer systemd and Podman state, including `podman-frontier-indexer.service`, `podman-frontier-timescaledb.service`, and `frontier-indexer-wait-for-db.service`.
- [x] 1.3 Validate Frontier Indexer runtime files without printing secrets: state directory permissions, env file keys, database password file ownership/mode, and generated secret availability.
- [x] 1.4 Test TimescaleDB connectivity from the Frontier Indexer Podman network using the same host, port, database, and user expected by the indexer.
- [x] 1.5 Identify the host and device behind PCIe address `0000:00:1c.0` and record whether the error is hardware, firmware, kernel, or peripheral related.
- [x] 1.6 Identify the Grafana version, plugin/feature context, and subject identities associated with `resource-client-auth-interceptor` warnings.

## 2. Frontier Indexer Remediation

- [x] 2.1 Update `src/roles/nixos/files/etc/nixos/modules/frontier-indexer.nix` to add or improve a non-secret database setup preflight before `podman-frontier-indexer.service` starts.
- [x] 2.2 Correct any discovered Frontier Indexer database configuration mismatch, such as database host, schema setup, readiness timing, env variable shape, or network dependency ordering.
- [x] 2.3 Ensure the preflight runs through the declared Podman network where practical and emits actionable diagnostics without logging credentials.
- [x] 2.4 Keep all database credential handling in the existing Ansible Vault/agenix/runtime-file flow with no hardcoded secrets in Nix, OpenTofu, dashboards, or logs.

## 3. Noise Triage and Declarative Decisions

- [x] 3.1 Decide and document the PCIe AER outcome: no change, firmware/kernel follow-up, or host-specific reversible boot mitigation.
- [x] 3.2 If PCIe mitigation is needed, implement it only in the affected host configuration with rollback notes.
- [x] 3.3 Decide and document the Grafana resource-client warning outcome: declarative config/update fix or accepted benign noise.
- [x] 3.4 If Grafana warning handling requires dashboard/log treatment, implement it declaratively in the existing Grafana/OpenTofu workflow.

## 4. Operations Portal Updates

- [x] 4.1 Review the Frontier Indexer dashboard and operations portal entries for current service health, recent errors, and metrics context.
- [x] 4.2 Add or adjust declarative Grafana dashboard/catalog content so operators can distinguish an active Frontier Indexer database setup failure from a healthy service.
- [x] 4.3 Document accepted-noise status for reviewed PCIe or Grafana warnings where applicable so they are not confused with unresolved failures.

## 5. Validation and Deployment

- [x] 5.1 Run repository checks for changed Nix/OpenTofu/dashboard files, using targeted commands where available.
- [x] 5.2 Deploy host-level changes with `./scripts/play.sh --limit habiki --tags nixos` unless the implementation proves a narrower or additional tag is required.
- [x] 5.3 Apply any Grafana/OpenTofu changes through `scripts/tofu.sh` only, if dashboard or Grafana resources changed.
- [x] 5.4 Verify `podman-frontier-indexer.service` remains active and no longer logs `Failed to get connection for database setup` after deployment.
- [x] 5.5 Verify Frontier Indexer metrics are scrapeable through the managed Prometheus/Mimir path and visible in Grafana.
- [x] 5.6 Re-run the Grafana error investigator for a post-change window and confirm the remediated findings are resolved or explicitly documented as accepted.
- [x] 5.7 Stage all required files for commit and perform the repository sign-off checklist, including secret hygiene and dangling route/endpoint review.
