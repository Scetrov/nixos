# Agent Workflows & Infrastructure Standards

This document outlines the foundational standards and workflows for managing the NixOS infrastructure, identity providers, and proxy services within this repository.

## 🏗 Infrastructure as Code (IaC)

We use **OpenTofu** for declarative management of application-level resources (Authentik, Caddy routes, etc.).

### **1. Tooling Choice**
*   **OpenTofu** is the mandatory tool for IaC.
*   The `tofu` CLI is installed as a system package via NixOS (`src/roles/nixos/files/etc/nixos/modules/pkgs.nix`).

### **2. Secret Management (CRITICAL)**
*   **Zero Hardcoding:** Never hardcode API tokens, database passwords, or connection strings in `.tf` or `.nix` files.
*   **Ansible Vault Integration:** The source of truth for secrets is `src/secrets.yml` (encrypted via Ansible Vault).
*   **Secure Wrapper:** All OpenTofu operations MUST be performed via the `scripts/tofu.sh` wrapper.
    *   This script extracts secrets from the vault at runtime and injects them into OpenTofu using environment variables (`TF_VAR_*`).
    *   It also dynamically configures the remote backend connection string.

### **3. Remote State**
*   **Backend:** We use the PostgreSQL (`pg`) backend for OpenTofu state storage.
*   **Location:** The state is stored in the `terraform_state` database on the `habiki` host (running in the `authentik-postgresql` container).
*   **Permissions:** Use the dedicated `terraform` user with limited schema permissions for state operations.

## 📊 Monitoring & Observability

We use **Grafana** and **Loki** for central observability.

### **1. Error Investigation**
*   **Workflow:** Systematic investigation of system logs (Loki) should be performed whenever service degradation is suspected.
*   **Instructions:** Detailed procedures are located in `.agents/instructions/grafana-error-investigator.instructions.md`.
*   **Automation:** Use the investigation script at `.agents/skills/grafana-error-investigator/scripts/investigate_errors.sh` to quickly pull and prioritize recent errors.

## 🛠 Operation Standards

### **Declarative vs. Imperative**
*   **NixOS/Ansible:** Used for host-level configuration, package installation, and container orchestration (systemd/podman).
*   **OpenTofu:** Used for configuring the internal state of services (creating Authentik applications, groups, users, and Caddy API-based routing).

### **Repository Hygiene**
*   The `terraform/.gitignore` MUST exclude `.terraform/`, `.opentofu/`, and any `*.tfstate` files to prevent accidental leakage of resource metadata or cached secrets.
*   The `terraform/.terraform.lock.hcl` should also be ignored to avoid platform-specific lock conflicts in this environment.

## Task Sign Off Checklist

For each tasks ensure the following is complete:

- [ ] All of the required files are staged ready for commit in git (Staging Rule)
- [ ] No files contain secrets, keys or sensitive material (Toxic Waste Rule)
- [ ] Any new aliases have been added to device hosts and resolve via `local-networking.nix` (Local DNS Rule)
- [ ] Identity and Access management is handled using Authentik (IdAM Rule)
- [ ] Logging, Monitoring and Alerting is configured to send data to Grafana (Observability Rule)
- [ ] No additional ports, endpoints or routes are left dangling (Hygiene Rule)
- [ ] Modern versions of all software is in use (Concurrency Rule)
- [ ] New updates that don't fix CVSS >= 7.0 are differed for 7 days (7x7 Rule)

## 🎓 Lessons Learned (Security Remediation)
*   **Incident:** Hardcoded secrets were accidentally committed to Git history.
*   **Mitigation:** The branch was force-reset to a clean state, and history was scrubbed via `git push --force`.
*   **Future Prevention:** Always define variables with `sensitive = true` in `main.tf` and use runtime injection via environment variables or CLI flags.
