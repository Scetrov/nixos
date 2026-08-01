## Context

Habiki currently runs a native Python exporter that owns a copied ChatGPT OAuth credential, refreshes it with a custom request, and polls the private `https://chatgpt.com/backend-api/wham/usage` route. The deployed credential expired on 2026-07-18, and Loki shows the exporter repeatedly receiving HTTP 401 from the refresh endpoint. The implementation uses an obsolete client identifier and encoding, does not persist rotated credentials, and assumes `primary_window` always means 5 hours while `secondary_window` always means 7 days.

The current account response has one 604,800-second weekly window in the primary slot and no secondary window. Therefore authentication repair alone would restore collection but publish the weekly value under the wrong label and fabricate an unused 7-day window.

Codex app-server provides a local JSON-RPC account API, managed ChatGPT login, automatic token refresh with persistence, and duration-bearing rate-limit snapshots. The repository already manages long-running Podman workloads through NixOS and routes custom Prometheus exporters through Alloy to Mimir and Grafana.

The app-server interface is still evolving, there is no dedicated official app-server container image, and ChatGPT OAuth requires an interactive consent step. These constraints make image pinning, protocol isolation, mutable credential state, rollback, and recovery explicit parts of the design.

## Goals / Non-Goals

**Goals:**

- Restore reliable Codex usage collection without maintaining a private OAuth implementation.
- Run a pinned Codex app-server as an isolated, declaratively managed Podman workload on Habiki.
- Keep app-server communication local to Habiki over a Unix socket.
- Give the app-server a dedicated ChatGPT login and protected persistent state for rotated credentials.
- Interpret windows by provider-reported duration and correctly support a weekly-only response.
- Prevent stale cached values from appearing current in Grafana.
- Preserve the existing OpenRouter collection path and shared Prometheus endpoint.
- Provide automated protocol, parser, metric, service, and dashboard validation.

**Non-Goals:**

- Redesigning OpenRouter collection or reconciling unrelated historical OpenRouter specification drift.
- Exposing Codex app-server to the LAN or through Caddy/Authentik.
- Running general Codex conversations, shell execution, or repository work through this app-server.
- Synchronizing a workstation's Pi/Codex credential to Habiki.
- Creating a public API around ChatGPT subscription usage.
- Guaranteeing recovery from provider-side token revocation without a new interactive login.
- Introducing the repository's first declarative Grafana notification routing and alert-rule framework; health metrics and panels from this change remain suitable for a focused follow-up alerting change.

## Decisions

### 1. Run a pinned Codex app-server in a Podman container

Habiki SHALL run a repository-defined OCI image containing a pinned official Codex release. The image SHALL be addressed by an immutable version and content hash/digest, run as a non-root container user, use a read-only root filesystem where compatible, and receive only the state and runtime mounts it requires. NixOS/systemd SHALL own container lifecycle and restart behavior.

The container SHALL set `CODEX_HOME` to a persistent mounted directory under a dedicated host state path. A separate runtime mount SHALL contain the Unix control socket. The image SHALL not use a floating tag or an unofficial prebuilt image. App-server SHALL run with `LOG_FORMAT=json` and a warning-level `RUST_LOG` filter by default; debug/trace logging and protocol body logging SHALL be disabled. Pre-cutover validation SHALL fail if ephemeral in-memory fingerprints for the enrolled access token, refresh token, authorization header, device code, or sanitized account markers occur in journald/Loki output.

A native NixOS process was considered and would be simpler, but the container boundary allows Codex to be upgraded and rolled back independently from the host Python exporter while containing its comparatively broad runtime. A third-party image was rejected because provenance and release cadence would be outside repository control.

The accepted compatibility candidate is official Codex 0.145.0 from the current Nixpkgs evaluation. A 2026-07-31 spike on Habiki (`x86_64-linux`) verified `codex-cli 0.145.0`, the `app-server` command, `unix://` transport, a successful Unix WebSocket upgrade and protocol initialization, `account/read`, `account/login/start` with `type="chatgptDeviceCode"`, login cancellation, and `account/rateLimits/read`. An isolated mode-0700 `CODEX_HOME` was enrolled through operator consent, proactively refreshed through `account/read` with `refreshToken=true`, and remained authenticated with working rate-limit reads after an app-server restart. The persisted `auth.json` was mode 0600, the temporary state was logged out and removed after the spike, and an in-memory fingerprint scan found no credential or account marker in warning-level app-server output.

The sanitized live response selected `rateLimitsByLimitId.codex`, with the backward-compatible `rateLimits` field also present. The selected snapshot contained `credits`, `individualLimit`, `limitId`, `limitName`, `planType`, `primary`, `rateLimitReachedType`, `secondary`, and `spendControlReached`; the only present window was `primary` with `windowDurationMins=10080`, numeric `usedPercent`, and a reset timestamp, while no secondary window was emitted. No account identity, token, device code, percentage value, reset value, or complete response payload was recorded. Image containment and non-account RPC boundary validation remain separate pre-cutover gates.

The selected OCI build method is Nix `dockerTools.buildLayeredImage`, loaded into Podman from a Nix-store `imageFile` rather than pulled from a registry. The package input is pinned to Nixpkgs revision `9bc02893134c733dd85de46ee4fb2fac696b5529` with tarball hash `sha256-eoS3KQTO0aPWXZvIaRbRAzSSHW3l5wdMFXtT1ISfoKA=`. That snapshot packages official `openai/codex` tag `rust-v0.145.0` with source hash `sha256-/r4mBoJhHB1v5NTA4Hk565/D5B0deYJf9xJW330hyf0=` and Cargo dependency hash `sha256-t9IMRK9R+Z67ThEcgBI0HQU0E4aJHcOjKp22RFclh9U=`. These repository-recorded fixed-output hashes bind the upstream release and dependency graph; the image derivation binds the resulting Codex closure, CA certificates, entrypoint, and image configuration. The runtime image name is metadata only and SHALL NOT trigger a floating registry pull. Reproducibility validation SHALL inspect the loaded image ID and OCI manifest digest produced by the Nix derivation. The accepted local `x86_64-linux` build produced image ID `36f83b340141e20a1e126603eb746fe57c4a27a85c2bac771ef199e41269e5cf` and OCI manifest digest `sha256:165c5ffec3763da949a82807527df6937d46f75e4c36c6c65ea4ee171c64fa23`; validation SHALL fail if rebuilding the unchanged derivation produces different identity.

### 2. Use a Unix socket, not a TCP/WebSocket listener

The app-server SHALL listen on `/run/codex-app-server/control.sock`, bind-mounted to the host. Rootless Podman SHALL run under the dedicated `codex-app-server` host identity with keep-id user mapping, `--group-add keep-groups`, and retained membership in the `ai-usage-exporter` access group. `/var/lib/codex-app-server` SHALL be mode 0700 and owned by `codex-app-server:codex-app-server`; `/run/codex-app-server` SHALL be mode 2770 and owned by `codex-app-server:ai-usage-exporter`; the socket SHALL be mode 0660 under umask 0007. The state directory SHALL NOT be readable through the access group. Before starting, systemd SHALL verify the prior Podman container is absent or stopped and that no process owns the path before deleting a stale socket. A dedicated 10-second readiness helper SHALL complete the Unix WebSocket handshake, protocol initialization, and `account/read`; file existence alone is insufficient. No app-server port SHALL be published by Podman or opened in the host firewall.

Although app-server can listen on a TCP WebSocket, upstream labels that transport experimental and unsupported for production. Stdio would avoid a socket but would require the exporter to own and restart the app-server child process, weakening systemd health separation. A long-lived Unix-socket service provides local isolation and independent supervision.

Upstream does not provide method-level authorization on this control socket. Access therefore confers the full app-server RPC surface. This design accepts that limitation only because the access group contains no interactive users, the container mounts no workspace or host executable paths, runs with a read-only root filesystem and dropped capabilities, and exposes no shell tooling beyond what the account-only runtime needs. The compatibility spike SHALL verify those constraints and document the residual risk of quota-consuming RPC misuse; if they cannot be enforced, implementation SHALL introduce an allowlisting local bridge or stop for a design revision.

### 3. Let Codex own OAuth and persist rotating credentials

The service SHALL use app-server's managed ChatGPT authentication. Initial enrollment SHALL use `account/login/start` with the device-code flow through a restricted administrative procedure. It SHALL create a dedicated Habiki login session rather than copying the workstation's `auth.json`, preventing two machines from competing over one rotating refresh-token lineage.

The app-server SHALL persist refreshed credentials in its protected `CODEX_HOME`. The state directory SHALL be readable and writable only by the dedicated runtime identity and SHALL never be logged, committed, placed in Terraform state, or exposed as a metric label.

The existing static `codex_oauth_env` age secret SHALL cease to be the runtime source after migration. OAuth consent is an external identity action that cannot be fully declared; the repository SHALL declaratively provision the service and provide an idempotent enrollment/reauthentication runbook. Recovery SHALL restore protected app-server state from an approved encrypted host backup when available or repeat device-code enrollment when the state is unavailable or provider-revoked. Implementation SHALL identify and test the applicable backup mechanism before production cutover; when no approved encrypted backup exists, an isolated-state device-code re-enrollment exercise SHALL be the mandatory tested recovery path and its expected outage SHALL be documented before the exporter or dashboard is cut over.

A 2026-07-31 repository and Habiki inspection found no declared or active Restic, Borg, Kopia, Duplicity, btrbk, Syncoid, ZFS send/snapshot, or other approved encrypted backup covering `/var/lib/codex-app-server`. The accepted BCDR procedure is therefore device-code re-enrollment of the dedicated Habiki account into a newly created mode-0700 state directory, followed by authenticated `account/read`, `account/rateLimits/read`, restart-persistence, and log-redaction checks before service restoration. The expected outage lasts until an authorized operator completes provider consent and those checks pass. Recovery SHALL NOT copy workstation state or reuse `codex_oauth_env`; adding encrypted backup coverage requires a separately reviewed declarative change and a successful restore test before this procedure may claim backup recovery.

**Hard-gate disposition:** Sections 1.1-1.3 are accepted. Codex 0.145.0 passed the Habiki compatibility spike; the image will be built from the pinned official source and dependency closure with Nix; containment is defined by a non-root identity, no host workspace or executable mounts, a read-only root filesystem, dropped capabilities, Unix-only transport, and pre-cutover negative RPC validation; and recovery is explicit device-code re-enrollment because no approved encrypted backup covers the state. Section 2 may proceed. Any failure of the image containment checks, non-account RPC boundary test, re-enrollment exercise, or sensitive-log scan remains fail-closed and SHALL stop production cutover.

The 2026-07-31 deployed pre-cutover log gate passed after enrollment, explicit unauthenticated account observation, authenticated account and rate-limit reads, proactive refresh, restart persistence, an authorized malformed protocol frame, and denied access from an unauthorized local identity. A scanner loaded four live credential/account fingerprints only in memory and found zero exact fingerprints, Bearer credentials, JWTs, token values, device codes, verification prompts, or complete account payload markers across 885 relevant journald lines and 1,355 Loki lines. The enrollment helper now uses `--log-driver=none` so future device-code output remains confined to the operator terminal.

The non-account RPC boundary check intentionally invoked `fs/readDirectory` and `fs/writeFile` through the authorized control socket. Reading the container root exposed no Habiki workspace marker, `/workspace` was unavailable, and a write beneath `/etc` was rejected by the read-only root filesystem; Podman inspection simultaneously showed only the declared state and runtime mounts, no published ports, dropped capabilities, and no-new-privileges. This accepts the residual fact that a compromised authorized socket can still invoke upstream non-account methods and may consume provider quota, but it cannot thereby reach a host workspace, host executable, privileged operation, or undeclared writable host path under the tested container boundary.

Continuing custom refresh logic was rejected because matching the current JSON request would only repair today's contract while retaining responsibility for client IDs, refresh-token rotation, persistence, and error classification. Periodically copying workstation credentials was rejected because it depends on workstation availability and creates token rotation races.

### 4. Treat app-server as an adapter and keep metric normalization in the exporter

The native exporter SHALL establish the app-server JSON-RPC session, complete protocol initialization, and call `account/rateLimits/read` on each Codex polling cycle. It SHALL prefer `rateLimitsByLimitId["codex"]` when available and fall back to the backward-compatible `rateLimits` snapshot. It SHALL tolerate nullable primary and secondary windows, unknown fields, new plan values, and retryable protocol-overload responses.

Provider slots SHALL never define metric meaning. Each returned window SHALL be normalized from `windowDurationMins`, `usedPercent`, and `resetsAt`. Known durations SHALL receive stable semantic labels, including `window="weekly"` for 10,080 minutes and `window="5h"` only when a real 300-minute window is present. Unknown positive durations SHALL receive a deterministic duration-derived label rather than being discarded or mapped to a known period. Two windows that normalize to the same semantic duration SHALL be treated as an ambiguous schema error rather than overwriting or duplicating one Prometheus series.

The exporter SHALL not emit zero-valued placeholders for absent windows. It SHALL reject malformed or non-finite values, clamp valid percentages to the documented 0-100 range only when necessary, and log schema diagnostics without logging the account response or credentials.

Invoking the private WHAM endpoint directly was rejected because it would preserve the unstable authentication and schema boundary this change is intended to remove.

### 5. Migrate to semantic and freshness-aware Prometheus metrics

The existing `ai_codex_window_used_percent` name SHALL remain, but fixed always-present `5h` and `7d` label series SHALL be retired. The exporter SHALL emit only windows actually returned by Codex, including:

```text
ai_codex_window_used_percent{window="weekly"}
ai_codex_window_duration_seconds{window="weekly"}
ai_codex_window_reset_timestamp_seconds{window="weekly"}
ai_codex_window_present{window="weekly"}
ai_codex_authenticated
ai_exporter_last_success_timestamp_seconds{source="codex"}
```

`ai_codex_authenticated` SHALL be 1 after an explicit authenticated account response and 0 only after app-server explicitly reports an unauthenticated account. Socket, container, timeout, and protocol failures SHALL leave the last explicit authentication value unchanged, or omit it when no explicit state has ever been observed; scrape success and freshness metrics identify those unknown/unreachable failures separately.

An absolute reset timestamp is preferred over a cached countdown because Grafana can calculate `clamp_min(reset_timestamp - time(), 0)` continuously between source polls. `ai_codex_limit_reached`, plan information, scrape success, and scrape duration SHALL remain with app-server-derived semantics.

On a failed poll, the exporter MAY retain last-known usage samples for continuity, but it SHALL set scrape success to 0, leave the last-success timestamp unchanged, and publish authentication state independently. Dashboard and future alert consumers SHALL gate usage values on the timestamp age so retained samples cannot appear current.

Compatibility aliases for absent windows were rejected because they would recreate the misleading 0%/100%-remaining behavior. Mimir will retain historical old-label data according to normal retention, but new samples will use only current semantic labels.

### 6. Keep the 15-minute source poll and define staleness as two intervals

The NixOS module's deployed 900-second poll interval SHALL become the documented default. Alloy SHALL continue scraping the cached Prometheus endpoint at its existing interval. Codex data SHALL be considered stale when no successful source poll has completed for two configured source intervals, normally 1,800 seconds.

A 60-second provider poll was rejected because weekly quota does not need minute-level resolution and the repository already intentionally reduced polling frequency. The source poll SHALL remain configurable for testing or future provider changes.

### 7. Replace fixed-window panels and add freshness-aware health evaluation

The dashboard SHALL display weekly remaining percentage as the primary stat, weekly consumed percentage as a trend, and the weekly reset countdown derived from the absolute reset timestamp. It SHALL use the approved Heart Pumps Neon palette: teal for healthy remaining capacity, amber for approaching exhaustion, and pink for low remaining capacity or failures.

PromQL SHALL suppress quota values when the Codex last-success timestamp is older than the stale threshold or authentication is explicitly unavailable. Separate indicators SHALL distinguish exporter target health, app-server authentication, source scrape success, and stale data. Existing OpenRouter panels SHALL remain unchanged.

This change SHALL NOT introduce notification contact points, routing policies, or alert rules because the repository has no existing declarative Grafana alerting foundation. The new metrics and freshness predicates SHALL be documented as inputs to a separate alerting proposal rather than creating an unreviewed notification path in this repair.

### 8. Test protocol boundaries without real credentials

Tests SHALL use recorded, sanitized JSON-RPC fixtures and a fake local app-server transport. Coverage SHALL include weekly-only primary windows, optional 5-hour windows, null secondary windows, multi-limit maps, unknown durations, reset timestamps, authentication failures, malformed responses, retryable overloads, stale-cache behavior, and valid Prometheus exposition. No test SHALL require or print a live OAuth token.

NixOS evaluation or service-level checks SHALL verify the pinned image, non-root identity, persistent and runtime mounts, Unix-only listener, service ordering, and absence of published ports. Dashboard validation SHALL parse the JSON and assert the expected PromQL, units, thresholds, datasource, folder, and freshness gating.

## Risks / Trade-offs

- **[App-server protocol or CLI changes]** → Pin the Codex version and image digest, isolate protocol parsing, cover fixtures, and upgrade deliberately after compatibility testing and the repository's update deferral policy.
- **[No official app-server-specific image]** → Build a minimal repository-defined image from the pinned official Codex distribution and verify provenance during automation.
- **[Mutable OAuth state conflicts with pure declarative recovery]** → Isolate the state, protect it as a credential, include it in an approved encrypted backup when available, and maintain a device-code reauthentication runbook.
- **[Device-code enrollment requires an operator]** → Make enrollment a documented, bounded bootstrap step; service configuration and subsequent refresh remain automated.
- **[Unix socket permissions or stale socket prevent exporter access]** → Use keep-id rootless mapping, retained supplementary groups, a setgid runtime directory, restrictive umask, guarded stale-socket cleanup, bounded RPC readiness, and targeted access-denial tests.
- **[Control socket exposes more than account RPCs]** → Limit membership to service identities, mount no workspace or host executable paths, drop capabilities, minimize the image, test the residual surface, and require an allowlisting bridge or design revision if isolation is insufficient.
- **[App-server logs expose account or token material]** → Set structured non-debug logging, prohibit request/response body logging, and scan journald/Loki integration output during enrollment, refresh, failure, and restart tests.
- **[Provider returns no recognizable weekly window]** → Emit only actual duration-derived windows, mark weekly presence absent, keep scrape/auth health truthful, and show missing fresh weekly data without fabricating a value.
- **[Provider returns duplicate-duration windows]** → Reject the ambiguous snapshot as a schema failure so Prometheus series cannot collide or silently overwrite each other.
- **[Short dashboard gap during breaking metric migration]** → Deploy and verify app-server first, then exporter and dashboard in a coordinated targeted rollout; retain rollback artifacts and do not delete historical Mimir data.
- **[Container increases operational complexity]** → Keep a single-purpose image, no exposed network route, narrow mounts, systemd supervision, and explicit health telemetry.

## Migration Plan

1. Verify a pinned Codex release and repository-defined OCI image on the target architecture, including Unix transport, device-code login, automatic token persistence, and `account/rateLimits/read` weekly-only output.
2. Add the declarative Podman workload, dedicated identity, state/runtime directories, socket permissions, and systemd ordering without changing the active exporter source.
3. Enroll a dedicated Habiki ChatGPT session and verify credential persistence across an app-server restart. Confirm the recovery/reauthentication path and ensure no credential enters logs or Git.
4. Add the app-server JSON-RPC client, duration-based normalization, freshness metrics, and tests to the exporter while preserving the OpenRouter path.
5. Deploy to Habiki with a targeted NixOS run and verify the local socket, service logs, `/metrics`, Alloy target, and new Mimir series. Do not cut the dashboard over until weekly data is fresh.
6. Apply the Terraform dashboard update through `scripts/tofu.sh`; verify weekly usage, reset countdown, health states, stale suppression, and palette behavior.
7. Exercise restart, explicit unauthenticated, protocol failure, and the available refresh/persistence test path; verify recovery, redacted logs, OpenRouter continuity, and stale suppression.
8. Remove the direct WHAM/OAuth refresh code and obsolete runtime secret wiring only after the app-server path and recovery procedure have passed the preceding cutover checks.
9. Update operational documentation and confirm only intended files are staged with no sensitive material.

Rollback SHALL restore the previous NixOS generation and dashboard JSON. Because the old OAuth credential is already expired, rollback restores the former architecture but not necessarily working Codex collection; OpenRouter collection remains available. App-server state SHALL be retained during rollback so a corrected forward deployment does not require unnecessary reauthentication.

## Open Questions

- Which pinned official Codex release is the first version that passes the Habiki compatibility spike and repository update policy?
- Should the OCI image be built directly with Nix tooling or by the repository's existing container build workflow? The implementation task shall choose the method with reproducible dependency hashes and the least additional machinery.
- Which approved encrypted host-backup mechanism, if any, currently covers the app-server state directory? If none exists, the production runbook shall explicitly use device-code reauthentication as the disaster-recovery procedure rather than claiming recoverability from the obsolete bootstrap credential.
- Which follow-up OpenSpec change should establish declarative Grafana contact points, notification routing, and alert rules using the freshness metrics introduced here?
