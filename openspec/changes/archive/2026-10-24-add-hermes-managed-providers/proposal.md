## Why

Hermes currently regenerates a single OpenRouter model configuration during deployment, preventing durable use of the operator's ChatGPT subscription and local Qwen server. Managed multi-provider configuration should survive rebuilds without overwriting OAuth credentials or requiring secrets in Nix expressions.

## What Changes

- Add managed provider definitions for ChatGPT/Codex subscription access and a named local Qwen OpenAI-compatible endpoint, retaining OpenRouter and its existing default until explicitly changed.
- Generate configuration safely and idempotently, preserving unrelated settings and Hermes-owned authentication/session state.
- Prepare optional local-endpoint credential fields in Ansible Vault during implementation; omit empty values from runtime secrets. Authenticate ChatGPT through Hermes' native interactive OAuth flow, not an OpenAI API key or static token placeholder.
- Verify the pinned agent and WebUI support provider discovery, selection and execution; document a compatibility blocker rather than silently claiming CLI support covers browser chats.
- Document operator-supplied Qwen endpoint/model settings, subscription enrollment, provider switching, focused deployment and rollback.
- Preserve existing native background auxiliary routing with explicit operator approval: primary chat/tool inference is provider-isolated, but auxiliary work may use OpenRouter and incur charges.

## Capabilities

### New Capabilities

- `hermes-managed-providers`: Persistent managed provider configuration, secure credentials, native subscription enrollment, and verified selection in gateway and browser runtimes.

### Modified Capabilities

None. Existing browser-access and scheduling requirements remain unchanged.

## Impact

- NixOS module: `src/roles/nixos/files/etc/nixos/modules/hermes.nix` and Habiki device configuration.
- Secret handling: encrypted `src/secrets.yml`, Hermes environment template and focused runtime automation where necessary.
- Tests: configuration generation, environment rendering, pinned-image compatibility and controlled provider acceptance checks.
- Documentation: `docs/hermes.md`.
- No new public listener, identity application, inference server installation, automatic cross-provider fallback for primary inference, or model download. Endpoint address/model ID are operator inputs, not inferred values. No live changes or vault edits occur during proposal creation.
