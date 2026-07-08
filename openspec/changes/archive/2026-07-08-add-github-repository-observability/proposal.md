## Why

The operations portal does not currently surface repository-level operational risk for the managed GitHub estate. Open pull request backlog, Dependabot alerts, and SARIF-backed code scanning findings are important supply-chain and maintenance signals, but they are not collected into Mimir or visible from Grafana today.

## What Changes

- Add a repo-packaged GitHub repository observability exporter that authenticates exclusively as a GitHub App, not with personal access tokens.
- Collect repository inventory, open pull request counts and age, Dependabot alert counts and age, and code scanning alert counts and age for repositories under the `Scetrov` and `RichardSlater` owners.
- Expose cached Prometheus metrics for GitHub repository health and exporter self-health so the existing Prometheus/Mimir/Grafana path can consume them without querying GitHub on every scrape.
- Configure the exporter declaratively through NixOS, with GitHub App credentials sourced from the existing Ansible Vault/age secret workflow.
- Add a dedicated Grafana dashboard for repository/supply-chain health and add summary panels to the existing Operations Platform Overview dashboard.
- Support repository inclusion policy controls such as excluding archived repositories, excluding forks, and explicit repo exclusions to avoid long-term dashboard noise.

## Capabilities

### New Capabilities

- `github-repository-observability`: Covers GitHub App authenticated collection of repository inventory, pull request, Dependabot, code scanning, coverage, and collector health metrics.

### Modified Capabilities

- `grafana-operations-portal`: Extend the operations portal to include GitHub repository/supply-chain health summary panels and a drilldown dashboard.

## Impact

- Adds a repo-local exporter package or service implementation for GitHub repository observability.
- Adds a NixOS module/service configuration for the exporter, its age secrets, and Prometheus scrape configuration.
- Adds new secrets for GitHub App identity/private key material using the existing encrypted secret pipeline.
- Adds or updates Grafana dashboard JSON under `terraform/dashboards` and Terraform dashboard registration as needed.
- Requires a GitHub App installed for the `Scetrov` and `RichardSlater` repository estate with read-only permissions for metadata, pull requests, Dependabot alerts, and code scanning alerts.
