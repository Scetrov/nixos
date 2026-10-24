# Private GitHub SBOM uploads

The collector downloads trusted GitHub Actions CycloneDX artifacts and uploads
BOMs to private Dependency-Track. **Its job ends when the upload API accepts the
BOM and returns a token.** It does not verify internal BOM processing, query
inventory, poll processing tokens, or correlate success logs. An `uploaded`
message means accepted upload, not verified inventory correctness.

## Producer contract

The approved first source is independent of Forgejo mirror policy:

| Field | Value |
| --- | --- |
| Repository | `Scetrov/efctl`, ID `1166984576` |
| Workflow | `.github/workflows/ci.yml`, ID `238717662` |
| Eligible event/ref | Successful completed `push` on `refs/heads/main` |
| Artifact | `cyclonedx-sbom-v1` |
| Archive layout | Exactly one regular file, `bom.json` |
| Format | CycloneDX JSON 1.6 |
| Retention | 30 days |
| Poll / recovery | Every 15 minutes / previous 7 days |
| Target | Pre-provisioned `efctl`, version `main`, UUID `3761ac8d-a1ce-4b1e-bfa6-7ae29141160a` |

PR/fork artifacts are never eligible. Repository and source-repository IDs,
workflow identity, event, branch and head SHA must match API metadata; filenames
alone establish no trust. A rerun must publish an artifact created during the
current attempt. Missing artifacts are reported and do not prevent a newer run
from uploading. Once a newer upload has been accepted, earlier runs are stale
and are not backfilled over it. This is an inventory uploader, not an archive of
every historical SBOM.

The efctl producer change adds generation and upload steps only on main pushes.
It uses `cyclonedx-gomod v1.12.0`, the current release checked during implementation,
with the Linux amd64 archive pinned to SHA-256
`004b9f5cc595b797fb5423e2ae4c97bcf0f18c712ed2faee1640b09e5efd6d15`.
It requests JSON 1.6 explicitly and uses `actions/upload-artifact v7.0.2`, pinned
to `cf430e030ddbb5b0abf93d22962f4752f3646cd9`. Both releases were more than seven
days old when selected. No Dependency-Track URL or credential is given to CI.

Producer generation happens in CI, never on the collector. A successful overall
workflow is required even when the SBOM-producing job itself succeeded.

## Packaging and limits

The NixOS module is imported by `dependency-track.nix` and disabled by default.
It packages Python/jsonschema from the existing nixpkgs input, plus official
CycloneDX schemas at immutable upstream commit
`55343ba19dee1785acf1ce9191540d5fd7b590db`. Each schema and its SPDX/JSF resources
has a fixed-output SHA-256 pin in the module. Schema references resolve only
against the packaged registry; no remote schema fetching occurs at runtime.

Bounds are deliberately fixed for this first slice:

- Compressed artifact: 10 MiB; expanded BOM: 50 MiB; one ZIP member.
- No extraction to disk; reject unsafe paths, symlinks, special/encrypted files,
  duplicate members/JSON keys, malformed BOMs and digest mismatches.
- JSON depth: 64; JSON value nodes: 500,000.
- GitHub pages: 20 of 100 entries per listing; API response: 5 MiB.
- Read requests: 30-second timeout, three attempts, bounded backoff. Long rate
  limits defer to the next timer invocation rather than sleeping indefinitely.
- Uploads: at most three persisted attempts per artifact/run/target, one per
  poll. No unbounded in-process upload retry.
- Service: 300 seconds, 512 MiB memory, 16 tasks, 64 MiB maximum file size.

The process runs as a dedicated unprivileged user. Systemd provides a private
scratch directory, protected filesystem and runtime credentials. A nonblocking
file lock prevents overlapping instances. It creates no inbound listener, DNS
alias, firewall rule, runner or tunnel. HTTP code permits only GitHub API calls,
HTTPS artifact-storage redirects, and the configured HTTPS Dependency-Track
origin. GitHub authorization is **not** forwarded to storage redirects. Existing
host firewall policy is unchanged; this is not a per-destination kernel egress
firewall for GitHub's changing IP addresses.

## Credentials and configuration

Create a **dedicated SBOM GitHub App**, separate from `Richard's Grafana Dashboard`.
Grant only **Actions: read** and the automatically required **Metadata: read**.
Disable webhooks and user OAuth for this polling-only App; no callback URL,
webhook receiver, client secret or Dependency-Track credential is needed.
To install it across your organisations, make the App installable by those
accounts (GitHub calls this a public App); this visibility does not grant anyone
your private key or repository access. Install it separately in each account or
organisation, choosing **All repositories** if you want to cover future projects.
Record the **App ID** and each **installation ID**. Organisation policy/approval
may be needed before the installation's requested permissions take effect.

Configure the installation IDs as an explicit array. For each allowlisted
repository, the collector resolves its installation using an App JWT, checks it
against that array, and mints a token restricted to that repository ID and
Actions read. Different organisations use their respective installations;
repositories in the same installation still get individually scoped tokens.
Tokens expire after about an hour; they are cached only in memory and refreshed
60 seconds before expiry. Each oneshot starts with a fresh cache. Authentication
failures fail the poll without falling back to a PAT or the Grafana App. Neither
an all-repository installation nor adding an installation ID automatically adds
trusted producers. The App's signing key can access its installed scope, so keep
it protected even though individual issued tokens are narrower.

Find the App ID on the App's settings page. Each installation ID is the numeric
ID in that account/organisation's installation settings URL. Put these public
IDs in `githubAppId` and `githubInstallationIds` below; they are not client secrets.
Use `./scripts/visecret.sh` to store the private key as multiline
`sbom_bot_github_private_key` in encrypted `src/secrets.yml`. The public App ID
and installation ID list belong in `sbom_bot_github_app_id` and
`sbom_bot_github_install_ids`. Do not paste the PEM into chat or commit a
plaintext `.pem` file. The vault key is specific to this App; no Grafana
credential or permission is changed.

Authentication follows GitHub's documented [JWT contract](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app)
and [installation-token scoping](https://docs.github.com/en/rest/apps/apps#create-an-installation-access-token-for-an-app).

Provision a pre-created Dependency-Track project and a dedicated API team/key
with `BOM_UPLOAD`, restricted to the approved project through server-side access
control. The runtime collector needs neither project creation nor
`VIEW_PORTFOLIO`. Upload uses the configured UUID with `autoCreate=false`; SBOM
names/versions cannot redirect it to a different project.

Store `sbom_bot_github_private_key` (the complete RSA PEM) and
`dtrack_sbom_collector_token` in encrypted
`src/secrets.yml` using existing Ansible Vault procedures. The secrets role also
accepts the older `github_sbom_collector_private_key` name. Set inventory variable
`github_sbom_collector_enabled: true` to validate and render them through the
existing secrets role, and deploy them
as `/root/secrets/github_sbom_collector_private_key.age` and
`/root/secrets/dtrack_sbom_collector_token.age`. The module expects their decrypted
runtime files via systemd `LoadCredential`; plaintext must never enter a Nix
expression, command argument, Git history or ordinary journal. Secret rendering
and team/project provisioning must be configured before activation; the module
alone does not create API keys or modify the vault.

Example host configuration (replace the placeholder with the approved real
project UUID; this example deliberately cannot activate as written):

```nix
scetrov.services.github-sbom-collector = {
  enable = true;
  reportOnly = true; # Review discovery before enabling uploads.
  githubAppId = 0; # Replace with the dedicated App's actual numeric ID.
  githubInstallationIds = [ ]; # Replace with installation IDs, one per account/org.
  sources = [ {
    repository = "Scetrov/efctl";
    repositoryId = 1166984576;
    workflowId = 238717662;
    branch = "main";
    artifact = "cyclonedx-sbom-v1";
    path = "bom.json";
    project = "3761ac8d-a1ce-4b1e-bfa6-7ae29141160a";
    version = "main";
  } ];
};
```

Multiple explicit records are supported without code changes. Each target UUID
must have one configured producer to keep ordering unambiguous. Release/tag
mappings are not supported in the initial slice; do not map release versions
implicitly onto the rolling main project. Adding another branch requires a
separate pre-provisioned target. A BOM upload updates that target's inventory;
it does not merge a history of snapshots.

Use the existing targeted deployment entry point, for example
`./scripts/play.sh --limit habiki --tags dependency-track`, only after reviewing
its full plan/host drift and configuring the required credentials and UUID.
The `dependency-track` tag includes the existing NixOS flow; it is not a
collector-only rollout. Start in report-only mode, inspect eligible run/artifact
IDs, then set `reportOnly = false` through automation. Report-only mode never
downloads or uploads artifacts or writes acceptance checkpoints.

## State, retries and recovery

`/var/lib/github-sbom-collector/state.json` is service-owned/private. It stores
per-target accepted repository/workflow/run/attempt, artifact ID/digest,
configured version, returned token and upload time. It contains no API bearer
credentials. State replacement is atomic and fsynced. A persisted attempt count
is written before each upload; the accepted checkpoint is written immediately
after the token is returned. Accepted uploads are skipped after restart.

There is an unavoidable at-least-once window if the API accepted an upload but
the connection broke or the process crashed before its token/checkpoint was
persisted. The next poll may resubmit, within the three-attempt budget. Do not
claim exactly-once delivery. Accepted uploads are not retried merely because
Dependency-Track later fails to process them.

- **Exhausted attempts:** inspect the redacted failure and Dependency-Track/API
  availability. Prefer a deliberate new producer run after fixing the cause.
  Do not delete all checkpoint state, which could replay older inventories.
- **Missing/expired artifacts or outages beyond seven days:** rerun the current
  approved main workflow to publish a fresh artifact. Do not ingest a PR artifact
  or an older inventory as an ad-hoc substitute. The timer is persistent but
  cannot recover artifacts GitHub has deleted.
- **Credential rotation:** add a new private key to the dedicated App, update
  `sbom_bot_github_private_key` in the encrypted vault and deploy through
  secret automation, then revoke the old key after a successful poll. Systemd
  loads fresh credentials at the next service start; accepted-upload checkpoints
  remain intact. Installation tokens are generated automatically, not stored in
  the vault. Rotate the separate Dependency-Track API key through its own team.
- **Target/policy change:** a producer or configured version change on a UUID
  with accepted state fails closed. Provision a new explicit target or perform a
  deliberate reviewed checkpoint migration; do not silently reuse its ordering.
- **Rollback:** disable the collector declaratively, deploy to Habiki only, and
  revoke dedicated credentials if retiring it. Retain checkpoints and existing
  Dependency-Track projects/inventory. Disabling does not delete them.

## Observability

Structured journal messages already flow through Alloy to Loki. The journal
relabel sets `service=github-sbom-collector` for this unit. Query
`{service="github-sbom-collector"} | json` and distinguish `eligible`,
`uploaded`, `failed`, and `poll_complete` events. Failure reasons are fixed codes,
not response bodies or downloaded content. Tokens are not printed.

A public, credential-free metrics file at
`/var/lib/github-sbom-collector-metrics/collector.prom` is read by the existing
Alloy unix textfile exporter and forwarded through the existing Prometheus path
(`job="node"`, external `host` label). The checkpoint directory stays private.
Metrics cover per-poll uploads, skips, eligible artifacts, failures, rejections,
expired artifacts, backlog count/age, last poll and last accepted upload times.
The existing Dependency Track service dashboard shows last accepted upload age,
backlog age, poll failures, rejected artifacts and expired artifacts. These are
transfer signals, not verified internal processing.

Use `github_sbom_collector_failed > 0` and
`time() - github_sbom_collector_last_poll_timestamp_seconds > 3600` for transfer
failure/stalled-poll checks. `github_sbom_collector_backlog_age_seconds` is the
age of the oldest downloadable artifact not yet accepted in that poll.
`github_sbom_collector_expired` is a retention gap, not a backlog. Last-upload age
is not an error by itself for an idle repository. Dependency-Track's UI failure
presentation has not been verified.

## Target provisioning

Project, team, `BOM_UPLOAD` permission and project ACL mapping are provisioned by
the existing Dependency-Track configuration role when
`github_sbom_collector_provision: true`. It calls
`scripts/provision_github_sbom_target.py`, which does not print credentials.
Portfolio ACL stays unchanged unless `github_sbom_enable_portfolio_acl: true`.
No upload key is issued while ACL is disabled, or if the team already has a key
that is not recorded in the vault. A newly issued key is appended to encrypted
`src/secrets.yml` as `dtrack_sbom_collector_token` and is not rotated
automatically. Record the printed project UUID in the collector source mapping
before enabling uploads. The role consumes the script's sanitized JSON result;
normal provisioning does not write evidence into a temporary change directory.
An optional `DT_EVIDENCE_PATH` is only for an explicitly selected operator-owned
output file whose parent already exists, not an operational OpenSpec dependency.

## Validation and rollout status

Run `nix-build --no-out-link tests/github-sbom-collector-eval.nix -A check` for
network-free deterministic collector tests inside the Nix build sandbox, including
the actual integrity-pinned schemas. Evaluate the fixture with `enable=false` to
confirm no service/timer is created. The tests cover provenance, unsafe artifacts,
retry/crash windows, accepted-upload restart/no-op behavior, explicit targets and
redaction; they deliberately do not assert internal processing success.

Run `nix-shell -p python3Packages.jsonschema python3Packages.cryptography --run 'PYTHONDONTWRITEBYTECODE=1 python3 -m scripts.tests.run_github_sbom_upload_integration'` for a real disposable 4.14.5 acceptance check. It honors the initial `FORCE_PASSWORD_CHANGE` login response, changes the default bootstrap password to a random in-memory value, creates a temporary BOM_UPLOAD-only team/key, and exercises real uploads plus repeat/restart behavior. All credentials are redacted and the container/data are removed; this does not contact production or verify internal processing.

The first production upload is accepted. Run `39319650171` artifact
`12219308929` was uploaded to project `3761ac8d-a1ce-4b1e-bfa6-7ae29141160a`,
version `main`. Repeat and restart polls skipped it. The checkpoint stores the
returned token and no GitHub credential. Historical runs without the new artifact
are reported as missing; they are not backfilled over the newer accepted upload.
`TimeoutStartSec=300` bounds the oneshot. `RuntimeMaxSec` does not apply to
`Type=oneshot` and is not used.

Issue #27 asks for internal processing evidence. The operator removed that from
collector acceptance. Do not report it as verified, and do not close #27 on upload
acceptance alone.
