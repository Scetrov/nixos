## Summary

```text
Habiki maintenance
  verified dumps + cold PG16 copies + Redis RDB
  → isolated PG17 restores → database-only activation
  → Authentik 2026.8.3 → OIDC checks → full no-op OpenTofu apply
```

Digest-pin reviewed images, upgrade the toolchain/providers, and prevent the admin blueprint from replacing OpenTofu-owned application memberships. Includes the Codex 0.162 private-socket relay required by its changed Unix transport.

### Version / integrity / deferred table

| Component | Previous → pinned target | Integrity anchor | Deferred / exception |
|---|---|---|---|
| Home Assistant | stable → 2026.10.0 | `sha256:1b64d38f38d922bf9d59336451fd6453e1d614f934456af4ee3d2a51061be3a4` | 2026.10.1, released 2026-10-10 |
| Matter Server | stable → 8.1.2 | `sha256:6827e352011e2d8c2bde771e446fcf72acc49150ef66bad978816bac1762aad3` | — |
| Authentik | 2026.5 → 2026.8.3 | `sha256:ab9b4e8cc4ab3f8d1198d2db6aeea66bafea1963b3f2843589e0d163f97d9849` | Provider remains 2026.8.0 |
| Dependency-Track API | 4.14.1 → 4.14.5 | `sha256:4d41f29ce886a7fcb94a424b3eb2bfd17497ba92d48d43896c48e87a69bcf335` | 5.2.0 major migration out of scope |
| Dependency-Track frontend | 4.14.1 → 4.14.5 | `sha256:d675efbd80facddb696c21c82e1973d0dc83ae38b3c896d1c87bf78a26a6c9eb` | Same minor line |
| PostgreSQL (three stacks) | 16-alpine → 17-alpine (live 17.11) | `sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24` | PG18 out of scope |
| OnCall Redis | 7-alpine → 8-alpine (live 8.10.2) | `sha256:3811787313eba226a2ef38658c6ccb91cd5e110edc89c37767de373120a0e5a0` | Persisted in named oncall-redis-data volume |
| OnCall | latest → v1.16.11 | `sha256:9abc7342e10022da5893867789a91112fe366b3cd064a07a32d752f9de395fe5` | — |
| Grafana MCP | latest → 2.0.2 | `sha256:78d208116ec52b09b44f0eca66892073b39aefcb64483c54d43255c8eab7e97a` | — |
| Hermes Caddy | 2-alpine → 2.11.7-alpine | `sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f` | — |
| TimescaleDB HA | pg17 → digest-anchored pg17 | `sha256:20534b8a06680956336604f3735d5811807f5244c6a364c761a70dea9c63de36` | Exact versioned tag not verifiable |
| Hermes WebUI | latest → digest-anchored latest | `sha256:5fb831ca2a9f3f0b93b84c1ebaaeedf5809d914a33bbf969e5c29a5bb75cb47c` | Versionless public tags |
| Hermes agent | latest unchanged | None; documented private/unresolvable registry exception | No invented version/digest |
| Codex | 0.145.0 → 0.162.0 | nixpkgs `1c18abadea1a7d275e35a09495fd563c25b75753`; NAR `1rna5my9cjxna9x60vr2jlxchwrd5xmkqhmvlqwykahyx7sx5qan` | 0.162.1, released 2026-10-09; deferred at review cutoff |
| Codex source / cargo | 0.162.0 | `sha256-YG/9hFOCl4cMYzjaH/3gBid4osxcrvCYQUDDzdbIygo=` / `sha256-UTu+ws1DqL375C+1jaVI9HBqDHnTuAQr7/h1rSzsEzg=` | Build assertions retained |
| Rust | 1.97.0 → 1.99.0 | overlay `f91010a5c1b6125b715eb78a84fb5dd8fb74a2b0`; `sha256-HJ4TEF3j7HmLYeEP/PtqjeiBX/6TppXB2qY53HcrWbs=` | Release 2026-10-01 |
| pre-commit-hooks | v5.0.0 → v6.0.0 | commit `3e8a8703264a2f4a69428a0aa4dcb512790b2c8c` | — |
| Grafana provider | 4.47.0 → 4.49.0 | Registry checksum/signature verification during wrapper init | 4.50.0, released 2026-10-14 |
| Random provider | ~>3.0 → exact 3.9.1 | Registry checksums during wrapper init | Operator chose exact pin; ~>3.9 would permit later 3.x minors |

Unchanged verified-current components: Frontier Indexer v0.4.0, ESPHome 2026.9.1, Authentik provider 2026.8.0 and Caddy provider 0.2.8. NixOS channel, OpenTofu and google-antigravity-cli remain out of scope. Version selection is frozen at the reviewed 2026-10-14 cutoff, not a claim about future latest releases. The operator explicitly approved a one-time five-day cooldown exception for these targets; the standing policy remains seven days.

## Evidence

- **Before:** PG16/Redis7 data; Authentik image/provider mismatch; floating images. Local pinned-container tests reproduce Codex's inaccessible socket and blueprint imports reducing multi-group users to authentik Admins only.
  **After:** all three live databases report major 17; Authentik, Dependency-Track, OnCall and AI usage exporter return HTTP 200; no failed systemd units. Codex host-side WebSocket/socket regression passes. Fixed blueprint repeatedly preserves application and unrelated groups while still bootstrapping new admins and reconciling recovery credentials.
- Operator confirmed Forgejo and Dependency-Track SSO logins work after restoring memberships and removing the stale resetting blueprint. Bearer-auth reconciliation now asserts that existing admin memberships remain unchanged.
- Targeted Habiki maintenance and final `scripts/play.sh --limit habiki --tags nixos` both finish with failed=0. No unnecessary other-host activation.
- Full OpenTofu root plan and apply through `scripts/tofu.sh`: 0 added, 0 changed, 0 destroyed. Explicit authorization redirect types and trimmed branding CSS match the upgraded server defaults without live resource edits.
- Local script suite: 40 tests, 10 opt-in skips. Pinned Authentik/PG17 importer regression: 2 passing tests. Pinned PG16→17 restore, Codex container test and Nix build/evaluation passed during maintenance. Pre-commit includes the new group-ownership guard and secret scanning.
- Sandbox exception approved by operator for the script suite: `/nix/store` read-only; no network, private home, project-only writes. Disposable project TMPDIR avoids the standard 1 GiB tmpfs conflicting with the migration fixture's free-space guard. Container integration tests use isolated internal networking and disposable fixture credentials, not live secrets.
- Loki check distinguishes existing session/syncthing/Frontier noise and local test-container logs from service regressions. Matter investigation: most advertisement errors occur during teardown, one at startup; all three subscriptions succeed. Node 3's later timeout recovers in approximately 1.5 seconds, and live read-only WebSocket `get_nodes` reports all three devices available. No speculative network change or blanket log suppression.

## Merge Danger

**Door:** Two-way with retained backups, not by blindly reverting database image pins.

**Blast Radius:** Habiki

SSO and all three database-backed stacks were stopped during the coordinated maintenance. NixOS switches are whole-host activations even when Ansible uses component tags.

### Backup retention and rollback

**Do not delete before 2026-10-21 17:51:36 UTC** (minimum seven days); no cleanup is scheduled by this change.

Root-only host directory: `/var/lib/component-upgrade/20261014T175136` (0700, root-owned), verified present after final deployment:

- `manifest.json` with original data locations and prepared status.
- `previous-system` GC root retaining the pre-maintenance generation.
- `dump.rdb`.
- `oncall-postgres/dump.sql` and `oncall-postgres/cold-pg16/`.
- `dtrack-db/dump.sql` and `dtrack-db/cold-pg16/`.
- `authentik-postgresql/dump.sql` and `authentik-postgresql/cold-pg16/`, including the terraform_state database and roles.
- Every original PG16 directory remains alongside its active directory as `*.pg16-before-upgrade`, with exact paths in the manifest.

Explicit rollback (restores prior generation, retained PG16 originals and Redis snapshot; retains failed PG17 data):

```sh
scripts/play.sh --limit habiki --tags database-upgrade -- \
  -e upgrade_confirm=true -e upgrade_action=rollback \
  -e upgrade_backup_dir=/var/lib/component-upgrade/20261014T175136
```

Do not rerun `migrate`: live data is already PG17. A normal Habiki rebuild refuses restored pre-PG17 data. Database rollback also restores old application state; reconcile any subsequent declarative identity changes deliberately.
