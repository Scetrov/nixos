# Deferred Actions — historical requirements, not part of this change

The operator deferred Actions and chose to retain experimental code disabled.
These earlier requirements are reference material for a separately agreed future
change, not an active capability or acceptance gate for `add-private-forgejo`.
No end-to-end checkout/artifact compatibility has been accepted. Production
Forgejo Actions and runner activation remain off.

## Historical requirements

### Requirement: Trusted personal repository CI
The system SHALL run Forgejo Actions on Habiki for trusted owner repositories, using owner-user or explicitly selected repository registration scope rather than unrestricted instance-global scope. Initial supported workloads SHALL be tests and application builds, not container-image builds or deployments.

#### Scenario: Owner workflow runs
- **WHEN** an enabled trusted owner repository requests the configured runner label
- **THEN** its test/build workflow runs and reports its result to Forgejo

#### Scenario: Repository outside registration scope requests work
- **WHEN** a repository outside the runner's configured owner/repository scope requests the runner
- **THEN** that runner does not execute its job

### Requirement: Dedicated container execution boundary
The runner SHALL execute jobs in containers using a dedicated non-administrative account and a compatible rootless runtime isolated from Habiki's shared rootful runtime. Jobs MUST NOT receive privileged mode, a host-execution label, a container-engine socket, arbitrary host mounts, or unrelated service/deployment/runner secrets.

#### Scenario: Job inspects available credentials and mounts
- **WHEN** a test job inspects its environment and mounts
- **THEN** it cannot find runner registration credentials, unrelated service secrets, a host runtime socket, or host administrative storage

#### Scenario: Workflow requests prohibited execution
- **WHEN** a workflow requests privileged or direct host execution through this runner
- **THEN** the configured runner does not provide those capabilities

#### Scenario: Runtime compatibility is validated
- **WHEN** the selected rootless runtime is accepted for deployment
- **THEN** a real job has demonstrated checkout, application test/build execution, and artifact upload with that runtime

### Requirement: Resource and storage limits
The system SHALL limit runner concurrency to one job and enforce configurable job CPU/memory ceilings, initially 2 vCPUs and 2 GiB unless host-capacity validation requires lower limits. It SHALL bound or periodically clean runner-owned transient workspace/cache storage without deleting Forgejo data or other services' storage.

#### Scenario: Two jobs are queued
- **WHEN** two eligible jobs are ready simultaneously
- **THEN** at most one runs on the runner at a time

#### Scenario: Job exceeds its memory limit
- **WHEN** a job exceeds its configured memory ceiling
- **THEN** the runtime constrains or terminates the job instead of permitting unbounded memory consumption

#### Scenario: Transient data is cleaned
- **WHEN** runner cleanup executes
- **THEN** only intended runner-owned transient data is removed and Forgejo repositories remain intact

### Requirement: Repeatable registration and rotation
The system SHALL register and reconcile the runner through automation, keep registration credentials in protected persistent state outside job access, preserve valid registration across rebuilds, and support controlled revoked-credential recovery without duplicate runner records.

#### Scenario: Deployment repeats
- **WHEN** the runner is redeployed with valid existing registration
- **THEN** it reconnects as the existing runner without creating another registration

#### Scenario: Runner credentials are revoked
- **WHEN** controlled registration recovery is requested after revocation
- **THEN** automation establishes valid replacement credentials without disclosing them or leaving an unintended duplicate active runner

### Requirement: Job connectivity and reproducible acceptance
Job containers SHALL resolve and securely reach Forgejo for checkout and artifact exchange, with explicit DNS/TLS configuration where needed. The acceptance workflow SHALL use fully qualified digest-pinned job images and fully qualified commit-pinned actions, and SHALL require no deployment credentials.

#### Scenario: End-to-end acceptance workflow
- **WHEN** the acceptance workflow executes inside the selected job image
- **THEN** checkout, test/build, and artifact upload succeed with trusted TLS using the private Forgejo endpoint

#### Scenario: Host-only alias is insufficient
- **WHEN** job containers do not inherit Habiki's host aliases
- **THEN** the configured container DNS path still resolves the private Forgejo hostname correctly
