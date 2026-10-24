# Operations documentation

These runbooks are the living documentation for the managed infrastructure.
Configuration remains the authority for current package versions, resource names
and runtime settings. Dated acceptance records describe what was observed then;
they are not fresh health checks or certification of untested clients.

## Identity and applications

- [Authentik](authentik.md): native passkeys/fallback, automation ownership,
  generated OIDC secrets and branding.
- [Hermes](hermes.md): proxy-only access, native scheduling, session expiry,
  GitHub CLI and managed inference providers.
- [Forgejo](forgejo.md) and [GitHub mirrors](forgejo-mirrors.md): private native
  OIDC/Git access, automatic browser entry, safe discovery and data preservation.
- [Miniflux](miniflux.md): native runtime/database, subscriptions, audit provenance,
  additive sync and accepted verification limits.
- [Immich](immich.md): native web/mobile OIDC, local recovery and private ingress.
- [FileBrowser Documents](filebrowser.md): immutable enrollment, scopes/ACLs,
  reconciliation and state-only recovery.
- [ArtCraft](artcraft.md): verified static release publication and shared
  authorization, including the distinction between operator and agent evidence.
- [Home Assistant](home-assistant.md): configuration ownership, native OIDC,
  Matter/Thread, Bluetooth discovery gaps and private environmental metrics.
- [Dependency-Track](dependency-track.md) and
  [OIDC auto-login decision](dependency-track-oidc-autologin.md).

## Network, storage and maintenance

- [Headscale](headscale.md): controller admission, DDNS and narrow HTTPS ingress.
- [Garage](garage-backup-target.md): private S3, management broker, operator
  Minecraft bucket, credential boundaries and recovery limits.
- [Shared PostgreSQL TLS](postgresql-tls.md): verified clients, certificate
  renewal and non-destructive recovery.
- [Maintenance](maintenance.md): dependency integrity/release policy, stateful
  upgrades and retained recovery assets, declarative Rust/Cargo tooling.
- [Frontier cycle recovery](frontier-indexer-cycle-recovery.md) and
  [follow-ups](frontier-indexer-follow-ups.md): release contracts, monotonic
  schema reset, ingestion concurrency and chain-head probe gap.
- [Project Zomboid operations](project-zomboid.md): private co-op profile,
  controlled maintenance, recovery and bounded reset.

## Observability

- [Grafana operations portal](grafana-operations-portal.md): declarative ownership,
  fleet/resource and house semantics, signal coverage and accepted noise.
- [Codex app-server and AI usage](codex-app-server.md): private socket/auth state,
  exporter window/freshness contracts and both dashboard presentations.
- [GitHub repository observability](github-repository-observability.md): App-only
  collection, coverage versus findings and bounded metric labels.
- [GitHub SBOM ingestion](github-sbom-ingestion.md): trusted producers,
  least-privilege Apps, upload acceptance, checkpoint/retry semantics and recovery.
- [Project Zomboid telemetry](project-zomboid-observability.md): verified native
  signals, private map/renderer, interval events and observed-player roster.
- [UniFi logging](unifi-network-logging.md): source-restricted syslog and filtering.

## Change records

Read [the documentation workflow](documentation-workflow.md) when proposing,
implementing or finalizing a change. OpenSpec artifacts are temporary planning
material; enduring contracts and unresolved operational work belong in the
relevant runbooks or tracked issues.

The former 54 archived changes and 44 capability specs were consolidated by
service rather than copied verbatim. Completed task lists, superseded designs,
handoffs, old release inventories and raw acceptance transcripts remain in Git
history. Use `git log --all -- openspec` and `git show <revision>:<old-path>`
for historical investigation; live tooling and documentation must not depend
on a deleted artifact path. The dated [security review](security-review-2026-05-19.md)
is likewise historical evidence, not the current configuration authority.
