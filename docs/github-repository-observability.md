# GitHub Repository Observability

This service exports repository-level maintenance and supply-chain signals for the `Scetrov` and `RichardSlater` GitHub owners into the existing Prometheus/Mimir/Grafana path.

## GitHub App prerequisites

Create one read-only GitHub App and install it for the repositories that should be monitored under both owners.

Required repository permissions:

- **Metadata:** read-only. Required for repository inventory and installation repository discovery.
- **Pull requests:** read-only. Required for open pull request backlog and oldest open pull request age.
- **Issues:** read-only. Required for the rolling seven-day issue-creation count in private repositories. After adding it to an existing App, approve the permission update for both owner installations; public-only success is not complete estate coverage.
- **Contents:** read-only. Required to resolve literal `main` to its current commit and distinguish an absent branch from unavailable access.
- **Checks:** read-only. Required for GitHub Actions and other App check-run results on that commit.
- **Commit statuses:** read-only. Required for external CI/status contexts on that commit.
- **Dependabot alerts:** read-only. Required for open Dependabot alert counts and oldest alert age by severity.
- **Code scanning alerts:** read-only. Required for open SARIF/code scanning alert counts and oldest alert age by severity/tool.

The App does not need write permissions, webhook delivery, user OAuth, or personal access tokens. Missing permissions or incomplete installation scope are reported as unavailable coverage metrics, not as healthy zero findings.

Installation requirements:

1. Install the App for the `Scetrov` account repositories to be monitored.
2. Install the App for the `RichardSlater` account repositories to be monitored.
3. Record the numeric App ID in `github_repository_observability_app_id` in `src/secrets.yml`.
4. Generate a private key for the App and store the PEM content in `github_repository_observability_private_key` in `src/secrets.yml`.
5. Deploy secrets through the existing Ansible Vault to age workflow; do not commit generated plaintext, JWTs, installation tokens, or private key content.

## Deployment

The NixOS module is enabled on `habiki` through `scetrov.services.github-repository-observability`. Defaults collect non-archived, non-fork repositories for `Scetrov` and `RichardSlater`, with explicit `owner/repository` exclusions available for intentionally noisy repositories.

The exporter listens on `127.0.0.1:9177` and Prometheus scrapes it with job `github-repository-observability`. Collection runs in the background every 15 minutes by default; `/metrics` serves the last cached result and does not call GitHub during scrapes.

## Coverage and failure semantics

Installation visibility bounds discovery; pagination and declarative inclusion
policy decide the estate, not a hardcoded snapshot. Aggregate by bounded owner,
repository, severity and tool dimensions. Do not use alert titles, arbitrary
URLs, CVEs, package names, rule IDs or branches as unbounded metric labels.
Use repository links for detailed remediation instead.

The GitHub Repository Health dashboard and platform risk summary use retained
Mimir metrics. A missing permission, disabled scanner, exhausted rate limit or
collection failure is unknown coverage, not zero alerts. Review source
availability, last-success age and collection duration/rate-limit metrics along
with backlog/severity counts. Rollback disables the service/scrape and removes
its dashboard resources through automation; App revocation is a separate action
and retained observability history is not purged.

## GitHub Issues 7d

The platform overview's **GitHub Issues 7d** card sits immediately left of
**GitHub Open PRs**. Repository Health's **Issues and Main Failures by Repository**
table shows the same rolling count per repository. It counts issues created by any author in monitored
repositories owned by `RichardSlater` or `Scetrov`. It includes open and closed
issues, excludes pull requests, and retains the existing App installation
visibility, fork/archive and explicit repository-exclusion policy. It is not a
count of issues authored by those accounts elsewhere, nor a promise of coverage
outside the monitored estate.

The collector reuses the existing App and 15-minute polling cycle. Each cycle
uses one fixed seven-day window anchor. The repository Issues API uses `since`
for *updated* time, so the collector pages all returned results and filters
`created_at` locally to the inclusive creation window, deduplicating issue
numbers. No issue titles, URLs, authors or issue numbers become metric labels.
The per-repository gauge represents a rolling count, not a monotonically
increasing counter; do not apply Prometheus `increase()` to it.

A successful empty response emits zero. Missing permissions, disabled issue
access, rate limits, malformed responses and transport failures emit unavailable
`signal="issues"` coverage rather than a synthetic zero. The card requires
inventory from both owners, issue counts for every inventoried repository,
complete issue-signal coverage, collection success and a last-success age no
older than two configured collection intervals. Otherwise it displays **N/A**,
not a partial total. Counts reflect the last successful provider poll, not every
Grafana refresh.

Validate with:

```sh
python3 -m unittest discover -s src/roles/nixos/tests -p 'test_github_repository_observability.py'
```

For exporter-only deployment, copy the exporter through Ansible, review the
complete host's `nixos-rebuild dry-activate` plan, then switch without channel
updates or blanket container restarts. Apply only the platform overview through
`scripts/tofu.sh`, verify both owner/repository coverage and the Mimir total, then
inspect a Grafana snapshot. The GitHub App permission change requires owner
approval in GitHub; this deployment never adds write permissions or a PAT.
After a collector restart, cards can be temporarily unavailable while the first
provider collection finishes and the next 60-second Prometheus scrape arrives.

On 2026-10-28, both installations were verified with Issues read-only permission.
The targeted NixOS activation restarted only this collector, and OpenTofu updated
only the platform overview. Live collection and Mimir reported 11 recent issues
(Scetrov 11, RichardSlater 0), with successful issue coverage for all 27 monitored
repositories. The rendered overview confirmed the new card immediately left of
Open PRs. Nine issue-collector/dashboard tests and 43 AI-usage regression tests
passed, along with changed-file pre-commit and Grafana schema validation. Counts
and repository scope are dated observations, not a fixed inventory.

## Failing statuses on main

The platform overview's **GitHub Main Failures** card sits immediately left of
**GitHub Issues 7d**. It sums failing check runs and commit-status contexts on the
latest commit of the literal `main` branch across the same monitored estate.
It does not count historical runs, failed repositories, or default branches with
a different name. Both status APIs are pinned to one resolved commit SHA per
repository so a branch advancing during collection cannot mix commits.

Commit statuses in `failure` or `error` count as failures. Completed check runs
with `failure`, `timed_out`, `action_required` or `startup_failure` count; success,
pending/in-progress, cancelled, skipped, neutral and stale results do not. The
latest result by ID wins per status context and per check `(App ID, name)`, so
superseded failed attempts are not counted after a successful or pending rerun.
Commit-status contexts and check runs remain distinct signals even if their
names match. Names, commit SHAs and run IDs are never metric labels.

The collector pages both APIs and checks reported totals against unique returned
IDs. Incomplete/changing pagination, malformed/unknown states, mismatched SHAs,
permission/rate-limit failures and transport errors produce unavailable
`signal="main_statuses"` coverage and no count. A branch lookup 404 is not proof
that `main` is absent: a successful branch listing must confirm absence. Confirmed
absence emits `github_repository_main_branch_present = 0`, a zero failure count,
and available `status="no_main"` coverage. It never silently checks `master` or
another default branch. A present branch with no checks/status contexts also has
zero failures; this is not proof that CI is configured.

The overview applies the same whole-estate coverage and two-interval freshness
gates as Issues 7d. It uses teal for zero and pink for one or more failures.
Repository Health's per-repository table includes **Issues 7d**, **Failing main**
and **Has main**, keeps inventory rows when a single signal is unavailable, and
shows missing values as N/A rather than zero. Each value is individually gated on
its repository's signal availability and collector freshness. Confirmed absent
`main` is explicitly shown as **No**, with zero applicable failures.

Validate both issue and main-status collection with:

```sh
python3 -m unittest discover -s src/roles/nixos/tests -p 'test_github_*.py'
```

Deploy the collector through the targeted Ansible/NixOS procedure above; apply
both `grafana_dashboard.platform_overview` and
`grafana_dashboard.github_repository_health` through `scripts/tofu.sh`. Verify
all repository coverage, per-repository values and the aggregate in Mimir, then
visually inspect snapshots of both dashboards. Adding Contents/Checks access
requires permission approval on both App installations, not new credentials.

On 2026-10-28, Contents, Checks and Commit statuses were verified read-only for
both installations. The collector-only activation restarted no unrelated service,
and OpenTofu updated only these two dashboards. All 27 repositories had complete
main-status coverage: 26 had `main`, one was confirmed absent, and the aggregate
was one failing result in `RichardSlater/dotfiles`. Mimir independently returned
27 per-repository rows with Issues 7d totaling 11 and main failures totaling one.
Both dashboards and the new table were visually inspected. Automatic-height
rendering of Repository Health initially returned 404; an explicit 1600px height
render succeeded. The 25 GitHub tests, 43 AI-usage regression tests, changed-file
pre-commit checks and both Grafana schema checks passed. These are dated results;
future runs and repository inclusion can change the counts.

## Key metrics

- `github_repository_info`
- `github_repository_open_pull_requests`
- `github_repository_issues_created_last_7_days`
- `github_repository_main_failing_statuses`
- `github_repository_main_branch_present`
- `github_repository_oldest_open_pull_request_age_seconds`
- `github_repository_dependabot_open_alerts`
- `github_repository_dependabot_oldest_open_alert_age_seconds`
- `github_repository_code_scanning_open_alerts`
- `github_repository_code_scanning_oldest_open_alert_age_seconds`
- `github_repository_signal_available`
- `github_repository_observability_collection_success`
- `github_repository_observability_last_success_timestamp_seconds`
- `github_repository_observability_repositories_seen`
- `github_repository_observability_collection_duration_seconds`
- `github_repository_observability_collection_interval_seconds`
- `github_repository_observability_rate_limit_remaining`
- `github_repository_observability_rate_limit_reset_timestamp_seconds`
