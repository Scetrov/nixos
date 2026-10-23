## Context

All participating Documents directories are local to Habiki. Some Unix accounts remain to be created. Habiki currently imports a Filebrowser module that installs `unstable.filebrowser` but does not deploy Quantum or implement SSO. Native Authentik OIDC patterns already exist in `terraform/miniflux.tf`; Caddy, Alloy, vault-backed secret delivery, and targeted NixOS/Ansible deployment are established infrastructure.

The agreed trust boundary is homelab application-level isolation: users must not access each other's Documents through Quantum, but a compromised shared process is not required to be isolated from its other mounts. Browser-created files may be owned by the service identity if the corresponding Unix user retains full access. The exposed content is the literal Documents tree, with no automatic exclusions for names such as `passwords`.

## Goals / Non-Goals

**Goals:**
- One shared, non-root Quantum service with native Authentik login.
- Full browse/download/create/edit/rename/move/delete operations within each enrolled user's own Documents tree.
- Explicit identity-to-Unix-account enrollment, including safe creation of missing approved accounts and directories.
- Bidirectional filesystem access between each Unix owner and the service identity without broadening access to unrelated users.
- Declarative, repeatable deployment and scope reconciliation, fail-closed onboarding, and non-destructive rollback. Automated offboarding is deferred by the operator; enrollment removal is rejected fail-closed.

**Non-Goals:**
- Per-user service instances, Unix impersonation, LDAP/SSSD, or automatic Unix-account creation for every Authentik user.
- Exposing all of `/home`, remote-machine home directories, or cross-user collaboration.
- Public/anonymous sharing, WebDAV, office integrations, or other optional access paths in the initial deployment.
- Content-based exclusions, recursively changing file ownership, or deleting personal data during offboarding.

## Decisions

### One shared runtime, narrowly mounted data

Deploy Quantum as a digest-pinned Podman container using existing NixOS OCI conventions, a dedicated host service UID/GID, private persistent application state, and a loopback-only backend behind Caddy. Run the container process as that same non-root host UID/GID with an explicit host UID mapping so ACL principals match the process's host credentials; never run the application as root. Retire the old package-only stub on Habiki rather than accidentally deploying classic Filebrowser alongside Quantum.

Bind-mount each approved `<home>/Documents` separately at a stable container path such as `/documents/alice`. Resolve the actual configured home directory instead of assuming every home is `/home/<username>`. Do not mount whole homes. Paths must be validated against configured accounts and must not be symlinks to unrelated host directories. Keep the container unprivileged, without host runtime sockets or unnecessary capabilities. Avoid Podman `:U` or other recursive ownership rewriting on user data.

Alternative: per-user processes would preserve natural ownership and reduce compromise impact, but were explicitly rejected as unnecessary homelab complexity. Running as root to bypass Unix permissions is also rejected.

### Explicit enrollment is the authority

Maintain one small declarative enrollment collection binding an explicitly selected Authentik identity to an approved Unix username. Derive the Documents path and Quantum source/scope from that record. Validate uniqueness, usernames, account existence/provisioning, and home paths before applying access changes. Only explicitly enrolled missing accounts are created; reuse existing account declarations without changing their UID, credentials, shell, or groups. New document-only accounts need no password or SSH access by default.

The initial approved Unix usernames are `scetrov`, `pinkgiraffes`, and `flyingfire`, preserving the exact lowercase spelling supplied by the operator. Enrollment records SHALL bind each Unix username to the Authentik user's immutable UUID/subject, not a mutable login name, email, or display name. Resolve the initial Authentik user records by the supplied username case-insensitively and require exactly one match for each; persist the resolved immutable IDs in the reviewed enrollment data. The application-specific OIDC claim mapping SHALL emit the exact lowercase enrolled Unix username as `preferred_username` for that immutable identity. Quantum v2.1.3-beta uses the configured claim value as the login username and performs an exact username lookup (SQLite `username = ?` with no `NOCASE` collation); thus claim casing is settled: exact lowercase output is required, and mismatches fail closed. Do not change global identity claims or let a renamed/reassigned Authentik identity inherit a previous enrollment.

Initial identity resolution through the vault-authenticated Authentik users API returned exactly one case-insensitive exact username match per supplied name:

| Unix username / required `preferred_username` | Immutable Authentik user UUID |
| --- | --- |
| `scetrov` | `c719e38e-de05-413d-a3fd-5f0c346c4981` |
| `pinkgiraffes` | `b6d44f49-e8fe-4452-9878-e10cf43f79f3` |
| `flyingfire` | `d06bec1d-51e5-4d7e-bf3c-2e68f60d78d9` |

These UUIDs are enrollment identifiers, not credentials. Runtime claim emission and the disposable integration tests remain unverified.

Alternative: matching arbitrary Authentik usernames to home-directory names is smaller initially but creates accidental authorization and rename/reuse hazards.

### Native OIDC with explicit application access

Use the confirmed hostname `files.net.scetrov.live`. Create a confidential Authentik provider/application, a strict callback URI (`https://files.net.scetrov.live/api/auth/oidc/callback` for the root URL), and an explicit access group/policy via OpenTofu. Require enrollment and application authorization together. Quantum documents `userIdentifier: preferred_username` as the default and documents disabling password authentication when OIDC is the only method. Configure OIDC as the only ordinary login method; keep any bootstrap/recovery procedure restricted and separate from normal access. Quantum's OIDC `adminGroup` grants administrator rights, so do not map the ordinary application-access group to it; operator administration is a separate, explicit privilege.

OIDC credentials originate in Ansible Vault and are delivered through existing runtime secret mechanisms, not Nix-store literals or committed plaintext.

### Explicit sources and scopes, never broad defaults

Use one Quantum source per enrolled Documents mount, set `defaultEnabled: false` (the documented default, and explicitly required because `true` grants the source to all users on creation, login, and startup), and explicitly assign only that source and its full per-scope file-operation permissions to its mapped user. Set each source `private: true` to prevent sharing, and disable WebDAV with `server.disableWebDAV: true`; set new-user global `admin`, `api`, and `share` permissions to false. The v2 user-management documentation describes per-source `view`, `download`, `modify`, `create`, and `delete` permissions and API-managed scope records. In v2.1.3-beta, OIDC creates a Quantum account after Authentik authorization; `createUser` is deprecated and cannot disable this behavior. Therefore Authentik application authorization SHALL admit only explicitly enrolled identities, while Quantum account defaults and all sources remain unprivileged/unassigned until reconciliation; the newly created account cannot access Documents before its explicit scope is applied. Do not rely on deprecated `createUserDir` behavior to create or authorize host Documents trees.

Application state must be automated, not created through manual UI steps. OpenTofu owns Authentik resources; all OpenTofu operations use `scripts/tofu.sh`. Reconcile Quantum account/scope state through its documented API or CLI with an idempotent integration after validating the pinned release's exact API contract. Do not embed API credentials into configuration, process arguments, logs, or state unnecessarily. The documentation establishes configuration and API concepts but does not define this repository's reconciliation lifecycle or prove session invalidation; cover both in implementation tests.

Reconciliation must repair scope drift and remove obsolete source grants. Automated offboarding is deferred by the operator for this initial family rollout: reject removal/reassignment of an existing enrollment and keep the public route unavailable. Do not silently drop a mount while assuming an OIDC logout revoked Quantum sessions. The pinned beta's account deletion/token rejection was verified with an existing synthetic bearer token, but the documented admin API cannot retrieve or mint another user's session for an independent per-offboarding probe. No user-session collection or direct database mutation will be added for this deferred workflow.

For non-interactive scope reconciliation, use a separate Authentik service account and client-credentials provider. Its application-specific scope mapping emits private machine username/group claims only for that service UUID. Quantum's RS256 external-JWT method verifies Authentik's public signing certificate and allows only that private machine role; ordinary OIDC grants no administrator role. Machine tokens expire after two minutes. Caddy must strip the machine assertion header on every public request. Credentials pass through encrypted generated secrets, agenix and systemd credentials. The provider's numeric user PKs are only directory locators: OpenTofu verifies each lookup's immutable UUID before adding group membership.

### Managed access and default ACLs

Use NixOS/Ansible-managed named POSIX ACL entries for the dedicated service UID and the enrolled Unix owner. Apply service `rwX` access to existing entries and default `rwX` entries for both principals to existing directories so new content inherits bidirectional access; do not change file ownership. Traverse only enrolled Documents trees and do not follow symlinks. Bind mounts must not require service access to parent homes.

ACL masks constrain all named-user and group entries. When widening a mask to enable the managed entries, preserve every unrelated entry's prior effective permissions by constraining its ACL entry to the prior effective permission set; preserve/restore the original ACL snapshot for rollback. Apply changes idempotently and report failures rather than broadening unrelated access. A locally imposed restrictive chmod/ACL can deliberately remove effective service access and must yield a clear permission error, never privilege escalation. Acceptance tests use disposable trees and distinct owner/service UIDs, covering pre-existing restrictive modes, existing ACL entries, uploads, nested directories, replacements, and unchanged unrelated effective permissions. No live personal tree is used for initial validation; deployment remains blocked until the same tests pass with Habiki's Podman UID mapping.

### Existing observability and recovery patterns

Collect service and reconciliation logs through journald/Alloy into Loki without tokens, credentials, or file contents. Add a basic service-health signal and Grafana alert using existing provisioning; do not create a bespoke dashboard for this small service. Document backup/restore for Quantum state and preserve existing Documents backup/sync arrangements without pretending Syncthing alone is a backup.

## Risks / Trade-offs

- [Shared process can access all enrolled mounts] → Accepted homelab trade-off; non-root runtime, Documents-only mounts, explicit scopes, and no public shares limit exposure.
- [Uploads have service ownership] → Accepted; verify effective Unix-user access using ACLs, including nested directories and replacements.
- [Auto-provisioned SSO users inherit broad sources] → Disable automatic grants and test first login, restart, and reconciliation before real data is exposed.
- [Scope/API semantics differ between Quantum releases] → Validate the exact eligible pinned release; documentation contains mixed deprecated and current directory-creation settings. Avoid relying on username-directory templates.
- [Identity renames or stale sessions retain access] → Explicit mapping, reassignment checks, session revocation, and offboarding tests.
- [Symlinks or API paths bypass scopes] → Test cross-user reads/writes, traversal, symlink escape, direct downloads, search, and preview paths. Indexing not following symlinks is not sufficient evidence of request-time confinement.
- [Recursive ACL initialization is expensive or invasive] → Touch only enrolled trees and managed grants, preserve unrelated ACL entries, avoid symlink traversal, and verify idempotence and rollback on representative data.
- [Files inside Documents are sensitive] → Expose the requested literal tree, but restrict access to its owner; do not silently implement exclusions.

## Migration Plan

1. Confirm the hostname and initial explicit enrollment (begin with the existing `scetrov` account unless the operator supplies additional mappings). Verify the latest applicable released Quantum version, publication age/security exceptions, digest, API contract, and runtime UID behavior.
2. Reproduce OIDC/scoping and ACL behavior with two synthetic users and non-sensitive local fixtures. Do not test access-control boundaries against personal files first.
3. Provision accounts/directories and managed ACLs; deploy the runtime initially inaccessible to ordinary users. Back up any pre-existing application state before replacement or migration.
4. Provision Authentik, Quantum accounts/scopes, and credentials through the secure automation paths; enable the Caddy route only after authorization and filesystem tests pass. Use targeted Habiki deployment and component tags.
5. Verify full browser operations, local-owner access, cross-user denial, restart persistence, enrollment/offboarding, and Grafana visibility. Document recovery and the accepted ownership model.

Rollback: deny application access and remove the route, stop Quantum, restore the prior service configuration/state if needed, and remove only service-managed ACL grants/mounts. Preserve Unix accounts, Documents data, unrelated permissions, and browser-created file access for their Unix owners. Never roll back personal Documents contents as a side effect of application-state recovery.

## Implementation acceptance criteria

These are settled implementation contracts, not product decisions. The initial host is x86_64. The operator approved the v2.1.3-beta release-track/digest update on 2026-10-23 after the security review below. Pin the runtime to `ghcr.io/gtsteffaniak/filebrowser@sha256:989e2dc6c491bda3c8bb82b27cd7798924ff3025cabdcad2444eb42f774836f6`, revision `b0f6d53f49a87eae32e2022819fa116da13349a7`; do not substitute a moving tag. Its under-seven-day age is accepted specifically for the CVSS 8.8 security fix. Recheck the policy before deployment and change the digest only through a reviewed update.

Implement and test: exact lowercase claim-to-Quantum usernames; immutable Authentik identity binding; application authorization limited to enrollment; explicit per-source scopes; automatic Quantum account creation with zero privilege before scope reconciliation; fail-closed rejection of unsupported enrollment removal; and bidirectional ACL behavior using disposable data and Habiki's actual UID mapping. Local ACL testing in the current agent environment is unavailable because the agent lacks permission to switch to a second UID (`setpriv` fails with `Operation not permitted`); this is not a design ambiguity. Keep deployment blocked until the prescribed disposable-UID test passes.

The previously reviewed v2.0.1-stable source confirms the exact username database lookup in [`sqldb/users.go`](https://github.com/gtsteffaniak/filebrowser/blob/v2.0.1-stable/backend/internal/database/sqldb/users.go), OIDC account creation after authorization in [`web/oidc.go`](https://github.com/gtsteffaniak/filebrowser/blob/v2.0.1-stable/backend/internal/web/oidc.go), and per-user token removal when deleting an account in [`state/users.go`](https://github.com/gtsteffaniak/filebrowser/blob/v2.0.1-stable/backend/internal/state/users.go). The source tag is `v2.0.1-stable` at commit `aa4dd3ae95ea8f54959e3df8187b4c02247601cb`.

## Implementation security gate

Release/advisory recheck on 2026-10-23 found a blocker for the reviewed v2.0.1-stable pin. The stable release was published 2026-10-13 (older than seven days), but upstream now lists it in affected ranges for scope-containment vulnerabilities:

- [GHSA-g2q5-r6ch-v25f](https://github.com/gtsteffaniak/filebrowser/security/advisories/GHSA-g2q5-r6ch-v25f): authenticated preview can read outside scope through a symlink; the advisory explicitly describes the incomplete v2.0.1 fix.
- [GHSA-qqf3-2wvq-q4w9](https://github.com/gtsteffaniak/filebrowser/security/advisories/GHSA-qqf3-2wvq-q4w9): archive downloads can follow symlinks outside scope.
- [GHSA-3j46-5w28-f8p2](https://github.com/gtsteffaniak/filebrowser/security/advisories/GHSA-3j46-5w28-f8p2): CVSS 8.8 archive/WebDAV symlink-relocation write escape. Disabling WebDAV mitigates this particular chain, not the preview/archive read issues above.

The advisories name v2.1.0-stable and v2.1.3-beta as patched versions on their respective tracks. The latest ten published releases returned by the upstream releases API include v2.1.3-beta (published 2026-10-20), but no v2.1.0-stable release. Do not assume that a named patched stable release or image is available. A candidate security update requires release/image availability checks, a reviewed digest and artifact update, and disposable regression tests before personal data is mounted. The CVSS 8.8 fix qualifies for the repository's seven-day-deferral exception; this does not independently approve changing release tracks.

The operator authorized evaluation and subsequently approved the v2.1.3-beta release-contract update. Registry evaluation on 2026-10-23 verified:

- Published version: `v2.1.3-beta`, released 2026-10-20; selected by its versioned registry tag `2.1.3-beta`, not a moving `beta` tag.
- Candidate Linux amd64 image: `ghcr.io/gtsteffaniak/filebrowser@sha256:989e2dc6c491bda3c8bb82b27cd7798924ff3025cabdcad2444eb42f774836f6`.
- Multi-platform index: `sha256:c91fbf4b442ba14f5d45f8687b74cf71477e36a1a8118b5d0643522dcf78f73c`.
- Image config: `sha256:049cc8a4fd81ef45d92da69115ac2f5372bba23089807d24dc1066fd6ad241c6`; image declares user `filebrowser`, entrypoint `./filebrowser`.
- OCI version/revision labels: `v2.1.3-beta` / `b0f6d53f49a87eae32e2022819fa116da13349a7`. Manifest bytes were SHA256-verified against the reported platform digest; this is integrity verification, not publisher-signature verification.
- The release notes list all three advisories above as fixed. Source at the image revision adds scoped symlink checks to archive walks, and retains claim-selected OIDC usernames with automatic account creation. This is static evidence only, not runtime isolation or token-revocation verification.

**Approved contract update:** replace the v2.0.1-stable version/digest requirement in proposal/spec/design with the verified amd64 image above and revalidate all release-specific API/identity/token assertions against its source and disposable runtime. Its under-seven-day age is accepted specifically as a CVSS 8.8 security-fix exception, not a general beta/update-policy exemption.

The release-contract approval unblocks disposable integration testing, not personal-data deployment. Disposable synthetic integration tests have passed on Habiki; no personal-data service deployment has been performed. Strict host-key-checked Habiki SSH and noninteractive sudo were verified available; local host UID switching remains unavailable.

## References

- [OIDC authentication](https://filebrowserquantum.com/en/docs/configuration/authentication/oidc/) — `userIdentifier`, callback URL, proxy headers, password-method disablement, and OIDC admin/group controls.
- [Sources](https://filebrowserquantum.com/en/docs/configuration/sources/) — `defaultEnabled`, `private`, scope, and the deprecated directory-creation setting.
- [User management](https://filebrowserquantum.com/en/docs/configuration/users/) — OIDC account creation, per-source permissions, scopes, and user API shape.
- [Docker deployment](https://filebrowserquantum.com/en/docs/getting-started/docker/) — image/runtime UID and health check.
- [WebDAV](https://filebrowserquantum.com/en/docs/features/webdav/) — `server.disableWebDAV`.
- [Stable releases](https://github.com/gtsteffaniak/filebrowser/releases) — release track and exact image pin must be rechecked before deployment.
