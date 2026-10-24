# Provider contract and acceptance evidence

## Unchanged runtime pins

- Agent: `docker.io/nousresearch/hermes-agent:v2026.9.24@sha256:fca358f12efd65bfaaca05884166f15c0e2788375ca30d77061ac1ebc96452b7`
- WebUI: `ghcr.io/nesquena/hermes-webui:latest@sha256:5fb831ca2a9f3f0b93b84c1ebaaeedf5809d914a33bbf969e5c29a5bb75cb47c`

No image upgrades, new listeners, identity resources or inference-server installation were needed.

## Verified native configuration contract

Agent `hermes_cli/config_providers.py` and `runtime_provider_custom.py` support keyed `providers` definitions with `api`, `default_model`, `models`, positive per-model `context_length`, `key_env` and `transport: chat_completions`.

`resolve_runtime_provider(requested="custom:local-qwen", target_model=...)` preserves the configured endpoint and environment credential. WebUI `api.config.resolve_custom_provider_connection("custom:local-qwen")` resolves the same connection, `get_available_models()` discovers the declared model, and `model_with_provider_context(...)` preserves explicit provider identity as `@custom:local-qwen:model`. Codex context is preserved as `@openai-codex:model`. WebUI reads its initial selection from `HERMES_WEBUI_DEFAULT_MODEL`.

Keyless entries omit `key_env`; internal SDK placeholders are not operator credentials and are not written into Vault or the runtime environment. The shared reconciler generates only a reference for an authenticated provider, never the resolved key.

## Disposable checks

`scripts/tests/check_hermes_provider_images.py` seeds a uniquely named disposable source volume from the exact agent image and uses the real new reconciler with synthetic state, endpoint and credentials. Agent checks run network-isolated. With operator-approved network access, the pinned WebUI's normal entrypoint installs its existing dependencies, becomes healthy and passes generated-model discovery, explicit local/Codex routing and authenticated/keyless resolution checks. No host port, production mount or real credential is used. All disposable containers/volumes were removed.

Fresh-image system Python lacks PyYAML; the WebUI entrypoint prepares `/app/venv`. An initial bootstrap without the required `HERMES_WEBUI_STATE_DIR` exited; deployment-equivalent settings succeeded. A synthetic catalog build exceeded its four-second budget and served its declared-model fallback successfully. These were not production compatibility defects. Startup dependency resolution is an existing reproducibility limitation: image digests alone do not pin those Python packages.

Both rootful/rootless setup scripts were Nix-evaluated and passed `bash -n`. Config/ownership outputs are mode 0600 and container-owned; the mode-0600 WebUI environment is owned by the setup identity so host rootless Podman can read it.

## Confirmed operator inputs and secrets

- URL: `http://10.229.2.10:9931/v1`
- Model: `qwen3.8-27b`
- Server context: 65,536 tokens; OpenAI-compatible tool calling confirmed supported.
- Operator approved HTTP on the protected trusted network path; HTTP alone does not encrypt credentials.
- The absent `hermes_local_qwen_api_key` field was prepared empty in encrypted Vault without replacing existing entries. The operator then provisioned the real key. Only non-emptiness was reported; no value entered source, arguments or logs.
- Both production containers reached `/models` with the key and found the exact model before enablement. Credentials were supplied through captured pipes for this preflight, then through the existing no-log encrypted runtime pipeline for deployment.

## Native subscription enrollment

The operator completed `hermes auth add openai-codex --type oauth --no-browser` in their own terminal; no device codes/tokens were captured. CLI help verifies that command; `hermes auth login` does not exist and deprecated `hermes login --provider` ignores its provider argument.

Native credential resolution and `get_codex_model_ids` succeeded independently in agent and WebUI environments. The discovered `gpt-6.1-sol` was used successfully for controlled acceptance, not made the default. Shared `auth.json` remained usable after restart and redeployment. Source inspection of `hermes_cli/auth_codex.py` confirms source-store locking across refresh, adoption of a peer's rotated pair, and native failure/recovery handling. Forced expiry, revocation and refresh races were not tested live; credentials were not copied into Vault.

## Deployment and lifecycle acceptance

Remote preflight compared 110 repository-managed paths; actual host files matched the expected baseline except intended Hermes changes and unrendered template paths. A non-activating baseline build differed from the active generation only in `/etc/issue`; activation scripts matched after path normalization and systemd/package/kernel/initrd outputs matched. No failed units, active agents/jobs or active session flags were found.

Both deployments used exactly `./scripts/play.sh --limit habiki --tags hermes-runtime` with `age` supplied through `nix-shell`:

- First: `ok=17 changed=6 failed=0`.
- Second: `ok=17 changed=5 failed=0`; copied implementation files were unchanged. Ciphertext refresh, setup and container restarts are intentional repeated-deployment actions.

`scripts/tests/check_hermes_provider_execution.py` verifies one exact harmless terminal call, a non-error tool result and the exact final marker for both providers. Checks passed initially, after Ansible-controlled service restarts and after the second deployment. The operator confirmed the same explicit-provider tool checks in the Authentik-protected WebUI at all three stages. The separate automation browser reached Authentik and did not bypass authentication.

The default remained `openrouter` / `qwen/qwen3.6-flash` with its existing URL. Native scheduling job `c61825580460` passed before/after restart; it reached its bounded 12-run limit while awaiting operator validation. It was removed, and fresh fixture `7f0d5c704601` advanced from one successful run before redeployment to two afterward. Fresh/advancing metadata checks passed. Both test definitions/scripts/markers were removed via the native API; native history was retained.

## Observability and approved routing boundary

A bounded one-hour/500-record Loki query through Grafana returned HTTP/status 200 and Hermes logs. Journal review identified the same native auxiliary paid-lane warning and expected WebUI container-binding/no-password warning; package-name keyword matches were not tracebacks. No failed units were present. A journal-processing attempt encountered a list-valued MESSAGE; handling binary/list records fixed the diagnostic, with no service change.

The operator explicitly chose **primary inference only** when clarifying provider isolation. Existing native auxiliary routing may independently use OpenRouter, including paid models. The native paid-lane warning is emitted before credential lookup/client use and is not proof of an actual billed request. No auxiliary policy was silently changed, and this work does not claim whole-runtime inference isolation. The proposal, design, delta spec and runbook now disclose that approved boundary.

Final publications: no agent port; WebUI only `127.0.0.1:8787`. Public unauthenticated `/` returned 302 to Authentik; `/health` and `/api/crons` returned 401 with no-store and no redirect. Caddy/identity routes remained unchanged.

## Validation and rollback evidence

37 focused unit tests pass, including configuration/state preservation, disablement, invalid-input/atomic failure, ownership/permissions, optional secret rendering, Vault preservation/failure and bounded/redacted live-probe result handling. Pinned-image generated-config checks pass. Strict OpenSpec validation and full pre-commit passed at final sign-off, including Gitleaks. The operator approved syncing the six requirements into the new main capability spec and archiving this change; the final archival/staging checkbox was completed after the successful archive operation.

Live rollback was not activated. Synthetic disablement and atomic-failure tests verify preservation; `docs/hermes.md` documents restoring the prior managed default and disabling the owned local definition through the same focused automation without deleting native authentication/session/job/workspace state. Reverting to the old truncating setup is discouraged. No commit has been made; archive must precede any final implementation commit/PR, which must remain signed and attributed.
