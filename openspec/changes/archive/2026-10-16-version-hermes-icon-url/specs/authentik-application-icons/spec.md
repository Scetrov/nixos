## MODIFIED Requirements

### Requirement: Current Hermes caduceus artwork

The Hermes application icon SHALL reproduce the operator-supplied caduceus
artwork with its original path, viewBox, transform, even-odd fill rule, and
cyan-to-blue gradient. A self-contained SVG source SHALL be retained alongside
a transparent 512 × 512 PNG served at a content-addressed Hermes branding URL.
The PNG filename SHALL include the first 12 hexadecimal digits of its SHA-256
checksum, and OpenTofu SHALL configure that URL as the application icon.

#### Scenario: Update Hermes branding without changing authentication

- **WHEN** the Hermes branding artwork changes
- **THEN** its application icon reference changes to a new content-addressed URL
- **AND** the new URL returns the rendered caduceus PNG without reusing the old image cache key
- **AND** no authentication policy change is needed
