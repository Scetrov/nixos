## Context

Authentik OAuth2 providers for Grafana and Dependency Track are managed by OpenTofu in `terraform/authentik.tf`. Their generated client IDs and secrets are exported by `scripts/tofu.sh` into `src/generated-secrets.yml`, then consumed by Ansible to render agenix files that NixOS services read at runtime.

The current flow can apply service configuration with stale or placeholder OIDC values because `vars_files` are loaded at play start, while generated OpenTofu outputs can be refreshed later by the `authentik-config` role. Dependency Track currently exposes `dtrack_oidc_client_id_placeholder` in its frontend config, and Grafana redirects with a client ID that does not match the current Authentik provider value.

## Goals / Non-Goals

**Goals:**
- Make OIDC client IDs/secrets required inputs for Grafana and Dependency Track deployments.
- Ensure OpenTofu-generated Authentik provider outputs are refreshed before agenix secrets and NixOS service configuration are rendered.
- Ensure changes to generated OIDC secrets cause affected services to receive refreshed runtime config via IaC.
- Add safe validation/verification that uses presence, placeholder checks, lengths, hashes, or Authentik API comparisons without printing secret values.

**Non-Goals:**
- Replace Authentik, OpenTofu, agenix, or the PostgreSQL OpenTofu backend.
- Manually edit running service configuration on Habiki.
- Rotate unrelated secrets or change Authentik flows outside the affected OIDC clients.
- Redesign Grafana dashboards, Dependency Track policy configuration, or Caddy routing beyond what is necessary for login correctness.

## Decisions

1. **Use OpenTofu outputs as the source of truth for service OIDC credentials.**
   - Rationale: Authentik provider resources are already declaratively managed by OpenTofu, and the generated client IDs must match those resources exactly.
   - Alternative considered: hardcode stable client IDs in Nix or service config. This reduces drift but weakens secret lifecycle hygiene and bypasses the existing generated-secret workflow.

2. **Fail fast on missing, placeholder, or malformed OIDC generated secrets.**
   - Rationale: A failed deploy is safer than a successful deploy that writes invalid OIDC config and breaks login.
   - Alternative considered: silently keep old agenix files. That can preserve service availability temporarily but hides drift and makes incident diagnosis harder.

3. **Separate or explicitly order generated-secret refresh before host/service deployment.**
   - Rationale: Ansible `vars_files` are evaluated before roles run, so generated values produced mid-play cannot reliably influence earlier `secrets` or `nixos` roles in the same play.
   - Alternative considered: keep the current role order and require operators to run deployment twice. That matches the accidental recovery path but is brittle and undocumented.

4. **Restart/re-render only affected services when OIDC material changes.**
   - Rationale: Grafana reads OAuth client values from systemd EnvironmentFiles; Dependency Track frontend/apiserver environment files are generated from agenix secrets and containers must see the new values.
   - Alternative considered: restart all Habiki services after any generated-secret change. This is simpler but increases blast radius.

5. **Verify by comparing non-sensitive fingerprints.**
   - Rationale: Hashes, lengths, placeholder checks, and Authentik provider metadata confirm consistency without leaking client IDs or secrets into logs.
   - Alternative considered: print full values during deploy or troubleshooting. This violates the repository's toxic-waste and secret-management standards.

## Risks / Trade-offs

- **Risk: OpenTofu output generation fails before host deploy** → Mitigation: surface a clear error and leave existing deployed services unchanged.
- **Risk: service restarts briefly interrupt Grafana or Dependency Track access** → Mitigation: restart only affected units/containers and perform targeted deploys with `--limit habiki`.
- **Risk: stale local generated files are committed or used accidentally** → Mitigation: add validation around placeholder/empty values and keep generated-secret handling documented in the deployment flow.
- **Risk: validation accidentally logs sensitive values** → Mitigation: use redacted output, hashes, and length checks only.

## Migration Plan

1. Update the deployment flow so OpenTofu outputs are refreshed before agenix secret generation and NixOS service deployment consume them.
2. Add Ansible validation for required Grafana and Dependency Track OIDC generated-secret variables.
3. Update service/unit dependencies or handlers so Grafana and Dependency Track runtime environment is regenerated/restarted when relevant agenix inputs change.
4. Run a targeted IaC deploy for Habiki using the appropriate tags rather than making direct runtime edits.
5. Verify Dependency Track `/static/config.json` no longer contains a placeholder client ID and Grafana's OAuth redirect client ID fingerprint matches Authentik's provider fingerprint.
6. Roll back by reverting the IaC change and re-running the prior deployment, or by restoring the previous generated-secret file from version control/vault history if credential rotation caused unexpected mismatches.

## Open Questions

- Should `scripts/play.sh --tags authentik` become responsible for a complete two-phase Authentik/generated-secret refresh, or should `scripts/tofu.sh` remain the explicit pre-step before `--tags nixos`/service deploys?
- Should Grafana and Dependency Track OIDC client IDs be made stable explicit values while keeping client secrets generated, or should both remain OpenTofu-random generated outputs?
