## Why

Miniflux subscriptions currently exist only in application state or operator-held OPML. Keep the homelab reading list in Git so additions are reviewable and subscriptions can be restored without reconstructing the list by hand.

## What Changes

- Add a simple JSON catalogue of the 47 distinct subscriptions identified in `feed-audit.md`, initially 39 enabled and eight unresolved sources disabled with reasons.
- Generate deterministic OPML offline for portable, authenticated manual import.
- Add a small, explicitly invoked additive sync through Miniflux's native API: create missing categories/feeds and leave existing reader state alone.
- Run sync only through an opt-in targeted Ansible operation on Habiki, using a NixOS-packaged oneshot and existing Vault/agenix/systemd credential delivery. Provide a read-only plan before applying.
- Document catalogue maintenance, token enrollment, recovery, and non-destructive disablement. Report sync failures through command results and existing journal ingestion.

No custom publisher auditor, boot/change-triggered reconciliation, retry timer, status database, private metrics, or new Grafana alerts. Miniflux owns publisher fetching and parsing. `feed-audit.md` remains point-in-time research, not a schema or a new tool to maintain.

## Capabilities

### New Capabilities

- `miniflux-subscription-management`: Git-managed subscription list, deterministic OPML export, and explicit non-destructive API sync.

### Modified Capabilities

- `miniflux-private-service`: Add catalogue-based subscription recovery and OPML fallback while preserving OIDC bootstrap and exclusions for historical application state.

## Impact

- A catalogue, small standard-library Python tool, focused tests, and `docs/miniflux.md`.
- Existing Miniflux NixOS module, optional Vault/agenix credential delivery, Alloy journal labels, and a dedicated opt-in Ansible subscription-sync tag limited to Habiki.
- Ordinary Miniflux deployment remains unchanged and does not automatically sync subscriptions. No new provider, dependency, public endpoint, database writes outside the native API, or scheduled service.
