## Why

Authentik already gates remote access to the Hermes WebUI, but the deployment still injects a separate WebUI password, adding a redundant login step and credential to maintain. Hermes also needs GitHub CLI (`gh`) available inside the environment where its agent commands execute so repository workflows can use it.

## What Changes

- Stop configuring the Hermes WebUI password while retaining Authentik as the required external access gate.
- Ensure the `gh` executable and its runtime dependencies are available to Hermes agent execution, without assuming that adding a host package makes it available in the container.
- Add regression coverage for passwordless WebUI access behind Authentik and for `gh` availability in the agent execution environment.

## Capabilities

### New Capabilities
- `hermes-runtime-access`: Defines the access boundary and required command availability for the deployed Hermes WebUI and agent execution environment.

### Modified Capabilities

## Impact

- Hermes secret environment template and Habiki deployment configuration.
- Hermes NixOS module/container runtime and possibly the Hermes image or execution setup, depending on where agent commands run.
- Hermes deployment and regression tests; OpenSpec capability specs.
