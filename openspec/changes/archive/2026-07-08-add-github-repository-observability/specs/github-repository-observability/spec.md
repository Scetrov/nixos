## ADDED Requirements

### Requirement: GitHub repository observability uses GitHub App authentication
The system SHALL collect GitHub repository observability data using GitHub App authentication and MUST NOT use personal access tokens, fine-grained personal access tokens, or user OAuth tokens for collection.

#### Scenario: Exporter authenticates as a GitHub App
- **WHEN** the GitHub repository observability exporter starts
- **THEN** it reads GitHub App identity and private key material from runtime secret files and obtains installation access tokens for GitHub API calls

#### Scenario: Personal access tokens are not configured
- **WHEN** the GitHub repository observability service is configured declaratively
- **THEN** the configuration does not require or expose a personal access token setting for GitHub API access

#### Scenario: GitHub App permissions are insufficient
- **WHEN** the installed GitHub App cannot read a required repository signal because of missing permissions or installation scope
- **THEN** the exporter reports the affected signal as unavailable through collector or coverage metrics rather than reporting it as zero findings

### Requirement: Exporter discovers configured repository estate
The system SHALL discover repositories visible to the GitHub App installation for the configured `Scetrov` and `RichardSlater` owners, subject to declarative repository inclusion policy.

#### Scenario: Configured owners are collected
- **WHEN** the exporter performs a collection cycle
- **THEN** it discovers repositories visible to the GitHub App under the `Scetrov` and `RichardSlater` owners

#### Scenario: Archived and fork repositories follow policy
- **WHEN** discovered repositories include archived repositories or forks
- **THEN** the exporter includes or excludes them according to the declarative repository policy

#### Scenario: Explicit repository exclusions are respected
- **WHEN** a repository is listed in the declarative exclusion policy
- **THEN** the exporter does not emit repository risk metrics for that repository

### Requirement: Exporter emits pull request backlog metrics
The system SHALL emit Prometheus metrics for open pull request backlog by repository.

#### Scenario: Open pull requests are counted
- **WHEN** a repository has open pull requests visible to the GitHub App
- **THEN** the exporter emits an open pull request count labelled by owner and repository

#### Scenario: Pull request age is visible
- **WHEN** a repository has one or more open pull requests
- **THEN** the exporter emits an age metric for the oldest open pull request or equivalent stale backlog signal labelled by owner and repository

#### Scenario: No open pull requests are represented
- **WHEN** a repository has no open pull requests and pull request collection succeeded
- **THEN** the exporter emits metrics that allow Grafana to distinguish a healthy zero backlog from a collection failure

### Requirement: Exporter emits Dependabot alert metrics
The system SHALL emit Prometheus metrics for open Dependabot alerts by repository and severity.

#### Scenario: Open Dependabot alerts are counted by severity
- **WHEN** a repository has open Dependabot alerts visible to the GitHub App
- **THEN** the exporter emits open alert counts labelled by owner, repository, and severity

#### Scenario: Dependabot alert age is visible
- **WHEN** a repository has open Dependabot alerts visible to the GitHub App
- **THEN** the exporter emits an oldest open alert age or timestamp metric by owner, repository, and severity

#### Scenario: Dependabot coverage is unavailable
- **WHEN** Dependabot alerts cannot be queried for a repository because the feature is disabled, unavailable, forbidden, or unsupported
- **THEN** the exporter emits coverage or accessibility metrics that show the Dependabot signal is unknown or unavailable rather than reporting zero open alerts

### Requirement: Exporter emits code scanning alert metrics
The system SHALL emit Prometheus metrics for open GitHub code scanning alerts from any SARIF-producing source normalized by GitHub.

#### Scenario: Open code scanning alerts are counted
- **WHEN** a repository has open code scanning alerts visible to the GitHub App
- **THEN** the exporter emits open alert counts labelled by owner, repository, severity, and scanning tool where available

#### Scenario: SARIF source is represented by GitHub code scanning tool metadata
- **WHEN** a code scanning alert originated from CodeQL, Semgrep, Trivy, or another SARIF-producing tool
- **THEN** the exporter represents the source using bounded GitHub code scanning tool metadata rather than arbitrary SARIF payload labels

#### Scenario: Code scanning coverage is unavailable
- **WHEN** code scanning alerts cannot be queried for a repository because the feature is disabled, unavailable, forbidden, or unsupported
- **THEN** the exporter emits coverage or accessibility metrics that show the code scanning signal is unknown or unavailable rather than reporting zero open alerts

### Requirement: Exporter serves cached Prometheus metrics
The system SHALL serve cached Prometheus metrics from a local metrics endpoint instead of calling GitHub during every Prometheus scrape.

#### Scenario: Collection runs independently of metrics scraping
- **WHEN** Prometheus scrapes the exporter metrics endpoint
- **THEN** the exporter returns the latest cached metrics without making a GitHub API request as part of that scrape

#### Scenario: Collection interval is configurable
- **WHEN** the exporter is configured declaratively
- **THEN** the GitHub collection interval can be set independently from the Prometheus scrape interval

#### Scenario: Stale cache is detectable
- **WHEN** GitHub collection fails or has not completed recently
- **THEN** the exporter emits self-health metrics showing collection success and last successful collection time

### Requirement: Exporter metrics avoid high-cardinality alert details
The system SHALL avoid exposing arbitrary per-alert details as Prometheus labels.

#### Scenario: Bounded labels are used
- **WHEN** the exporter emits repository risk metrics
- **THEN** labels are limited to bounded dimensions such as owner, repository, severity, tool, package ecosystem, archived state, fork state, and signal type

#### Scenario: Detailed remediation uses GitHub links
- **WHEN** an operator needs to inspect individual pull requests or findings
- **THEN** Grafana can link to the relevant GitHub repository pull request, Dependabot, or code scanning views rather than relying on per-alert Prometheus labels

### Requirement: GitHub observability service is declaratively managed
The system SHALL deploy and configure the GitHub repository observability exporter through the repository's NixOS and secret-management workflows.

#### Scenario: Secrets are sourced from encrypted secret workflow
- **WHEN** the exporter requires GitHub App private key material
- **THEN** the material is sourced from the existing Ansible Vault/age runtime secret workflow and is not hardcoded in Nix, Terraform, dashboard JSON, or source code

#### Scenario: Prometheus scrapes the exporter
- **WHEN** the exporter service is enabled on the observability host
- **THEN** Prometheus has a declarative scrape configuration for the exporter metrics endpoint

#### Scenario: Exporter package is managed in source control
- **WHEN** the exporter is implemented
- **THEN** its code and packaging are managed in this repository so deployment is reproducible through automation
