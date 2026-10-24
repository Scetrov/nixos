# Docs-first change workflow

## Sources of truth

- `docs/README.md` routes operators to living service runbooks. Update the owning
  runbook when behaviour, security boundaries, recovery or verification changes.
- Declarative configuration and tests own current implementation/version facts.
- `openspec/changes/<name>/` contains temporary proposal, design, delta specs and
  implementation tasks only while a change is active. Keep the `spec-driven`
  schema for CLI compatibility, but use `docs/` as the existing-system baseline.
- Completed proposals/checklists/transcripts belong in Git history and PR/issue
  discussion, not a permanent archive or a second capability-documentation tree.
  `openspec/specs/` is intentionally absent. This repository policy takes
  precedence over generated upstream guidance to sync main specs.

## Explore

Read the relevant runbooks and actual configuration. Use `openspec list --json`
for active work, then read its artifacts if relevant. Investigate constraints,
options and evidence without implementing while in explore mode. Record a new
proposal or edit artifacts only when requested; distinguish observations from
assumptions and obtain decisions only where needed to proceed.

## Propose

1. Clarify the goal/scope and choose a new kebab-case name; resolve collisions
   with the operator rather than overwriting an active change.
2. Run `openspec new change <name>`, then `openspec status --change <name> --json`
   and artifact-specific `openspec instructions <artifact> --change <name> --json`.
3. Read dependencies and create artifacts in schema order until apply-ready.
   Reference the owning runbooks/configuration as baseline. Temporary delta specs
   capture the affected desired behaviour and acceptance scenarios; they do not
   require creating or restoring permanent capability files. For a changed
   contract, include enough desired behaviour to review it without an absent
   main-spec file. Keep scope proportionate to the request.
4. Include explicit tasks to reconcile runbooks, retain genuine unresolved work
   in the owning doc/issue, and finalize using the process below. Validate with
   `openspec validate <name> --strict`; report readiness without implementing.

## Apply

1. Select the named/inferred change, or ask if selection is ambiguous. Read
   status and `openspec instructions apply --change <name> --json`, all returned
   context files, and the affected runbooks/configuration.
2. Work one task at a time, marking it complete only after its required checks
   pass. Record blockers honestly; ask before destructive or expanded scope.
3. Update the runbooks as behaviour is established. Preserve architecture and
   access contracts, credential ownership, targeted deployment/recovery commands,
   meaningful rejected alternatives, known risks and reproducible verification.
   Consolidate by service, not one new document per implementation task.
4. Separate fixture results, agent-observed live results and operator reports.
   An unchecked test is not passed; a completed checkbox alone is not a detailed
   live evidence record. Do not claim new live verification from old acceptance.
5. On interruption, retain the active artifacts/handoff. On completion, report
   applicable tests and remaining limits, then finalize when authorized.

## Finalize and archive

1. Select the change explicitly; if none was supplied, ask the operator which
   active change to finalize. Check artifact status and read every unchecked
   task. Block on failing required checks unless the operator explicitly accepts
   a scoped deferral; preserve the unperformed scope and rationale in a runbook
   or tracked issue. Never mark deferred work passed.
2. Compare all change artifacts, including delta scenarios, decisions, research,
   compatibility notes and acceptance evidence, with the owning runbooks. Each
   enduring fact needs one documentation home; superseded instructions and raw
   transcripts can remain in Git history. Remove references to transient files
   from docs, automation, tests and editor tasks. Runtime outputs/checkpoints
   belong in appropriate protected runtime locations, not planning directories.
3. Validate the active change and relevant implementation/docs checks, then run
   `openspec archive <name> --skip-specs`. This performs the required archive
   before final commit/PR **without** generating permanent capability files.
   Review warnings and confirm only the selected change was archived. Keep
   validation enabled; `--skip-specs` skips synchronization, not tests.
4. Record the outcome, evidence limits and deferred-work links in the runbook
   and final change summary/PR. Once preservation is verified, remove only that
   completed archive directory. Do not delete another active change. The final
   working tree retains neither historical archive files nor main capability
   specs; earlier committed material remains retrievable from Git history.
5. Run `pre-commit run --all-files`, inspect the secret-redacted diff and stage
   only intended files. A commit or push requires explicit authorization;
   commits remain signed with required agent/model attribution. Report any
   blockers instead of bypassing gates.

## Retention test

Keep a detail in `docs/` when an operator needs it to deploy, diagnose, authorize,
recover, verify or safely change the service. Keep a short dated decision when
it explains an important restriction or an accepted risk. Use an issue or a
clearly scoped runbook follow-up for unresolved work. Leave completed task lists,
obsolete version tables, superseded designs, temporary handoffs and raw logs in
Git history rather than copying them wholesale into living documentation.
