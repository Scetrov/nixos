## Context

Habiki runs a rootful Podman Hermes agent and WebUI with shared `hermes-home` state. Their home paths differ, but both mount that volume. The setup unit currently truncates `config.yaml` to a single `model` block and writes a WebUI default-model environment file. The secret template requires OpenRouter credentials. There is no checked-in local inference endpoint/model inventory.

Current upstream provider documentation describes `openai-codex`, native OAuth persisted in `auth.json`, and named OpenAI-compatible endpoints. These docs are not proof of support in Habiki's pinned agent or independently pinned WebUI. Confirm their actual schema, environment expansion, selection behavior and credential refresh before choosing exact serialized fields. Reference: https://hermes-agent.nousresearch.com/docs/integrations/providers/.

## Goals / Non-Goals

**Goals:**
- Keep OpenRouter working while making subscription and local-Qwen providers durable and selectable.
- Separate managed non-secret configuration, optional runtime secrets and native refreshable OAuth state.
- Preserve unrelated home state across deployments and verify both execution runtimes.

**Non-Goals:**
- Install or expose an inference server, pull models, introduce automatic cross-provider fallback for primary inference, or replace Authentik.
- Change Hermes' pre-existing background auxiliary routing. The operator explicitly approved primary-inference-only isolation during acceptance: native auxiliary work may use OpenRouter, including paid models, and is disclosed in the runbook.
- Build an OAuth client, copy browser cookies, or implement a generic provider-management framework.
- Upgrade images speculatively or silently change the default provider.

## Decisions

### 1. Inspect pinned implementations before finalizing provider syntax

Use disposable containers and synthetic state to identify the supported native provider format and WebUI picker/request behavior. Prefer native named-provider configuration over patches or a new proxy. Do not assume the latest `providers` dictionary or CLI `/model` semantics exist in these images. A required image upgrade is a separately reviewed compatibility decision with digest pins, release-age/security review and paired startup/scheduling regression checks; do not upgrade merely to match current docs.

### 2. Extend the existing module with a small managed provider surface

Represent named endpoint enablement, URL, model ID and optional context length as typed non-secret options; keep existing default-model/provider/base-URL options backwards compatible. Configure Codex as a built-in provider, not an API-compatible custom URL. Keep OpenRouter as the deployment default unless the operator explicitly chooses another configured provider. Synchronize the WebUI initial model with that managed default using the pinned runtime's supported mechanism.

Implement one structured configuration merge path used by rootful and rootless setup. Parse existing YAML, replace only explicitly managed model/provider entries, retain unrelated and unmanaged entries, and write atomically with existing UID/GID ownership and restrictive permissions. Reject invalid configuration before replacement and retain the original on failure. Serialize data rather than interpolating endpoint/model strings into shell heredocs. Deployment owns the configured default; a transient UI selection need not become an IaC edit. Do not touch `auth.json`, sessions, cron state or workspace. Disabling a managed endpoint removes only its managed definition.

Alternative: `manageConfig = false` plus manual wizard edits avoids overwrite but abandons declarative ownership and reproducibility; rejected.

### 3. Prepare only meaningful vault fields

During implementation add `hermes_local_qwen_api_key: ""` to encrypted `src/secrets.yml` if absent, without replacing any existing value. Map a non-empty value to `HERMES_LOCAL_QWEN_API_KEY` in the existing environment template. Use the pinned runtime's verified environment-reference mechanism; never place the resolved key in a Nix-store config. If it lacks such support, inject the key only into a restrictive runtime-generated provider entry, keeping the declarative source non-secret. Omit empty credentials, and make `OPENROUTER_API_KEY` optional when unused while preserving it when configured.

Do not pre-create ChatGPT API-key/access-token/refresh-token placeholders: subscription authentication belongs to Hermes' refreshable native OAuth store. The local key is unnecessary for an unauthenticated local Ollama endpoint. Endpoint URL and model ID are non-secret host configuration inputs; leave local Qwen disabled until both are supplied and validated. Never ship a fake working endpoint or credential.

Vault editing/rendering uses existing secure tooling, no plaintext files or secret-bearing logs, and `no_log` for Ansible secret tasks. Preserve the existing agenix recipients and focused renderer.

### 4. Treat OAuth as a bounded operator enrollment

Provide a verified command/runbook that launches the native subscription enrollment as the Hermes runtime user in the existing agent container with the shared home. The human approves the device flow. Automation prepares and verifies the runtime but does not impersonate that approval. Verify the WebUI reads the same native credentials and refresh behavior without printing credential contents. Keep native OAuth state writable and outside recurring secret-file replacement. Document reauthentication and revocation; do not automatically export refresh tokens into Vault.

The existing shared-home deployment has shared provider credentials; this change does not introduce per-Authentik-user subscription isolation. Document that only appropriately authorized users should access it.

### 5. Preserve the network and deployment boundaries

Qwen uses an operator-confirmed OpenAI-compatible URL reachable from both containers; container `localhost` is not the host. Verify DNS, routing and model discovery without exposing inference to the Internet. Retain Authentik/Caddy, loopback-only WebUI publishing and no agent listener. Add a local DNS alias only if needed, through existing managed networking. No new public ports or identity resources are necessary.

## Risks / Trade-offs

- [Pinned runtime or WebUI lacks compatible provider switching] → Reproduce precisely and stop activation pending a reviewed solution; CLI-only success does not satisfy browser acceptance.
- [Unknown local endpoint/model or subscription eligibility] → Optional disabled configuration supports landing safely; enrollment and live acceptance remain explicitly incomplete until operator inputs/access exist.
- [YAML merge loses unrelated state or races native edits] → Test preservation and atomic failure; perform activation during an idle window and define managed-key ownership clearly.
- [Shared OAuth refresh contention] → Verify agent/WebUI coexistence using native storage/locking; do not add a second token copier.
- [Local model lacks tool calling or adequate context] → Check real model capabilities and server context; a successful `/models` response alone is insufficient.
- [Provider errors leak credentials] → Assert redacted failure paths and retain existing journal/Loki collection; inspect bounded relevant logs without dumping environment or auth files.
- [Background auxiliary routing differs from the selected primary provider] → Preserve the existing native policy with explicit operator approval and a billing/privacy disclosure. A paid-lane warning is emitted before client use and does not itself prove a billed request. Acceptance establishes primary model/tool routing, not whole-runtime inference isolation.

## Migration Plan

1. Inspect pinned images offline/disposably, implement configuration and synthetic tests, then prepare the optional encrypted vault field.
2. Obtain the local server's exact URL/model and optional key from the operator before enabling Qwen. Retain OpenRouter's current default.
3. Run configuration/environment tests and repository pre-commit gates. Review remote NixOS drift and active chat/job state before a targeted rollout.
4. Deploy using `./scripts/play.sh --limit habiki --tags hermes-runtime`; complete native subscription enrollment with human approval.
5. Verify both providers in browser chats and gateway execution using bounded, operator-approved calls. Confirm persistence after restart and a second focused deployment, along with unchanged Authentik boundary and scheduling health.
6. Roll back module/template/device changes through the same focused automation if needed. Restore prior managed config without deleting the shared home or native OAuth state; revoke subscription access through its native mechanism only when intended. A previous NixOS generation alone does not restore copied runtime configuration/secrets.

## Open Questions

- What hosts the existing local Qwen service (Ollama, LM Studio or vLLM), and what are its exact reachable URL, model ID, tool-calling capability and configured context limit?
- Does that endpoint require an API key, and is its transport appropriately protected for the network path?
- Do the pinned agent and WebUI support the same provider schema and OAuth refresh store without an upgrade?
- Which Codex model is offered by the operator's entitlement? Discover rather than hardcode a presumed latest model.

These are activation/compatibility gates, not reasons to invent defaults or credential values during proposal creation.
