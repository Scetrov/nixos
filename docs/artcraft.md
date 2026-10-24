# ArtCraft static WASM suite

## Implementation status

Work in progress under `openspec/changes/host-artcraft-wasm/`. All thirteen
packages and icons were published on Habiki and targeted identity provisioning
and NixOS activation succeeded. Deployment then stopped at an unsupported Blocky
reload. Live DNS/authentication/logging and production browser acceptance remain
unverified; do not treat the suite as accepted.

The operator confirmed **All Applications** on 2026-10-24 for both shared proxy
authorization and launcher visibility. Do not change group memberships or grant
General User access.

## Pinned inputs

`config/artcraft.yml` lists thirteen explicit official GitHub web ZIP URLs,
filenames, versions and SHA-256 checksums. All thirteen ZIPs were downloaded on
2026-10-24 and their computed hashes matched GitHub release-asset digests.
Immutable source revisions identify official icon provenance only; icon hashes
were verified from bytes during the earlier provenance check. Icons must be
served locally by existing branding automation, not fetched by browsers upstream.

GitHub release APIs were checked on 2026-10-24. Selected stable releases were at
least seven days old. Newer releases are deferred; no critical-security exception
was assumed. Dates below are UTC.

| Editor | Selected release | Published (UTC) | Latest release observed (held back) |
| --- | --- | --- | --- |
| PhotoCraft | v0.9.0 | 2026-10-14 16:36:26 | v0.15.1 (2026-10-23 22:44:33) |
| PdfCraft | v0.8.0 | 2026-10-14 15:21:59 | v0.13.0 (2026-10-23 00:43:39) |
| FilmCraft | v0.8.0 | 2026-10-14 16:28:45 | v0.12.0 (2026-10-23 00:35:04) |
| VectorCraft | v0.12.0 | 2026-10-16 12:26:40 | v0.16.0 (2026-10-23 01:01:59) |
| LightCraft | v0.8.0 | 2026-10-14 15:30:00 | v0.13.0 (2026-10-23 00:35:08) |
| DesignCraft | v0.8.0 | 2026-10-14 14:15:00 | v0.12.0 (2026-10-22 20:50:19) |
| EffectCraft | v0.10.0 | 2026-10-14 16:16:19 | v0.16.0 (2026-10-23 00:35:00) |
| GridCraft | v0.7.0 | 2026-10-14 15:36:59 | v0.11.1 (2026-10-22 20:44:41) |
| CADCraft | v0.7.0 | 2026-10-14 15:29:49 | v0.12.0 (2026-10-23 00:34:58) |
| DeckCraft | v0.7.0 | 2026-10-14 15:04:51 | v0.10.0 (2026-10-22 20:44:35) |
| SoundCraft | v0.7.0 | 2026-10-14 16:16:07 | v0.12.1 (2026-10-22 20:30:32) |
| WordCraft | v0.7.0 | 2026-10-14 13:56:11 | v0.10.0 (2026-10-22 20:44:31) |
| FigCraft | v0.6.0 | 2026-10-14 14:26:24 | v0.10.0 (2026-10-22 20:44:45) |

Release evidence is available at
`https://api.github.com/repos/storytold/<slug>/releases`; commit resolution at
`https://api.github.com/repos/storytold/<slug>/commits/<release>`.

## Download and publication automation

`src/artcraft.yml` runs the isolated `artcraft` role without vault credentials.
Check-only is the default. Ansible downloads each ZIP with a pinned SHA-256;
`scripts/artcraft.py` verifies it again before safe extraction. No source builds,
upstream scripts, toolchain installation or containers are used. Traversal, links,
special files, duplicates and oversized archives are rejected. Complete bundles
are retained except `_headers` and `.htaccess`, which are hosting instructions
rather than browser assets. Caddy must implement relevant headers itself.

Candidates must contain valid WASM, entry HTML and its referenced local assets,
including inline module/boot URLs. Unchanged candidates are reused only after
download and manifest integrity checks. Failed downloads/checks do not publish.
Atomic publication retains one previous version; rollback swaps current/previous.

Check all thirteen (or select one as shown):

```sh
ansible-playbook -i src/inventory.yml src/artcraft.yml --limit habiki \
  --tags artcraft-download -e '{"artcraft_select":["photocraft"]}'
```

After package acceptance, add `-e artcraft_publish=true` to publish. Roll back a
selected editor with `-e artcraft_rollback=true`; repeat to switch back.
Neither action changes URLs or authorization. The private download workspace is
`/var/tmp/artcraft-downloads`; publications live in `/var/lib/artcraft`.

Deploy the accepted suite, official local icons, shared identity boundary and
Caddy/DNS on Habiki with:

```sh
./scripts/play.sh --limit habiki --tags artcraft
./scripts/play.sh --limit fyne --tags local-dns
```

The ArtCraft tag requires exactly Habiki and cannot be combined with other tags.
It does not update channels, regenerate secrets or restart unrelated containers.
The full playbook also publishes the suite on Habiki for recovery. Before the
first deployment, review the targeted identity plan and stop on unrelated changes:

```sh
./scripts/tofu.sh -- plan -target=authentik_policy_binding.artcraft_access \
  -target=authentik_policy_binding.artcraft_editor_access -target=authentik_outpost.proxy
```

Launcher-only applications omit protocol providers intentionally. The installed
Authentik 2026.8.3 application API accepts explicit launch URLs without providers,
filters hidden apps and evaluates application policies for launcher visibility.
Actual allowed/denied launcher behavior still requires live acceptance.
Old compilation inputs/cache under `/var/tmp/artcraft-build` are not used by this
flow. No deletion of that pre-existing workspace or image cache is implied.

## Validation evidence (2026-10-24)

- All thirteen official ZIPs downloaded locally to
  `/tmp/artcraft-release-check` and matched their pinned SHA-256.
- `python3 -m unittest scripts.tests.test_artcraft scripts.tests.test_artcraft_configuration`
  with `ARTCRAFT_CADDY` set: 26 passing tests covering
  package safety, inline module/boot assets, checksum/download/candidate failures,
  unchanged-input reuse, atomic preservation and previous-version rollback,
  plus real Caddy route/auth/asset/cache/fail-closed regression checks.
- Ansible syntax checks: both download and targeted deployment playbooks passed.
- `nix-instantiate --eval --strict --json tests/artcraft-eval.nix`: passed.
- `scripts/tofu.sh -- validate` and formatting: passed.
- `pre-commit run --all-files`: all configured hooks passed, including gitleaks.
  The Git pre-commit hook is installed.
- Targeted identity plan: 29 creates (provider, hidden application, thirteen tiles
  and fourteen bindings), one in-place outpost membership update, no deletes or
  unrelated application/group changes.
- Upstream hosting guidance says the current builds do not need COOP/COEP.
  Local isolated Chromium initialized all thirteen editor canvases at their
  intended prefixes with no uncaught exceptions or required-asset HTTP failures.
  The only 404s were the browser favicon and PhotoCraft's documented optional
  font manifest. This is not authenticated production/browser-interaction acceptance.
- PhotoCraft describes its absent external fonts directory as optional.
  VectorCraft's ZIP has no external fonts directory despite hosting documentation
  describing it for releases; upstream says the app runs without it but Arabic
  text displays as boxes. Do not claim complete font acceptance without runtime
  checks or silently supplement/rebuild an upstream bundle.

All thirteen bundles passed extraction and entrypoint/inline-asset checks. Local
browser tests used ephemeral profiles with external DNS blocked and SwiftShader;
no upstream scripts or source builds were run. VectorCraft initialized without
requesting external fonts, but Arabic rendering is not verified.

## Deployment blocker (2026-10-24)

`./scripts/play.sh --limit habiki --tags artcraft` downloaded, verified and
published all thirteen packages, copied the icons, provisioned targeted identity
resources and completed `nixos-rebuild switch`. It then failed at the explicit
Blocky reload because `blocky.service` does not support the systemd reload job:

```text
Failed to reload blocky.service: Job type reload is not applicable for unit blocky.service.
```

No follow-up restart or rollback was attempted. The play recap was 65 successful
tasks, 47 changed, one failed; the final Caddy-active check was not reached.
The deployment log is `/tmp/artcraft-deploy.log` (private, ephemeral). Changes
before the failure remain applied; this was not an atomic whole-suite rollout.

Pending: correct DNS activation through automation with operator approval,
rerun the targeted deployment, propagate DNS on Fyne, verify live authentication,
callbacks, denied assets, tile visibility, local icons and Loki delivery, then
complete production browser interactions and automated preservation/rollback.
Do not archive or commit/PR before successful acceptance.
