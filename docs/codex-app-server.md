# Codex app-server operations

This runbook covers the Habiki-only Codex app-server used by the AI usage exporter. The service has no Caddy route, Authentik application, published port, or LAN listener. Its full JSON-RPC control surface is available only through `/run/codex-app-server/control.sock`.

## Safety boundaries

- Use the dedicated Habiki ChatGPT account. Never copy a workstation `auth.json`.
- Never paste device codes, account responses, access tokens, refresh tokens, or authorization headers into chat, tickets, shell history, logs, metrics, or repository files.
- Run all Podman commands as the `codex-app-server` host identity with its declared `HOME` and `XDG_RUNTIME_DIR`.
- Do not add interactive users to `ai-usage-exporter` or `codex-app-server` groups.
- Do not mount workspaces, host executables, Docker/Podman sockets, or additional writable paths into the container.
- Socket access grants the complete upstream app-server RPC surface. The container boundary prevents host access, but an authorized-socket compromise may still invoke non-account methods or consume quota.

## Deploy the unauthenticated runtime

Use the targeted NixOS workflow from the repository root:

```bash
./scripts/play.sh --limit habiki --tags nixos
```

Before enrollment, verify the unit, image, local socket, identity, and absence of published ports:

```bash
ssh habiki 'systemctl status podman-codex-app-server-runtime.service --no-pager'
ssh habiki 'sudo -u codex-app-server env HOME=/var/lib/codex-app-server-podman XDG_RUNTIME_DIR=/run/user/979 podman inspect codex-app-server-runtime --format "user={{.Config.User}} readonly={{.HostConfig.ReadonlyRootfs}} ports={{json .HostConfig.PortBindings}}"'
ssh habiki 'stat -c "%U:%G %a %n" /var/lib/codex-app-server /run/codex-app-server /run/codex-app-server/control.sock'
ssh habiki 'sudo -u codex-app-server env HOME=/var/lib/codex-app-server-podman XDG_RUNTIME_DIR=/run/user/979 podman port codex-app-server-runtime'
```

Expected results are image user `10001:10001`, a read-only root filesystem, no port bindings or `podman port` output, state mode `0700`, runtime mode `2770`, and socket mode `0660` owned by `codex-app-server:ai-usage-exporter`.

## Initial device-code enrollment

Enrollment is the only non-declarative identity step. Stop app-server so a second Codex process cannot race the managed credential writer:

```bash
ssh -t habiki 'sudo codex-app-server-enroll'
```

The declaratively installed helper stops the managed service, runs the pinned image as the dedicated rootless identity with only the protected state mount, and restarts the service only after login succeeds.

Complete consent in the operator's browser using the dedicated account. Keep the device code only in that terminal. Then restart and verify bounded protocol readiness:

```bash
ssh habiki 'sudo systemctl start podman-codex-app-server-runtime.service && systemctl is-active podman-codex-app-server-runtime.service'
ssh habiki 'journalctl -u podman-codex-app-server-runtime.service --since=-5m --priority=warning --no-pager'
```

After the exporter migration is active, require all of the following before cutover:

```text
ai_codex_authenticated 1
ai_exporter_scrape_success{source="codex"} 1
ai_exporter_last_success_timestamp_seconds{source="codex"} <recent timestamp>
ai_codex_window_present{window="weekly"} 1
```

Do not print or retain the complete `account/read` or `account/rateLimits/read` response.

## Restart and refresh persistence

1. Confirm Codex authentication and a successful fresh rate-limit read through exporter metrics.
2. Restart only the app-server unit:

   ```bash
   ssh habiki 'sudo systemctl restart podman-codex-app-server-runtime.service'
   ```

3. Confirm the unit passes its 10-second Unix-WebSocket `initialize` plus `account/read` check.
4. Confirm authentication and rate-limit collection recover without a new login and that the last-success timestamp advances.
5. Scan warning-level journald and Loki output using ephemeral in-memory fingerprints. Any credential, authorization header, device code, or complete account marker is a fail-closed cutover blocker.

## Authentication status and failure classification

Use metrics and service state together:

- `ai_codex_authenticated == 0`: app-server explicitly reported no authenticated ChatGPT account; re-enroll.
- Authentication metric absent or unchanged with Codex scrape failure: socket, container, timeout, or protocol state is unknown; inspect the unit and readiness path before re-enrolling.
- App-server active but Codex scrape unsuccessful: inspect sanitized app-server and exporter warnings for protocol/schema failures.
- Retained usage with an old last-success timestamp: treat as stale, not current quota.

Never infer authentication from socket existence alone.

## Re-enrollment and disaster recovery

No approved encrypted Habiki backup currently covers `/var/lib/codex-app-server`. Loss, corruption, refresh-token reuse, or provider revocation therefore requires device-code re-enrollment; the obsolete `codex_oauth_env` and workstation state are not recovery sources.

1. Stop app-server and the exporter.
2. Move invalid state to a mode-0700 root-owned quarantine path for bounded rollback; do not inspect or copy credential contents.
3. Recreate `/var/lib/codex-app-server` as `0700 codex-app-server:codex-app-server` through the declared tmpfiles configuration.
4. Repeat the initial device-code enrollment procedure.
5. Start app-server, verify account/rate-limit reads, restart persistence, warning-level log redaction, and then start the exporter.
6. Remove quarantined invalid state after sign-off. Do not commit, archive, or move it to an unapproved backup.

Expected outage: Codex quota metrics remain unavailable from state loss until an authorized operator completes provider consent and the authentication, restart, metric, and redaction checks pass. OpenRouter collection must remain available throughout.

If a future declarative encrypted backup is approved, this runbook may name it only after a restore into isolated protected state succeeds and `account/read` reports authenticated without exposing credentials.

## Alerting follow-up inputs

This change adds dashboard health only; it does not create Grafana contact points, notification policies, or alert rules. A separate declarative alerting proposal can use:

- `up{job="ai-usage"}` for exporter target health.
- `ai_exporter_scrape_success{source="codex"}` for source collection failure.
- `ai_codex_authenticated` for explicit authentication loss.
- `time() - ai_exporter_last_success_timestamp_seconds{source="codex"} > 2 * ai_exporter_poll_interval_seconds{source="codex"}` for stale data.
- Absence of `ai_codex_window_present{window="weekly"}` during an otherwise fresh authenticated scrape for provider schema drift.
- Fresh `ai_codex_limit_reached == 1` for quota exhaustion.

Notification ownership, routing, inhibition, and recovery behavior remain intentionally out of scope until that follow-up is reviewed.

## Rollback

- Stop the app-server and exporter before changing generations.
- Restore the previous NixOS generation using the repository's targeted deployment/rollback procedure.
- Restore the previous dashboard revision only through `scripts/tofu.sh`; never run OpenTofu directly.
- Retain protected app-server state during rollback unless it is known compromised. The old direct OAuth path is already expired, so rollback restores architecture, not guaranteed Codex availability.
- Verify no app-server TCP listener, Caddy route, Authentik application, firewall port, or orphaned container remains.

## Rollout sign-off

The post-rollout recovery check stopped and restarted the app-server, completed device-code enrollment, and confirmed both the app-server and exporter active with authenticated Codex weekly metrics and successful Codex/OpenRouter scrapes. Exporter unit/integration tests, dashboard tests, Nix evaluation, OpenTofu formatting, OpenSpec validation, whitespace checks, and a staged Gitleaks scan passed.

Rollback is the targeted NixOS rollback above followed, if needed, by restoring the dashboard only with `scripts/tofu.sh`; retain the protected app-server state. The expected recovery outage lasts until authorized device-code consent and the documented readiness checks complete. Socket access retains the residual upstream full-RPC/quota-consumption risk, but the container has no host workspace or executable mounts, no published ports, dropped capabilities, and a read-only root filesystem.

Record the NixOS generation, dashboard revision, changed files, validation output, expected outage, and the residual full-control-socket/quota risk in the change sign-off.
