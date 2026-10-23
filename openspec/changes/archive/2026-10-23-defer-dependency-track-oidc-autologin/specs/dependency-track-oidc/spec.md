## ADDED Requirements

### Requirement: Dependency-Track web login initiation stays explicit while auto-redirect is unsupported
The Dependency-Track web UI on habiki SHALL authenticate users through Authentik via the Dependency-Track OIDC login button on the DT login page, and SHALL NOT initiate the OIDC flow automatically, while the deployed Dependency-Track release (4.14.x) provides no supported auto-redirect or auto-initiate mechanism.

#### Scenario: Unauthenticated browser reaches the DT web UI
- **WHEN** a browser without a DT session loads `https://dtrack.net.scetrov.live`
- **THEN** the DT login page is shown with the Authentik OIDC login button, and the browser is not redirected automatically

#### Scenario: API-key automation is unaffected
- **WHEN** an automated client authenticates against `https://dtrack-api.net.scetrov.live` with a Dependency-Track API key
- **THEN** API access succeeds without any web login flow and is unaffected by the web login initiation behaviour

### Requirement: Auto-login deferral decision is recorded
The repository SHALL record the deferral of DT OIDC auto-login, including the version evidence, the rejected alternatives, and the re-evaluation triggers, so the decision can be revisited without re-investigating.

#### Scenario: Future work re-evaluates auto-login
- **WHEN** a future change evaluates automatic DT OIDC initiation (e.g. as part of a DT 5.x migration)
- **THEN** the recorded decision provides the evidence (DT 4.14.5 lacks the feature; upstream #1855 open), the rejected alternatives (patched pinned frontend image, Caddy-level redirect), and the triggers to re-open the work
