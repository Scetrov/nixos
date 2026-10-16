## Context

The deployed `hermes-webui` is `ghcr.io/nesquena/hermes-webui`, not the WebUI shipped directly by `NousResearch/hermes-agent`. Its upstream README documents password authentication as optional and off by default; `HERMES_WEBUI_PASSWORD` enables it. The deployment currently renders that variable in `src/roles/secrets/templates/hermes-webui.env.j2`, and the WebUI receives the generated environment file. Caddy on the public Hermes hostname already delegates authentication to Authentik.

Hermes runs as separate gateway agent and WebUI containers. Exact-image source inspection found WebUI imports `AIAgent` in `/app/api/agent_runtime.py` and constructs agents in `streaming.py` and `routes.py`; WebUI chats can execute tools in that container too. Cover both containers, not merely the host or one runtime. The current agent image is configurable in `hermes.nix` and defaults to the upstream private `nousresearch/hermes-agent:latest` image.

## Goals / Non-Goals

**Goals:**
- Remove the redundant WebUI password prompt while preserving Authentik as the external access control.
- Make the `gh` executable usable from Hermes agent command execution and document how credentials are supplied (without embedding credentials in images or Nix store paths).
- Add tests/validation that cover both the proxy access boundary and command availability in the correct container.

**Non-Goals:**
- Replace Authentik with native WebUI OIDC or alter Authentik policy.
- Automatically grant a GitHub identity/token to Hermes. CLI availability and GitHub authentication are separate concerns; credentials must remain operator-provided and secret-managed.
- Install `gh` on the host as a substitute for availability inside the agent container.

## Decisions

1. **Disable the password by omitting its environment variable, not by setting it to an empty string.** Upstream documents password auth as off by default and enabled via `HERMES_WEBUI_PASSWORD`. Remove the variable from the generated WebUI environment while preserving unrelated secrets. Confirm the resulting container environment has no variable and the WebUI starts without its login screen.
   - Alternative: retain the variable with an empty value. Rejected because unset and empty may be interpreted differently and upstream explicitly describes optional/off-by-default behavior.

2. **Keep Authentik enforced at ingress and retain a private backend.** Do not remove or weaken the Caddy `forward_auth` policy. Validate unauthenticated public requests are denied/redirected by Authentik and the WebUI port remains unpublished directly when Caddy is enabled.
   - Alternative: rely on network privacy alone. Rejected because the service is remotely reachable through the configured proxy.

3. **Provide `gh` in the agent execution environment, not on the host or only in WebUI.** Inspection found the deployed agent uses Debian 13 on x86_64 and has no `gh`. Bind-mount only `${pkgs.pkgsStatic.github-cli}/bin/gh` read-only at `/usr/local/bin/gh` in both the gateway agent and WebUI containers, covering both command-execution paths (operator-approved correction after exact-image inspection). The static build avoids container dynamic-loader dependencies and exposing the host Nix store. Its source and vendor dependencies are hash-verified by Nix; retain the current channel during deployment. The applicable release checked against GitHub is 2.102.0, matching current nixpkgs. Keep authentication out of the binary and Nix store; credentials remain a separate runtime concern.
   - Alternative: host-level Nix package or WebUI container installation. Rejected because Hermes commands execute in the agent container.
   - Alternative: mutable install during container startup. Avoid unless the image cannot be reproducibly extended; it introduces network/startup dependency and supply-chain drift.

4. **Treat CLI presence and GitHub login as independent acceptance conditions.** Verify `gh --version` in the agent container. Do not require `gh auth status` to succeed unless a secret/token is separately configured; document the supported secret-injection boundary and avoid logging credential values.

## Risks / Trade-offs

- [The WebUI image version may differ from the repository's current upstream branch] → Confirm behavior against the deployed digest or a matching release before removing the variable; add an integration check for passwordless start and Authentik gating.
- [The private Hermes agent image may be difficult to extend or reproduce] → Inspect its build and execution environment first; choose a pinned derived image or an explicitly reproducible package-install approach and record the source/digest.
- [Removing the app password makes ingress the sole browser access gate] → Preserve the Authentik forward-auth route and verify direct host/container port exposure is absent.
- [A usable `gh` binary without credentials can appear broken for API operations] → State clearly that CLI installation does not authenticate it; credentials are optional and must be supplied through existing secret management.

## Migration Plan

The existing `--tags hermes` path updates channels, restarts unrelated containers, and performs an unrestricted OpenTofu apply. Operator-approved scope adjustment: add a guarded `--limit habiki --tags hermes-runtime` entrypoint. It renders/encrypts only the Hermes secret, copies only the Hermes module, Habiki device configuration and existing auth routing files, rebuilds without channel updates, refreshes the shared `.env`, and restarts only the Hermes containers. No OpenTofu operation is needed because Authentik policy is unchanged. Review host configuration drift before activating: a NixOS switch can still activate pre-existing unrelated changes.

1. Update generated Hermes environment handling so the WebUI password variable is absent (including removing Habiki's explicit empty override), then deploy with the focused Hermes automation.
2. Add `gh` to the agent execution image/runtime using a reproducible, pinned source and deploy the image change through the same targeted automation.
3. Verify WebUI passwordless behavior through Authentik, verify unauthenticated access remains blocked, confirm the backend is not directly exposed, and run `gh --version` inside both `hermes-agent` and `hermes-webui`.
4. Roll back by restoring the prior environment template/password configuration and prior agent image reference, then redeploy the targeted Hermes component.

## Open Questions

- Does the exact deployed WebUI digest behave as documented by the current upstream README when `HERMES_WEBUI_PASSWORD` is absent? Confirm via image-level smoke test before deployment.
- What GitHub authentication method, if any, should Hermes use for `gh` operations? This proposal only guarantees the binary is available; it does not provision a token.
- Resolved: mount the same single Nix-built static GitHub CLI executable into both agent runtimes; do not modify or republish the private image.

## Inspection evidence

- Habiki uses the configured WebUI digest `sha256:5fb831ca2a9f3f0b93b84c1ebaaeedf5809d914a33bbf969e5c29a5bb75cb47c`. A disposable container with no network, no host volumes, no password variable, and fresh state returned false for password authentication and overall authentication.
- The exact image falls back to `settings.json` when the password variable is absent. Habiki's persisted password hash is not configured. Retain trusted-proxy settings; the isolated smoke check deliberately tests the passwordless baseline without those settings.
- Habiki is rootful, disables the optional Caddy container, and publishes WebUI only on `127.0.0.1:8787` for host Caddy. The agent publishes no ports. Ten configuration tests and five Caddy container fixture tests passed before runtime deployment.
