# Immich on Habiki

Immich 3.3.1 is served at **https://immich.net.scetrov.live** through Caddy,
using the existing `scetrov.live` wildcard certificate. The application binds
`127.0.0.1:3000`; do not open port 3000 or add Caddy forward authentication.
The existing unstable package/channel selection is unchanged by this integration.

## Deployment

Recovery administrator: `git@scetrov.live`. Its strong password is generated once
in encrypted `src/secrets.yml`; never rotate it implicitly or paste it into chat,
CLI arguments or logs. Provision through the existing PyYAML-capable environment:

```bash
.venv/bin/python scripts/provision_immich_vault.py
./scripts/play.sh --limit habiki --tags immich -- --syntax-check
./scripts/play.sh --limit habiki --tags immich
```

The `immich` tag must be used alone, limited to Habiki. It applies only the
Immich Authentik binding dependency graph through `scripts/tofu.sh`, refreshes
matching sensitive outputs into encrypted `src/generated-secrets.yml`, then
loads Ansible variables, validates credentials, generates/copies protected age
files and rebuilds NixOS. Missing/placeholder credentials fail closed. Do not use
`--skip-generated-refresh`; do not call OpenTofu directly. Targeted OpenTofu
applies intentionally exclude unrelated resources; review their warnings.

This consumer run skips channel refreshes, unrelated container restarts and
Frontier Indexer transition operations. A NixOS rebuild still activates the
**complete host configuration**; inspect outstanding host changes first.

Root-readable agenix files feed the NixOS module's native `_secret` facility.
Systemd `LoadCredential` and runtime secret substitution produce
`/run/immich/config.json`, not a secret-bearing Nix-store derivation. Extra
systemd credentials feed the recovery bootstrap. Do not print these files.
The file-based configuration disables settings editing through the web UI;
change settings through automation instead.

## Browser and mobile

Select **Sign in with Authentik** at the HTTPS URL. Authorization reuses the
**All Applications** group (currently scetrov); General User alone is not enough.
New authorized OIDC users are provisioned automatically. Automatic SSO redirect
is disabled so local recovery remains accessible.

Use a supported Immich mobile client compatible with server 3.3.1. Enter the
same HTTPS URL and select OAuth login. Allow the OS to reopen Immich, enable
backup, grant photo/background permissions and test foreground/background
sync. Browser login alone does not prove mobile backup works.

Strict Authentik callbacks:

- `https://immich.net.scetrov.live/auth/login`
- `https://immich.net.scetrov.live/user-settings`
- `app.immich:///oauth-callback`

Native API keys, media requests and websocket connections go directly through
Caddy to Immich, without an Authentik HTML proxy login.

## Local administrator recovery

Retrieve the recovery credential through an operator-controlled encrypted Vault
workflow (for example `scripts/visecret.sh`); do not print the decrypted vault or
copy the password into a shell command. Open the HTTPS login page and use local
email/password login as `git@scetrov.live`, not the OAuth button.

On each service start, `immich-bootstrap.py` polls the loopback API. Only when
`/api/server/config` reports `isInitialized: false` does it use the native
`POST /api/auth/admin-sign-up` endpoint. It then verifies the configured account
can log in as administrator and invalidates its temporary session. An initialized
instance with a mismatched account/password fails startup verification rather
than resetting anything. Changing a Vault password alone does **not** rotate an
existing Immich password: use the supported application workflow, then update
Vault to match before rebuilding.

Test recovery with Authentik unreachable in an isolated test-client session,
without stopping shared identity infrastructure or locking out other services.
Verify local login and administrator access with OAuth unavailable. This check
must be performed explicitly; bootstrap success alone is not an outage test.
If reconciliation fails, inspect `immich-server.service` and account state; do
not delete database/media directories or run a storage reset.

## Storage-preserving rollback

Through automation, set `services.immich.settings.oauth.enabled = false` while
retaining `passwordLogin.enabled = true`, the bootstrap/recovery credentials,
loopback listener and Caddy HTTPS host. Deploy with the same targeted command.
Do not revert to the old wildcard/network listener or reopen port 3000.
After native local access is verified and OIDC sessions no longer matter, remove
the Immich provider/application/binding through a separately reviewed OpenTofu
plan using `scripts/tofu.sh`; adapt the targeted deployment step before removing
its target. Do not remove shared users/groups or unrelated identity resources.
Keep database/media storage and existing NixOS database/Redis configuration intact.
No user migration, storage initialization/reset or package upgrade is part of this
change or its rollback.

## Verification checklist

Run network checks from a **different host**, with certificate verification on:

```bash
curl --fail --silent --show-error https://immich.net.scetrov.live/api/server/version
curl --fail --silent --show-error https://immich.net.scetrov.live/api/server/features
# Must fail to connect (not return an Immich response):
curl --connect-timeout 3 --max-time 5 http://10.229.10.2:3000/api/server/version
```

Record each result explicitly; unavailable client/manual checks are **unverified**:

- Valid HTTPS certificate/hostname and functional web UI.
- Remote port 3000 blocked; on Habiki, listener only `127.0.0.1:3000`.
- Authorized browser OIDC login/new account; disallowed General User rejected.
- Supported mobile OAuth callback and foreground/background backup.
- Native API-key upload/download with matching media, including a representative
  large upload. Use protected header files or a trusted client, not API keys in
  shell arguments; verify responses are not an Authentik HTML login page.
- Authenticated realtime/websocket connection works through the HTTPS endpoint.
- Local administrator login with Authentik unavailable.
- Restart/rebuild persistence of OIDC, local recovery and stored media.
- Service logs reach the existing Grafana journal/Loki pipeline.

For a service restart use targeted automation, for example:

```bash
ansible habiki -i src/inventory.yml --become \
  -m ansible.builtin.systemd_service -a 'name=immich-server state=restarted'
```

Do not close issue #30 until all required deployed checks have passed. Do not
finalize a change while implementation/required verification is blocked.
The retired implementation checklist marked these checks complete but did not
include a separate per-check live evidence record. Preserve that limitation;
this consolidation does not certify a new mobile/recovery/security test.

## Troubleshooting and regression checks

Inspect the journal without dumping runtime files or session/API tokens:
`journalctl -u immich-server -u caddy --since '-15 minutes'` on Habiki. Existing
Alloy journal collection sends these logs to Grafana/Loki. Use the existing
[Grafana error-investigation procedure](../.agents/instructions/grafana-error-investigator.instructions.md)
and [investigation script](../.agents/skills/grafana-error-investigator/scripts/investigate_errors.sh).
Avoid changing shared identity policy, log pipelines or unrelated proxy hosts to
work around an Immich login failure.

```bash
.venv/bin/python -m unittest discover -s scripts/tests -p 'test_immich.py'
.venv/bin/python -m unittest discover -s scripts/tests -p 'test_render_generated_secrets.py'
nix-instantiate --eval --strict --json -I nixpkgs='<installed-nixos-channel>' \
  -I nixos-unstable='<installed-unstable-channel>' tests/immich-eval.nix
./scripts/tofu.sh -- validate
pre-commit run --all-files
```

Use actual installed channel paths in the evaluation command. The fixture
asserts the security boundary without reading production secrets or activating
services. Version-specific references: [OAuth](https://github.com/immich-app/immich/blob/v3.3.1/docs/docs/administration/oauth.md),
[reverse proxy](https://github.com/immich-app/immich/blob/v3.3.1/docs/docs/administration/reverse-proxy.md),
[configuration files](https://github.com/immich-app/immich/blob/v3.3.1/docs/docs/install/config-file.md).
