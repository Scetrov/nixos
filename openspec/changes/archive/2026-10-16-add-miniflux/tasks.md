## Sign-off and accepted deferrals

On 2026-10-16 the operator confirmed the deployed service works and explicitly approved archiving and committing with documented verification deferrals. Unchecked tasks 3.4, 5.4 and 5.5 below retain the unperformed portions of their original scope; they are not claims of failed service operation or passed tests. See verification.md for independent live evidence. The confirmation does not individually establish repeatability, fault/rotation recovery, negative authorization, authenticated API, OPML or notification-delivery coverage.

## 1. Verify implementation prerequisites

- [x] 1.1 Inspect the deployed NixOS Miniflux module, credential/configuration precedence, migration behavior, and dynamic-user restrictions; record the selected free loopback port.
- [x] 1.2 Verify the latest applicable released package, release age, and security status against primary sources; select an integrity-pinned package consistent with the seven-day non-critical update policy.
- [x] 1.3 Confirm the existing operator identity and authorization selector, OIDC first-login behavior, and whether reader operation requires an automated administrator bootstrap.

## 2. Provision identity and secrets

- [x] 2.1 Add the Miniflux Authentik confidential OIDC provider, strict callback, application, and operator-only group/policy binding through OpenTofu, preserving unrelated group memberships.
- [x] 2.2 Export provider-generated credentials into the existing protected generated-secret workflow and add missing/empty/placeholder validation and redacted consistency checks.
- [x] 2.3 Add the Vault-backed database credential and agenix rendering for database and generated OIDC inputs, with restricted runtime access and no plaintext tracked outputs.
- [x] 2.4 Add regression coverage for unauthorized-user denial, strict redirect configuration, generated-secret validation, and non-disclosure of credentials.

## 3. Integrate the native runtime and shared database

- [x] 3.1 Add the Habiki Miniflux integration module and enable flag using the native service, loopback binding, public base URL, disabled local database creation, and bounded database connection use.
- [x] 3.2 Add idempotent database/role reconciliation after PostgreSQL readiness with safe SQL quoting, bounded failures, migration ownership, least privileges, and non-destructive repeated execution.
- [x] 3.3 Configure native OIDC, automatic authorized account creation, disabled local login, runtime secret files, and correctly ordered credential rotation/restart behavior.
- [ ] 3.4 Test first setup, repeated setup, password rotation, PostgreSQL outage/restart, migration startup, restricted database privileges, and runtime credential accessibility using isolated disposable database/container fixtures without touching production data.

## 4. Wire routing, observability, and deployment

- [x] 4.1 Add the Caddy HTTPS virtual host and local networking alias, avoiding blanket forward authentication and any new Grafana dependency for the feed service; deny public metrics access.
- [x] 4.2 Add private Prometheus scraping, identifiable Alloy/Loki service logs, and sustained availability alerting with existing routing.
- [x] 4.3 Add the Miniflux targeted deployment tag and help text, ensuring provider provisioning and generated-secret refresh precede consumer secrets, database setup, and NixOS activation.
- [x] 4.4 Add tests for deployment ordering/targeting, Caddy metrics denial, native API routing, loopback-only listeners, DNS aliasing, monitoring configuration, and disabled-service hygiene.

## 5. Validate and document operations

- [x] 5.1 Document targeted deployment, OIDC access policy, safe credential verification/rotation, shared-database coupling, and the single-trusted-user outbound-fetch boundary.
- [x] 5.2 Document OPML import/export and empty-database recovery, explicitly accepting other state loss and adding no PostgreSQL backup jobs; document non-destructive rollback and schema downgrade limitations.
- [x] 5.3 Run relevant regression tests, NixOS evaluation, Ansible/OpenTofu formatting and validation through approved tooling, secret scanning, and configured pre-commit gates; resolve failures before sign-off.
- [ ] 5.4 Preview infrastructure changes through `scripts/tofu.sh` and perform the targeted Habiki deployment; verify repeatability, database isolation, HTTPS/DNS, feed fetching, credential consistency, private metrics, logs, and alert routing.
- [ ] 5.5 Complete operator-assisted authorized/unauthorized OIDC and local-login checks, OPML import, and authenticated/unauthenticated native API checks without exposing credentials.
- [x] 5.6 Review rollback resource cleanup and retained-database behavior without deleting production data; record validation evidence and any remaining operator actions.
- [x] 5.7 Archive the completed OpenSpec change before final commit/PR, confirm no sensitive material is staged, and stage all required implementation and archived-spec files for sign-off.
