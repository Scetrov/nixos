# GitHub Repository Observability

This service exports repository-level maintenance and supply-chain signals for the `Scetrov` and `RichardSlater` GitHub owners into the existing Prometheus/Mimir/Grafana path.

## GitHub App prerequisites

Create one read-only GitHub App and install it for the repositories that should be monitored under both owners.

Required repository permissions:

- **Metadata:** read-only. Required for repository inventory and installation repository discovery.
- **Pull requests:** read-only. Required for open pull request backlog and oldest open pull request age.
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

## Key metrics

- `github_repository_info`
- `github_repository_open_pull_requests`
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
- `github_repository_observability_rate_limit_remaining`
- `github_repository_observability_rate_limit_reset_timestamp_seconds`
