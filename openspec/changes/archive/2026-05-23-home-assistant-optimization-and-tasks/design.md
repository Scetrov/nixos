# Home Assistant Optimization and Tasks

## Context

Home Assistant is deployed on `habiki` through `src/roles/nixos/files/etc/nixos/modules/home-assistant.nix`. The module currently generates `configuration.yaml`, installs the vendored `hass-oidc-auth` custom integration, configures Authentik OIDC, preconfigures core locale settings, writes onboarding completion state, and bootstraps the first owner user.

The committed repository does not currently contain standalone `configuration.yaml`, `automations.yaml`, `scripts.yaml`, `scenes.yaml`, blueprints, or custom dashboard files. The generated configuration references `automations.yaml`, `scripts.yaml`, and `scenes.yaml`, but those files are not managed by this repository today. Any optimization plan must therefore start by inventorying live runtime state and deciding what should be imported into source control.

## Goals / Non-Goals

**Goals:**

- Establish an auditable source-controlled Home Assistant configuration layout.
- Compare live Home Assistant runtime YAML and storage-backed dashboards against the repository before making changes.
- Add missing managed placeholder files for referenced YAML includes where needed.
- Require explicit behavioral specs for every new or changed automation/script.
- Prefer official Home Assistant integrations and built-in YAML/helpers before adding HACS or new custom integrations.
- Identify opportunities for Matter/Thread, dashboard organization, observability, and template/helper cleanup.

**Non-Goals:**

- Replace Home Assistant with another automation platform.
- Add HACS or arbitrary custom integrations as part of the audit baseline.
- Migrate Zigbee, Matter, Thread, or dashboards without a separate implementation decision.
- Store secrets, tokens, device credentials, or one-off runtime IDs in Git.

## Decisions

- Treat live `/var/lib/homeassistant` state as input, not source of truth.
  - Rationale: Home Assistant stores many IDs and runtime artifacts in `.storage`; importing them blindly risks committing machine-specific or sensitive state.
  - Alternative considered: copy the full runtime directory into the repo. This conflicts with the repository's automation and hygiene standards.

- Manage YAML includes declaratively under `src/roles/nixos/files/etc/nixos/home-assistant/`.
  - Rationale: it keeps automation files adjacent to the vendored OIDC integration and lets the Nix module install them into `/var/lib/homeassistant`.
  - Alternative considered: embed all YAML into the Nix string. That would make automations and scripts hard to review and lint.

- Require behavioral specs for automations and scripts before implementation.
  - Rationale: Home automations are user-facing behavior; GIVEN/WHEN/THEN scenarios reduce ambiguity and support later regression checks.
  - Alternative considered: implement changes directly from live UI state. That makes intent hard to recover.

- Prefer official integrations over HACS/custom integrations.
  - Rationale: official integrations receive compatibility updates with Home Assistant Core and reduce maintenance risk.
  - Alternative considered: use HACS for convenience. This should require an explicit exception and rollback plan.

- Keep `hass-oidc-auth` as an existing documented exception.
  - Rationale: it is already required for native Authentik OIDC integration and was introduced deliberately.

## Risks / Trade-offs

- Live runtime state may contain secrets or personal data -> Review and redact before importing anything into Git.
- Empty placeholder include files can mask missing runtime automations -> Compare live files before replacing them.
- Storage-backed dashboards are not simple YAML -> Export dashboard definitions intentionally and avoid committing unrelated `.storage` state.
- Official Matter/Thread integrations may require host hardware or border-router dependencies -> Treat protocol enablement as a follow-up implementation decision.
- Automation behavior may change during cleanup -> Write specs and test each automation incrementally.

## Migration Plan

1. Inventory committed Home Assistant files and live `/var/lib/homeassistant` files on `habiki`.
2. Identify files safe to manage declaratively.
3. Add repository-managed YAML include files for automations, scripts, scenes, and selected dashboard exports.
4. Update `home-assistant.nix` to install those files without overwriting unreviewed runtime state.
5. Validate Home Assistant configuration inside the running container.
6. Deploy with `./scripts/play.sh --limit habiki --tags nixos`.
7. Verify OIDC login, onboarding bypass, Home Assistant root route, and logs.

Rollback is to revert the Nix module and managed Home Assistant files, then redeploy the same targeted workflow.

## Open Questions

- Which live automations, scripts, scenes, and dashboards should be imported into source control?
- Which devices are planned for Matter or Thread, and what border router hardware is available?
- Should dashboards remain Home Assistant UI-managed or become fully declarative YAML/resources?
- Are any existing entity IDs orphaned or renamed in the live registry?
