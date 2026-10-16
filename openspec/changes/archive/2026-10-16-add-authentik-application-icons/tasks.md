## 1. Identify and prepare assets

- [x] Identify official Forgejo and Miniflux artwork and pin source provenance.
- [x] Prepare 512 × 512 PNGs and document reproduction and deployment.

## 2. Configure and test

- [x] Add both assets to Ansible's branding copy task and a targeted deployment tag.
- [x] Update both Authentik application icon references through OpenTofu.
- [x] Add and pass three offline icon contract tests.

## 3. Deploy and verify

- [x] Deploy branding to Habiki using targeted Ansible automation.
- [x] Review and apply the targeted plan: zero additions, two metadata updates,
  zero deletions.
- [x] Verify all six visible application icons return HTTP 200 and both new PNGs
  match checked-in checksums; leave two hidden applications unchanged.
- [x] Run repository-wide pre-commit gates successfully.
