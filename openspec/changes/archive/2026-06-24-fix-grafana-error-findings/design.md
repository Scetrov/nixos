## Context

The Grafana/Loki 24-hour investigation found three operationally important classes of log findings:

1. `podman-frontier-indexer.service` exits with `Error: Failed to get connection for database setup`, producing a real service failure.
2. The kernel emits high-volume PCIe AER correctable errors for `pcieport 0000:00:1c.0`, creating observability noise and possible hardware/firmware concern.
3. Grafana emits repeated `resource-client-auth-interceptor` warnings about calls without an id token or service identity.

Frontier Indexer is managed declaratively by `src/roles/nixos/files/etc/nixos/modules/frontier-indexer.nix`, which creates a Podman network, prepares database secret/env files, runs TimescaleDB, waits for `pg_isready`, and then starts the indexer container. The observed failure happens after basic readiness and appears tied to the indexer's database setup connection path rather than generic host availability alone.

Repository constraints require all fixes to remain declarative, secrets to stay in Ansible Vault/agenix/runtime files, and deployment to use targeted automation where possible.

## Goals / Non-Goals

**Goals:**

- Make Frontier Indexer startup resilient enough that database setup succeeds or fails with a clear preflight diagnostic instead of repeated opaque crash loops.
- Preserve the existing declarative NixOS/Ansible/OpenTofu operating model.
- Add post-deployment verification for the fixed service, including systemd state, DB readiness, logs, and metrics visibility.
- Triage PCIe AER and Grafana auth warning noise with safe, reversible decisions.
- Surface the remediation state in the Grafana operations workflow so future investigations can distinguish active failures from accepted noise.

**Non-Goals:**

- Replacing Frontier Indexer or TimescaleDB.
- Broad Grafana or Loki architecture changes unrelated to these findings.
- Suppressing kernel or Grafana warnings without first documenting root cause and operator impact.
- Fixing low-priority Home Assistant Chromecast reachability, Syncthing NAT-PMP mappings, or transient Authentik client disconnects unless they prove related during investigation.

## Decisions

### Decision: Fix Frontier Indexer first and treat it as the blocking operational failure

The Frontier Indexer issue is the only top finding that includes repeated service exits. Implementation should start by checking the generated env file shape, secret file permissions, Podman network DNS, TimescaleDB readiness from the indexer network, and whether the indexer expects a different database host, schema, TLS mode, or startup delay.

Alternative considered: address the highest-frequency PCIe messages first. This was rejected because they are correctable kernel events, while Frontier Indexer is an application outage.

### Decision: Add explicit database preflight before the indexer starts

The module already waits for `pg_isready`, but that only proves the server accepts basic readiness checks. Add or improve a preflight that validates the same connection parameters the indexer will use, including host, port, database, user, password source, and schema setup expectations. The preflight should fail before `podman-frontier-indexer.service` starts and emit an actionable log message.

Alternative considered: only increase `RestartSec` or retry counts. This may reduce noise but does not prove database setup works or make failures actionable.

### Decision: Keep secret flow unchanged

The database password must remain sourced through the existing generated secret/agenix path and copied into root-owned runtime state only as needed for the containers. Any new check must read existing runtime files and must not log secret values.

Alternative considered: embedding password values into Nix or OpenTofu variables for easier diagnostics. This violates repository security standards and is not acceptable.

### Decision: Treat PCIe AER mitigation as host-specific and reversible

The PCIe AER finding should be investigated with hardware identity, affected host, kernel logs, firmware/kernel version, and device mapping before applying boot parameters. If a mitigation is needed, prefer a narrowly documented host-specific NixOS boot option with rollback instructions. Do not globally disable AER across the fleet without evidence.

Alternative considered: immediately add `pci=noaer`. This would suppress logs but may hide useful hardware fault reporting.

### Decision: Treat Grafana resource-client warnings as either fixable configuration or documented accepted noise

The Grafana warning should be checked against the deployed Grafana version, plugins/features using resource APIs, service accounts, and upstream known issues. If it is fixable through configuration or upgrade, apply that declaratively. If it is benign upstream noise, document the decision and add monitoring/log filtering guidance rather than leaving it unexplained.

Alternative considered: immediately filter the log line. This hides symptoms before proving they are benign.

## Risks / Trade-offs

- **[Risk] Preflight check uses different connection behavior than the application** → Use the same environment file values and run the check from the same Podman network where possible.
- **[Risk] Additional startup dependencies create longer boot times** → Keep timeouts bounded and fail with clear diagnostics.
- **[Risk] PCIe AER suppression hides real hardware degradation** → Require root-cause notes and a host-specific rollback path before suppression.
- **[Risk] Grafana warning cause is upstream/internal and not locally fixable** → Record accepted-noise rationale and avoid broad log suppression unless operator value is clear.
- **[Risk] Fix requires credential changes** → Use existing Ansible Vault/agenix flows only; never hardcode or print secrets.

## Migration Plan

1. Inspect Frontier Indexer runtime state on `habiki`: systemd status, TimescaleDB status, recent logs, env file keys only, Podman network resolution, and DB readiness from inside the network.
2. Update the declarative Frontier Indexer module with a connection/setup preflight or corrected database configuration.
3. Deploy only the affected host/configuration with `./scripts/play.sh --limit habiki --tags nixos`.
4. Verify `podman-frontier-indexer.service` stays active, logs no longer contain the database setup failure, and Frontier Indexer metrics are scraped.
5. Investigate PCIe AER source and decide between no change, firmware/kernel update follow-up, or host-specific boot mitigation.
6. Investigate Grafana resource-client warnings and decide between declarative config/update fix or documented accepted-noise handling.
7. Update Grafana operations/dashboard artifacts if needed to show remediation state.

Rollback: revert the NixOS/OpenTofu changes, redeploy the affected host with the same targeted command, and confirm services return to their previous state. For boot-parameter changes, keep a documented generation rollback path.

## Open Questions

- Which host emits the PCIe AER events, and which physical device maps to `0000:00:1c.0`?
- Does Frontier Indexer require schema/database initialization not covered by current TimescaleDB readiness checks?
- Are the Grafana resource-client warnings from a specific plugin, dashboard feature, service account, or known upstream issue in the deployed version?
