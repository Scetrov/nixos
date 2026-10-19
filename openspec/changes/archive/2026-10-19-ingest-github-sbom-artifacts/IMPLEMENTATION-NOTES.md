# Implementation notes

## Operator-approved first slice

The operator approved the following contract during `/opsx-apply`, after read-only discovery, and authorized the minimal producer workflow change in `Scetrov/efctl` plus project/least-privilege identity provisioning through existing automation. No activation has occurred.

- Repository: `Scetrov/efctl`, numeric repository ID `1166984576`.
- Workflow: `.github/workflows/ci.yml`, workflow ID `238717662`.
- Eligibility: successful completed `push` runs on `refs/heads/main`, originating from that repository; PR/fork artifacts excluded.
- Proposed producer addition: artifact `cyclonedx-sbom-v1`, exactly one payload `bom.json`, CycloneDX JSON 1.6. Generation tooling and schema integrity pins still require verification.
- Retention: 30 days; polling: every 15 minutes; supported recovery window: 7 days.
- Compressed artifact bound: 10 MiB; expanded payload bound: 50 MiB. Additional file-count, JSON complexity, time, disk, and pagination bounds remain to be specified before task 1.1 is complete.
- Target: pre-provision `efctl` version `main` through existing automation after checking for an existing exact match. The UUID is not known yet and must not be invented or derived from the payload.
- Version strategy: rolling development inventory only; release/tag versions are not eligible in the initial slice. Explicit additional pre-provisioned mappings will be required for releases.
- Selection is independent of issue #26 and Forgejo mirror policy.

## Read-only discovery evidence

- Originating issue: <https://github.com/Scetrov/nixos/issues/27>.
- GitHub API workflow identity: <https://api.github.com/repos/Scetrov/efctl/actions/workflows/238717662>.
- Inspected efctl CI workflow blob: `54c40b2e58f08d62c9944580a1c7ddb78bee1f63`. Current CI triggers include push and pull requests on main; collector trust must narrow this to push only.
- Inspected artifact metadata for the 14 active non-fork repositories returned by the account repository listing. No names containing `bom`, `cyclone`, or `dependency` were found, including older artifact pages for `void-eid` and `frontier-flow`. This name-based discovery is not evidence that arbitrary artifacts contain no SBOMs, nor approval of any repository.
- Private unauthenticated `/api/version` reported Dependency-Track `4.14.5`, matching the integrity-pinned API image declared in `dependency-track.nix`. This is not evidence of successful BOM processing or a full runtime image-drift check.
- Existing `src/roles/dependency-track-config/tasks/main.yml` configures SSO; it does not declare an ingestion project or a dedicated upload identity. No authenticated project inventory was queried and no vault credentials were read.

## Historical API semantics finding (no longer a blocker)

The proposed design must not equate a processing token becoming idle with successful ingestion.

Version-matched upstream evidence:

1. [`EventResource.java` at 4.14.5](https://github.com/DependencyTrack/dependency-track/blob/4.14.5/src/main/java/org/dependencytrack/resources/v1/EventResource.java): `GET /v1/event/token/{uuid}` reports whether associated tasks are processing. Its documentation explicitly states that `false` does not confirm the token is valid; it only means no processing is associated with it.
2. [`BomResource.java` at 4.14.5](https://github.com/DependencyTrack/dependency-track/blob/4.14.5/src/main/java/org/dependencytrack/resources/v1/BomResource.java): the older `/v1/bom/token/{uuid}` endpoint has the same limitation and is deprecated since 4.11.0. It documents `BOM_UPLOAD` permission.
3. [`BomUploadProcessingTask.java` at 4.14.5](https://github.com/DependencyTrack/dependency-track/blob/4.14.5/src/main/java/org/dependencytrack/tasks/BomUploadProcessingTask.java): a runtime processing exception emits `BOM_PROCESSING_FAILED`; successful processing emits `BOM_PROCESSED`. The token polling response alone does not carry this distinction.

The live OpenAPI probe timed out; no authentication or configuration changes were attempted. The semantic finding above comes from successfully fetched version-matched upstream source, not from that failed probe.

**Implementation pause:** confirm a supported, durable success/failure correlation mechanism before building the checkpoint state machine. Options to investigate include authenticated project BOM/inventory read-back or existing-path notification/log evidence correlated to the exact upload. Neither is verified yet. Do not introduce a new ingress endpoint or silently broaden permissions. The design expressly requires exposing an inadequate completion signal as a blocker rather than claiming success.

## Authenticated read-back investigation

The operator selected read-back investigation. Results are recorded in [READBACK-RESEARCH.md](READBACK-RESEARCH.md), citing immutable upstream source. Project timestamps reflect import transactions and inventory export requires `VIEW_PORTFOLIO`, but exports replace the original serial number and the reviewed REST resources do not expose a token-correlated import receipt. Read-back alone cannot distinguish the exact upload's success from an identical pre-existing inventory or another outstanding writer/import. A constrained single-writer design remains possible only with explicit additional assumptions and validation; it has not been approved or tested. Recommended next step: investigate token-correlated success/failure logs through the existing observability path, without adding ingress. No authenticated live requests or grants were made.

## Operator-approved scope correction

The operator explicitly clarified that the collector's job ends when Dependency-Track accepts the upload. Internal ingestion correctness is outside scope. The earlier completion-verification investigation was unnecessary and is closed by this scope decision, not by proving internal success. `READBACK-RESEARCH.md` remains historical research, not an implementation requirement. Do not add token polling, read-back, log correlation, or extra permissions for processing verification. Persist the acceptance/token, skip repeats, and retry transfer failures. No assumption is made about which UI element reports internal failures.

## Implementation progress after scope correction

- Implemented the collector in `src/roles/nixos/files/etc/nixos/pkgs/github-sbom-collector.py`: trusted GitHub selection, bounded in-memory ZIP handling, packaged local schema validation, digest checking, trusted UUID upload with `autoCreate=false`, durable acceptance/token checkpoints, stale-run protection and bounded transfer retries. No internal processing verification.
- Added the disabled-by-default/report-only NixOS module, runtime systemd credentials, locking, sandbox/resource bounds, Persistent timer, and existing-path Alloy textfile metrics. `dependency-track.nix` imports it; production host configuration does not enable it.
- Added optional existing secrets-role integration for dedicated vault values, encrypted only to existing operator recipients and Habiki. No production credentials were generated/read or committed.
- Added the minimal producer generation/upload steps to the existing local `/home/scetrov/source/efctl/.github/workflows/ci.yml`. This checkout's existing action versions differ from remote main; only new steps were added, without rebasing or changing its existing pins. The change is staged locally, not committed or published.
- Operational contract and recovery procedures: `docs/github-sbom-ingestion.md`. Additional resource bounds are now specified there.

Validation:

- `openspec validate ingest-github-sbom-artifacts --strict`: passed before and after the scope correction.
- `nix-build --no-out-link tests/github-sbom-collector-eval.nix -A check`: passed, 27 tests with the real integrity-pinned schema resources (including first-login password-change regression coverage). No skipped tests in this build.
- Enabled/disabled NixOS fixture evaluations: passed; disabling creates no collector service/timer/credentials.
- `actionlint /home/scetrov/source/efctl/.github/workflows/ci.yml` through nix-shell: passed.
- NixOS repository `pre-commit run --all-files`: passed all configured gates, including redacted gitleaks and nixfmt. The efctl full Go/security hook suite has not been run; its existing gocyclo hook declares mutable `@latest`, and this change does not modify that unrelated configuration.

Disposable acceptance check now passes. Diagnosis reproduced HTTP 401 and inspected its redacted, non-secret reason: `FORCE_PASSWORD_CHANGE`. The upstream default admin is deliberately created with a forced password change; the original probe discarded this response and incorrectly treated it as generic authentication failure. The corrected fixture follows `/api/v1/user/forceChangePassword` with a random in-memory password, then logs in, creates a dedicated team with only `BOM_UPLOAD`, and generates its API key through `/api/v1/team/{uuid}/key`. No production API key is involved. Version-matched sources: [default account creation](https://github.com/DependencyTrack/dependency-track/blob/6d0406a27531bc6db24cb84e7fdf3e54ee83b281/src/main/java/org/dependencytrack/persistence/DefaultObjectGenerator.java#L139-L142), [login reason and password-change flow](https://github.com/DependencyTrack/dependency-track/blob/6d0406a27531bc6db24cb84e7fdf3e54ee83b281/src/main/java/org/dependencytrack/resources/v1/UserResource.java#L89-L229).

Reproducer/regression command: `nix-shell -p python3Packages.jsonschema python3Packages.cryptography --run 'PYTHONDONTWRITEBYTECODE=1 python3 -m scripts.tests.run_github_sbom_upload_integration'`. It now passes against the exact pinned 4.14.5 image: real collector uploads accepted for two configured fixture targets, tokens/checkpoints persisted, zero extra submissions after simulated restart/repeat, and malformed archives rejected before submission. No internal processing polling or inventory read-back was performed. Generated passwords/API keys stay in memory and are never printed. Disposable containers and temporary data are removed after each run; the retained diagnosis container is also removed at the end of the investigation. The production API was not changed.

## Dedicated GitHub App decision and implementation

The operator rejected extending the Grafana observability App and selected a separate SBOM GitHub App, potentially installed on all repositories across several organisations. Implemented one public App ID, a protected RSA PEM private key and a nonempty array of approved installation IDs. `GitHubApp` resolves each configured repository's installation, rejects IDs outside the array, and requests Actions-read tokens restricted to that repository's stable ID. It never requests a default all-repository token. All-repository installation coverage does not expand the producer allowlist. Private keys, signed App JWTs and installation tokens remain in memory/runtime credential paths, never in checkpoint state or logs. Tokens refresh 60 seconds before expiry; every oneshot starts with a fresh cache.

NixOS now exposes `githubAppId`, `githubInstallationIds` and `githubPrivateKeyFile`; the secrets role renders `github_sbom_collector_private_key.age` from the dedicated vault key. This replaces the earlier, unactivated static GitHub token input. Existing Grafana App registration, permissions, key and exporter are unchanged. No client secret or user OAuth flow is used. Cryptography comes from the existing nixpkgs package set already used by repository observability, not an unpinned new Python installation.

Verification: 37 sandboxed collector/authentication tests pass, including two installations, repository token scopes, RS256 signatures, cache refresh, unknown/suspended/wrong-App installation rejection, permission/expiry rejection and redaction. Enabled/disabled NixOS fixture evaluation passes; missing or duplicate installation IDs produce a failing activation assertion. Disposable DTrack acceptance/restart/repeat/malformed-archive integration passes again with this code. A fixture assertion-reporting probe initially forced unrelated lazy NixOS messages; its filter now evaluates failed assertions only, and all four evaluation cases pass. No host service has been activated or production credentials changed. Full NixOS pre-commit gates and strict OpenSpec validation pass after these changes. A presence-only vault check confirmed the dedicated App private key and optional App ID/installation-ID vault entries are absent, as is the dedicated DTrack upload key; no secret values were displayed. Operator-provided App ID, installation IDs and dedicated private key are still required for a real GitHub authentication test. Production project/team/key provisioning remains pending separately.

## Task 1.1 / 1.2 evidence

The operator-approved slice in the first section is unchanged and independent of #26. The production target now exists: project `efctl`, version `main`, UUID `3761ac8d-a1ce-4b1e-bfa6-7ae29141160a`. Team `sbom-collector` has only `BOM_UPLOAD`, is ACL-mapped to that project, and has one API key recorded in the vault. Evidence file: `target.json` in this change directory. No collector activation.

Deployed `/api/version` is Dependency-Track `4.14.5`. Disposable upload acceptance against the pinned 4.14.5 image remains the BOM submission evidence; least privilege is `BOM_UPLOAD` plus the project ACL mapping. Live portfolio ACL (`access-management` / `acl.enabled`) is `true` after the operator approved that change. GitHub artifact `digest` is the SHA-256 field added for upload-artifact integrity checks; the collector verifies it when present. Pagination is local and bounded. Reruns are eligible only when artifact `created_at` is at least the current attempt's `run_started_at`. Producer pins remain cyclonedx-gomod `v1.12.0` SHA-256 `004b9f5cc595b797fb5423e2ae4c97bcf0f18c712ed2faee1640b09e5efd6d15` and `actions/upload-artifact` `cf430e030ddbb5b0abf93d22962f4752f3646cd9`. The efctl workflow change is local and unpublished, so production is not yet a compliant producer.

Dedicated App material already in the vault, without values recorded here: `sbom_bot_github_app_id`, `sbom_bot_github_install_ids`, and `sbom_bot_github_private_key`. The secrets role renders those into the existing age files. `dtrack_sbom_collector_token` is present and was not printed.

## Resume

The operator approved enabling portfolio ACL and issuing the upload key. `access-management` / `acl.enabled` is `true`. `dtrack_sbom_collector_token` is in the encrypted vault and was not printed. Admin login can still see `efctl`/`main`. The team still has only `BOM_UPLOAD` and one key.

Producer publication: https://github.com/Scetrov/efctl/pull/100 merged as `c2d673e`. Workflow run `39319650171` succeeded and published artifact `cyclonedx-sbom-v1` ID `12219308929`, digest `sha256:bffa3c6835730a3d6201a879b96bafbca29769e650ae30ee81f5d3fe1878f4fc`.

Habiki report-only activation: `github_sbom_collector_enabled` and `scetrov.services.github-sbom-collector` with `reportOnly = true` were deployed with `./scripts/play.sh --limit habiki --tags nixos --skip-generated-refresh`. The oneshot runs as `github-sbom-collector`, has no listener, and did not write `state.json`. Its journal recorded the new run/artifact as `eligible` and five older runs as `missing_artifact`. The unit exits 1 because those historical gaps count as failures; that does not block a later upload of the newer artifact. Uploads remain disabled.

Live activation used the focused `github-sbom-collector` play. The first dry-activation differed only in `github-sbom-collector.service`. Uploads were then enabled. Systemd warned that `RuntimeMaxSec` has no effect on `Type=oneshot`; it was replaced with `TimeoutStartSec=300` before treating the rollout as complete. The timeout correction also differed only in that unit.

Manual start uploaded run `39319650171`, artifact `12219308929`, digest `sha256:bffa3c6835730a3d6201a879b96bafbca29769e650ae30ee81f5d3fe1878f4fc`, to project `3761ac8d-a1ce-4b1e-bfa6-7ae29141160a`. The checkpoint records a 36-character acceptance token and no GitHub credential marker. A repeat start and a service restart both finished successfully with `uploaded: 0, skipped: 5`. No collector listener was added. Existing listeners on ports 80, 443, and 8080 remained Caddy/Mimir. A search of collector Nix store paths found no private-key or GitHub token marker.

The oneshot still exits unsuccessfully on a poll that only reports historical `missing_artifact` runs. After the accepted upload, those older runs are skipped rather than failed. This is not a live expired-artifact event; expiry remains covered by deterministic tests and the retention-gap procedure.

Issue #27 remains open. Upload acceptance is not internal processing verification, by the operator's explicit scope decision. Do not close the issue on this evidence.
