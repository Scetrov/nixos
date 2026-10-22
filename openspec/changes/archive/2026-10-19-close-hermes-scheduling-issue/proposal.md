## Why

GitHub issue #29 remains open although the archived scheduling repair and runbook record successful Habiki lifecycle acceptance. Verify that evidence still applies and close the issue truthfully without repeating an already-completed repair.

## What Changes

- Reconcile issue #29 against the archived repair, current repository configuration, and bounded current health evidence.
- Publish a redacted closure summary linking durable evidence, then close #29 only when its acceptance criteria are satisfied.
- Leave the issue open and identify the unmet criterion if verification discovers a regression; do not silently expand this change into runtime remediation.

## Capabilities

### New Capabilities
- `hermes-scheduling-issue-closure`: Evidence-gated completion of issue #29.

### Modified Capabilities
None. Existing `hermes-native-scheduling` runtime requirements remain unchanged.

## Impact

Documentation and GitHub issue #29 only. Uses the archived `2026-05-22-fix-hermes-scheduled-jobs` artifacts, `docs/hermes.md`, existing health probes, and read-only observability. No new services, dependencies, secrets, routes, deployment, or runtime changes.
