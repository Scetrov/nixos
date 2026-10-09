## Scope update

Actions is deferred by operator decision. Experimental runner code/fixtures are
retained disabled, not part of deployment acceptance. Historical requirements
are in `deferred-actions.md`; prior probes in `implementation-notes.md` are not
claims of production CI readiness. No runner registration or first-login gate is
required by this change.

## 1. Verify implementation prerequisites

- [x] 1.1 Inspect configured NixOS Forgejo module APIs and available versions; verify supported release compatibility, upstream release dates/security fixes, and cryptographic integrity against repository dependency policy. (Findings: implementation-notes.md §1.1)
- [x] 1.2 Confirm the owner's existing Authentik identity with the operator and record a non-sensitive configuration input for owner-only group membership. (Confirmed `scetrov`; recorded as `forgejo_owner_username` variable — implementation-notes.md §1.2)
- [x] 1.3 Inspect Habiki listeners, capacity, existing logging/metrics collection, and actual Teleport/Headscale source addresses; choose non-conflicting loopback HTTP/metrics ports and private access rules. (Loopback 127.0.0.1:3002; private sources 10.229.0.0/16, 100.64.0.0/10, fd0b:281e:d657:3ca1::/64, fd7a:115c:a1e0::/48 — implementation-notes.md §1.3)

## 2. Provision identity and authoritative secrets

- [x] 2.1 Add the dedicated Forgejo Authentik group, confirmed owner membership, OIDC provider/application, strict callback URI, and access policy to OpenTofu; validate and review plans only through `scripts/tofu.sh`. (Compatible provider remediation passes validate/plan; shared field-level plan review and apply remain 6.3. See implementation-notes.md §2.1.)
- [x] 2.2 Add sensitive Forgejo OIDC outputs and extend protected `src/generated-secrets.yml` extraction, including safe match verification and fail-fast checks for missing, malformed, empty, placeholder, and stale inputs. (Shared renderer `scripts/render_generated_secrets.py` + outputs.)
- [x] 2.3 Extend secret rendering/agenix declarations for Forgejo service and OIDC credentials plus any required metrics material; use vault-backed inputs or generated protected state and suppress secret output. (secrets.nix + secrets role; forgejo_enabled-scoped fail-fast.)
- [x] 2.4 Add fixture-based tests for first-deploy credential generation, repeated refresh, rotation, and invalid-input rejection; verify Grafana/Dependency Track generated-secret behavior remains intact. (`scripts/tests/test_render_generated_secrets.py`, 12 tests pass.)

## 3. Configure Forgejo and private access

- [x] 3.1 Add the Forgejo repository module and enable it only on Habiki with SQLite, persistent service-owned repositories/state/keys, external root URL, and a loopback HTTP listener. (forgejo.nix + Habiki/inventory enablement; forgejo-eval.nix passes against 26.05.)
- [x] 3.2 Configure the Caddy virtual host using the existing wildcard certificate, correct proxy trust, private source restrictions, no forward-auth gate, and denial of internal metrics routes. (forgejo.nix; real Caddy fixture verifies peer denial despite spoofed headers and admitted internal-route denial.)
- [x] 3.3 Configure dedicated Git SSH on TCP 2222 with correct advertised clone URLs, persistent host keys, and private IPv4/IPv6 access restrictions; preserve administrative SSH. (Built-in server, persistent RSA-4096 key path, source-scoped iptables/ip6tables and nftables alternatives; evaluated. Live key persistence remains 6.6.)
- [x] 3.4 Add `source.net.scetrov.live` to Habiki's shared `local-networking.nix` entry and provide a targeted DNS-only deployment path for Fyne without enabling Forgejo there. (`play.sh --limit fyne --tags local-dns`; task listing confirms only alias copy/rebuild/Blocky restart.)
- [x] 3.5 Automate idempotent Forgejo OIDC authentication-source reconciliation and owner administration using supported interfaces; disable open registration, anonymous repository access, and normal local-password bypass while safely handling any bootstrap account. (Protected runtime CLI reconciliation before web startup; signed owner-group admission/admin mapping, no bootstrap account, closed local registration with OIDC auto-enrollment. Real v16.0.5 first/repeat/rotation fixtures pass; live login acceptance remains 6.4.)
- [x] 3.6 Test service restart/rebuild and disable behavior for persistent data and SSH keys, and test repeated identity reconciliation without duplicate authentication sources. (Real v16.0.5 disposable lifecycle fixture preserves account/token/repository/README and SSH key across migrate/restart, closes listeners without deleting state on stop; Nix evaluation removes disabled service/routes/rules. Live NixOS rebuild acceptance remains 6.6.)

## 4. Keep Actions deferred

- [x] 4.1 Disable Forgejo Actions and independently gate retained experimental runner code default-off; verify the service-only configuration has no runner account, units/timer, registration command, or runner egress rules on either firewall backend. (Habiki explicitly disables the runner; service-only Nix evaluation passes on iptables and nftables; experimental opt-in tests retained.)

## 5. Integrate observability

- [x] 5.1 Route Forgejo logs into existing Loki collection with stable labels and verify secret values are not emitted. (Alloy `forgejo\.service` relabel → `service=forgejo`; real-binary fixture confirms the metrics token never appears in the console log that Loki ships.)
- [x] 5.2 Add a private authenticated Forgejo Prometheus scrape where supported and Forgejo service-health signals; verify no auxiliary listener is exposed through the forge. (Token-protected `metrics.ENABLED` on the shared loopback listener via the module `secrets.metrics.TOKEN` credential; Prometheus job `forgejo` with `bearer_token_file`; real v16.0.5 fixture proves 401 bare / 200 bearer; Caddy fixture re-verifies `/metrics` denial through the virtual host. No auxiliary port.)
- [x] 5.3 Discover real Forgejo availability signals and add compact declarative Grafana health visibility and alerts using the repository palette. (Discovered against real v16.0.5: `/api/healthz` database/cache ping, `gitea_*` gauges incl. `gitea_build_info`/`repositories`/`users`/`accesses`, and scrape `up`. Added `terraform/dashboards/forgejo-service.json` (uid `svc-forgejo`, palette colors), a `grafana_dashboard` resource, a service-catalog row, and the `ForgejoServiceUnavailable` Prometheus alert rule.)

## 6. Orchestrate and validate deployment

- [x] 6.1 Add/document a targeted Habiki Forgejo deployment tag/path that sequences Authentik provisioning, generated-secret refresh/validation, runtime secret deployment, NixOS rebuild, and identity reconciliation without a second undocumented deployment; omit runner registration and its first-login gate. (`forgejo` tag on the secrets+nixos roles; `play.sh` pre-flight refreshes/validates generated OIDC outputs for it; first-deploy identity prerequisites via a reviewed `scripts/tofu.sh` apply, fail-closed on missing values; reconciliation in the unit `preStart`. Documented in docs/forgejo.md; syntax-checked.)
- [ ] 6.2 Run Nix/Ansible/script/OpenTofu configuration checks and isolated first-deploy/repeat/OIDC-rotation tests using non-sensitive fixtures; reproduce and resolve failures before live deployment.
- [ ] 6.3 Review the shared Authentik plan's blast radius via `scripts/tofu.sh`, then perform the explicitly targeted Habiki deployment and separately targeted Fyne DNS configuration rollout.
- [ ] 6.4 Query both Blocky servers and verify trusted HTTPS, owner-only OIDC, unauthorized/anonymous denial, correct clone URLs, SSH clone/push, and Git/API token access from the LAN.
- [ ] 6.5 Verify DNS, HTTPS/SSO, and SSH from Teleport and Headscale clients; verify denied sources and internal listener restrictions without silently changing VPN routes or ACLs.
- [ ] 6.6 Repeat deployment and OIDC credential reconciliation, verify persistent data/SSH identity and observability, confirm Actions/runner inactivity, and confirm existing Habiki services and administrative SSH remain healthy.

## 7. Document and finalize

- [x] 7.1 Document targeted deployment commands, owner access management, SSH URLs, OIDC credential rotation, account/session/key/token revocation, Actions being disabled/deferred, and no formal backup guarantees. (docs/forgejo.md.)
- [x] 7.2 Document automated disable/rollback, persistent-state retention, and consistent manual pre-upgrade snapshots with schema-compatible restore cautions. (docs/forgejo.md.)
- [ ] 7.3 Run applicable repository checks and configured pre-commit checks, review changes for sensitive material and dangling listeners/routes, and stage only intended files; prompt for `pre-commit install` if configured but not installed as a hook.
- [ ] 7.4 After successful implementation and validation, archive the OpenSpec change before the final signed conventional commit/PR; include model and Pi Coding Agent attribution and never disable signing on failure.
