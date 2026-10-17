## ADDED Requirements

### Requirement: Native authentication configuration is declarative

The system SHALL manage the native passkey authentication configuration and relevant brand/flow selection through OpenTofu. All OpenTofu operations MUST use `scripts/tofu.sh`. Managed objects MUST have one declarative owner; unrelated brand settings, packaged fallback stages, and application authorization MUST be preserved. Secrets MUST remain vaulted or runtime-injected and MUST NOT appear in committed files or evidence.

#### Scenario: Candidate provisioning
- **WHEN** the candidate configuration is provisioned before activation
- **THEN** the previous authentication flow remains selected
- **AND** the reviewed plan contains no unrelated configuration changes

#### Scenario: Existing ownership
- **WHEN** the existing brand selects the candidate
- **THEN** its existing OpenTofu ownership and unrelated settings are preserved without competing blueprint management

### Requirement: Native passkeys authenticate without redundant challenges

A valid discoverable WebAuthn assertion with required user verification SHALL identify and authenticate its account without username, password, or redundant login MFA. Skipping identification, password, or applicable login MFA after passkey success MUST rely only on trusted native success in the current transaction; choosing password fallback is not authenticated success. Existing application authorization and independent step-up requirements MUST remain unchanged.

#### Scenario: Existing compatible passkey
- **WHEN** the operator uses an existing compatible passkey with the recorded browser/device against the candidate
- **THEN** login succeeds without username, password, or redundant login MFA

#### Scenario: Rejected authentication
- **WHEN** an assertion is invalid or lacks required user verification
- **THEN** it cannot establish a session or satisfy a stage bypass

#### Scenario: Forged success state
- **WHEN** a client supplies a success-like parameter without completing verified WebAuthn authentication
- **THEN** password and applicable MFA cannot be skipped on that basis

### Requirement: Native entry attempts passkeys before fallback

The login entry point SHALL initiate native passkey authentication before requiring a username or password. After cancellation or failure, the page SHALL offer a visible route to username/password login with existing applicable MFA, without relying solely on browser Back. Native conditional UI MAY supplement this behavior where supported, but is not a substitute for the explicit passkey-first path. The change MUST NOT introduce custom passkey CSS or login JavaScript. Native configuration feasibility and any broader configuration ownership impact MUST be reviewed before implementation or further live changes; investigation does not establish acceptance.

#### Scenario: Conditional UI available
- **WHEN** optional native conditional UI is configured and supported by the client
- **THEN** it offers native passkey discovery without requiring a typed username

#### Scenario: Conditional UI unavailable
- **WHEN** conditional UI is unavailable
- **THEN** the entry point initiates the native explicit passkey path before asking for username/password
- **AND** cancellation or failure leaves a visible password/MFA fallback action available without browser Back

### Requirement: Existing access paths are preserved

The change SHALL retain accessible password login with existing applicable MFA, existing credentials and enrollment, RP identity, recovery routing, and the administrator helper's explicit `default-authentication-flow` target. It MUST NOT require universal re-enrollment, weaken MFA for automation, enable the disabled bootstrap administrator, or introduce a recovery bypass. A new enrollment path SHALL be included only for a demonstrated compatibility need; if included, it MUST require authorized enrollment, discoverable credentials, and user verification.

#### Scenario: Password and MFA fallback
- **WHEN** a user signs in through fallback
- **THEN** the existing password and applicable MFA protections remain effective
- **AND** an invalid password or incomplete required MFA does not establish a session

#### Scenario: Cancelled or failed passkey attempt
- **WHEN** a user cancels or fails a passkey prompt
- **THEN** the page offers a visible action returning to working password/applicable-MFA fallback without a redirect loop or an MFA bypass
- **AND** the fallback preserves the original application return destination

#### Scenario: Unchanged administrator and recovery routing
- **WHEN** the candidate becomes the selected interactive login flow
- **THEN** helper/caller routing remains explicitly on the existing fallback flow
- **AND** existing recovery and enrollment routes and protections are not changed merely to support passkey login

#### Scenario: Additional enrollment is necessary
- **WHEN** a demonstrated compatibility gap requires a new passkey enrollment path
- **THEN** only an authenticated or otherwise securely authorized account can enroll a discoverable, user-verified credential
- **AND** existing credentials remain intact

### Requirement: Deployment is verified and reversible

Candidate provisioning and activation MUST each have operator approval. Activation SHALL require focused configuration/authentication checks, successful candidate use with the operator's existing passkey/browser, working fallback, and one representative application-return check. Known failures affecting these paths MUST block activation until resolved. The prior flow MUST remain available for declarative rollback, and a subsequent wrapper plan SHALL show no unintended drift. Existing authentication telemetry MUST remain available without sensitive authentication payloads.

A hardware-class matrix, comprehensive recovery audit, live repair exercise for unchanged automation, mandatory restart/rebuild, production rollback drill, or upstream WebAuthn conformance suite SHALL NOT be a completion requirement. These exclusions do not waive observed regressions or authorize weakening existing protections.

#### Scenario: Scoped candidate acceptance
- **WHEN** candidate acceptance is recorded
- **THEN** it identifies the tested existing passkey/browser combination and focused check outcomes without credential material
- **AND** untested combinations are documented as unverified rather than universally supported

#### Scenario: Application return
- **WHEN** login starts from one representative existing application
- **THEN** authentication completes and returns to that application without changing its authorization policy

#### Scenario: Approved activation
- **WHEN** scoped candidate acceptance passes and the operator separately approves activation
- **THEN** the existing brand/flow selection is changed through a reviewed wrapper plan/apply
- **AND** passkey login, fallback, existing error telemetry, and subsequent configuration drift are checked

#### Scenario: Rollback
- **WHEN** activation causes an authentication regression
- **THEN** restoring the previous declarative selection through the wrapper restores the prior route without deleting users or credentials
- **AND** fallback access is rechecked

### Requirement: Operational guidance is concise and truthful

Documentation SHALL state the native UI limitation, tested client/passkey combination, unchanged fallback/admin targets, any actual enrollment need, activation selection, and rollback procedure. Evidence MUST distinguish completed checks, unresolved in-scope failures, and deferred work. It MUST NOT claim that existing recovery controls or untested devices have been certified.

#### Scenario: Scope and evidence
- **WHEN** the change is documented for completion
- **THEN** required scoped acceptance has recorded outcomes
- **AND** deferred recovery/device/conformance work is not represented as either passed testing or an additional activation gate
