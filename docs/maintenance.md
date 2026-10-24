# Dependency and host maintenance

## Release selection and integrity

Configuration and package expressions are the version authority. Verify the
latest applicable stable release from primary sources when proposing an update;
historical upgrade tables are not a current release inventory. Select releases
at least seven days old unless the repository's CVSS >= 7.0 rule or an explicitly
approved scoped exception applies. Record held-back release dates and the reason
for each exception in the change/PR; previous one-off exceptions do not alter
standing policy. Leave already-current unrelated components untouched.

Public OCI images need a reviewed version and SHA-256 manifest digest. A digest
is the integrity anchor when an upstream only publishes a channel tag; document
that limitation. An unresolved/private image needs a documented exception, not
an invented digest. Investigate unexpected registry digest changes before
rollout. Source archives, toolchains and actions likewise need immutable
revisions and cryptographic integrity verification.

Keep the Authentik server and provider on the same compatible release line.
Pin OpenTofu providers at least to a reviewed minor series (or exactly where
required); inspect plans for unintended changes after any provider upgrade.
Run every OpenTofu operation through `scripts/tofu.sh`, including formatting,
validation and fixtures. Verify protected state transport before writing secrets;
`sensitive = true` controls display, not encryption.

## Stateful upgrades and recovery

Major database upgrades require verified dumps and stopped/cold state copies,
a disposable restore rehearsal, a coordinated application outage, and a defined
rollback to the previous binaries **and matching data**. Never start old
PostgreSQL binaries over a newer data directory. Preserve roles, credentials
and the OpenTofu state database; verify real consumers and OIDC after activation.
NixOS component tags still activate the whole checked-out host configuration.

The 2026-10-14 Habiki maintenance upgraded three PostgreSQL stacks from 16 to
17 and OnCall Redis from 7 to 8. Recorded recovery assets are root-private under
`/var/lib/component-upgrade/20261014T175136`: `manifest.json`, a
`previous-system` GC root, `dump.rdb`, and `dump.sql`/`cold-pg16` for
`oncall-postgres`, `dtrack-db` and `authentik-postgresql`. Original PG16
directories were retained as `*.pg16-before-upgrade`; exact paths are in the
manifest. These are historical locations, not a fresh existence or restore check.
The seven-day minimum retention has elapsed, but that is **not deletion approval**.

The reviewed rollback entry point is:

```sh
./scripts/play.sh --limit habiki --tags database-upgrade -- \
  -e upgrade_confirm=true -e upgrade_action=rollback \
  -e upgrade_backup_dir=/var/lib/component-upgrade/20261014T175136
```

Obtain separate authorization and verify retained assets/manifest before use.
It restores old application/database state as well as the prior generation;
review subsequent identity changes and the current [TLS policy](postgresql-tls.md)
before activation. Retain failed upgraded state for diagnosis. Do not rerun
`migrate` against the already-migrated stacks or treat an ordinary rebuild as a
database rollback. Current recovery may require forward repair instead.

## Declarative developer tooling

The `scetrov` user module installs the repository-pinned Rust toolchain and
`cargo-audit` through Nix. The fixed-hash rust-overlay package keeps compiler,
Cargo and their runtime interpreter closure rooted in the deployed profile.
Rustup proxies or `cargo install` copies must not silently replace them.
Existing `~/.rustup` state need not be deleted.

After a toolchain change, evaluate/build before deploying to the affected host
(for example `./scripts/play.sh --limit bullit --tags nixos`), then use a fresh
login shell to check `rustc --version`, `cargo --version`,
`cargo audit --version`, and command resolution through the Nix profile. Obtain
the expected versions from the current package expression, not the superseded
Rust 1.97.0 repair spec. This infrastructure repo has no Cargo workspace;
a version/provenance check is appropriate here, not a fabricated dependency audit.

## Completion evidence

Run applicable focused regressions and `pre-commit run --all-files`, review
secret-redacted results and stage only intended files. Confirm deployed runtime,
real client paths, telemetry and a repeat/no-drift plan where applicable.
Distinguish fixture, agent-observed live and operator-reported evidence; keep
unverified recovery/failure tests explicit rather than marking them passed.
