## ADDED Requirements

### Requirement: Declarative complete source discovery
The system SHALL periodically discover repositories matching Scetrov/*, RichardSlater/*, and storytold/*craft using paginated GitHub user/organization discovery. Policy SHALL declare owner identity, name pattern, eligibility, destination namespace, and cadence. Default eligibility SHALL exclude private, forked, and archived sources unless explicitly enabled. Discovery SHALL provide a report-only inventory including exclusions and conflicts before initial creation.

#### Scenario: Requested selection
- **WHEN** discovery includes repositories from all three owners over multiple API pages
- **THEN** all eligible Scetrov and RichardSlater repositories and only eligible storytold names ending in craft are selected without modifying nonmatching repositories

#### Scenario: Opt-in eligibility
- **WHEN** a private, forked, or archived repository matches a name pattern but its class is not enabled
- **THEN** it is reported as excluded and no mirror is created for it

#### Scenario: Review without mutation
- **WHEN** reconciliation runs in report-only mode
- **THEN** it reports source selection, destination mapping, and conflicts without creating or modifying Forgejo namespaces or repositories

### Requirement: Managed pull mirrors converge safely
The system SHALL create native Forgejo pull mirrors in deterministically mapped source-owner namespaces, identify managed sources by stable GitHub repository identity, and converge idempotently without recreating healthy mirrors or adopting unrelated repositories. A new matching source SHALL be created on a subsequent successful reconciliation; Forgejo-native synchronization SHALL propagate supported Git branch and tag changes.

#### Scenario: New matching repository and repeat run
- **WHEN** a new eligible source is discovered and reconciliation subsequently runs twice
- **THEN** exactly one managed destination exists and the repeated run does not recreate it or duplicate namespaces

#### Scenario: Source changes synchronize
- **WHEN** a mirrored source receives branch or tag changes
- **THEN** the configured native mirror synchronization updates corresponding destination Git content within the documented synchronization policy

#### Scenario: Destination collision
- **WHEN** a proposed destination already contains an unrelated or ambiguously owned repository
- **THEN** reconciliation reports a conflict without overwriting, adopting, or deleting it

### Requirement: Lifecycle preserves data and visibility
Managed destinations SHALL remain private under the existing Forgejo access model. Source rename, transfer, deletion, or visibility changes SHALL be detected without automatic destination deletion, access broadening, or unreviewed retargeting. Disabling reconciliation SHALL preserve mirrored data and state, with native polling behavior documented separately. LFS completeness and unchanged submodule references SHALL be explicit.

#### Scenario: Source lifecycle changes
- **WHEN** a managed source is renamed, transferred, deleted, or changes visibility
- **THEN** its destination data and access boundary are retained and any required remapping is surfaced for explicit managed review

#### Scenario: Private mirror access
- **WHEN** private-source mirroring is explicitly enabled
- **THEN** only authorized Forgejo users can access its destination and upstream credentials are not exposed through clone URLs, ordinary logs, or generated source configuration

#### Scenario: LFS or submodules
- **WHEN** a source contains LFS objects or submodule references
- **THEN** supported LFS transfer is verified or incompleteness is reported as a blocking mirror status, and submodule references remain unchanged with their separate access requirements documented

### Requirement: Scheduled mirroring is secure and observable
The reconciler SHALL run as a declaratively provisioned least-privilege NixOS service/timer with protected vault-backed runtime credentials, persistent atomic ownership state, non-overlapping runs, bounded retries, pagination/rate-limit handling, and recoverable per-repository errors. Existing journal/Loki and Prometheus/Grafana paths SHALL expose reconciliation failure, last success, mirror errors, and stale synchronization. It MUST NOT enable Forgejo Actions, new public ingress, or unrelated hosts.

#### Scenario: Transient or individual failure
- **WHEN** one source API/import fails or GitHub rate-limits a run
- **THEN** bounded retry or deferral preserves ownership state, avoids duplicate creation, records an actionable failure, and allows independent repositories to progress where safe

#### Scenario: Restart and rebuild
- **WHEN** the reconciler or Habiki restarts or is rebuilt
- **THEN** discovery resumes with prior managed identities and credentials remain runtime-only without losing repositories or activating Actions

#### Scenario: Mirror becomes stale
- **WHEN** native synchronization fails or exceeds the configured freshness threshold
- **THEN** the failure or age is visible through existing observability with sufficient repository identity for recovery and no secret values
