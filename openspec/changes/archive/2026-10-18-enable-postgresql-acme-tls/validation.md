# Validation evidence (2026-10-18)

## Passed

- Isolated Python suite: **38 passed**, with the opt-in PostgreSQL test skipped in that run. Covers certificate pair validation, atomic publication, permissions, expired/malformed/untrusted/wrong-host material, real socketpair TLS verification, wrapper fixture isolation, existing Miniflux deployment/configuration/socket reconciliation and five acceptance-play safety tests. Both live acceptance playbooks passed isolated Ansible syntax checks. The reboot regression specifically checks the NixOS shutdown search path and executable preflight.
- Separately approved host Podman integration: **1 passed** using `docker.io/library/postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24`, cached image only (`--pull=never`), no external network (`--network=none`), no published ports or production credentials. Seeded a cluster with TLS off, enabled TLS on that same populated cluster using the production HBA file, verified TLS/SCRAM, rejected wrong hostname/CA and plaintext, retained socket administration and seeded data. PostgreSQL accepted a root-owned/GID-70 key with mode 0640. Post-test queries found no `pg-tls-test-*` containers or volumes remaining.
- Strict Nix assertions: `nix-instantiate --eval --strict --expr 'import ./tests/postgresql-tls-eval.nix {}'` with approved read-only `-I nixpkgs=/nix/store/77dysp5fl6b4mfnbh7h553fyiv8k5irg-nixos-26.05/nixos`. Checks populated data mount/port preservation, native TLS, private alias, preparation ordering, ExecReload (not dependency restart), preserved Caddy renewal consumer and explicit migration option.
- Existing Miniflux Nix-backed configuration tests passed with the same approved snapshot.
- Full configured `pre-commit run --all-files` passed (including redacted gitleaks, Nix formatting, YAML/JSON, Authentik regression checks and wrapper-only OpenTofu formatting). Existing Git hook is installed. No gate bypasses.
- Approved host command `openspec validate enable-postgresql-acme-tls --strict` passed.
- `git diff --check` passed.

## Isolation and exceptions

Local tests/evaluation/formatting ran through the installed Bubblewrap launcher with network and credentials isolated and only this repository writable. Already-read-only Nix store executables supplied OpenSSL, nixfmt and a PyYAML-enabled Python; no dependency downloads or installs. The launcher was separately authorized to expose the immutable user-profile ripgrep executable directory on PATH.

Explicitly approved host-side exceptions: read-only OpenSpec status/apply-instructions/strict validation; read-only SSH inventory through the existing `scetrov@habiki` alias; the disposable network-disabled Podman integration test and cleanup verification. Standard trusted-repository pre-commit ran on the host under the configured workflow. After a separate explicit maintenance approval, targeted Ansible/Vault/NixOS deployments, wrapper-only OpenTofu plans, live transport/health checks and an Ansible certificate-handoff reload ran on the host against Habiki. The operator subsequently approved one real replacement-certificate exercise and separately confirmed the recovery route and Habiki reboot. Both passed using opt-in Ansible plays with cleanup, live session continuity and boot-order checks. See `live-verification.md`, including the first reboot attempt's harmless shutdown-path lookup failure and the tested, explicitly approved correction/retry. No credentials were forwarded into Bubblewrap; no OpenTofu apply or unrelated image/package upgrade occurred.

## Live acceptance complete

- Tasks 3.3 and 3.4 passed: `live-verification.md` records real clients, protected state, plaintext/verification rejection, socket administration, actual renewed served certificate without PostgreSQL restart, surviving authenticated session, Caddy health and startup ordering across an approved reboot.
- Acceptance runtime overrides/scripts were removed and normal renewal scheduling restored. The separate Garage transport prerequisite has recorded evidence; its proposal remains untouched.
- The three requirements and nine scenarios were synced unchanged into `openspec/specs/shared-postgresql-tls/spec.md`; strict main-spec validation passed. The change and its evidence were archived under `openspec/changes/archive/2026-10-18-enable-postgresql-acme-tls/`. Final quality gates and intended staging complete task 4.1. No signed commit or PR has been requested or created.
