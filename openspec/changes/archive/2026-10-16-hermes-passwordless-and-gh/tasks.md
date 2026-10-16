## 1. Remove redundant WebUI password

- [x] 1.1 Confirm the deployed WebUI image digest supports password auth disabled when `HERMES_WEBUI_PASSWORD` is absent; add or run an image-level smoke check.
- [x] 1.2 Stop rendering `HERMES_WEBUI_PASSWORD` into the Hermes runtime environment while retaining other secrets and model settings.
- [x] 1.3 Verify Caddy still requires Authentik and the WebUI backend is not directly published; add/update regression coverage for unauthenticated and authenticated requests.
- [x] 1.4 Add and deploy through the focused `hermes-runtime` automation (no channel updates, OpenTofu, unrelated secrets, or blanket restarts), and verify WebUI login behavior and Authentik enforcement.

## 2. Make GitHub CLI available to Hermes

- [x] 2.1 Inspect the actual Hermes agent image and execution environment to select a reproducible, pinned method for adding GitHub CLI.
- [x] 2.2 Add `gh` to both Hermes gateway and WebUI agent execution environments without embedding GitHub credentials in the image or Nix store.
- [x] 2.3 Add a regression check that runs `gh --version` inside both Hermes agent and WebUI containers and document that authentication is configured separately.
- [x] 2.4 Deploy through focused Hermes automation and verify CLI availability and credential handling inside both agent runtimes.

## 3. Validate and document

- [x] 3.1 Update Hermes documentation with the Authentik-only WebUI access model, GitHub CLI location, and optional credential setup boundary.
- [x] 3.2 Run relevant Hermes regression tests and NixOS/module validation; record deployment verification and rollback steps.
