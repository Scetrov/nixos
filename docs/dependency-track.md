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

### How to add secrets:

1.  Edit the vault:
    ```bash
    ansible-vault edit src/secrets.yml --vault-password-file ~/.ansible/nixos_vault_password
    ```
2.  Add the keys:
    ```yaml
    dtrack_db_password: "your_secure_password"
    dtrack_github_pat: "ghp_your_token"
    dtrack_nvd_api_key: "your-nvd-uuid-key"
    ```
3.  Deploy the changes:
    ```bash
    ./scripts/play.sh
    ```

## 🛠 Resource Management

The API Server is configured with:
-   **Memory Limit**: 4GB
-   **CPU Limit**: 2.0 cores

These can be adjusted in `src/roles/nixos/files/etc/nixos/modules/dependency-track.nix` if needed.
