# hermes-managed-providers Specification

## Purpose
Define persistent, secret-safe Hermes provider management for OpenRouter, native ChatGPT/Codex subscriptions and local Qwen, with verified primary inference in browser and gateway runtimes across deployment lifecycle operations.
## Requirements
### Requirement: Managed providers coexist without changing the existing default
The Hermes deployment SHALL support OpenRouter, native ChatGPT/Codex subscription authentication, and a named local-Qwen OpenAI-compatible endpoint. It SHALL retain the existing OpenRouter default unless explicitly changed through managed configuration and SHALL keep the WebUI initial model consistent with that default.

#### Scenario: Existing installation has no new provider settings
- **WHEN** the existing configuration is deployed without a local endpoint or subscription enrollment
- **THEN** OpenRouter and its configured default continue working without requiring new credentials

#### Scenario: Additional providers are configured
- **WHEN** an operator enrolls a subscription and enables a valid local Qwen definition
- **THEN** both providers are available alongside OpenRouter without silently changing the deployment default

### Requirement: Configuration reconciliation preserves persistent state
Setup SHALL structurally merge only its explicitly managed model/provider entries, preserve unrelated settings and unmanaged providers, and atomically replace valid configuration with the correct runtime ownership and restrictive permissions. It MUST NOT overwrite native authentication, sessions, scheduled jobs or workspace state.

#### Scenario: Rebuild reconciles managed entries
- **WHEN** setup runs twice with unchanged input and existing unrelated settings and OAuth state
- **THEN** managed configuration is semantically identical after both runs and unrelated configuration and authentication state remain unchanged

#### Scenario: Invalid existing or requested configuration
- **WHEN** setup encounters malformed YAML or invalid provider inputs
- **THEN** setup fails with a redacted actionable error before replacing the last valid configuration

#### Scenario: Managed local endpoint is disabled
- **WHEN** an operator disables a previously managed Qwen endpoint
- **THEN** its managed definition is removed without deleting unmanaged providers or native authentication state

### Requirement: Optional provider secrets use the existing encrypted pipeline
The implementation SHALL pre-create the optional empty `hermes_local_qwen_api_key` field in encrypted Ansible Vault when absent, preserve existing values, and emit `HERMES_LOCAL_QWEN_API_KEY` only when non-empty. OpenRouter credentials SHALL remain available when configured and SHALL NOT be required when OpenRouter is unused. Resolved keys MUST NOT enter Nix-store content, repository plaintext or logs.

#### Scenario: Local endpoint needs no authentication
- **WHEN** the optional local key is absent or empty
- **THEN** no placeholder key is injected and a valid unauthenticated endpoint can be used

#### Scenario: Local endpoint requires authentication
- **WHEN** a non-empty local key is supplied through Vault
- **THEN** both execution runtimes receive it through the secure runtime pipeline and use it without exposing its value

#### Scenario: Vault already contains the field
- **WHEN** credential preparation runs with an existing local key
- **THEN** the stored value and unrelated vault entries remain unchanged

### Requirement: Subscription enrollment uses native persistent OAuth
ChatGPT subscription access SHALL use the pinned runtime's verified native Codex authentication mechanism and operator-approved login flow. Refreshable credentials SHALL remain in the persistent native authentication store shared by agent and WebUI. Setup MUST NOT fabricate subscription API keys or replace OAuth state through the environment-file deployment.

#### Scenario: Operator enrolls a subscription
- **WHEN** the operator completes native enrollment as the Hermes runtime user
- **THEN** the entitled subscription models become usable without an OpenAI API key and credentials persist across container restart

#### Scenario: Credentials require reauthentication
- **WHEN** native authentication reports expired or revoked access that cannot be refreshed
- **THEN** Hermes reports an actionable primary-inference authentication failure without exposing tokens or silently routing that primary request to a billed provider

### Requirement: Local Qwen activation requires a real reachable endpoint
Local Qwen SHALL remain disabled until an operator supplies a valid OpenAI-compatible URL and exact model ID. Enabled configuration SHALL use an address reachable from both containers and SHALL NOT assume container loopback reaches the inference host. Acceptance SHALL verify primary model execution and tool-calling/context suitability, not merely model discovery. Primary chat/tool inference SHALL remain on the explicitly selected provider without introducing automatic cross-provider fallback. Existing native auxiliary routing is outside this isolation guarantee and MAY use OpenRouter, including paid models; the runbook MUST disclose this boundary.

#### Scenario: Endpoint details are unavailable
- **WHEN** no complete endpoint and model configuration exists
- **THEN** the optional provider stays disabled and deployment continues without inventing endpoint or model values

#### Scenario: Enabled endpoint is incomplete
- **WHEN** local Qwen is explicitly enabled without a valid URL or model ID
- **THEN** configuration validation fails before activation

#### Scenario: Local inference succeeds
- **WHEN** a configured local provider is selected in either execution runtime
- **THEN** primary model/tool inference requests reach the specified model and a bounded tool-use acceptance interaction succeeds without routing primary inference to another provider

#### Scenario: Native auxiliary routing is retained
- **WHEN** Hermes performs background auxiliary work under its existing native routing policy
- **THEN** that work may use OpenRouter independently of the primary provider selection, and operators are informed that it may incur charges

### Requirement: Both execution runtimes and redeployment are verified
Implementation SHALL establish pinned-agent and pinned-WebUI compatibility and demonstrate provider discovery, explicit selection and successful execution for each newly enabled provider in browser chats and gateway execution. Verification SHALL include restart and repeated focused deployment, preserve existing access/network/scheduling boundaries, and avoid secret-bearing telemetry.

#### Scenario: Providers remain usable after redeployment
- **WHEN** both providers passed controlled acceptance and containers restart followed by another focused runtime deployment
- **THEN** definitions and enrollment remain available, provider interactions still succeed, and Authentik, loopback publishing and scheduling health remain intact

#### Scenario: Browser compatibility or operator access is missing
- **WHEN** CLI checks pass but the pinned WebUI cannot use a provider, or required endpoint/login access is unavailable
- **THEN** the implementation records an explicit blocker and does not declare full provider acceptance complete
