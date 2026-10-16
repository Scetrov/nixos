## ADDED Requirements

### Requirement: Appropriate icons for visible applications

Every visible Authentik application SHALL have an appropriate application icon.
Forgejo and Miniflux SHALL use official upstream artwork, served locally as
512 × 512 PNGs from the existing branding volume. Source provenance SHALL include
immutable upstream URLs and SHA-256 checksums.

#### Scenario: Inspect the application launcher inventory

- **WHEN** the complete application inventory is queried
- **THEN** every non-hidden application has a non-empty, retrievable icon
- **AND** Forgejo uses Forgejo artwork rather than Gitea artwork
- **AND** Miniflux uses its official application icon

### Requirement: Declarative targeted deployment

Ansible SHALL deploy the icon assets and OpenTofu SHALL own their application
metadata references. Branding-only deployment SHALL avoid unrelated host rebuilds
and SHALL NOT change application access policies or expose new ports.

#### Scenario: Deploy updated application icons

- **WHEN** branding assets and the two application metadata changes are deployed
- **THEN** both local icon URLs return the exact checked-in PNG bytes
- **AND** existing applications and authorization boundaries remain unchanged
