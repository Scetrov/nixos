# filebrowser-documents-service Specification

## Purpose
Provide enrolled users with browser access to their own Habiki Documents trees through one shared, non-root FileBrowser Quantum service, native Authentik OIDC, explicit enrollment, and managed filesystem interoperability.

## Requirements

### Requirement: Shared private Quantum runtime

The system SHALL deploy one FileBrowser Quantum instance on Habiki using the amd64 image `ghcr.io/gtsteffaniak/filebrowser@sha256:989e2dc6c491bda3c8bb82b27cd7798924ff3025cabdcad2444eb42f774836f6` (v2.1.3-beta, verified and operator-approved 2026-10-23 as a security-fix exception), a dedicated non-root host service identity with explicit host UID mapping, and persistent private application state. It SHALL expose the backend only through the approved HTTPS Caddy route and SHALL mount only explicitly enrolled Documents trees, not entire Unix homes. Each source SHALL be private and unavailable by default to new or existing users until explicitly assigned; WebDAV and ordinary local-password authentication SHALL be disabled.

#### Scenario: Private service startup
- **WHEN** the service is deployed or restarted
- **THEN** it runs as the dedicated non-root identity, retains application state, and has no directly exposed backend port or broad home-directory mount
- **AND** access through optional public shares or WebDAV is unavailable

### Requirement: Explicit identity enrollment and account provisioning

The system SHALL maintain a declarative mapping from approved Authentik identities to unique Unix accounts and Quantum scopes. It SHALL create missing explicitly approved accounts and their configured-home Documents directories through automation, reuse existing accounts without altering their identity or login settings, and reject ambiguous mappings or unsafe paths. Ordinary SSO login SHALL NOT create a Unix account or grant a directory based solely on an email, display name, or unapproved username.

#### Scenario: Enroll a user whose Unix account is missing
- **WHEN** an administrator applies a valid enrollment for an approved Authentik identity whose Unix account does not yet exist
- **THEN** automation creates the approved Unix account and its Documents directory and configures only that user's Quantum scope
- **AND** it does not enable password or SSH access merely to support browser file access

#### Scenario: Reuse an existing Unix account
- **WHEN** a valid enrollment references an existing Unix account
- **THEN** automation preserves its UID, credentials, shell, groups, and Documents contents

#### Scenario: Reject unsafe or ambiguous enrollment
- **WHEN** enrollment duplicates a Unix account assignment, reassigns an existing identity without approval, or resolves Documents through an unsafe path or symlink
- **THEN** automation rejects the enrollment before granting filesystem or application access

### Requirement: Authentik native SSO authorization

The service SHALL authenticate ordinary users through native Authentik OIDC with a strict callback URI and explicit application authorization. It SHALL map the approved identity to the enrolled Unix username using administrator-controlled application-specific claims, emitting the exact enrolled username as `preferred_username`. It SHALL deny data access to unauthenticated, unenrolled, or unauthorized identities, disable ordinary local signup/password login, and keep operator administration separate from ordinary file access. Initial approved Unix usernames SHALL be exactly `scetrov`, `pinkgiraffes`, and `flyingfire`; claim spelling/casing SHALL be verified against the selected Quantum release before any scope is granted.

#### Scenario: Approved login
- **WHEN** an enrolled identity authorized for the application completes OIDC login
- **THEN** Quantum recognizes the mapped user and grants only their declared Documents scope

#### Scenario: Authenticated but unenrolled identity
- **WHEN** an Authentik identity without an approved enrollment attempts access
- **THEN** the service denies access to every Documents source and does not create a Unix account

#### Scenario: Ordinary membership does not grant administration
- **WHEN** an ordinary enrolled user signs in
- **THEN** they cannot administer Quantum users, sources, scopes, or global service settings

### Requirement: Full access confined to the user's literal Documents tree

Each ordinary enrolled user SHALL have full browse, search, preview, download, upload, create, edit, rename, move, and delete access within their own literal configured-home Documents directory, subject to effective host permissions. The service SHALL NOT silently exclude subdirectories based on names. It SHALL deny reads, writes, and metadata access outside the user's declared scope through UI and API paths, including traversal, symlinks, search, previews, and cross-source operations.

#### Scenario: Manage the complete Documents tree
- **WHEN** an enrolled user performs supported file operations within their own Documents tree
- **THEN** the operations succeed for entries with the managed effective permissions, including nested directories without name-based exclusions

#### Scenario: Attempt cross-user or out-of-scope access
- **WHEN** a user attempts to list, search, preview, download, copy, modify, or delete another user's data or escape their mount through an API path or symlink
- **THEN** access is denied without exposing the target's contents or metadata

### Requirement: Unix-owner and service filesystem interoperability

Automation SHALL manage named-user access and default ACLs for existing and newly created enrolled content so that both the service identity and the corresponding Unix user can manage it. Browser-created content SHALL be permitted to remain service-owned, provided the Unix user retains full effective access. When widening an ACL mask for managed entries, automation SHALL preserve the prior effective permissions of unrelated ACL entries and SHALL restore prior ACL state on rollback. It SHALL avoid following symlinks and recursive ownership changes, and SHALL NOT grant equivalent access to unrelated Unix users.

#### Scenario: Unix user manages a browser upload
- **WHEN** Quantum uploads a file, creates a nested directory, or replaces an existing file
- **THEN** the corresponding Unix user can read, edit, rename, and delete the resulting content and create children in the resulting directory despite service ownership

#### Scenario: Quantum manages Unix-created content
- **WHEN** the Unix user creates nested content under an ACL-managed Documents directory with the supported default permission behavior
- **THEN** Quantum can manage that content through the user's scope without root privileges

#### Scenario: Existing entries and deliberate permission restrictions
- **WHEN** automation initializes existing entries or encounters a later deliberate restrictive chmod or ACL change
- **THEN** initialization preserves ownership and unrelated ACLs
- **AND** inaccessible operations fail clearly without privilege escalation or access to another user's content

### Requirement: Declarative reconciliation and fail-closed enrollment changes

Service configuration, enrollment, Authentik resources, and Quantum account/source/scope assignments SHALL be provisioned through repository automation. OpenTofu operations SHALL use `scripts/tofu.sh`. Repeated application SHALL converge without duplicating resources or broadening grants. Quantum may auto-create an account after successful OIDC authorization; such accounts SHALL have no data access before their explicit assignments exist. Automated offboarding is deferred by explicit operator decision for the initial family rollout. Automation SHALL reject removal or reassignment of an existing enrollment and keep the public route unavailable rather than apply an unverified revocation lifecycle. Unix accounts, Documents data, and Unix-owner access to service-created files SHALL be preserved.

#### Scenario: Reapply configuration and restart
- **WHEN** the same declaration is reapplied and Quantum restarts
- **THEN** only declared sources remain granted, no resources are duplicated, and a broad default source is not assigned

#### Scenario: First login precedes scope assignment
- **WHEN** Quantum creates an OIDC account before explicit scope reconciliation completes
- **THEN** the account cannot access any Documents source until its approved assignment is applied

#### Scenario: Reject unsupported enrollment removal
- **WHEN** an administrator removes an existing enrollment and attempts deployment
- **THEN** automation rejects the change and keeps the public route unavailable pending a separately reviewed revocation procedure
- **AND** it does not delete Unix accounts or Documents contents or remove Unix-owner access to browser-created content

### Requirement: Secure and observable operation

The system SHALL source credentials from the encrypted vault and inject them at runtime without committed plaintext or Nix-store secrets. It SHALL collect runtime/reconciliation logs into the existing Loki/Grafana stack without credentials or file contents and provide a service-health signal with an actionable alert. Deployment and recovery documentation SHALL describe targeted Habiki operations, identity enrollment/removal, the accepted file-ownership model, and application-state restoration without overwriting Documents data.

#### Scenario: Operate and recover the service
- **WHEN** the service fails or an operator restores its application state
- **THEN** the failure is visible through the existing observability stack and the documented recovery path preserves personal Documents contents
- **AND** no credential or file content is emitted into operational logs
