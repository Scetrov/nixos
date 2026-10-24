## 1. Establish the runtime contract

- [x] 1.1 Inspect the pinned agent and WebUI in disposable containers with synthetic state; record supported provider schema, credential lookup/refresh and browser discovery/selection behavior. Reproduce any incompatibility before proposing a fix; do not silently upgrade images.
- [x] 1.2 Obtain the operator's exact Qwen endpoint, model ID, context/tool capabilities and optional authentication requirement; determine available subscription models through native enrollment/discovery. Record missing inputs as activation blockers rather than inventing values.

## 2. Implement managed configuration and secrets

- [x] 2.1 Add typed optional provider settings and an atomic structured configuration reconciler shared by rootful/rootless setup; preserve unrelated settings/state, remove disabled managed definitions safely, retain the existing default and synchronize the WebUI initial model.
- [x] 2.2 Extend the Hermes environment template for a non-empty optional local key and optional unused OpenRouter credentials; securely pre-create `hermes_local_qwen_api_key: ""` in encrypted Vault only if absent. Verify both runtime credential paths without logging values; do not add subscription token placeholders.
- [x] 2.3 Add synthetic tests for backwards compatibility, provider generation/disablement, repeated reconciliation, unrelated-state preservation, malformed inputs/atomic failure, ownership/permissions, optional credentials and secret-safe rendering. Run focused tests and pinned-image provider smoke checks.

## 3. Enroll, deploy and verify

- [x] 3.1 Document the verified native subscription enrollment command, managed settings, shared-credential boundary, local-endpoint networking, explicit provider switching and rollback in `docs/hermes.md`; run configured pre-commit gates and review staged files for secrets.
- [x] 3.2 Review remote drift and active work, configure the confirmed endpoint through IaC, deploy with `./scripts/play.sh --limit habiki --tags hermes-runtime`, and have the operator approve native OAuth enrollment. Preserve Authentik and current listener boundaries.
- [x] 3.3 Verify controlled model/tool interactions with each new provider in both browser and gateway runtimes, then repeat after restart and a second focused deployment. Check native scheduling health and bounded journal/Loki errors without exposing secrets; leave acceptance incomplete if required access or compatibility is blocked.
- [x] 3.4 Record acceptance/rollback evidence, confirm all requirements and gates pass, archive the completed OpenSpec change before the final implementation commit/PR, and stage only intended files.
