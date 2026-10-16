# Handoff: add-miniflux

_Updated: 2026-10-16 · State: operator confirmed working and approved archive with documented test deferrals_

## Current position

The operator explicitly requested finishing the configuration without waiting for incremental runtime tests. Routing, private monitoring, targeted deployment orchestration, rollback handling and operations documentation are now implemented. See `tasks.md` for current progress and `verification.md` for evidence.

The operator reported deployment and subsequently confirmed the service works. Independent read-only verification confirmed healthy runtime/setup, HTTPS boundaries, private metrics, Loki ingestion, an inactive/healthy Grafana rule, restricted database-role flags and matching live credentials. At that earlier check Fyne lacked the feed alias; there was no independent DNS recheck after operator confirmation. See `verification.md` for the chronological evidence.

The earlier **Keep tests offline** decision still applies to disposable fixtures/builds. The agent performed no deployment, restart or data modification; only database catalog metadata was read. The operator explicitly approved archive/spec sync and signed commit/push with the remaining verification gaps documented. Tasks 3.4, 5.4 and 5.5 retain unchecked scope rather than claiming unperformed tests passed.

## Decisions and approvals

- The external Bubblewrap launcher was adapted with approved read-only `/nix/store` and `/run/current-system/sw` mounts. No home, credentials, sockets or host network were exposed.
- Vault operations outside Bubblewrap and later use of `scripts/tofu.sh` were approved. `miniflux_db_password` already exists in encrypted `src/secrets.yml`; the idempotent provisioning script must not regenerate it.
- Runtime/build fixtures were declined; this did not prevent further independent configuration work.
- Grafana alert provisioning inherits the existing notification tree rather than creating contact points. Disabling the service explicitly deletes the alert. Native feed routing works with Grafana disabled.

## Working tree

Work is on `main`, with the original OpenSpec proposal artifacts staged before implementation. Preserve all existing staged changes. Review `git status` for the current implementation staging state; do not overwrite the operator's work. The external launcher modification is not part of this repository.

The targeted workflow is `./scripts/play.sh --limit habiki --tags miniflux`. It applies only `authentik_policy_binding.miniflux_access` and its dependency graph, refreshes generated outputs, then invokes Ansible's secrets/NixOS roles. It does not mutate infrastructure for check/list/syntax modes. Target/refresh overrides are rejected. Component-only rebuilds skip unrelated channel updates, blanket container restarts, Frontier writer stops, Headscale enrollment and Garage provisioning. NixOS still activates the complete host configuration.

Shared DNS alias propagation to Fyne uses a separate explicit `--limit fyne --tags local-dns` rollout; the Habiki tag never silently deploys to another host. See `docs/miniflux.md`.

## Verification

- 37 Miniflux/generated-secret tests pass, including actual Nix configuration evaluation and stubbed deployment ordering.
- Expanded shared suite: 47 tests, 45 passing and two explicit opt-in tests skipped.
- Repository `tests/`: 31 passing tests. Total: 76 passing, two skipped.
- Nix evaluation covers enabled, disabled and Grafana-disabled service variants.
- Ansible Habiki/Miniflux syntax validation passes.
- `scripts/tofu.sh -- validate -no-color` passes against installed providers; the wrapper now supports credential-free local formatting/validation and pre-commit uses it.
- Nix/shell formatting and syntax, redacted secret scanning and all configured pre-commit gates pass for tracked and explicitly selected new files.
- The pre-commit hook is installed. No dependencies were added.

One unrelated shared regression fixture assumed more than 1 GiB temporary capacity. Confirmed its production code/test were initially unchanged and that the sandbox provides exactly 1 GiB. The unit test now mocks capacity so its intended restore-failure path is exercised; the production disk-space check is untouched.

Use the project `.venv/bin/python` in the launcher because system Python lacks PyYAML. For Nix tests, pass the non-secret `NIXPKGS` setting inside the sandbox via `env`:

```sh
/home/scetrov/.agents/skills/bubblewrap-isolation/scripts/run-isolated.sh -- \
  env NIXPKGS=/nix/store/77dysp5fl6b4mfnbh7h553fyiv8k5irg-nixos-26.05/nixos \
  /home/scetrov/source/nixos/.venv/bin/python -m unittest \
  scripts.tests.test_render_generated_secrets scripts.tests.test_miniflux_identity \
  scripts.tests.test_miniflux_vault scripts.tests.test_miniflux_dbsetup \
  scripts.tests.test_miniflux_configuration -q
```

## Next actions

This handoff is retained as archival implementation context. Read `verification.md` and the accepted-deferral note in `tasks.md` before any follow-up verification. The operator has confirmed working operation; the agent did not execute the documented DNS-only Fyne rollout or independently recheck its result.

Repeatability, rotation/restart behavior, full database isolation, live authorized/unauthorized OIDC, disabled local login, authenticated APIs, feed/OPML operation and notification delivery remain unverified. The service has successfully started, and its actual loaded runtime credentials match their sources, but this is not a substitute for the deferred disposable-fixture tests. Remaining checks are explicitly deferred by the operator's archive/sign-off decision, not marked passed. Retain the database/role and never delete production data to force a test or rollback to pass.
