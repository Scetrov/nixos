## ADDED Requirements

### Requirement: Hermes WebUI access is gated by Authentik without a second password
The remotely exposed Hermes WebUI SHALL use Authentik at the Caddy ingress as its required user-facing access control and SHALL NOT require the WebUI's optional `HERMES_WEBUI_PASSWORD` authentication.

#### Scenario: Authentik-authenticated browser opens the WebUI
- **WHEN** a user passes the Authentik policy and opens the Hermes WebUI
- **THEN** the WebUI is accessible without a separate Hermes password prompt

#### Scenario: Unauthenticated browser requests the WebUI
- **WHEN** a browser requests the public Hermes hostname without an accepted Authentik session
- **THEN** Caddy denies access or redirects to Authentik and does not expose WebUI content

#### Scenario: Password variable is absent
- **WHEN** the Hermes WebUI container starts with the deployment environment
- **THEN** `HERMES_WEBUI_PASSWORD` is not set and optional WebUI password authentication remains disabled

### Requirement: GitHub CLI is available to Hermes command execution
The Hermes agent execution environments in both the gateway agent and WebUI containers SHALL provide the `gh` executable, independently of whether GitHub credentials have been configured.

#### Scenario: Agent runs GitHub CLI version check
- **WHEN** a Hermes agent command executes `gh --version`
- **THEN** it succeeds and reports the installed GitHub CLI version

#### Scenario: GitHub CLI has no configured credentials
- **WHEN** Hermes invokes a GitHub operation without configured GitHub credentials
- **THEN** the CLI remains available but reports its normal unauthenticated-operation error without exposing or fabricating credentials

#### Scenario: GitHub credentials are configured
- **WHEN** an operator configures GitHub credentials through the approved runtime secret mechanism
- **THEN** credentials are available to agent execution without being embedded in the image or Nix store
