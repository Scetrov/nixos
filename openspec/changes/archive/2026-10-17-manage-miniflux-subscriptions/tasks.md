## 1. Catalogue and portable export

- [x] 1.1 Confirm the existing Miniflux API, remote file-copy layout, optional secret rendering, and targeted Ansible conventions; keep implementation within the existing toolchain.
- [x] 1.2 Add `config/miniflux/feeds.json` with 47 entries from `feed-audit.md`: 39 enabled, eight disabled with reasons, and explicit aliases only where needed for matching. Leave audit provenance in `feed-audit.md` and label ZDNet general news.
- [x] 1.3 Implement offline catalogue validation and deterministic category-grouped OPML export with focused tests for invalid/duplicate URLs, credentials, disabled entries, and XML escaping.

## 2. Small additive sync

- [x] 2.1 Implement credential-file authentication, operator verification, redirect refusal, and a read-only plan using the pinned release's native API.
- [x] 2.2 Implement URL/alias matching and create-only category/feed apply; preserve existing state, serialize execution, use bounded timeouts, re-read uncertain writes, and report partial failures without an automatic retry framework.
- [x] 2.3 Test read-only planning, identity/auth failures, aliases/ambiguity, repeat-run zero writes, unchanged existing/unmanaged state, and partial/uncertain create outcomes.

## 3. Explicit homelab automation

- [x] 3.1 Add optional Vault/agenix token delivery and package the tool/catalogue in the deployed NixOS tree without exposing plaintext secrets or breaking unenrolled deployments.
- [x] 3.2 Add a hardened, credential-backed apply oneshot with no boot/change triggers or timer, plus equivalent secure plan execution. Add a dedicated `miniflux-subscriptions` Ansible tag restricted to Habiki, defaulting to plan with explicit apply opt-in; leave ordinary Miniflux deployment unchanged.
- [x] 3.3 Surface actual execution results and label the oneshot journal for existing Alloy/Loki ingestion. Test explicit invocation, enable/disable, credential handling, and no writes in check/syntax/list modes; add no metrics or alerts.

## 4. Verify and document

- [x] 4.1 Exercise the pinned Miniflux API in a disposable environment: initial creation, repeat-run no-op, partial failure, representative large-feed ingestion, and OPML import. Verify replacement-token bootstrap after database loss without touching production data.
- [x] 4.2 Document catalogue edits, exact plan/apply/export commands, secure token enrollment, recovery, failure reruns, and non-destructive disablement in `docs/miniflux.md`. With operator authorization, review a live Habiki plan, apply, and verify a repeat-run no-op; record any ingestion failures honestly.
- [x] 4.3 Run focused tests, configured pre-commit gates, OpenSpec validation, and secret/diff checks. Archive only after implementation and verification are complete, before any authorized final commit/PR; stage reviewed files and retain signing/attribution.
