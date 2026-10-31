# Penpot

## Scope and status

Penpot is configured for Habiki at `https://penpot.net.scetrov.live`, with native
Authentik OIDC browser login and Penpot's supported remote MCP integration.
**The configuration has not been deployed or live-accepted.** Offline evidence
below is not a claim that browser login, MCP or persistence has been tested live.

The implementation deliberately uses the official six-service topology and
existing repository automation. There is no custom authentication gateway,
custom MCP key validator, admin-console container, SMTP, bespoke dashboard or
backup service. Trust upstream's native MCP-key mechanism; verify the deployed
workflow rather than maintaining an upstream security audit.

Configuration owners:

- `src/roles/nixos/files/etc/nixos/modules/penpot.nix`: pinned images, private
  Podman bridge, resource limits, persistent state, runtime secrets, Caddy and
  readiness alert.
- `terraform/penpot.tf`: confidential OIDC provider/application, strict callback,
  existing **All Applications** group binding and generated credentials.
- `scripts/render_generated_secrets.py` and `src/roles/secrets/tasks/main.yml`:
  encrypted generated outputs and agenix delivery.
- `local-networking.nix`, `prometheus.nix`, `alloy.nix` and
  `terraform/dashboards/service-catalog.json`: existing shared infrastructure.

## Access and credentials

Browser login uses Authentik OIDC only. Password login and public registration
are disabled; OIDC registration is enabled so an authorized first-time user can
receive a Penpot account. The backend resolves the identity host through the
Podman network (private IP), so `PENPOT_SSRF_ALLOWED_HOSTS` allowlists
`identity.net.scetrov.live`; without it Penpot 2.15+ SSRF protection blocks OIDC
discovery and login fails with a generic error. Authentik restricts the
application to **All Applications**.

`disable-email-verification` is set in `PENPOT_FLAGS` because SMTP is not
configured: OIDC-registered profiles are activated immediately instead of being
held on a verification e-mail that can never be delivered. Identity (and
e-mail verification) is delegated to Authentik. If this flag is ever removed
while an inactive profile exists, re-registration fails with
`email-already-exists`; activate the row in the `profile` table instead. The callback is
`https://penpot.net.scetrov.live/api/auth/oidc/callback`, using the issuer
`https://identity.net.scetrov.live/application/o/penpot/`. There is no SMTP, so
email invitations/password recovery are not an operational access path.

MCP clients must not pass through interactive Authentik forward-auth. Sign in to
Penpot, open **Account → Integrations → MCP Server**, enable the integration and
generate an **MCP key**. Store the one-time value securely in the client's secret
configuration, never in Git, a shell command/history, screenshots or diagnostics.
The supported endpoint is:

```text
https://penpot.net.scetrov.live/mcp/stream?userToken=<MCP_KEY>
```

Open the MCP plugin in the design to be inspected. Operations act on the focused
page in the active MCP tab; use a read-only inspection for acceptance. Remote
MCP also supports editing, so the key grants more than read-only access. The
pinned official MCP image starts in multi-user/remote mode without local
filesystem tools. Do not override its command into single-user/local mode.
See `GLOSSARY.md` for the canonical vocabulary.

To rotate a key, regenerate it through Penpot, replace it in each MCP client's
protected configuration and reconnect the plugin/client. Treat a leaked URL as
a leaked credential. Verify that the old key cannot inspect designs; do not
assume how an already-open upstream session behaves without checking it.

**Accepted risk:** the operator accepts the native key-in-HTTPS-URL mechanism.
TLS protects transit, not browser history, client configuration, screenshots or
accidental sharing. No additional authentication service is introduced.

The frontend's release-pinned Nginx template is used unchanged except that
access logs and request-bearing error logs are disabled. Caddy site access
logging is off, and its runtime log filter removes `userToken` from request URIs
and drops the Referer header. Other services retain journal logs. Do not enable
proxy debug/request logging or collect raw MCP client traces containing the key.
A synthetic-key check of the deployed proxy/application/Loki path remains part
of live acceptance.

## Runtime and persistent state

Containers are `penpot-frontend`, `penpot-backend`, `penpot-postgres`,
`penpot-valkey`, `penpot-exporter` and `penpot-mcp`. Valkey is the selected
release's Redis-compatible dependency, not an additional service. All use the
private `penpot` Podman network. Only frontend port `127.0.0.1:9011` is published;
Caddy is the HTTPS entry point and preserves streaming and WebSockets natively.
No database, exporter or internal MCP port is opened in the host firewall.

The backend is capped at 4 GB / 2 CPUs. Companion caps and image digests are
owned by `penpot.nix`. Images are digest-pinned; updates must preserve compatible
release versions and follow the seven-day deferral policy unless a qualifying
security update applies. The 2026-10-31 selection uses Penpot 2.18.4 because
2.18.5 is inside that window. PostgreSQL/Valkey retain the official Compose
major versions with eligible older patch images rather than mutable tags whose
current builds are also inside the window.

Persistent paths on Habiki:

- `/var/lib/penpot/postgres`: PostgreSQL data.
- `/var/lib/penpot/assets`: filesystem asset storage, writable by the backend
  and read-only in the frontend.
- `/var/lib/penpot/{postgres,backend,frontend,exporter}.env`: root-only runtime
  files generated atomically from systemd credentials; never copy them to logs.

OpenTofu generates the OIDC client credentials, database password and stable
Penpot secret key. `scripts/tofu.sh` captures sensitive outputs into the
Ansible-Vault-encrypted `src/generated-secrets.yml`; Ansible validates and
renders age secrets, and systemd loads them to prepare container environments.
There are no default/placeholder Penpot credentials. Do not regenerate the
master key or database password as an ordinary update. Changing a PostgreSQL
initialization password alone does not rotate an existing database user's
password; any such rotation needs coordinated database and consumer changes.

**Accepted risk — no backups:** the operator explicitly accepted local-only
persistence without backups. Host or storage failure can permanently destroy
all designs and assets; that loss is unrecoverable. Restart persistence is not
a backup or disaster-recovery guarantee.

## Deployment

Obtain authorization before changing live identity resources, rebuilding Habiki
or modifying DNS/ingress. No external DNS/port-forward changes are implicit in
this configuration.

1. Review the narrow identity/credential plan, then apply it when authorized.
   All OpenTofu operations must use the secure wrapper. Keep random credential
   targets on first provision: the application binding alone does not depend
   on the database password or master key.

   ```bash
   ./scripts/tofu.sh -- plan \
     -target=authentik_policy_binding.penpot_access \
     -target=random_password.penpot_db_password \
     -target=random_password.penpot_secret_key
   ./scripts/tofu.sh -- apply \
     -target=authentik_policy_binding.penpot_access \
     -target=random_password.penpot_db_password \
     -target=random_password.penpot_secret_key
   ```

   The apply refreshes encrypted generated secrets. Before this first apply,
   refreshing the expanded manifest fails because the new outputs do not yet
   exist. Do not bypass that failure with placeholders.

2. Run `./scripts/play.sh --limit habiki --tags penpot`. This reuses the
   secrets/NixOS roles without channel updates, unrelated provisioning, the
   Frontier transition or blanket Podman restarts. NixOS still evaluates and
   activates the complete declarative host: inspect any unrelated source drift
   before authorizing the switch.
3. Propagate the shared alias to the other existing Blocky server with
   `./scripts/play.sh --limit fyne --tags local-dns` when authorized. Habiki's
   rebuild already updates its local alias and reloads Blocky. Verify both DNS
   servers; their old negative caches can outlast deployment.
4. Plan/apply `grafana_dashboard.service_catalog` through `scripts/tofu.sh` when
   authorized to publish the catalog row. The NixOS readiness alert and journal
   labeling deploy with the host; no new dashboard is needed.
5. Run the live acceptance checks below and record actual observations before
   declaring the service ready or archiving the active change.

The existing ACME certificate includes `*.net.scetrov.live`. A certificate
wildcard is **not** evidence of wildcard DNS or Internet reachability. On
2026-10-31, local resolution of the new name failed (the alias was not yet
deployed), and public Cloudflare DNS-over-HTTPS returned no A, AAAA or CNAME
answer for it. Public routing therefore remains unverified; if Internet access
rather than home-network access is required, obtain approval for the required
DNS/ingress work. Do not silently create a public record or widen the firewall.

## Monitoring and diagnosis

Existing Alloy journal collection assigns `service="penpot"` to container and
preparation units. Start in Grafana Explore with:

```logql
{host="habiki", service="penpot"}
```

Podman health checks are disabled, including any supplied by the images: their
transient systemd units reported startup check failures during NixOS activation.
Systemd can restart containers that exit, but a hung container is not
necessarily restarted automatically.

The existing blackbox exporter probes HTTPS `/readyz` through Caddy and the
backend (`job="penpot-edge"`, `service="penpot"`).
`PenpotServiceUnavailable` fires after five minutes of probe failure or missing
probe data. This is basic web/backend readiness, not a separate functional MCP
or image-export alert. Use the journal and live smoke checks for those paths;
no custom metrics exporter is added.

Investigate container/preparation unit status and the readiness probe without
dumping environments or raw secret-bearing URLs. Nginx request diagnostics are
intentionally unavailable; use backend/MCP startup errors and live smoke checks.

## Verification and remaining work

Agent-observed offline checks on 2026-10-31:

- Official Docker Hub manifest digests verified for all six configured images.
- `nix-instantiate --eval --strict --json tests/penpot-eval.nix` passed: image
  integrity pins, private ports/network, resource caps, credential delivery and
  readiness wiring are asserted.
- 21 focused unittest checks passed with `CADDY_BINARY` set to the repository
  channel's Caddy binary, including runtime env permissions/validation,
  generated-secret rendering, deployment scope guards and an isolated proxy
  error whose synthetic URL key was absent from the emitted log.
- The hash-pinned Nginx-template derivation built successfully; its request-log
  destinations are disabled. This is not a container-level Nginx startup test.
- `scripts/tofu.sh -- validate`, wrapper formatting check, shell syntax and
  `scripts/play.sh --limit habiki --tags penpot -- --syntax-check` passed.
- `pre-commit run --all-files` passed all configured gates, including the
  redacting secret scanner. The active OpenSpec change passed strict validation;
  that validates planning artifacts, not live service behavior.

Reproduce the focused suite with:

```bash
python3 -m unittest scripts.tests.test_penpot scripts.tests.test_render_generated_secrets
# Set CADDY_BINARY to a trusted Caddy executable to include the isolated log test.
```

The operator explicitly deferred deployment, live acceptance and the public-DNS
scope decision to their own follow-up before the change was archived. These are
**unperformed checks**, not accepted test passes. After deployment verify:

- Both local DNS servers, intended public resolution/reachability if required,
  valid TLS and HTTPS `/readyz`.
- Authorized OIDC first login and return; a user outside All Applications is
  denied; password/public registration remain unavailable.
- Native MCP read-only inspection through the plugin; missing/invalid/old keys
  do not return design content after rotation/reconnection. No Authentik HTML
  redirect on the machine path.
- A synthetic MCP URL key is absent from Caddy, frontend, MCP/application logs
  and Loki on successful and rejected/failed connections. Never use a real key
  as the diagnostic canary.
- Saved designs/assets survive a managed restart, image export works, and a
  controlled failure is visible in systemd status, journal or probe alerts.

Do not substitute fixture results or upstream trust for these operational
observations. Record any accepted limitation explicitly rather than ticking an
unperformed check.

## Rollback

Disable `scetrov.services.penpot.enable` on Habiki and deploy through the
reviewed targeted automation. This removes its managed containers, route and
probe configuration while preserving `/var/lib/penpot`; the bridge can remain
unused. Remove catalog/access resources declaratively through OpenTofu if the
service is being retired, and revoke keys/credentials if exposure is suspected.
Do not destroy data directories, volumes or credential state without explicit
approval. There is no backup restore path.
