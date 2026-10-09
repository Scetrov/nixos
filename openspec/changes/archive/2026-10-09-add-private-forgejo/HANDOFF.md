# Handoff — add-private-forgejo

**Branch:** `main` (uncommitted working tree) · **Current progress:** 14/27 tasks complete

## Current scope (operator decision)

Deploy a private Forgejo Git service on Habiki at
`https://source.net.scetrov.live`, with native Authentik OIDC, Git SSH on 2222,
persistent SQLite/repositories/keys, private DNS/network access, and Grafana
service observability. **Actions/CI is deferred.** The operator chose to retain
experimental runner code disabled, not delete it.

Proposal/design/specs/tasks reflect that scope. The former runner spec is now
`deferred-actions.md` outside the active `specs/` tree. Earlier runner findings in
`implementation-notes.md` are historical, not current acceptance gates.

## Resume instructions

Resume with `/opsx-apply add-private-forgejo` and start at **task 5.1**.
Read `proposal.md`, `design.md`, active `specs/`, and `tasks.md`; use the
“Current scope” section of `implementation-notes.md` before its historical logs.
OpenSpec currently reports schema `spec-driven`, **14 complete / 13 remaining**.
The count changed because runner tasks were removed, not because they passed.

**Do not resume Actions troubleshooting, enable the runner, or add a first-login
registration gate.** Retained runner code is future-work reference only. Current
work is Forgejo service observability, then targeted deployment and acceptance.
Load the applicable Grafana skill before discovering signals or authoring health
visibility. Keep all host changes automated and deployment runs targeted.

## What is complete

- Tasks 1.1–1.3: supported Forgejo/module/source/network/owner checks.
- Tasks 2.1–2.4: Authentik resources and authoritative protected generated-secret
  pipeline with validation/fixtures. Plan validated, **not applied**.
- Tasks 3.1–3.6: private Forgejo service, scoped HTTPS/SSH, shared DNS alias and
  Fyne DNS-only deployment path, protected OIDC reconciliation and local
  persistence/reconciliation fixtures. Live deployment acceptance remains pending.
- Task 4.1: default-off independent experimental runner gate;
  `scetrov.services.forgejo.runner.enable = false` explicitly on Habiki.
  `actions.ENABLED` follows that option and is false for current deployment.
  Service-only Nix evaluation checks no runner account, runtime/daemon/cleanup
  units, timer, registration command, readiness service or egress rules on
  either firewall backend. Retained opt-in runner regression assertions pass.

Latest scoped checks: Nix evaluation, strict OpenSpec validation and whitespace
checks pass; all 12 generated-secret regression tests pass. Retained experimental
Python files pass syntax checks only (no further Actions jobs run). Before scope
change, three cleanup unit tests and the real Alpine Podman daemon regression
passed. No Actions E2E acceptance has passed.

### Repeat the scoped local checks

```bash
nix-instantiate --eval --strict --json --expr \
  'import ./src/roles/nixos/tests/forgejo-eval.nix {}'
python3 -m unittest scripts.tests.test_render_generated_secrets -v
openspec validate add-private-forgejo --strict
git diff --check
```

The Nix evaluation includes retained experimental **configuration assertions**,
not execution of Actions jobs. Do not set opt-in runner fixture variables for
current-scope acceptance. Live OIDC/network/persistence checks remain pending.

## Next tasks

1. **5.1–5.3:** Forgejo-only journal/Loki labels, private authenticated metrics,
   actual service-health signal discovery, declarative Grafana visibility/alerts.
2. **6.1:** targeted Habiki deployment ordering: Authentik → generated-secret
   refresh/validation → runtime secrets → rebuild → OIDC reconciliation.
   **No runner registration or first-login deployment gate.** Owner OIDC login
   remains an access acceptance check after provisioning.
3. **6.2–6.6:** isolated checks, shared-plan blast-radius review, explicit targeted
   Habiki/Fyne rollout, LAN/Teleport/Headscale access/denial, repeat/rotation/
   persistence/observability acceptance and confirmation Actions stays inactive.
4. **7.1–7.4:** runbooks, rollback/snapshot cautions, pre-commit/security review,
   intended-file staging, archive before final signed conventional commit/PR.

## Verified choices and constraints

- Forgejo `pkgs.forgejo` 16.0.5, not module-default LTS. Owner `scetrov` is the sole
  `Forgejo Owners` member; native OIDC grants administration from signed groups.
- Backend `127.0.0.1:3002`; existing wildcard TLS/Caddy; metrics on the same
  loopback listener when configured. Git built-in SSH 2222, persistent host key;
  administrative SSH 22 untouched.
- Allowed private sources: `10.229.0.0/16`, `100.64.0.0/10`,
  `fd0b:281e:d657:3ca1::/64`, `fd7a:115c:a1e0::/48`.
- Both Blocky servers need shared alias `source.net.scetrov.live → 10.229.10.2`;
  Fyne DNS-only path is `scripts/play.sh --limit fyne --tags local-dns`.
- Habiki uses iptables; module also supports nftables. No global SSH 2222 opening,
  router forwarding, public DNS or VPN route/ACL expansion.
- All OpenTofu goes through `scripts/tofu.sh`. Compatible Authentik provider
  2026.5.1 resolves prior `pbm_uuid` skew; last refreshed plan was 6 additions,
  5 in-place changes, 0 destroys. Shared changes require field-level review.
- Authoritative Forgejo OIDC outputs are not yet generated because no apply has
  occurred. Do not deploy incomplete consumers through generic `nixos` tags.
- Bounded accepted exception: upstream OIDC CLI receives client secret in runtime
  argv. Protected runtime input and suppressed diagnostics do not eliminate
  process-inspection risk. Do not extend this exception to safe stdin/file APIs.

## Deferred experimental code

Runner modules/helpers/templates/tests and `examples/forgejo-acceptance/` remain,
but cannot activate just by enabling Forgejo. Podman acceptance failed copying
an action `.git` archive (`path escapes from parent`) before checkout execution.
A dedicated rootless Docker direct cgroup probe passed; its acceptance attempt
was interrupted by scope change. No Docker E2E result or production switch.
The exact interrupted fixture process, transient unit and storage are gone.

Fixture improvements retained: bounded 600-second immutable pull, checked
rootless image-graph cleanup (including same-filesystem overlay bind mount),
isolated action cache, and opt-in dedicated Docker adapter. Experimental runtime
and dependency/security-age decisions need a separately agreed future change.

Nothing has been deployed, committed or archived. No new staging this session;
the pre-existing index still includes the old runner-spec addition until final
staging reconciles it with the working-tree move. See `implementation-notes.md`
for detailed verified facts and historical decisions.
