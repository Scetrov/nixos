# Implementation verification

## Deployment

Operator approved the focused automation, host-side Nix builds, disposable
container tests, and Habiki SSH/sudo access. Executed:

```sh
nix-shell -p age --run './scripts/play.sh --limit habiki --tags hermes-runtime'
```

Result: `ok=12 changed=6 unreachable=0 failed=0`, about 562 seconds. No channel
update, OpenTofu apply, unrelated secret rendering, or blanket container restart
was invoked. NixOS successfully evaluated, built, and activated the module.
Before deployment, 54 tracked remote Nix/Caddy configuration files matched Git
HEAD; generated/hardware files were outside that hash comparison. Caddy routing
files matched the repository exactly.

## GitHub CLI

- Both controller and Habiki nixpkgs provide `gh` 2.102.0, matching the latest
  applicable release returned by https://api.github.com/repos/cli/cli/releases/latest
  (published 2026-09-30, older than the seven-day update deferral).
- Nix source hash: `sha256-txjOmo46nwRxIutYR/lnFgYEWZpkbWC/ilrMAfTaFZc=`.
- Nix vendor hash: `sha256-hsG6wc7AfgPZhkWwO8Xzu4yR54Rp5+Z6yeTjwnI9S+o=`.
- The module's static package built successfully at
  `/nix/store/8ps48sh1rfh6z3y95f6z3ga6kdax2h7d-hermes-gh-2.102.0`.
- `check_hermes_runtime_images.py --gh <built-package>/bin/gh` passed in the exact
  pinned WebUI image, with network disabled and no persistent state/credentials.
- The deployment ran `gh --version` successfully in **both** `hermes-agent` and
  `hermes-webui`, and checked normal unauthenticated errors with token variables
  removed and an isolated CLI config directory.
- Post-deployment inspection confirmed the executable mount is read-only in both
  containers. No optional `GH_TOKEN` is configured. Existing App fields remain
  separate from CLI authentication; their values were not printed.

## WebUI access boundary

The deployed image digest is
`sha256:5fb831ca2a9f3f0b93b84c1ebaaeedf5809d914a33bbf969e5c29a5bb75cb47c`.
Image smoke checks confirmed authentication is disabled with an absent password
and fresh state. The running deployment reports:

- Password variable absent: true.
- Password authentication enabled: false (no persisted password fallback).
- Native trusted-header authentication enabled: false. Existing proxy-related
  environment settings were retained, but are not an additional access control;
  Caddy's enforced Authentik route is the browser boundary.
- WebUI port: only `127.0.0.1:8787`; agent: no published ports.

Public requests without cookies, without following redirects:

| Path | Result |
| --- | --- |
| `/` | 302 to `identity.net.scetrov.live` |
| `/login` | 302 to `identity.net.scetrov.live` |
| `/health` | 401 JSON, `no-store`, no redirect |
| `/api/projects` | 401 JSON, `no-store`, no redirect |

**Authenticated browser acceptance:** the operator confirmed that an
Authentik-authenticated browser opens Hermes without a second password prompt.
This is operator-verified, not a claim based on CDP (which timed out).

## Local validation

- 18 offline unit tests covering environment rendering, runtime deployment scope,
  proxy-only wrapper behavior, recipient encryption, and failure cleanup passed.
- Five disposable Caddy proxy regression tests passed, including authenticated
  requests and denial/redirect behavior without an accepted identity.
- Both changed Nix files passed parse validation; NixOS activation passed.
- Focused playbook syntax validation passed.
- Relevant source-file pre-commit gates passed, including gitleaks with redaction.
- An initial final gate exposed binary age output being modified by text hooks.
  Added a failing regression assertion, then changed the helper to `--armor`;
  all 18 unit tests pass with the fix. Regenerated and redeployed via the same
  focused play (`ok=12 changed=5 failed=0`, about 86 seconds). The resulting
  ciphertext is armored and newline-terminated. `.age` artifacts are explicitly
  Git-ignored and are not included in the commit.
- The regenerated armored artifact passed the formatting gates without any
  ciphertext changes. Full `pre-commit run --all-files` passed all configured
  hooks, including gitleaks, Nix formatting, Authentik ownership, and tofu fmt.

The unit tests used a temporary Nix Python environment containing Jinja2 and
PyYAML, inside Bubblewrap with no network and only the project writable. Approved
host-side exceptions were Nix provisioning/builds, pre-commit, Podman fixture/image
checks, and the targeted deployment/SSH verification. The disposable image check
mounted only the built `gh` file read-only; it did not mount the host Nix store,
credentials, container sockets, or persistent Hermes volumes.

## Rollback

Restore the previous Hermes template, module and Habiki device configuration,
then rerun the same focused play. This re-encrypts the previous environment and
refreshes the shared `.env`. A previous NixOS generation is an emergency fallback
but does not restore encrypted secrets or the copied `.env`. Preserve Authentik
and the loopback-only backend binding throughout rollback.
