## 1. Resolve Compatibility and Operational Decisions

- [x] 1.1 Test official Codex 0.145.0 as the initial candidate on Habiki's architecture for `app-server`, Unix-socket transport, `chatgptDeviceCode` login, persisted token refresh, and `account/rateLimits/read`; record the accepted pinned version and sanitized response shape or update the design before continuing if the candidate fails.
- [x] 1.2 Select the repository's reproducible OCI build method, pin the Codex release and all integrity hashes/digests, and document why the selected source satisfies image provenance requirements.
- [x] 1.3 Identify whether an approved encrypted host backup covers the planned Codex state directory; record either the tested restore path or device-code re-enrollment as the explicit BCDR procedure.
- [x] 1.4 Treat tasks 1.1-1.3 as a hard gate: update `design.md` with the accepted image and recovery decisions, and stop the apply run before section 2 if compatibility, reproducibility, containment, or recovery cannot be resolved.

## 2. Build and Validate the Codex App-Server Image

- [x] 2.1 Add a minimal repository-defined OCI image containing the pinned official Codex distribution, CA certificates, and an unprivileged runtime identity.
- [x] 2.2 Configure the image entrypoint to run `codex app-server` with persistent `CODEX_HOME`, `/run/codex-app-server/control.sock`, `LOG_FORMAT=json`, warning-level `RUST_LOG`, and debug/trace protocol logging disabled.
- [x] 2.3 Add reproducibility checks that fail on floating tags, missing dependency integrity data, or an unexpected Codex version.
- [x] 2.4 Build the image locally and verify app-server starts as non-root with no published listener and a read-only root filesystem where supported.

## 3. Provision the Podman Runtime on Habiki

- [x] 3.1 Extend the NixOS AI usage module with options for the pinned app-server image, protected state directory, runtime/socket directory, and Codex enablement.
- [x] 3.2 Declare the rootless NixOS-managed Podman workload with a dedicated host identity, keep-id user mapping, retained supplementary groups, persistent and runtime mounts, dropped capabilities, no workspace/host executable mounts, restart policy, and structured non-debug logging.
- [x] 3.3 Configure `/var/lib/codex-app-server` as 0700 `codex-app-server:codex-app-server`, `/run/codex-app-server` as 2770 `codex-app-server:ai-usage-exporter`, the socket as 0660 under umask 0007, guarded stale-socket cleanup, and a 10-second handshake/initialize/`account/read` readiness helper.
- [x] 3.4 Order the exporter after the app-server workload without making OpenRouter collection exit when app-server is temporarily unavailable.
- [x] 3.5 Add Nix evaluation or service tests for the image pin, non-root identity, mount permissions, systemd ordering, restart behavior, Unix-only transport, and absence of published ports.
- [x] 3.6 Write the restricted device-code enrollment, authentication-status, restart verification, re-enrollment, backup/restore, and rollback runbook, including the residual risk that control-socket compromise can invoke non-account RPCs or consume quota.
- [x] 3.7 Exercise enrollment, account reads, authentication failure, protocol failure, refresh, and restart logging paths; fail the pre-cutover gate if journald/Loki contains ephemeral in-memory fingerprints for access/refresh tokens, authorization headers, device codes, or sanitized complete-account markers.

## 4. Replace Direct Codex Polling in the Exporter

- [x] 4.1 Add a bounded Unix-socket JSON-RPC client that performs app-server initialization and calls `account/rateLimits/read` with retry handling for transient protocol and overload errors.
- [x] 4.2 Select `rateLimitsByLimitId.codex` when present and implement the documented fallback to the backward-compatible `rateLimits` snapshot.
- [x] 4.3 Normalize primary and secondary windows by `windowDurationMins`, including weekly, real 5-hour, null, unknown-duration, duplicate-duration collision, and malformed-window behavior without synthetic zero series.
- [x] 4.4 Replace cached reset countdowns with absolute `ai_codex_window_reset_timestamp_seconds` and emit usage, duration, presence, authentication, plan, and reached-limit metrics from the normalized snapshot.
- [x] 4.5 Emit `ai_exporter_last_success_timestamp_seconds` and `ai_exporter_poll_interval_seconds` for Codex and OpenRouter while preserving last-success timestamps across failures.
- [x] 4.6 Route production Codex collection exclusively through app-server, stop reading the legacy credential, and retain any legacy code or wiring only as an explicitly temporary rollback aid until cutover verification.
- [x] 4.7 Preserve the current OpenRouter collection and metric behavior while making Codex connection, authentication, protocol, and schema failures source-local.

## 5. Add Exporter Test Coverage

- [x] 5.1 Add sanitized JSON-RPC fixtures for weekly-only primary, 5-hour plus weekly, multi-limit map, backward-compatible snapshot, null windows, unknown plan, and unknown duration responses.
- [x] 5.2 Add a fake Unix-socket app-server covering initialization, successful reads, explicit logged-out responses, unobservable-login responses, malformed data, connection loss, timeout, and retryable overload behavior.
- [x] 5.3 Test semantic labels, absent-series behavior, duplicate-duration rejection, percentage validation, reset timestamps, plan and limit state, freshness timestamps, and retained-last-known behavior.
- [x] 5.4 Test valid Prometheus exposition and verify sensitive material and account payloads are absent from every fixture, error, log assertion, and metric label.
- [x] 5.5 Test that OpenRouter metrics remain available when every Codex failure mode is exercised.

## 6. Migrate Grafana Dashboard

- [x] 6.1 Replace the fixed 5-hour and 7-day stat panels with a freshness-gated "Weekly Remaining" panel using the approved pink, amber, and teal thresholds.
- [x] 6.2 Update the Codex trend panel to show weekly consumed usage and any actual additional semantic windows without relying on provider slot names.
- [x] 6.3 Replace cached reset-duration queries with a non-negative countdown derived from `ai_codex_window_reset_timestamp_seconds{window="weekly"} - time()`.
- [x] 6.4 Add distinct exporter target, Codex authentication, Codex scrape, Codex freshness, and weekly-window-presence indicators that display `N/A` for stale current values.
- [x] 6.5 Add dashboard validation for PromQL expressions, Mimir datasource UID, operations-services folder, units, thresholds, palette colors, and stale-data suppression.
- [x] 6.6 Verify existing OpenRouter panels and queries are unchanged by the dashboard migration, and record the new freshness metrics as inputs to a separate declarative alerting proposal.

## 7. Validate Before Cutover

- [x] 7.1 Run exporter unit/integration tests, Prometheus exposition checks, Nix formatting/evaluation checks, dashboard JSON validation, and OpenTofu formatting/validation through the repository's approved wrappers.
- [x] 7.2 Review generated service and container configuration for image pinning, rootless UID/GID mapping, setgid socket ownership, stale-socket cleanup, restricted mounts, dropped capabilities, no published ports, and non-debug logging.
- [x] 7.3 Run a sensitive-material scan across source, generated configuration, Terraform inputs, logs, fixtures, and staged files before any device-code enrollment or production deployment.
- [x] 7.4 Test either encrypted state restoration or isolated-state device-code re-enrollment before production cutover and document the expected recovery outage.
- [x] 7.5 Negatively test non-account control-socket methods against the container boundary and stop before production deployment unless no host workspace, executable, privileged operation, or undeclared writable path is reachable and the residual quota-consumption risk is explicitly accepted in the design.

## 8. Roll Out and Verify

- [x] 8.1 Deploy only the app-server runtime to Habiki with a targeted NixOS run and verify systemd/Podman health, rootless identity mapping, bounded RPC readiness, Unix socket access denial for unauthorized users, no network listener, and sanitized Loki logs.
- [x] 8.2 Complete the operator-assisted device-code enrollment and verify `account/read` plus `account/rateLimits/read` remain authenticated across a container restart without copying workstation credentials.
- [x] 8.3 Deploy the exporter to Habiki with `./scripts/play.sh --limit habiki --tags nixos` and verify `/metrics`, Alloy target health, weekly semantic series, freshness timestamps, explicit-versus-unknown authentication semantics, OpenRouter continuity, and absence of legacy fixed placeholders.
- [x] 8.4 Apply the dashboard change through `scripts/tofu.sh`, then verify weekly remaining, consumed trend, reset countdown, health indicators, and stale suppression in Grafana/Mimir.
- [x] 8.5 Exercise controlled app-server outage, explicit unauthenticated, protocol failure, restart, and available refresh/persistence paths to verify recovery, OpenRouter continuity, stale-value suppression, and Loki redaction.
- [x] 8.6 Reconfirm the tested recovery procedure and residual control-socket/quota risks in the production runbook after rollout.

## 9. Retire Legacy Path and Sign Off

- [x] 9.1 Remove the unused direct WHAM client, custom OAuth refresh manager, Codex credential argument, and legacy-only logging after the app-server cutover checks pass.
- [x] 9.2 Remove the `codex_oauth_env` age-secret mount, exporter option, secret generation, and declaration through existing Ansible Vault/age automation without exposing decrypted values.
- [x] 9.3 Re-run exporter, Nix, dashboard, OpenTofu, OpenSpec, and sensitive-material validation after legacy removal.
- [x] 9.4 Confirm no unrelated files, dangling routes, listeners, ports, secrets, or obsolete runtime dependencies remain; stage all required files and record rollback commands, changed files, validation output, and residual risks.
