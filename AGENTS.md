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

### **Dashboard Color Scheme**

* **Preferred Palette for Frontier Indexer:** Use the Heart Pumps Neon family as the base palette for detailed Grafana dashboards.
* **Approved Core Colors:**
  * `#FF3E8D` for hot/error-prone or fast-moving series.
  * `#BB5191` for primary highlight and indexed-state series.
  * `#855F90` for muted status/support usage.
  * `#4B678C` for cool secondary/reference usage.
  * `#008791` for healthy/current/head-state series.
* **Approved Bridge Color:**
  * `#E6C65B` as the yellow-amber midpoint between the pink/red side and the teal/green side of the palette.
  * Prefer this for mid-thresholds, smoothed 5-minute series, or limit/reference lines where the dashboard needs a warmer transition color.
* **Complementary Extension Colors:**
  * `#6F5D86` for a softer blue-violet support tone when another cool series is needed.
  * `#C86B8F` for a softer rose accent when another warm series is needed.
  * `#6FAE9F` for a muted teal support tone when a second healthy-state color is needed.
* **Usage Guidance:**
  * Keep the palette legible on Grafana dark mode; do not reintroduce overly fluorescent lime-heavy schemes.
  * Use teal/green for healthy or current state, amber-yellow for midpoint/reference, and pink/magenta for hot, lagging, or pressure-related signals.
  * Reserve additional extension colors for multi-series charts only; avoid turning stat rows into rainbow grids.

### **1. Error Investigation**
*   **Workflow:** Systematic investigation of system logs (Loki) should be performed whenever service degradation is suspected.
*   **Instructions:** Detailed procedures are located in `.agents/instructions/grafana-error-investigator.instructions.md`.
*   **Automation:** Use the investigation script at `.agents/skills/grafana-error-investigator/scripts/investigate_errors.sh` to quickly pull and prioritize recent errors.

## 🛠 Operation Standards

### Automation First
*   Automation is critical for BCDR recovery and reproducability
*   All changes must be made through Automation (Ansible / Terraform)
*   All state must be provisioned through Automation (Ansible / Terraform)

### **Declarative vs. Imperative**
*   **NixOS/Ansible:** Used for host-level configuration, package installation, and container orchestration (systemd/podman).
*   **OpenTofu:** Used for configuring the internal state of services (creating Authentik applications, groups, users, and Caddy API-based routing).

### **Deployment Orchestration (`play.sh`)**
*   **Default Behavior:** By default, running `./scripts/play.sh` deploys to all hosts without constraints.
*   **Modular Targeting (`--limit`):** To avoid deploying to all hosts, use the `--limit` flag to target specific hosts (e.g. `./scripts/play.sh --limit habiki`).
*   **Component-based Runs (`--tags`):** To run only specific configuration flows, restrict execution using tags:
    *   `nixos`: Lint, generate/copy secrets, and rebuild host-level NixOS configurations.
    *   `authentik`: Configure the Authentik identity platform and application configurations via OpenTofu.
    *   `hermes`: Perform end-to-end Hermes deployment (secrets, host services via NixOS, and SSO proxy via Authentik).
    *   `dependency-track`: Perform end-to-end Dependency Track deployment (secrets, host services, Authentik SSO, and API mappings).
*   **Agent Guideline:** When executing tasks as an agent, always prefer targeted runs using `--limit` and `--tags` to speed up execution, reduce resource utilization, and minimize blast radius (e.g., `./scripts/play.sh --limit habiki --tags hermes`).

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
