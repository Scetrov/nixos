# OWASP Dependency Track Deployment

This document outlines the deployment of OWASP Dependency Track on NixOS using OCI containers.

## 🏗 Architecture

The deployment consists of three containers managed by Podman:

1.  **`dtrack-db`**: PostgreSQL 16 database.
2.  **`dtrack-apiserver`**: The core API server (Java/Alpine).
3.  **`dtrack-frontend`**: The Vue.js web interface.

## 🌐 Networking

-   **Frontend**: `https://dtrack.net.scetrov.live`
-   **API**: `https://dtrack-api.net.scetrov.live`

Caddy acts as the reverse proxy and handles SSL/TLS certificates via the `scetrov.live` wildcard ACME host.

## 🔐 Secrets Configuration

To fully enable the integration and secure the database, the following secrets MUST be added to `src/secrets.yml` (Ansible Vault):

| Secret Key | Description |
| :--- | :--- |
| `dtrack_db_password` | Password for the `dtrack` PostgreSQL user. |
| `dtrack_nvd_api_key` | (Optional) NVD API Key to avoid rate-limiting during vulnerability data sync. |

### How to add manual secrets:

1.  Edit the vault:
    ```bash
    ansible-vault edit src/secrets.yml --vault-password-file ~/.ansible/nixos_vault_password
    ```
2.  Add the keys:
    ```yaml
    dtrack_db_password: "your_secure_db_password"
    dtrack_github_pat: "ghp_your_token"
    dtrack_nvd_api_key: "your-nvd-uuid-key"
    ```

### Automated Secrets:

OIDC credentials (`dtrack_oidc_client_id`, `dtrack_oidc_client_secret`) and `grafana_oncall_api_key` are automatically generated and stored in `src/generated-secrets.yml` by the infrastructure script.

1.  Apply infrastructure changes (this generates the OIDC credentials):
    ```bash
    ./scripts/tofu.sh
    ```
2.  Deploy the NixOS changes (this will automatically pick up the generated secrets):
    ```bash
    ./scripts/play.sh
    ```

## 🔐 Authentication (OIDC)

Manual user management is disabled in favor of **Authentik OIDC**. 

- **Redirect URI**: `https://dtrack.net.scetrov.live/static/oidc-callback.html`
- **Initial Login**: Users will be automatically provisioned on their first login.
- **Admin Access**: 
  1. Log in to Dependency Track using the default `admin` / `admin` account.
  2. Navigate to **Administration** > **Access Management** > **Teams**.
  3. Select the **Administrators** team.
  4. In the **OpenID Connect Groups** tab, add the group name exactly as it appears in Authentik (e.g., `All Applications` or `authentik Admins`).
  5. Save and log out. Your OIDC user will now have full admin rights upon the next login.

## 🛠 Resource Management

The API Server is configured with:
-   **Memory Limit**: 4GB
-   **CPU Limit**: 2.0 cores

These can be adjusted in `src/roles/nixos/files/etc/nixos/modules/dependency-track.nix` if needed.
