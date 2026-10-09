# Frontier Indexer Cycle 7 transition and recovery

## Managed transition

Deploy only after the OpenSpec predeployment checks pass:

```sh
./scripts/play.sh --limit habiki --tags frontier-indexer
```

This is a targeted host run, not an application-only rebuild: the NixOS role still synchronizes and switches the host configuration, then its existing Podman restart loop restarts all active Podman services on Habiki. Review all pending Habiki configuration changes and coordinate that host-wide container downtime before deploying.

The rebuild tasks stop `podman-frontier-indexer.service` before `nixos-rebuild switch`, then start it through the new dependencies only after a successful switch. First provisioning handles an absent old unit. Startup order is readiness → authenticated database preflight → schema reset → indexer.

Reset holds an exclusive filesystem lock, refuses destructive SQL if the old container is still running, and applies DROP/CREATE in a database transaction. Only the `indexer` schema is a cleanup target. Live inventory found no separate cycle caches/dumps/exports; do not delete `timescaledb-data`, secrets, or perform global pruning. TimescaleDB manages its own internal hypertable/chunk storage when the schema is dropped.

Generation `7` is published using atomic replacement and file/directory fsync after successful SQL. Equal generations skip reset; stale, malformed, or out-of-range generations fail closed. An existing marker also prohibits disabling reset by setting the generation to null. Failure leaves startup blocked; a retry before any writer starts can repeat the reset if publication did not complete.

Existing Alloy journal selectors include the unchanged preparation, readiness, preflight, reset, and container unit names; no new unit name is introduced.

## Recover forward, never blindly roll back

Cycle 6 application data is intentionally discarded. An old NixOS generation cannot recover it, and its old reset code may erase Cycle 7 state.

If cutover fails:

1. Keep the writer stopped. Use the managed rebuild workflow to apply any corrective configuration; do not manually edit the marker or database.
2. Retain reset generation `7`, the current monotonic reset logic, and the authenticated startup ordering.
3. Repair the configuration or deploy a tested Cycle 7-compatible digest-pinned image through NixOS/Ansible.
4. Verify TimescaleDB, preflight/reset outcomes, migration success, checkpoint progress, logs, and metrics before declaring recovery complete.

Do not activate a pre-transition NixOS generation, decrement the generation, or set it to null to bypass a guard. Any subsequent destructive reindex requires a separately reviewed higher generation.

A filesystem marker is not transactional with PostgreSQL. Database and marker backups/restores must be coordinated; restoring only one can trigger a reset or incorrectly suppress one. Marker persistence is not a complete disaster-recovery guarantee.
