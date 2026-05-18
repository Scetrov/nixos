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
| `dtrack_github_pat` | (Optional) GitHub Personal Access Token for repository analysis and intelligence. |
| `dtrack_nvd_api_key` | (Optional) NVD API Key to avoid rate-limiting during vulnerability data sync. |
| `dtrack_oidc_client_id` | OIDC Client ID from Authentik. |
| `dtrack_oidc_client_secret` | OIDC Client Secret from Authentik. |

### How to add secrets:

1.  Edit the vault:
    ```bash
    ansible-vault edit src/secrets.yml --vault-password-file ~/.ansible/nixos_vault_password
    ```
2.  Add the keys:
    ```yaml
    dtrack_db_password: "your_secure_db_password"
    dtrack_oidc_client_id: "your-authentik-client-id"
    dtrack_oidc_client_secret: "your-authentik-client-secret"
    dtrack_github_pat: "ghp_your_token"
    dtrack_nvd_api_key: "your-nvd-uuid-key"
    ```
3.  Apply infrastructure changes:
    ```bash
    ./scripts/tofu.sh
    ```
4.  Deploy the NixOS changes:
    ```bash
    ./scripts/play.sh
    ```

## 🔐 Authentication (OIDC)

Manual user management is disabled in favor of **Authentik OIDC**. 

- **Redirect URI**: `https://dtrack.net.scetrov.live/static/oidc-callback.html`
- **Initial Login**: Users will be automatically provisioned on their first login.
- **Admin Access**: To gain admin privileges, you must map your OIDC group to the `Administrators` team inside the Dependency Track UI (Administration > Access Management > Teams).

## 🛠 Resource Management

The API Server is configured with:
-   **Memory Limit**: 4GB
-   **CPU Limit**: 2.0 cores

These can be adjusted in `src/roles/nixos/files/etc/nixos/modules/dependency-track.nix` if needed.
