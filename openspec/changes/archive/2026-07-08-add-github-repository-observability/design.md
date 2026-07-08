## Context

Grafana is already the declarative operations entrypoint. Dashboard JSON lives under `terraform/dashboards`, dashboard registration lives in `terraform/grafana.tf`, and metrics are normally queried through the existing Prometheus/Mimir path. The current portal covers host health, observability stack health, service dashboards, and Home Assistant environmental summaries, but it has no repository-level view of GitHub maintenance or supply-chain risk.

The target estate is all repositories under the `Scetrov` and `RichardSlater` GitHub owners. The required signals are open pull requests, Dependabot alerts, and code scanning alerts from any SARIF-producing source that GitHub normalizes into code scanning. Authentication MUST use a GitHub App rather than personal access tokens. Long-lived GitHub App private key material must follow the existing Ansible Vault to age secret workflow and must not be hardcoded in Nix, Terraform, or dashboard JSON.

## Goals / Non-Goals

**Goals:**

- Package and deploy a GitHub repository observability exporter from this repository.
- Authenticate to GitHub exclusively as a GitHub App and use installation access tokens for API calls.
- Discover repositories under the `Scetrov` and `RichardSlater` owners, subject to declarative include/exclude policy.
- Collect repository inventory, pull request backlog, Dependabot alert, code scanning alert, coverage, and exporter health metrics.
- Serve cached Prometheus metrics so Prometheus/Mimir can scrape frequently without causing GitHub API calls on every scrape.
- Add a dedicated Grafana repository/supply-chain health dashboard and summary panels on the Operations Platform Overview dashboard.

**Non-Goals:**

- Do not use personal access tokens, fine-grained PATs, or user OAuth tokens for collection.
- Do not implement automated remediation, PR merging, issue creation, or GitHub write operations.
- Do not expose per-alert high-cardinality labels such as alert title, full URL, CVE, or arbitrary SARIF rule metadata as Prometheus labels.
- Do not make the Grafana GitHub plugin the primary data source. A plugin may be evaluated separately, but the required path is exporter metrics through Prometheus/Mimir.
- Do not require every repository to have Dependabot or code scanning enabled; absent coverage must be represented distinctly from zero findings.

## Decisions

### Use a repository-packaged exporter instead of a Grafana plugin

The implementation will add a repo-local exporter package or service implementation and deploy it through NixOS. Grafana will query the resulting Mimir metrics. This keeps the integration declarative, makes the data alertable, and follows the existing observability stack pattern.

Alternatives considered:

- Grafana GitHub plugin: useful for ad hoc exploration, but it centralizes GitHub credentials in Grafana/plugin configuration and may not expose all required Dependabot/code scanning dimensions as durable metrics.
- Manual dashboard data source calls: harder to alert on, harder to test, and less aligned with existing Prometheus/Mimir workflows.

### Authenticate exclusively with GitHub Apps

The exporter will read a GitHub App ID and private key from secret files, sign a GitHub App JWT, discover or select relevant installations, and exchange the JWT for short-lived installation access tokens. API calls to repositories will use installation tokens.

Alternatives considered:

- Personal access tokens: rejected because auth must be through GitHub Apps and because user-bound tokens are harder to govern and rotate safely.
- GitHub Actions-generated artifacts: rejected for phase one because collection needs to cover all repositories centrally, including repositories without suitable workflow configuration.

### Use cached collection rather than GitHub calls during `/metrics` scrapes

The exporter will run a background collection loop on a configurable interval, cache the latest metric values in memory, and serve `/metrics` from that cache. Prometheus can scrape the local endpoint at the normal platform cadence without multiplying GitHub API requests.

Collector self-health metrics will include last successful collection timestamp, collection success, repositories seen, API/rate-limit status where available, and token expiry/refresh status where useful.

### Keep metrics low-cardinality and dashboard links high-context

Metrics will aggregate by bounded labels such as `owner`, `repo`, `severity`, `tool`, `package_ecosystem`, `archived`, and `fork`. The exporter will avoid arbitrary alert titles, URLs, package names, CVEs, SARIF rule IDs, and branches as labels unless a future design explicitly bounds and justifies them.

Grafana panels and tables should use repository-level links to GitHub pull request, Dependabot, and code scanning pages for detailed remediation context.

### Represent coverage separately from findings

The exporter will emit coverage/accessibility metrics indicating whether repository inventory, pull requests, Dependabot alerts, and code scanning alerts were successfully queried or are unavailable/disabled/forbidden. Dashboards must distinguish "zero open findings" from "collector could not determine findings".

### Provide repository inclusion policy

The NixOS service configuration will include owners and repository policy controls. Defaults should include all non-archived, non-fork repositories visible to the GitHub App installation under `Scetrov` and `RichardSlater`, with an explicit exclusion list for noisy or intentionally ignored repositories.

## Risks / Trade-offs

- GitHub API permissions or installation scope are incomplete → emit collector and coverage health metrics, show them in Grafana, and document required GitHub App permissions.
- GitHub API rate limits are exhausted → use cached collection, configurable intervals, conditional pagination where practical, and expose rate-limit remaining/reset metrics.
- Metrics accidentally become high-cardinality → constrain labels to repository-level and small enumerations; rely on GitHub links for per-alert details.
- Private key material leaks into source or logs → source from Ansible Vault/age only, read from files at runtime, avoid logging key contents or JWTs/tokens.
- Large repository estates cause slow collection → collect per installation with pagination, cache partial failures carefully, and emit collection duration/success metrics.
- Disabled Dependabot/code scanning looks like healthy zero findings → emit explicit coverage/accessibility metrics and include coverage panels in Grafana.

## Migration Plan

1. Create and install a read-only GitHub App for the `Scetrov` and `RichardSlater` repository estate with metadata, pull request, Dependabot alert, and code scanning alert permissions.
2. Add GitHub App configuration/private key material to the existing secret pipeline.
3. Package and deploy the exporter on the observability host through NixOS.
4. Add a Prometheus scrape config for the exporter and verify metrics flow into Mimir.
5. Add the dedicated repository health dashboard and summary panels on Operations Platform Overview.
6. Validate dashboard behavior against known repositories with open PRs, Dependabot alerts, code scanning alerts, and repositories without enabled scanning.

Rollback is to disable the exporter service/scrape and remove or hide the Grafana panels. GitHub App installation can remain read-only or be uninstalled separately.

## Open Questions

- Exact GitHub App name and installation IDs are deployment-time values and should be captured during implementation.
- The first implementation should decide whether the repo-local exporter is packaged as a standalone Python package or embedded as a Nix-managed script; the preferred direction is standalone if the repository packaging structure is introduced cleanly.
