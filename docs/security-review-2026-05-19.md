# Security Review - 2026-05-19

## Executive Summary

Overall risk rating: **Critical**.

The repository has strong infrastructure-as-code intent, but several current workflows still move high-value credentials through unsafe boundaries: shell interpolation, command-line arguments, temporary plaintext files, debug output, and repository-managed encrypted bundles. The most urgent risks are token exposure during OpenTofu/Ansible handoff, public or weakly protected observability routes, and trusted-proxy headers that can become identity bypasses if direct service access is reachable.

Immediate priorities:

1. Stop printing or writing generated tokens in plaintext, remove `terraform/grafana_oncall_token.json`, and rotate any token generated or exposed through that path.
2. Put authentication in front of all read-capable `metrics.net.scetrov.live` routes, especially Loki and other observability backends.
3. Restrict Hermes trusted-proxy authentication to the actual Caddy/Auth proxy path and localhost/private proxy networks only.
4. Add automated secret scanning before commit and in CI, including history-aware scans for this repository.

## Scope

Reviewed areas:

- `src/` NixOS modules, Ansible roles, inventories, encrypted secret references, and generated secret flow.
- `terraform/` OpenTofu providers, variables, outputs, ignore rules, and local generated artifacts.
- `scripts/` operator wrappers and deployment helpers.
- `docs/`, `README.md`, and `AGENTS.md` for operational workflow guidance.
- Local redacted secret-scan results from `gitleaks dir . --redact` and `gitleaks detect --redact`.

Not reviewed:

- Live service authorization state beyond what is declared in the repository.
- Decrypted Ansible Vault contents or age-encrypted secret values.
- Cloud provider, DNS provider, or external account settings except where repository code references them.

## Secret-Scan Evidence

Redacted local scan commands were run on 2026-05-19:

| Command | Result | Evidence |
| --- | --- | --- |
| `gitleaks dir . --redact` | Failed with 1 finding | `terraform/grafana_oncall_token.json:1`, rule `grafana-service-account-token` |
| `gitleaks detect --redact` | Failed with 3 history findings | `src/roles/secrets/files/cloudflared/woodford.json:1` at commit `c81c94daf84cfe636d7ad9bb6ef83abeb2e3c13f`; `src/roles/nixos/files/etc/nixos/modules/dnscrypt-proxy.nix:23` at commit `6cd94ee96e982ac16fd4a750f58ab23be9075c3e`; `src/modules/networking.nix:31` at commit `6a1ff3b61cb3568ef4bf1553e47697d7ee582847` |

No secret values are reproduced in this report.

## Findings

| ID | Severity | Affected Paths | Evidence | Impact | Remediation Owner / Action |
| --- | --- | --- | --- | --- | --- |
| SR-001 | Critical | `src/secrets.yml`, `src/generated-secrets.yml`, `src/roles/secrets/files/secrets/secrets.nix`, history findings | The repository tracks encrypted operational secret bundles and age secret metadata (`src/roles/secrets/files/secrets/secrets.nix:14`, `:18`, `:24`, `:28-36`). Redacted `gitleaks detect` still reports three historical leaks. | A compromised repo, vault password, age identity, or historical clone can expose long-lived infrastructure credentials. Historical findings mean affected credentials should be treated as potentially exposed unless rotation is proven. | Platform owner: rotate credentials associated with history findings, document rotation status, review the vault/age trust hierarchy, and keep encrypted secret material out of broadly cloned repos where feasible. |
| SR-002 | Critical | `scripts/tofu.sh`, `src/roles/authentik-config/tasks/main.yml`, `terraform/grafana_oncall_token.json` | `scripts/tofu.sh` loads vault output into shell variables (`scripts/tofu.sh:5-10`), passes backend credentials via `tofu init -backend-config` (`scripts/tofu.sh:12`), runs `tofu apply -auto-approve` (`scripts/tofu.sh:13`), captures all outputs (`scripts/tofu.sh:16-22`), writes generated secrets before vault encryption (`scripts/tofu.sh:24-36`). The Ansible role builds a PostgreSQL connection string containing a secret (`src/roles/authentik-config/tasks/main.yml:490`), passes API tokens as `-var=` arguments (`:493-496`), writes `grafana_oncall_token.json` (`:499`), and prints the token in debug output (`:515-517`). | Secrets can leak through process listings, shell history, Ansible logs, temporary files, terminal scrollback, crash dumps, and ignored local artifacts. `terraform/grafana_oncall_token.json` was detected by `gitleaks dir`. | Platform owner: replace command-line secrets with environment variables or secure files, remove debug output, use `no_log: true` anywhere secrets are derived, delete plaintext token artifacts, and require manual approval for apply operations unless a controlled pipeline owns deployment. |
| SR-003 | High | `src/roles/nixos/files/etc/nixos/modules/caddy.nix`, `src/roles/nixos/files/etc/nixos/modules/grafana.nix` | Caddy protects only Loki push with basic auth (`caddy.nix:29-34`), while `/loki*` read routes and Tempo, OTLP, Mimir, Prometheus, Pyroscope, Alloy, OnCall, and Grafana proxy routes are exposed without Caddy/Auth forward auth in this module (`caddy.nix:36-69`). Grafana has OAuth configured (`grafana.nix:106-122`), but backend routes do not show equivalent protection. | Unauthenticated read or administrative access to observability backends can disclose logs, metrics, traces, profile data, service names, internal URLs, and potentially credentials embedded in telemetry. | Platform owner: put Authentik forward auth, mTLS, network ACLs, or service-native auth in front of every read-capable metrics route; keep only narrowly scoped ingestion endpoints exposed. |
| SR-004 | High | `src/roles/nixos/files/device-configuration/habiki.nix`, `src/roles/nixos/files/etc/nixos/modules/hermes.nix`, `src/roles/nixos/files/etc/nixos/modules/caddy.nix` | Habiki sets `HERMES_WEBUI_TRUSTED_PROXY_AUTH_HEADER = "X-Authentik-Username"` and `HERMES_WEBUI_TRUSTED_PROXY_NETS = "0.0.0.0/0"` while clearing `HERMES_WEBUI_PASSWORD` (`habiki.nix:30-35`). Hermes WebUI publishes directly when Caddy is disabled (`hermes.nix:500-504`) and binds the service to `0.0.0.0` inside the container (`hermes.nix:509-516`). Caddy forwards Authentik headers on the public hostname (`caddy.nix:76-85`). | If the direct WebUI bind is reachable from any untrusted source, a client can spoof `X-Authentik-Username` and bypass authentication. | Service owner: trust only the reverse proxy source CIDR or localhost, bind direct ports to loopback, do not clear password auth unless header trust is constrained, and add a regression check for trusted-proxy settings. |
| SR-005 | High | `src/roles/nixos/files/etc/nixos/modules/security.nix`, `src/roles/nixos/files/etc/nixos/modules/podman.nix`, `src/roles/nixos/files/etc/nixos/modules/user-scetrov-gui.nix` | Passwordless sudo is enabled for wheel (`security.nix:6`). Podman exposes a Docker-compatible socket (`podman.nix:55`, `:61`; `user-scetrov-gui.nix:118-121`). The privileged port boundary is lowered globally (`podman.nix:44-48`). `podman0` is fully trusted by the firewall (`podman.nix:74-76`). | Local user or container escape impact is amplified. Docker-compatible sockets are high-value privilege boundaries; trusting bridge interfaces can allow lateral movement across containers and host services. | Platform owner: require sudo authentication, minimize Docker socket exposure, restore privileged port defaults or scope exceptions, and replace trusted `podman0` with explicit allowed ports. |
| SR-006 | Medium | `src/roles/nixos/files/etc/nixos/modules/oncall.nix`, `src/roles/nixos/files/etc/nixos/modules/hermes.nix`, `src/roles/nixos/files/device-configuration/fyne.nix` | Containers use mutable tags such as `docker.io/grafana/oncall:latest` (`oncall.nix:82`, `:106`, `:116`) and Hermes defaults to `nousresearch/hermes-agent:latest` and `ghcr.io/nesquena/hermes-webui:latest` (`hermes.nix:304-313`). `fyne.nix` imports `nixos-hardware` from a moving `master` tarball (`fyne.nix:266-268`). | Rebuilds can silently change runtime code, making rollback, forensics, and vulnerability assessment harder. | Platform owner: pin image digests, pin Nix tarballs by immutable revision and hash, and document an update cadence that follows the 7x7 rule. |
| SR-007 | Medium | `src/roles/nixos/files/etc/nixos/modules/immich.nix`, `src/roles/nixos/files/etc/nixos/modules/user-scetrov-syncthing.nix`, `src/roles/nixos/files/etc/nixos/modules/xserver.nix`, `src/roles/secrets/tasks/main.yml` | Immich opens its firewall directly (`immich.nix:172-177`). Syncthing GUI password hash is embedded in Nix config (`user-scetrov-syncthing.nix:250-253`). A private key-looking path is registered as a CA certificate file (`user-scetrov-syncthing.nix:258-260`). Xrdp opens firewall access (`xserver.nix:186-188`). Secret deployment includes placeholder values for several secrets (`src/roles/secrets/tasks/main.yml:71-81`). | Service-specific exposure and configuration drift can undermine the central Authentik/proxy model. Placeholder secrets can accidentally become live credentials or mask missing provisioning. | Service owners: review each service for intended exposure, move hashes/secrets to age/vault-backed files, validate certificate file usage, and fail deployment on placeholder secrets in production. |
| SR-008 | Medium | `README.md`, `scripts/play.sh`, `docs/authentik.md`, `docs/dependency-track.md` | README and `scripts/play.sh` encourage `git add .` before deploy (`README.md:17-24`, `scripts/play.sh:3`). Authentik documentation recommends reducing special characters in generated secrets to avoid shell/YAML issues (`docs/authentik.md:547`). Dependency Track docs state generated credentials are stored by automation (`docs/dependency-track.md:44`). | Broad staging increases accidental secret commits. Weakening secret character sets treats shell handling symptoms rather than removing unsafe transport. | Repository owner: replace `git add .` with selective staging guidance, require secret scanning before commit/deploy, and update docs to prefer safe transport over restricted secret alphabets. |

## Mitigation Roadmap

### Phase 0 - Same Day

- Delete ignored plaintext artifacts such as `terraform/grafana_oncall_token.json`.
- Rotate Grafana OnCall tokens and any credentials associated with redacted gitleaks history findings unless already proven rotated.
- Remove the debug task that prints the Grafana OnCall token and set `no_log: true` on derived token facts.
- Restrict Hermes WebUI direct binding to loopback or disable it; change trusted proxy CIDRs from `0.0.0.0/0` to the actual proxy source.
- Add Authentik forward auth, mTLS, or network ACLs to `/loki*`, `/tempo*`, `/mimir*`, `/prometheus*`, `/pyroscope*`, `/alloy*`, and `/oncall*` routes.

### Phase 1 - Short Term

- Refactor OpenTofu invocation to use environment variables or secure files for credentials; remove `-var="secret=..."` and secret-bearing backend connection strings from command arguments.
- Replace automatic `tofu apply -auto-approve` with an explicit approval step or a controlled CI/CD deployment gate.
- Use `tofu output -json` only in a controlled process that writes directly to encrypted storage or a restricted temp file that is securely removed.
- Add pre-commit and CI secret scans: `gitleaks dir . --redact`, `gitleaks detect --redact`, and deny generated plaintext token artifacts.
- Review Caddy/Grafana/Loki/OnCall access paths and make Authentik coverage explicit for each route.

### Phase 2 - Medium Term

- Rework the vault and age identity model so a single repository checkout plus one operator secret cannot unlock all operational credentials.
- Pin container images by digest and Nix tarballs by immutable commit plus hash.
- Harden host defaults: require sudo authentication, restrict Docker-compatible Podman sockets, remove globally trusted container bridge interfaces, and avoid globally lowering privileged ports.
- Document credential recovery and rotation procedures for Authentik, Grafana, Loki, Cloudflare, DNS, SSH identities, and service-specific tokens.

### Phase 3 - Ongoing

- Run recurring redacted gitleaks scans against the working tree and full Git history.
- Maintain a dependency update cadence that respects the 7x7 rule and fast-tracks CVSS >= 7.0 fixes.
- Add a security review checklist for new services covering routes, Authentik integration, firewall openings, secret paths, telemetry, and rollback.
- Add observability alerts for authentication failures, unexpected exposed endpoint access, and direct backend route hits.

## Acceptance Checklist

- [x] No secret values, tokens, private keys, or decrypted vault content are included in this report.
- [x] Findings reference paths, line numbers, rule names, and commit IDs only.
- [x] Authentik coverage gaps are identified for metrics and service routes.
- [x] Observability implications are covered for Loki, Grafana, OnCall, and backend telemetry routes.
- [x] Dangling or weakly protected routes are called out for follow-up.
- [x] The report is documentation-only; remediation edits are intentionally out of scope for this task.
- [x] `docs/security-review-2026-05-19.md` is staged for commit after validation.
