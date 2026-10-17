## ADDED Requirements

### Requirement: Simple versioned subscription catalogue
The system SHALL maintain a Git-managed public subscription catalogue with titles, categories, HTTP(S) URLs, enabled state, optional URL aliases, and reasons for disabled entries. The initial list SHALL contain the 47 distinct subscriptions identified in `feed-audit.md`, initially 39 enabled and eight disabled; ZDNet SHALL be labelled as general news. The audit document SHALL remain the provenance record rather than a required operational metadata schema. Offline validation MUST reject invalid fields/types, embedded credentials, secret-bearing URLs, and duplicate or ambiguous URL ownership before API writes. Catalogue edits SHALL NOT require reconciliation code changes.

#### Scenario: Operator maintains the reading list
- **WHEN** the operator adds a valid entry or disables an existing entry
- **THEN** offline validation accepts the updated list without network access or code changes
- **AND** disabled entries remain documented but are excluded from provisioning and export

#### Scenario: Catalogue is invalid
- **WHEN** entries have invalid schema, credentials, or overlapping URL/alias ownership
- **THEN** the command fails before API writes with a sanitized diagnostic

### Requirement: Deterministic offline OPML export
The system SHALL generate deterministic escaped UTF-8 OPML from enabled entries, grouped by category, without API credentials, network access, or unstable timestamps. The catalogue SHALL be the sole hand-edited subscription authority. The system SHALL NOT implement publisher fetching/auditing or feed XML parsing; Miniflux SHALL retain responsibility for ingestion.

#### Scenario: Operator exports the catalogue
- **WHEN** the same catalogue is exported twice
- **THEN** both outputs are byte-identical valid OPML containing each enabled entry once and no disabled entries

### Requirement: Explicit additive native API sync
The system SHALL provide read-only plan and explicit apply operations against the existing loopback Miniflux API. It MUST verify the configured operator identity before writes, refuse authenticated redirects, and match existing subscriptions using URLs/explicit aliases rather than titles. Apply SHALL create only missing enabled feeds and necessary categories. It MUST NOT change or delete existing feeds, settings, categories, articles, read markers, or bookmarks, including unmanaged reader state. Ambiguous matches SHALL block creation for that entry.

#### Scenario: Apply is repeated
- **WHEN** apply runs against an empty reader and then runs again with the same catalogue and known stored URLs
- **THEN** the first run creates missing categories/feeds and the second performs zero mutation requests

#### Scenario: Plan is requested
- **WHEN** the operator requests a plan
- **THEN** the command validates the catalogue and reads authenticated inventory without any mutation requests

#### Scenario: Existing subscriptions differ
- **WHEN** matching feeds have UI-edited settings, unmanaged feeds exist, or catalogue entries are removed/disabled
- **THEN** apply leaves existing reader state unchanged

#### Scenario: Identity or URL matching is unsafe
- **WHEN** the token belongs to another operator or more than one subscription matches an entry
- **THEN** wrong identity prevents all writes and ambiguity prevents writes for that entry
- **AND** unexpected stored canonical URLs are reported for reviewed alias edits rather than guessed migrations

### Requirement: Bounded execution with visible failures
The system SHALL serialize plan/apply execution, bound request and execution time, and return nonzero for incomplete apply. It MUST stop writes on invalid configuration, authentication/identity failure, or inaccessible inventory. It SHALL continue independent entries after entry-specific failures. It MUST re-read inventory after an uncertain create before any future attempt and MUST NOT blindly retry POST requests or delete successful creations. No automatic retry scheduler or persistent status store is required.

#### Scenario: Creation fails or times out
- **WHEN** one create operation fails or its result is uncertain
- **THEN** inventory is re-read to check uncertain success, independent entries can proceed, and unresolved failures produce a nonzero result
- **AND** successful creations remain intact for the next explicit run

### Requirement: Optional credentials and targeted invocation
The system SHALL deliver an optional personal reader API token from Ansible Vault through existing agenix and systemd credential mechanisms, without plaintext secrets in Git, the Nix store, process arguments, or logs. Subscription sync SHALL be invoked explicitly through a dedicated Habiki-targeted Ansible tag, defaulting to plan and requiring explicit opt-in for apply. Its NixOS-packaged apply oneshot MUST NOT run on boot, catalogue/credential changes, ordinary Miniflux deployment, or a timer. Check/syntax/list modes MUST NOT write to Miniflux. Missing sync enrollment or failed sync MUST NOT prevent reader operation or weaken OIDC.

#### Scenario: Reader deploys without subscription enrollment
- **WHEN** subscription management is disabled and no token is configured
- **THEN** ordinary Miniflux deployment and reader access continue unchanged without subscription writes

#### Scenario: Operator explicitly applies subscriptions
- **WHEN** the enrolled operator invokes the subscription tag with Habiki limit and explicit apply opt-in
- **THEN** automation runs the bounded oneshot, waits for its actual outcome, and surfaces incomplete results
- **AND** sanitized summaries enter existing Alloy/Loki journal ingestion without new metrics, alerts, or public endpoints

#### Scenario: Subscription sync is disabled
- **WHEN** automation removes subscription-sync configuration and its credential consumer
- **THEN** no scheduled execution remains and existing subscriptions, database, reader access, and identity resources are retained

### Requirement: Honest subscription recovery
The system SHALL document first OIDC login and personal token enrollment for API sync. After database loss, recovery SHALL require a replacement token for API sync or authenticated import of catalogue-generated OPML. It MUST NOT introduce local-password/admin bootstrap, direct SQL subscription/token provisioning, or claims to restore historical application state.

#### Scenario: Old token survives only in Vault
- **WHEN** an empty replacement database rejects the old token
- **THEN** recovery directs the operator to OIDC login and replacement-token enrollment or OPML import
- **AND** it does not claim to restore reading history, bookmarks, preferences, sessions, or old credentials
