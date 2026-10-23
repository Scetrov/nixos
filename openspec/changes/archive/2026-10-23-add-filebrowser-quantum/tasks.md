## 1. Verify the integration contract

- [x] 1.1 Resolve each supplied initial Authentik username (`scetrov`, `pinkgiraffes`, `flyingfire`) to exactly one immutable Authentik user UUID, rejecting missing or ambiguous matches; emit the corresponding exact lowercase Unix username as `preferred_username`. Use the confirmed `files.net.scetrov.live` hostname and the reviewed amd64 image digest in `design.md`; recheck the 7-day security-update policy before deployment.
- [x] 1.2 Reproduce the shared service with two synthetic users and fixture Documents trees; verify non-root container UID mapping, exact OIDC username matching, automatic Quantum account creation with no scopes, explicit scope reconciliation, ACL inheritance and mask-preserving behavior, uploads, nested directories, overwrite-by-rename, and local-owner access to service-owned results. Resolve failures before touching personal data.

## 2. Configure Habiki and identity access

- [x] 2.1 Add the small declarative enrollment model, uniqueness/path validation, missing-account/Documents provisioning, and idempotent ACL application/removal; preserve existing accounts, unrelated permissions, ownership, and personal data.
- [x] 2.2 Replace the imported package-only stub with the pinned shared Quantum runtime, persistent private state, non-root identity, Documents-only mounts, loopback backend, private sources with `defaultEnabled: false`, WebDAV disabled, and OIDC-only ordinary login.
- [x] 2.3 Add the Authentik OIDC application/provider, strict callback, explicit access policy, and application-specific username mapping through OpenTofu; connect vault-backed runtime credentials without plaintext configuration or Nix-store secrets. Run OpenTofu only through `scripts/tofu.sh`.
- [x] 2.4 Automate Quantum user/source/scope reconciliation through the documented API/CLI and repository automation, using a minimal idempotent bridge only if necessary; grant full per-scope file permissions only to each mapped source, no default sources, and keep operator administration separate. Automated offboarding is deferred by operator decision: reject enrollment removal and keep the route closed instead of attempting an unverified session-revocation lifecycle.
- [x] 2.5 Add the Caddy HTTPS route, matching device/local-networking aliases, and targeted Ansible orchestration with a service component tag; avoid exposing the route before scope reconciliation succeeds.

## 3. Validate and operate

- [x] 3.1 Add focused regression coverage for immutable identity/username mapping and case rejection, path rejection, existing and missing Unix accounts, reconciliation idempotence/drift, no-source OIDC-created Quantum accounts, restart behavior, fail-closed rejection of enrollment removal, and non-destructive rollback.
- [x] 3.2 Test both users' full file operations and local-owner interoperability; prove cross-user/out-of-scope denial for UI/API, traversal, symlinks, search, previews, downloads, cross-source copy/move, and unauthorized identities. Verify optional public access paths remain disabled and logs contain no credentials or file contents.
- [x] 3.3 Integrate runtime/reconciliation logs and a basic service-health alert with the existing Alloy/Loki/Grafana stack; document enrollment, ownership/ACL expectations, targeted deployment, application-state backup/restore, and rollback without overwriting Documents.
- [x] 3.4 Run strict OpenSpec validation, applicable Nix/Ansible/OpenTofu checks and configured pre-commit gates; perform an authorized targeted Habiki deployment and verify SSO, filesystem isolation/interoperability, restart persistence, and observability. Do not claim deployment or browser checks that were not performed.
- [x] 3.5 After implementation and verification are complete, archive the OpenSpec change before any final signed commit/PR, stage only required secret-free files, and follow repository commit attribution and signing requirements.
