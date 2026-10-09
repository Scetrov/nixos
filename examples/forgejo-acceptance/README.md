# Deferred experimental Forgejo Actions fixture

**Not part of the current private Forgejo deployment.** The operator deferred
Actions; Habiki disables both Forgejo Actions and the independent runner option.
Do not enable this workflow or runner as part of `add-private-forgejo`. Retained
code is reference material for a future, separately validated change.

For a future isolated Actions experiment, copy these files (including `.forgejo/workflows/`) into a trusted owner repository
and enable Actions. This is not an infrastructure deployment workflow. It uses
no repository secrets or package dependencies.

Two eligible jobs exercise checkout, Node tests/build, one-day artifact uploads,
and the 2 CPU / 2 GiB / unprivileged runtime boundary. Observe queuing separately
through Forgejo's job API; repeat the workflow under an out-of-scope fixture owner
to verify that the owner-scoped runner does not execute it. Never print token or
environment values while inspecting jobs.

**Implementation status:** deferred, experimental and not accepted. Podman's
real daemon fixture fails copying the checkout action `.git` archive (`path
escapes from parent`), before checkout executes. A rootless Docker direct-limit
probe passed; its end-to-end acceptance run was interrupted when Actions was
deferred, and is not an acceptance result. Production Actions/runner activation
and labels remain disabled. Future work must still verify checkout/artifacts,
trusted HTTPS, scope exclusion, isolation and repeated deployment.

## Dependency provenance (checked 2026-10-08)

- Node 24.21.0 is the latest released Node 24 LTS (2026-09-07), from the official
  Node distribution index. The job digest is the official `24.21.0-bookworm`
  manifest recorded on 2026-09-19 by docker-library/repo-info commit
  `e5b5c696bc7353d0bf3eff9f70224a1c9daae40b`. Its amd64 manifest is
  `sha256:5a750d3be5e5c80275f8c9a5367c3aed99c2875656590c8d0701c7ee687f5f0a`.
  The current tag was rebuilt 2026-10-06 (only two days old); the workflow
  deliberately does not use that moving tag. Security-update classification of
  the newer base image remains to be reviewed before enabling production jobs.
- Checkout v7.0.1 is commit `3d3c42e5aac5ba805825da76410c181273ba90b1`
  (2026-07-17), requiring Node 24. Runner compatibility remains to be proven.
- Forgejo's upload-artifact fork v5 is commit
  `cb8afe72b42edc798abfb8fcb556cf660d894245` (2025-12-29). The v16 docs demonstrate
  its patched v4 predecessor; v5 compatibility is to be tested, not assumed.
  Do not substitute GitHub's unpatched artifact actions.

Sources: `https://nodejs.org/dist/index.json`,
`https://hub.docker.com/v2/repositories/library/node/tags/24.21.0-bookworm`,
`https://raw.githubusercontent.com/docker-library/repo-info/e5b5c696bc7353d0bf3eff9f70224a1c9daae40b/repos/node/remote/24.21.0-bookworm.md`,
Forgejo action repository tag/commit APIs, and
`https://forgejo.org/docs/v16.0/user/actions/advanced-features/`.
