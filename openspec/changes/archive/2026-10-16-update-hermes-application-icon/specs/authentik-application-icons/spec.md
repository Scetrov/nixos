## ADDED Requirements

### Requirement: Current Hermes caduceus artwork

The Hermes application icon SHALL reproduce the operator-supplied caduceus
artwork with its original path, viewBox, transform, even-odd fill rule, and
cyan-to-blue gradient. A self-contained SVG source SHALL be retained alongside
a transparent 512 × 512 PNG served at the existing Hermes branding URL.

#### Scenario: Update Hermes branding without changing authentication

- **WHEN** the Hermes branding asset is deployed
- **THEN** its existing icon URL returns the rendered caduceus PNG
- **AND** no application metadata or authentication policy change is needed
