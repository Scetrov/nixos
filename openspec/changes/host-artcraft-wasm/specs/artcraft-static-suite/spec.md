## ADDED Requirements

### Requirement: Thirteen editors served as static WASM sites

Habiki SHALL serve PhotoCraft, PdfCraft, FilmCraft, VectorCraft, LightCraft, DesignCraft, EffectCraft, GridCraft, CADCraft, DeckCraft, SoundCraft, WordCraft and FigCraft at `https://artcraft.net.scetrov.live/<slug>/`, using lowercase repository names as slugs. Existing Caddy SHALL serve their complete static outputs without application backend services, persistent per-editor runtime containers or new listening ports.

#### Scenario: Launch each editor
- **WHEN** an authorized user opens each of the thirteen editor URLs in a supported browser
- **THEN** each editor initializes its browser interface and supports a basic local interaction
- **AND** required JS, WASM, fonts and other packaged assets load successfully under that editor's path

### Requirement: Path-safe static delivery

The site SHALL canonicalize each editor's slashless URL to its trailing-slash URL, serve WASM as `application/wasm`, and require revalidation of entry HTML. Missing assets and unknown application paths SHALL return 404 without directory listings or an unrelated editor's HTML. The authenticated root SHALL redirect to `/photocraft/`.

#### Scenario: Open a slashless application link
- **WHEN** an authorized user visits `/pdfcraft`
- **THEN** the browser is redirected to `/pdfcraft/`
- **AND** the application's relative assets resolve within that prefix

#### Scenario: Request a missing asset
- **WHEN** an authorized user requests a nonexistent asset or unknown editor path
- **THEN** Caddy returns 404 without a directory listing or fallback application document

#### Scenario: Request an entrypoint and WASM payload
- **WHEN** an authorized browser requests an editor's entry HTML and WASM payload
- **THEN** the HTML requires cache revalidation and the WASM response has content type `application/wasm`

### Requirement: Shared fail-closed Authentik access

All editor documents and assets SHALL require Authentik proxy authorization through Caddy using one shared hostname-level provider and the existing embedded outpost. The site's outpost callback routes SHALL remain reachable without a recursive authentication check. The initial policy SHALL allow the existing `All Applications` group, subject to operator confirmation before identity deployment, and SHALL NOT grant `General User` access or change existing group membership.

#### Scenario: Anonymous asset request
- **WHEN** an unauthenticated client requests an editor page or directly requests its JS, font or WASM asset
- **THEN** it receives an authentication response rather than the protected file

#### Scenario: Allowed and denied users
- **WHEN** a member of the approved shared access group completes login
- **THEN** the member can access all thirteen editors through the shared authorization boundary
- **AND** an authenticated user outside that group cannot access their pages or assets

#### Scenario: Unavailable outpost
- **WHEN** Caddy cannot obtain an authorization decision from the Authentik outpost
- **THEN** it does not serve protected application files

#### Scenario: Authentication round trip
- **WHEN** a user follows an editor launch URL and completes an Authentik login round trip
- **THEN** the outpost callback succeeds and the user returns to the requested editor path

### Requirement: Individually branded launcher applications

OpenTofu SHALL manage thirteen visible Authentik launcher applications, each with its own application name, corresponding trailing-slash launch URL and official locally served icon. Icon provenance SHALL record immutable upstream references and SHA-256 checksums. Tile visibility SHALL match the shared access policy; individual tiles SHALL NOT create independent proxy authorization boundaries.

#### Scenario: Inspect the authorized launcher
- **WHEN** a member of the approved shared group opens the Authentik launcher
- **THEN** all thirteen editor tiles have distinct correct launch URLs and retrievable official application icons
- **AND** the shared authentication application is hidden

#### Scenario: Inspect an unauthorized launcher
- **WHEN** a user outside the approved shared group opens the launcher
- **THEN** the editor tiles are not visible
- **AND** manually entering a launch URL still does not grant access

### Requirement: Pinned builds and safe automated publication

Build automation SHALL compile the thirteen web packages from explicit immutable source revisions with source integrity verification and locked dependencies, using pinned build tooling in an isolated environment without production secrets. Publication SHALL include all upstream runtime assets, reuse unchanged pinned outputs, and preserve the currently served editor when a candidate build or package check fails. Deployment automation SHALL retain one previous working publication for rollback.

#### Scenario: Build and repeat deployment
- **WHEN** the operator runs targeted ArtCraft automation for Habiki
- **THEN** the declared inputs produce checked static packages for the thirteen editors
- **AND** rerunning with unchanged inputs reuses existing successful outputs without creating runtime services

#### Scenario: Candidate build fails
- **WHEN** an editor's compilation or package validation fails
- **THEN** deployment reports the failure and does not replace that editor's currently served files

#### Scenario: Restore a previous publication
- **WHEN** the operator selects the retained previous publication through deployment automation
- **THEN** the previous working static package is restored without changing the editor URL or shared access policy

### Requirement: Integrate with existing infrastructure automation

DNS aliases, Caddy routes, static file publication, branding and Authentik resources SHALL be managed through the repository's Ansible/NixOS and OpenTofu conventions. All OpenTofu operations SHALL use `scripts/tofu.sh`. The new hostname SHALL resolve to Habiki through the existing local-networking/device-host conventions and use existing TLS and Caddy logging infrastructure without exposing additional endpoints.

#### Scenario: Verify targeted deployment
- **WHEN** ArtCraft is deployed using host/component targeting
- **THEN** the hostname resolves to Habiki, HTTPS serves the authenticated suite and requests appear in existing Caddy log collection
- **AND** existing applications retain their routes and authorization policies
