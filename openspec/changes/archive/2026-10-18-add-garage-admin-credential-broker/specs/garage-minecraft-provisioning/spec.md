## ADDED Requirements

### Requirement: Wrapper-managed Minecraft resources

The system SHALL provision the `minecraft` bucket, dedicated S3 key and permission binding through OpenTofu using `scripts/tofu.sh` and the authenticated Caddy broker. Provider selection SHALL follow existing dependency policy. The key SHALL have read, list and write permissions only on `minecraft`, with owner and bucket-creation authority disabled and no other grants. Existing resource names SHALL require ownership review before adoption. The bucket SHALL be protected against accidental deletion.

#### Scenario: Backup ZIP upload succeeds
- **WHEN** the operator's laptop uses the dedicated pair to upload a backup ZIP to `minecraft` through `https://s3.net.scetrov.live` with region `garage` and path-style addressing
- **THEN** the upload SHALL succeed and the ZIP SHALL be readable and listable with the same pair

#### Scenario: Dedicated key exceeds its permissions
- **WHEN** the key attempts owner operations, bucket creation or access to an unrelated bucket
- **THEN** Garage SHALL deny the operation

### Requirement: Encrypted credential persistence

The access key and secret SHALL be stored in the main Ansible Vault and represented as sensitive values in remote state. The implementation SHALL use supported provider-supplied key inputs or securely capture provider-generated outputs. Vault updates SHALL preserve unrelated values and replace the encrypted file atomically. Credentials SHALL NOT be printed or persisted as plaintext repository files. Failed export after successful apply SHALL be recoverable using the same state-held pair without replacing the key.

#### Scenario: Credentials are persisted
- **WHEN** provisioning completes successfully
- **THEN** the same usable pair SHALL be available in Vault and sensitive remote state without exposure in normal output

#### Scenario: Vault export fails
- **WHEN** apply succeeds but encrypted Vault persistence fails
- **THEN** the workflow SHALL report failure and support persisting the existing pair on retry without key replacement

### Requirement: Safe existing workflow integration

The wrapper SHALL obtain its machine token without exposing credentials and SHALL retain credential-free local formatting, validation and fixture modes. Identity/broker bootstrap SHALL work before Garage resource provisioning. Before writing new live credentials to state, implementation SHALL verify protected backend transport and pause for separately agreed remediation if absent; sensitivity flags SHALL NOT be treated as encryption.

#### Scenario: Local checks run
- **WHEN** the wrapper runs a supported credential-free local check
- **THEN** it SHALL NOT load production credentials or request a machine token

#### Scenario: Backend protection is unverified
- **WHEN** no protected transport can be established for the existing state connection
- **THEN** live credential provisioning SHALL pause and identify the prerequisite without expanding this change silently

### Requirement: Verified repeatability and non-destructive rollback

Completion SHALL include a successful provider/authentication compatibility check, live upload and denied-access checks, confirmed Vault persistence and an unchanged repeat plan. Effective permissions SHALL be verified as read/list/write only, including the provider's treatment of disabled permissions. Rollback SHALL preserve the bucket, objects and client credentials while disabling management access. The bucket serves as Drive-style storage; overwriting and deleting objects is intended behaviour for the Minecraft key. Documentation SHALL explain that write permits overwrite/deletion and is not immutable backup protection, and that irreplaceable data requires a separate recovery mechanism. The intended consumer of the S3 pair is the operator's laptop manual backup workflow; the Minecraft server, automation and any other clients SHALL NOT receive the pair, the Authentik management identity or the native Garage token.

#### Scenario: Provisioning is repeated
- **WHEN** the unchanged configuration is planned after successful apply
- **THEN** it SHALL propose no resource or credential replacement

#### Scenario: Management route is rolled back
- **WHEN** operators disable the new route and dedicated management identity/token
- **THEN** existing S3 endpoints, Minecraft objects and encrypted client credentials SHALL remain intact
