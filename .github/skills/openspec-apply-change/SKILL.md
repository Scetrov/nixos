---
name: openspec-apply-change
description: Implement or resume an active OpenSpec change and update its owning service runbooks.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: repository
  version: "2.0"
---

Read `docs/documentation-workflow.md` from the repository root completely before
acting. Follow its **Apply** section and the shared sources-of-truth and
retention rules. Use the user's supplied goal/change name; ask when a concrete
decision is required.

Living contracts belong in the owning `docs/` runbook. OpenSpec artifacts are
temporary active-change context, not a second permanent documentation system.
Report progress, actual verification and unresolved work concisely. Preserve
unrelated work and the repository's automation, secret and signing boundaries.
