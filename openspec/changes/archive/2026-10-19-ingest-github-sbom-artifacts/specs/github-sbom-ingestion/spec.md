## ADDED Requirements

### Requirement: Explicit trusted producer contract
The collector SHALL ingest only configured repositories, trusted workflow identities, successful workflow attempts, permitted events/refs, and named versioned CycloneDX JSON artifacts. The producer contract SHALL define expected JSON path, supported schema versions, triggers/cadence, and retention longer than the supported outage window. Untrusted fork/PR artifacts SHALL be rejected by default. Selection SHALL be independent of Forgejo mirror policy; producer jobs MUST NOT receive Dependency-Track credentials.

#### Scenario: Trusted successful producer
- **WHEN** a successful workflow attempt matches the configured repository, workflow, event/ref, and artifact contract
- **THEN** its artifact becomes eligible for bounded validation and ingestion

#### Scenario: Untrusted or mismatched producer
- **WHEN** an artifact comes from an unapproved repository/workflow/ref, a failed run, or a disallowed pull-request/fork event
- **THEN** the collector rejects it without uploading a BOM even if its filename and payload appear valid

#### Scenario: Expired artifact
- **WHEN** an eligible artifact has expired before download
- **THEN** the collector records a recoverable retention gap and documents rerun/republication rather than recording an accepted upload

### Requirement: Dedicated multi-installation GitHub App authentication
The collector SHALL authenticate using a dedicated SBOM GitHub App with one App ID and runtime-protected RSA private key, plus a configured nonempty array of approved installation IDs. It SHALL resolve the installation for each explicitly configured repository, reject unapproved or suspended installations, and request short-lived tokens scoped to that repository ID and Actions read only (plus implicit Metadata read). It SHALL keep tokens in memory, refresh before expiration and never persist or log the private key, App JWTs or installation tokens. An all-repository App installation SHALL NOT expand artifact ingestion beyond the configured producer allowlist. The Grafana observability App SHALL remain unchanged.

#### Scenario: Multiple organisations use one dedicated App
- **WHEN** configured repositories belong to different approved installations of the dedicated App
- **THEN** each repository uses a token minted for its own installation and explicitly restricted to that repository with Actions read

#### Scenario: Unconfigured repository or installation
- **WHEN** authentication is requested for an unconfigured repository or its installation ID is outside the configured array
- **THEN** the collector refuses to mint an installation token and does not fall back to broader credentials

#### Scenario: Token expires or service restarts
- **WHEN** a cached installation token is close to expiry or the collector starts without a cache
- **THEN** it obtains a fresh scoped token without changing accepted-upload checkpoints or storing credentials in them

### Requirement: Artifact handling is bounded and non-executable
The collector SHALL enforce configured compressed/expanded size, file-count, time, disk, and JSON-complexity bounds; validate available digests; and reject unsafe paths, symlinks, duplicate/ambiguous payloads, unsupported schemas, and malformed CycloneDX. Schema validation SHALL use locally packaged integrity-verified schemas without remote reference resolution. No downloaded content SHALL be executed, and SBOM generation SHALL remain outside the collector.

#### Scenario: Valid artifact
- **WHEN** an approved archive contains the single expected valid CycloneDX JSON payload within all limits
- **THEN** validation yields a bounded payload without executing repository code or resolving remote schemas

#### Scenario: Hostile artifact
- **WHEN** an archive contains traversal, absolute paths, symlinks, duplicate payloads, excessive expansion, an available digest mismatch, or invalid schema content
- **THEN** it is rejected before BOM submission and protected host files remain unchanged

### Requirement: Trusted target and version mapping
The collector SHALL derive target project UUID/version from trusted repository/ref configuration rather than SBOM fields or archive paths. Default upload SHALL use pre-created projects with autoCreate=false. Rolling development and release mappings SHALL be documented explicitly; per-target ordering SHALL prevent stale runs from overwriting a newer inventory. Any future automatic provisioning SHALL require separately approved constrained permissions and automation.

#### Scenario: Payload attempts target substitution
- **WHEN** an otherwise valid SBOM declares a project identity different from the configured mapping
- **THEN** it cannot redirect the upload to another project or create an arbitrary project

#### Scenario: Older inventory arrives late
- **WHEN** an older authorized run is discovered after a newer inventory upload has been accepted for the same target
- **THEN** the older inventory does not overwrite the newer inventory

#### Scenario: Project version has no configured target
- **WHEN** a source version lacks an authorized pre-provisioned target mapping
- **THEN** ingestion reports the mapping gap rather than implicitly creating a project

### Requirement: Durable idempotent uploads
The collector SHALL persist atomic state keyed by repository identity, workflow run/attempt, artifact identity/digest, and destination UUID/version. It SHALL record an accepted submission and its returned tracking token, avoid normal repeated submissions after restart, serialize per-target uploads, and retry boundedly without advancing accepted-upload checkpoints on transfer failures. Upload acceptance SHALL be the collector's completion boundary, not proof of successful internal Dependency-Track processing. The collector SHALL NOT require processing-token polling, inventory read-back, or correlated logs as confirmation. The documented recovery model SHALL disclose any ambiguous at-least-once resubmission window.

#### Scenario: Repeat poll
- **WHEN** an already accepted artifact/target key is discovered again
- **THEN** it is not resubmitted and the accepted-upload checkpoint remains intact

#### Scenario: Submission is accepted but processing fails
- **WHEN** the BOM API accepts a submission but asynchronous processing subsequently fails
- **THEN** the collector retains its accepted-upload checkpoint without claiming verified ingestion; internal processing remains Dependency-Track's responsibility

#### Scenario: Restart after submission
- **WHEN** the service restarts with a persisted accepted submission and token
- **THEN** it skips uploading the same artifact again without needing to check internal processing

#### Scenario: Ambiguous acceptance
- **WHEN** a connection or crash prevents determining whether submission was accepted before the token was persisted
- **THEN** recovery records the ambiguity and follows documented bounded retry behavior without claiming exactly-once delivery

### Requirement: Private declarative operation and recovery
The collector SHALL run unprivileged on the private NixOS host as a oneshot service with a Persistent=true timer, bounded scratch/state access, least-required egress, and non-overlapping execution. Credentials SHALL be least-privilege and delivered through protected runtime secret paths, never committed, stored in Nix expressions, checkpoints, artifacts, or ordinary logs. Deployment SHALL use targeted existing automation without public ingress, a private-network CI runner, or repository-code execution. Existing journal/Loki and Prometheus/Grafana integration SHALL distinguish idle polls, accepted uploads, backlog, rejections, and failures.

#### Scenario: First vertical slice
- **WHEN** one authorized repository/workflow/artifact and one pre-created target are configured and enabled
- **THEN** the private host fetches outbound, validates the artifact and uploads its BOM with API acceptance without exposing Dependency-Track or sharing its API key with GitHub Actions

#### Scenario: Restart and credential rotation
- **WHEN** the service/host restarts or protected credentials rotate through automation
- **THEN** polling resumes from durable state using current credentials without printing or persisting bearer secrets

#### Scenario: Ingestion stalls and collection is disabled
- **WHEN** backlog exceeds policy or collection is disabled
- **THEN** stalled uploading is observable and disabling removes collector activity without deleting existing projects, inventories, or checkpoint evidence
