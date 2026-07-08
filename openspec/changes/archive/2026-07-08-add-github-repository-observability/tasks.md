## 1. GitHub App and Secret Plumbing

- [x] 1.1 Define the required GitHub App permissions and document the app installation prerequisites for `Scetrov` and `RichardSlater`
- [x] 1.2 Add encrypted secret inputs for GitHub App ID and private key using the existing Ansible Vault/age secret workflow
- [x] 1.3 Add runtime secret file handling for the exporter service without logging or embedding secret contents

## 2. Exporter Packaging and Configuration

- [x] 2.1 Add a repo-local GitHub repository observability exporter package or service implementation
- [x] 2.2 Add declarative configuration for owners, include archived policy, include forks policy, explicit repository exclusions, collection interval, and listen address
- [x] 2.3 Implement GitHub App JWT signing, installation discovery/filtering, and installation access token refresh
- [x] 2.4 Implement cached background collection so `/metrics` does not call GitHub during Prometheus scrapes

## 3. GitHub Signal Collection

- [x] 3.1 Collect repository inventory for visible repositories under `Scetrov` and `RichardSlater` subject to policy
- [x] 3.2 Collect open pull request counts and oldest/stale pull request age per repository
- [x] 3.3 Collect open Dependabot alert counts and oldest alert age per repository and severity
- [x] 3.4 Collect open code scanning alert counts and oldest alert age per repository, severity, and bounded tool metadata
- [x] 3.5 Emit coverage/accessibility metrics that distinguish collected zero findings from unavailable, disabled, forbidden, or failed signals
- [x] 3.6 Emit exporter self-health metrics for collection success, last success time, repositories seen, collection duration, and GitHub rate-limit status where available

## 4. NixOS and Prometheus Integration

- [x] 4.1 Add a NixOS module or service configuration for deploying the exporter on the observability host
- [x] 4.2 Add a declarative Prometheus scrape configuration for the exporter metrics endpoint
- [x] 4.3 Ensure logs from the exporter are captured by existing host logging conventions with stable service identity labels
- [x] 4.4 Validate that no personal access token configuration path exists and no secret material is written to source-controlled files

## 5. Grafana Dashboards

- [x] 5.1 Add a dedicated GitHub repository or software supply-chain health dashboard under `terraform/dashboards`
- [x] 5.2 Register the new dashboard in Terraform under the operations portal structure with stable naming and UID conventions
- [x] 5.3 Add repository risk summary panels to the Operations Platform Overview dashboard
- [x] 5.4 Add collector health and data freshness panels so repository risk values are not shown without trust context
- [x] 5.5 Add repository-level triage views and practical GitHub links for pull requests, Dependabot alerts, and code scanning alerts

## 6. Validation and Deployment

- [x] 6.1 Run exporter unit or smoke tests for GitHub App auth, pagination/error handling, metric rendering, and cache behavior
- [x] 6.2 Validate dashboard JSON and Terraform formatting without exposing secrets
- [x] 6.3 Run a targeted deployment using `./scripts/play.sh --limit habiki` with the appropriate tags for this change
- [x] 6.4 Verify Prometheus/Mimir receives exporter metrics and Grafana panels distinguish healthy zeroes from unknown coverage
- [x] 6.5 Stage all required files for commit and review the sign-off checklist for secrets, observability, hygiene, and declarative automation
