# Shared PostgreSQL TLS compatibility inventory

Read-only inspection via `ssh scetrov@habiki` (2026-10-18); no deployment performed.

- Shared container: PostgreSQL 17 Alpine, `postgres` UID/GID **70:70**. Container UID/GID maps are identity mappings, not rootless remapping; host GID70 has no named group. Preserve the existing data mount, image digest and published port 5433.
- Active TCP clients: Authentik server and worker on the private `authentik` Podman network, and native Miniflux through the host gateway. OpenTofu's intermittent PostgreSQL state connection is defined in `scripts/tofu.sh`.
- Existing HBA: local all/all trust; local replication/all trust; IPv4/IPv6 loopback TCP trust (including replication); remaining TCP scram-sha-256. TLS currently off. Retain local socket rules; replace TCP trust with SCRAM under TLS and reject non-TLS TCP after verification. No replication client was observed.
- `miniflux-dbsetup.py` and `upgrade_databases.py` use container-local sockets (no host argument); do not migrate them to TCP. Disposable subscription integration databases are separate instances and out of scope.
- Deployed Authentik **2026.8.3**: `/authentik/lib/config.py` and `/authentik/root/install_id.py` pass `postgresql.sslmode` and `postgresql.sslrootcert` to psycopg, including startup installation-ID access. Both server and worker have `/etc/ssl/certs/ca-certificates.crt`. Configure `AUTHENTIK_POSTGRESQL__SSLMODE=verify-full` and an explicit root bundle, not `require` or `use_ssl`.
- ACME public certificate: CN `scetrov.live`, issuer Let's Encrypt YE1, SANs `scetrov.live` and `*.net.scetrov.live`; validity 2026-10-02 through 2026-12-31. Covers `habiki.net.scetrov.live` and private alias `postgres.net.scetrov.live`. The database must receive only a dedicated copy of fullchain/key, not the ACME directory.
- Host CA bundle: `/etc/ssl/certs/ca-certificates.crt`. Use this explicit public root bundle for Miniflux and OpenTofu. OpenTofu's pg backend uses `github.com/lib/pq`; `sslrootcert` is supported alongside `verify-full` (upstream backend and driver source reviewed).
- Deployed ACME units are `acme-scetrov.live.service` and `acme-order-renew-scetrov.live.service`, not an `acme-finished` target. Existing ACME `reloadServices` uses nonblocking try-reload-or-restart; append the preparation oneshot without replacing Caddy consumers.
- Host `openssl` is not on PATH; NixOS services must use the explicit `${pkgs.openssl}/bin/openssl` executable. No package/image upgrade is needed.

Sources: deployed non-secret source/configuration above; https://github.com/opentofu/opentofu/blob/main/internal/backend/remote-state/pg/backend.go ; https://github.com/lib/pq/blob/master/ssl.go ; https://www.postgresql.org/docs/17/libpq-ssl.html ; https://github.com/NixOS/nixpkgs/blob/nixos-unstable/nixos/modules/security/acme/default.nix .

This inventory alone does not establish live acceptance. Subsequent cutover/transport checks and the still-partial renewal/reboot acceptance are recorded separately in `live-verification.md`.
