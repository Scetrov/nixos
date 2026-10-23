# Private Documents service (Habiki)

Status: implementation and disposable-fixture validation; live rollout acceptance must be recorded separately. No personal-data deployment is implied by the fixture results.

## Boundary

- URL: `https://files.net.scetrov.live`; native Authentik OIDC only for ordinary users.
- One non-root Quantum process, host UID/GID **61990**, Podman `--userns=host`, pinned amd64 image `ghcr.io/gtsteffaniak/filebrowser@sha256:989e2dc6c491bda3c8bb82b27cd7798924ff3025cabdcad2444eb42f774836f6` (`v2.1.3-beta`). The operator approved the release-track change and CVSS 8.8 security-update deferral exception on 2026-10-23. Recheck advisories before deploying/updating.
- Backend is published only at `127.0.0.1:8092`. Each user's actual NSS-configured `<home>/Documents` is separately mounted under `/documents/<username>`. Entire homes, runtime sockets and unrelated filesystems are not mounted.
- `/run/filebrowser/mounts` contains root-controlled mount-slot symlinks to the validated literal paths. Personal homes/Documents and their ancestors may not be symlinks. The real container UID mapping and mount-slot behavior are covered by the Habiki fixture.
- Sources are private, `defaultEnabled: false`, with no name-based exclusions. WebDAV, ordinary password login/signup and sharing are disabled. Caddy denies `/dav*`, `/public/share*` and `/public/api*`; **do not block `/public/static`**, which contains normal UI assets.
- Application isolation is not process isolation: a compromised shared process could access all enrolled mounts. This is the explicitly accepted homelab boundary.

## Enrollment and claims

Edit `src/filebrowser-enrollments.json`. Each entry contains:

- `identity_uuid`: immutable identity authority;
- `authentik_pk`: directory lookup locator only; OpenTofu rejects a lookup whose returned UUID differs;
- `unix_username`: exact lowercase Unix/Quantum username and emitted `preferred_username`.

Initial identities are `scetrov`, `pinkgiraffes` and `flyingfire`; confirmed UUIDs are recorded in the OpenSpec design. Resolve a new Authentik identity through the authenticated directory API, requiring exactly one case-insensitive exact username match before recording its UUID/PK. Never derive enrollment from email/display names or arbitrary SSO claims.

Existing Unix accounts retain their UID, shell, credentials and groups. Missing explicitly enrolled accounts are created with a locked password and `nologin`, without SSH keys or extra groups. Documents roots must belong to their Unix account. Unsafe paths, UID aliases, identity reassignment, nested filesystems, special files and hard-linked regular files fail closed and require review; symlinks inside Documents are not traversed by ACL automation.

**Automated offboarding is deferred**, per operator decision for this family rollout. Removing or reassigning an enrollment is rejected and leaves public readiness closed. Do not bypass this guard, delete personal data, or assume Authentik logout invalidates a Quantum session. A future offboarding procedure must explicitly address both authorization and sessions.

## Ownership and ACLs

Browser-created files may remain owned by UID 61990. Named access/default ACLs give that user and the corresponding Unix user effective `rwX`; Quantum creates files with mode `0660` and directories with mode `0770` so inherited named-user ACL masks retain write access. Normal local applications creating files with mode `0666` and directories with `0777` inherit the managed defaults. Applications deliberately creating `0600` content or applying restrictive chmod/ACLs can make it inaccessible to the service: expect a permission error, not runtime privilege escalation. An explicit administrator ACL preparation reapplies the declared grants.

Before widening a mask, automation clamps unrelated mask-governed entries to their previous **effective** permissions. It never recursively chowns personal data. Original numeric ACLs/inode identities are stored under root-private `/var/lib/filebrowser-enrollment`; this includes private path metadata, so protect/encrypt its backups. New/replaced service-owned files retain the Unix user's ACL on rollback. Restoring an ACL with no defaults requires explicitly removing current defaults first; `setfacl --set-file` alone does not remove them.

## Authentication and reconciliation

`terraform/filebrowser.tf` owns the ordinary application/provider, strict callback, application-access group, UUID policy and exact lowercase claim mapping. All OpenTofu commands go through `scripts/tofu.sh`.

A separate Authentik service account/provider owns machine administration. Its client-credentials JWT lasts two minutes and emits private machine-role claims only for that service UUID. Quantum verifies RS256 against Authentik's public signing certificate. Ordinary OIDC groups never grant administration. Caddy strips `X-Filebrowser-Admin-Assertion` from public requests; do not add a second proxy route that forwards it.

OIDC credentials, machine app password and verification certificate are rendered by `scripts/render_generated_secrets.py` into encrypted `src/generated-secrets.yml`, then through agenix and systemd `LoadCredential`. Runtime configuration exists only at protected `/run/filebrowser/config.yaml`, not in the Nix store. Never pass tokens through arguments, commit plaintext outputs, or enable HTTP debug/request logging.

On every start:

1. Clear `/run/filebrowser/ready`.
2. Validate enrollment/accounts/paths and apply managed ACLs.
3. Start the pinned container with only the declared mounts and private state.
4. `filebrowser-reconcile.service` creates missing OIDC accounts, converges exact scopes/permissions and removes extra grants from unmapped non-operator accounts.
5. Publish readiness only after an API readback verifies convergence. Caddy otherwise returns 503.

API permission `api: false` disables user token administration, not the UI's ordinary file APIs. Newly OIDC-created accounts have no source until their explicit assignment exists. Reconciliation can be rerun through Ansible's `systemd_service` module; failures keep readiness closed. It does not delete accounts or implement offboarding.

## Targeted deployment and validation

```sh
./scripts/play.sh --limit habiki --tags filebrowser -- --syntax-check
# Authorized live rollout only:
./scripts/play.sh --limit habiki --tags filebrowser
```

The component tag is standalone and rejects widened targets/trailing overrides. It closes readiness, rejects unsupported removals, applies only Filebrowser Authentik resources through the secure wrapper, reloads encrypted generated credentials, renders secrets and activates NixOS. It skips channel updates, unrelated container restarts and the Frontier writer stop/start flow. NixOS still activates the complete declarative host; review the resulting system diff first.

Read-only/disposable validation:

```sh
openspec validate add-filebrowser-quantum --strict
python3 -m unittest scripts.tests.test_filebrowser_identity scripts.tests.test_filebrowser_acl scripts.tests.test_filebrowser_host scripts.tests.test_filebrowser_configuration scripts.tests.test_filebrowser_reconcile
python3 scripts/tests/validate_filebrowser_tofu.py
python3 scripts/tests/run_filebrowser_integration.py --remote habiki.net.scetrov.live
```

The integration runner requires trusted SSH, noninteractive sudo, rootful Podman, ACL tools and Python `cryptography` on Habiki, plus local Chromium/Node/Nix. It uses only disposable trees, numeric UIDs 62001–62004 (refusing allocated UIDs), synthetic OIDC and loopback listeners. Browser contexts are isolated; fixture tokens cross private stdin/SSH pipes, not arguments or operational logs. Failed fixture directories are retained under `/var/tmp/filebrowser-fixture-*` for triage, with containers/listeners stopped; inspect/remove only the identified disposable directory. Successful runs clean up.

Before declaring live acceptance, verify real Authentik login for enrolled identities, denied unauthorized login, actual owner interoperability, restart persistence and the observability signals below. Fixture browser checks do not establish production SSO acceptance.

## Observability

- Journald/Alloy label both `podman-filebrowser.service` and `filebrowser-reconcile.service` with `service="filebrowser"`, forwarded through the existing Loki pipeline.
- Runtime warning/error logging excludes API request logs; semantic activity logging (which includes filenames) is disabled. Reconciliation logs only status/update counts. Do not enable content/token logging for troubleshooting.
- Existing Blackbox Exporter probes `https://127.0.0.1/health` with Host/TLS server name `files.net.scetrov.live`, validating HTTPS, readiness and runtime health.
- Query `probe_success{job="filebrowser-edge",service="filebrowser"}` in Grafana/Mimir; expect 1. The provisioned `FilebrowserServiceUnavailable` rule (`filebrowser-unavailable`) alerts after five minutes, including missing probe data, through the existing notification policy.
- Loki: `{service="filebrowser",host="habiki"}`. Inspect service failure categories and root-private enrollment metadata locally, not raw HTTP authorization headers.

## Application-state backup and restore

Persistent application state is `/var/lib/filebrowser`; enrollment/ACL metadata is `/var/lib/filebrowser-enrollment`. These are separate from personal Documents. Keep encrypted off-host backups of both, with ownership/ACL metadata; Syncthing alone is not a backup. OpenTofu's remote PostgreSQL state and the encrypted vault follow their existing backup procedures.

The dedicated maintenance play stops Quantum before copying SQLite and state, uses root-private snapshots and fixed application-state destinations, and restarts through preparation/reconciliation only if the service was previously active. Failures leave access closed.

```sh
ansible-playbook -i src/inventory.yml src/filebrowser-state.yml --limit habiki \
  -e filebrowser_state_id=before-change-2026-10-23
ansible-playbook -i src/inventory.yml src/filebrowser-state.yml --limit habiki \
  -e filebrowser_state_action=restore -e filebrowser_state_id=before-change-2026-10-23 \
  -e filebrowser_state_restore_confirm=true
```

Snapshots are under `/var/backups/filebrowser/<id>/`; copy them to encrypted off-host storage through the existing backup automation. Restore only with a compatible image/enrollment declaration. **Never copy a snapshot over Documents, restore an entire home, or use `rsync --delete` at `/var/lib` or `/home`.** Application-state restoration does not roll back personal files. Stale application state can also restore old sessions; keep access closed until the intended enrollment/scopes have been verified again.

## Non-destructive rollback

1. In IaC, set the ordinary Filebrowser enrollment policy expression to `return False`; apply that policy/binding only through `scripts/tofu.sh`.
2. Through Ansible, stop `podman-filebrowser.service`. Its stop hook clears readiness; do not reopen the route manually.
3. Before removing the deployed tools, invoke the tested host rollback through Ansible:
   ```sh
   ansible -i src/inventory.yml habiki --become -m ansible.builtin.command \
     -a 'python3 /etc/nixos/modules/filebrowser_host.py --rollback --state-directory /var/lib/filebrowser-enrollment'
   ```
   It refuses a running runtime, validates current account/home identities, restores original ACL snapshots for unchanged inodes and removes service grants from new/replaced entries while preserving Unix-owner access. It deletes neither accounts nor Documents.
4. Set `scetrov.services.filebrowser.enable = false` in Habiki's declaration and `filebrowser_enabled: false` in inventory, then use the targeted Filebrowser deployment to remove the runtime/route. The disabled rollout does not restart the removed service. Retain protected state/backups until recovery is accepted.
5. Re-enabling requires restoring the reviewed UUID policy and going through normal preparation, reconciliation and acceptance again. Do not revive old state as a substitute for session/authorization review.
