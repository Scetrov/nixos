## 1. Reproduce and isolate

- [x] 1.1 Inspect the actual Habiki images, gateway process, journal/Loki errors, heartbeat/job storage and WebUI reader; record redacted baseline evidence and distinguish empty inventory from scheduler failure. Attempt a disposable local container reproduction; document any environment limitation instead of inventing a root cause.
- [x] 1.2 Identify the demonstrated fault and the smallest supported correction. Resolve ordinary diagnostic unknowns autonomously; stop only for genuine access/safety/upstream blockers or a materially broader solution.

## 2. Correct and regression-test

- [x] 2.1 Apply only the required declarative runtime/configuration/state-path/permissions correction, or a proven compatible image change if necessary. Preserve existing jobs, secrets, ingress, rootful topology and disabled separate dashboard; do not add an external scheduler.
- [x] 2.2 Add a focused regression check using existing test patterns, rerun the reproduction with the fix, and run relevant Hermes configuration/auth/GitHub CLI checks. Verify healthy empty-inventory behavior and failure visibility in the disposable environment where possible; record limits honestly.

## 3. Deploy and verify on Habiki

- [x] 3.1 Check current activity and deployment scope, then deploy the candidate autonomously via `./scripts/play.sh --limit habiki --tags hermes-runtime` where sufficient. Confirm metadata advances over multiple expected heartbeat intervals and the authenticated Scheduled Jobs WebUI no longer reports stale metadata.
- [x] 3.2 Use a repeatable automated native-interface check to create one harmless, bounded test job; verify WebUI visibility and scheduled execution, then verify the same job remains visible and executes after gateway/WebUI restart and again after a targeted Habiki rebuild. Confirm existing access and state boundaries remain intact; clean up only test-owned jobs/markers.
- [x] 3.3 Update `docs/hermes.md` with the demonstrated cause, minimal correction, exact verification commands/results, actionable health/log checks and rollback guidance. Run strict OpenSpec validation and configured pre-commit gates before finalizing; archive the completed change before any final signed commit/PR. Leave acceptance tasks unchecked if live evidence is missing.
