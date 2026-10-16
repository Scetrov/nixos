# Verification — 2026-10-16

## Reproduction and Local Tests

`python3 scripts/tests/test_hermes_auth_expiry.py` initially failed authenticated GET/HEAD login recovery with `200 != 302`: the original ingress reached the application rather than resuming the return target. After the fix, all 10 container test methods pass, including modeled API expiry → Authentik navigation → accepted-cookie return → original session.

Security cases cover invalid/missing cookies, spoofed identity headers, Authentik 401/403/500, external URLs, protocol-relative paths, backslashes, control characters, nested encoding, dot segments, login loops, unsupported query/fragment targets, and POST preservation. An initial fallback regression exposed Caddy interpreting `/` as a matcher; explicit `redir * / 302` fixed it and all fallback cases pass.

Bubblewrap offline unittest discovery passed 18 tests, with the 10 container methods intentionally skipped there and executed separately. Full `pre-commit run --all-files` passed, including redacted Gitleaks. The Git pre-commit hook is installed.

## Deployment

The operator requested deployment and push to main. Remote main had three unrelated CodeQL commits; after explicit fetch/fast-forward approval, local main was safely advanced to `7f109b5` without changing the staged fix.

`./scripts/play.sh --limit habiki --tags hermes-auth -- --syntax-check` passed.

`./scripts/play.sh --limit habiki --tags hermes-auth` succeeded: `ok=4 changed=2 unreachable=0 failed=0`. Only `hermes-auth.caddy` needed copying; existing `caddy.nix` matched the local checksum. No channel update, secret refresh, OpenTofu apply or blanket restart was invoked.

Activated system: `/nix/store/r9247b3hsc8dl92qwzyp8y5ssyv0c1kf-nixos-system-habiki-26.05.11985.26f4107e47e3`.

Deployed and local ingress SHA256: `813ce94ad4312dd2702674251c20545cefa143120e392f4543aceb4582c20eec`.

Caddy, Hermes WebUI and Hermes agent remained active with unchanged service start timestamps. The recent error-level Caddy journal contained zero entries.

Public no-cookie checks, without following redirects or recording OAuth query parameters:

- `/` and `/login?next=…`: 302 to `identity.net.scetrov.live`.
- `/login?next=…` with a spoofed identity header: still 302 to Authentik.
- `/api/projects` and `/health`: 401, `Cache-Control: no-store`, no Location.

The authenticated return branch is verified in the pinned-Caddy fixture, not in a live authenticated browser. The agent browser cannot use the operator's passkey; final browser acceptance remains with the operator.

## Archive and Isolation

No active OpenSpec change existed for this small fix. This retrospective completed-change record is placed directly in the archive before the final commit; the canonical expiry specification is synchronized.

Offline tests used Bubblewrap with no network and project-only writes. The operator explicitly approved the rootless Podman fixture outside Bubblewrap: pinned Caddy image, temporary read-only Caddyfile, random localhost published port, no credentials or persistent application state, automatic cleanup. Its default container network permits egress. Deployment/SSH verification used operator-authorized host networking and sudo on Habiki; Git fetch was separately authorized. Pre-commit and signed commit/push use the repository's standard host-side workflows.
