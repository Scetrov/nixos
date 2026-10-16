## Implementation

- [x] Preserve the supplied Hermes caduceus as a standalone SVG.
- [x] Render and visually inspect the transparent 512 × 512 PNG.
- [x] Document reproduction and extend offline tests.

## Verification and Deployment

- [x] Pass all four icon tests and repository-wide pre-commit checks.
- [x] Deploy through `scripts/play.sh --limit habiki --tags authentik-branding --skip-generated-refresh`.
- [x] Verify live HTTP 200 and exact PNG bytes (SHA-256 `84a4bc433bfd8b3f46e8e85508a4a46029a23fc849f16416e6ae2359f3f9f379`).
- [x] Sync the Hermes requirement into the application icon specification and archive this change.
