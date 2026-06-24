## 1. Generated Secret Validation

- [x] 1.1 Add validation in the secrets role for `grafana_authentik_client_id`, `grafana_authentik_client_secret`, `dtrack_oidc_client_id`, and `dtrack_oidc_client_secret` before agenix files are generated.
- [x] 1.2 Reject empty, undefined, `null`, and `*_placeholder` OIDC values with clear non-secret error messages.
- [x] 1.3 Ensure validation runs for targeted Habiki deployments using `authentik`, `nixos`, or `dependency-track` tags that can affect OIDC-enabled services.

## 2. Deployment Ordering

- [x] 2.1 Update the documented or scripted deployment flow so OpenTofu outputs are refreshed into `src/generated-secrets.yml` before secrets/NixOS roles consume them.
- [x] 2.2 Prevent a single targeted service deployment from silently using stale generated OIDC values after OpenTofu changes Authentik provider credentials.
- [x] 2.3 Ensure `scripts/tofu.sh` continues to use the secure wrapper pattern and does not print raw client secrets or tokens.

## 3. Service Refresh Behavior

- [x] 3.1 Ensure Grafana receives updated `/run/agenix/grafana_authentik_client_id` and `/run/agenix/grafana_authentik_client_secret` values through IaC and restarts when those inputs change.
- [x] 3.2 Ensure Dependency Track apiserver and frontend environment generation reruns when `/run/agenix/dtrack_oidc_client_id` or `/run/agenix/dtrack_oidc_client_secret` changes.
- [x] 3.3 Ensure Dependency Track frontend/apiserver containers restart after regenerated OIDC environment files change.

## 4. Safe Verification

- [x] 4.1 Add or document a verification command that checks Grafana's OAuth redirect `client_id` fingerprint against the Authentik Grafana provider fingerprint without printing raw values.
- [x] 4.2 Add or document a verification command that confirms Dependency Track `/static/config.json` has a non-placeholder `OIDC_CLIENT_ID` matching the Authentik Dependency Track provider fingerprint.
- [x] 4.3 Confirm verification output redacts or hashes all client IDs and never prints client secrets.

## 5. Validation and Deploy Check

- [x] 5.1 Run local syntax/validation checks for modified Ansible, shell, and Nix files.
- [x] 5.2 Run a targeted IaC deployment plan or dry-run where available for Habiki using the smallest applicable tags.
- [x] 5.3 After deployment, verify Grafana and Dependency Track login initiation no longer produces Authentik `client_id` missing or invalid errors.
