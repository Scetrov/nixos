## RENAMED Requirements

- FROM: `### Requirement: OPML-only disaster recovery`
- TO: `### Requirement: Subscription catalogue and OPML disaster recovery`

## MODIFIED Requirements

### Requirement: Subscription catalogue and OPML disaster recovery
The system SHALL document recovery by reprovisioning Miniflux and its dedicated database, restoring authorized OIDC access, and restoring enabled subscriptions from the Git-managed catalogue through explicitly invoked additive API sync or authenticated import of catalogue-generated/operator-held OPML. API-driven restoration after database loss MUST explicitly require creation of the operator account through OIDC and secure enrollment of a replacement personal API token before reconciliation. The change MUST NOT add PostgreSQL backups, bypass OIDC through local-password/admin or direct SQL account/token bootstrap, or promise recovery of read history, saved articles, preferences, sessions, or API credentials.

#### Scenario: Miniflux state is lost
- **WHEN** the operator reprovisions an empty Miniflux database and imports their existing or catalogue-generated OPML after signing in
- **THEN** feed subscriptions can be restored
- **AND** documentation makes clear that other application state and prior API credentials are not recovered

#### Scenario: Catalogue restores subscriptions through automation
- **WHEN** the operator signs in through authorized OIDC after database loss, creates a new personal API token, stores it securely in Vault, and explicitly runs targeted plan/apply automation
- **THEN** enabled catalogue subscriptions are restored through the native API without local-password/admin bootstrap or direct SQL subscription changes
- **AND** disabled catalogue entries and missing historical application state are not represented as recovered

#### Scenario: Old credentials survive only in Vault
- **WHEN** an API token retained outside the lost database is rejected by the newly provisioned reader
- **THEN** recovery reports the credential bootstrap requirement without creating duplicate users, disabling OIDC, or claiming fully unattended restoration
