## Context

Habiki already runs Miniflux with Authentik OIDC, a loopback API at `http://127.0.0.1:8091`, Vault/agenix secrets, and journal collection through Alloy. An authorized first OIDC login creates the ordinary reader account. Current recovery uses operator-held OPML.

The reading list has 50 supplied entries representing 47 distinct subscriptions. `feed-audit.md` records the initial research: 39 usable candidates and eight unresolved sources. These are point-in-time observations, not proof of ingestion on Habiki.

## Goals / Non-Goals

**Goals:** keep the public reading list in Git, generate portable OPML, and explicitly add missing subscriptions through existing automation without damaging reader state.

**Non-goals:** continuous reconciliation, publisher auditing software, deletion or retagging, automatic URL migration, per-feed health monitoring, additional metrics/alerts, database backups, historical-state restoration, or unattended identity/token bootstrap.

## Decisions

### 1. Small catalogue and offline OPML

Use `config/miniflux/feeds.json`, consumed by a small Python standard-library tool. Entries contain `title`, `category`, `url`, optional `aliases`, and `enabled`; disabled entries also have a `reason`. Use the URL as identity and in diagnostics, rather than introducing separate stable IDs. Aliases are only for known alternative stored URLs, not a requirement to copy every historical audit URL into operational configuration.

Seed 47 entries from `feed-audit.md`, with 39 enabled and eight disabled. Keep stale-feed and changed-scope qualifications in the audit document; label ZDNet as general news in the catalogue. Do not require per-entry timestamps, provenance arrays, configurable fetch settings, or an audit history in JSON. Preserve the original research document unchanged.

Validate required fields/types, HTTP(S) URLs, absence of embedded credentials or secret-bearing URLs, and unique URL/alias ownership before using the catalogue. It is a reviewed public-URL list for one trusted operator, not an untrusted feed submission service. Do not add a custom DNS/SSRF firewall or XML feed parser; the existing Miniflux outbound-fetch trust boundary still applies. No network access occurs during validation, export, or Nix builds.

Export enabled entries as escaped UTF-8 OPML grouped by category, with deterministic ordering and no generated timestamps. JSON is the hand-edited authority; OPML is generated, not independently maintained. Manual authenticated import is a fallback, not a promise of idempotent API-sync semantics.

### 2. One explicit additive sync

The same tool provides a read-only `plan` and an `apply` operation against the loopback native API. Read the token from a credential file, refuse authenticated redirects, and verify `/v1/me` against the configured operator before mutation. Read categories and feeds, match by catalogue URL or explicit aliases, and create only missing enabled feeds and their categories. Never match by title alone. Multiple matches are an error for that entry.

Existing feeds, settings, categories, articles, read markers, and bookmarks are left untouched, including UI-managed feeds. Removing or disabling an entry only prevents future creation. A URL change requires keeping the previous stored URL as an alias; automatic migration is out of scope. If Miniflux stores an unexpected canonical URL, report the discrepancy for a reviewed alias edit rather than guessing.

Use finite request/service timeouts and a single-run lock shared by plan/apply execution. Do not build a retry framework: after a failed or uncertain create, re-read inventory to establish whether it succeeded; if unresolved, report it and let the operator rerun. Continue independent entries after individual failures and exit nonzero if any remain incomplete. Invalid catalogue, identity/authentication, or inventory failures stop writes. Never undo successful creations to imitate a transaction.

Miniflux handles publisher fetching, XML parsing, TLS, and body limits. Check representative feeds using the pinned Miniflux release rather than implementing a second feed client. No automatic substitutions or global TLS bypasses.

### 3. Reuse secure delivery; no automatic lifecycle

Add an optional dedicated Vault value, `miniflux_subscription_api_token`, delivered using existing agenix rendering and systemd `LoadCredential`. No token in tracked plaintext, Nix store, command arguments, or logs. Keep enrollment opt-in: absent subscription credentials must not break ordinary Miniflux deployment.

Package the tool and catalogue through the existing NixOS deployment tree. Define a hardened `miniflux-subscriptions` oneshot for apply, ordered after Miniflux but not required by the reader. It has no boot target, timer, automatic restart, or catalogue/credential restart trigger. Its only normal invocation is the explicit targeted Ansible subscription-sync operation. Plan uses the same runtime credential handling without invoking apply. No persistent reconciliation status store is needed.

Provide a dedicated `miniflux-subscriptions` tag used with `--limit habiki`, with plan as the default and apply requiring explicit opt-in. Document the exact invocation when implemented. Require that the existing Miniflux stack has already been deployed; do not duplicate identity provisioning or add OpenTofu calls. The ordinary `miniflux` tag must not run sync. Check/syntax/list modes must not mutate subscriptions. Ansible waits for the actual result and surfaces incomplete runs.

Emit short sanitized created/present/failed summaries and failure exit status. Extend existing Alloy journal labels to cover the oneshot. Existing reader availability monitoring remains unchanged. There are no subscription-specific metrics, alerts, or overdue-success concepts: a list unchanged for months is normal.

### 4. Explicit human bootstrap and simple recovery

The operator signs in via OIDC, creates a personal API token, and securely enrolls it through existing Vault tooling. Never create local-password/admin users or use SQL to create subscriptions/tokens. A fresh database invalidates old tokens even if Vault retains them.

Recovery: reprovision normally, sign in through OIDC, then either import generated OPML or enroll a replacement token and run plan/apply. Neither route restores history, bookmarks, preferences, sessions, or prior credentials. Test recovery with a disposable account/database, never a production reset.

Disablement: turn off subscription-sync configuration through automation, remove its credential consumer and optional Vault value when no longer needed, and retain all existing subscriptions and reader infrastructure.

## Verification

Use focused tests for catalogue errors, deterministic OPML, read-only planning, account/token failures, URL/alias matching, repeated apply with zero writes, unchanged existing state, and uncertain/partial failure handling. Test optional secret and explicit-invocation wiring, including no writes in Ansible check modes and no boot/timer activation. Exercise the pinned Miniflux API in a disposable environment, including a repeat run and representative podcast ingestion. Review a live plan before an authorized apply on Habiki.

## Trade-offs

- Manual sync is deliberate: less operational machinery, but Git edits require an explicit apply.
- Additive means removing a catalogue entry does not unsubscribe; destructive changes remain separate operator decisions.
- Publisher checks remain manual/Miniflux-owned; `feed-audit.md` can become stale without affecting the schema.
- Fresh-database API recovery needs a replacement token; OPML avoids that token requirement after OIDC login.

## Implementation Checks

Confirm deployed catalogue paths, the pinned release's API/canonical URL behaviour, exact Ansible tag/extra-var plumbing, and representative large-feed compatibility. Prefer existing Python/Nix dependencies. Any genuinely new dependency still requires release-policy and integrity verification. These checks do not justify expanding this into a general-purpose controller or auditing platform.
