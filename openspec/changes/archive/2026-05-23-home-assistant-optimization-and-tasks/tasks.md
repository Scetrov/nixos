# Home Assistant Optimization and Tasks

## 1. Audit Current State

- [x] 1.1 Inventory committed Home Assistant configuration in `src/roles/nixos/files/etc/nixos/modules/home-assistant.nix`
- [x] 1.2 Inventory repository-managed Home Assistant assets under `src/roles/nixos/files/etc/nixos/home-assistant/`
- [x] 1.3 Inventory live `/var/lib/homeassistant/configuration.yaml`, `automations.yaml`, `scripts.yaml`, `scenes.yaml`, blueprints, and dashboard storage on `habiki`
- [x] 1.4 Compare live files against repository-managed files and record which files are safe to import
- [x] 1.5 Check live Home Assistant logs for recurring configuration, integration, automation, and template warnings

## 2. Declarative File Structure

- [x] 2.1 Create repository-managed Home Assistant YAML asset locations for reviewed automations, scripts, scenes, and dashboards
- [x] 2.2 Add safe placeholder files only where Home Assistant includes require them and no reviewed runtime file would be overwritten
- [x] 2.3 Update `home-assistant.nix` to install reviewed YAML assets into `/var/lib/homeassistant`
- [x] 2.4 Preserve unreviewed live runtime files until an explicit import decision is made

## 3. Automation and Script Review

- [x] 3.1 For each imported automation, document GIVEN/WHEN/THEN trigger, condition, and action behavior before editing it
- [x] 3.2 For each imported script, document GIVEN/WHEN/THEN input, precondition, and service-call behavior before editing it
- [x] 3.3 Identify inefficient automations such as broad state triggers, repeated polling, redundant service calls, or missing conditions
- [x] 3.4 Refactor only one automation/script group at a time and validate behavior after each change

## 4. Integration and Protocol Review

- [x] 4.1 List current configured integrations from live Home Assistant state without committing secrets or runtime IDs
- [x] 4.2 Identify orphaned, unavailable, or renamed entities that need cleanup
- [x] 4.3 Review whether Matter or Thread support is needed and document available hardware, border router requirements, and official integration options
- [x] 4.4 Require a documented exception before adding HACS or any new custom integration beyond the existing OIDC integration

## 5. Dashboard and Helper Review

- [x] 5.1 Inventory live Home Assistant dashboards and classify each as UI-managed or candidate for declarative management
- [x] 5.2 Identify dashboard layout issues such as ungrouped areas, duplicated controls, or unclear operational views
- [x] 5.3 Inventory helpers, template sensors, and groups used by automations and dashboards
- [x] 5.4 Remove or replace unused helpers only after confirming no automation, script, scene, or dashboard references them

## 6. Validation and Deployment

- [x] 6.1 Run Home Assistant configuration validation inside the container before deployment sign-off
- [x] 6.2 Run `nix-instantiate --parse src/roles/nixos/files/etc/nixos/modules/home-assistant.nix`
- [x] 6.3 Run `openspec validate home-assistant-optimization-and-tasks --strict`
- [x] 6.4 Deploy with `./scripts/play.sh --limit habiki --tags nixos`
- [x] 6.5 Verify Home Assistant root route, OIDC login flow, onboarding bypass, and logs after deployment
