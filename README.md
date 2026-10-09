# NixOS Configuration and Deployment

## Abstract

This repository stores the NixOS configuration and an Ansible Playbook used to push configuration to a machine, predominantly expected to be run locally but can be run against a remote target.

## Running

Ansible needs to be installed and you will need access to the vault password, which can be done initially with:

```sh
nix-shell -p ansible python3
echo "[INSERT PASSWORD]" > ~/.ansible/nixos_vault_password
```

> [!TIP]
> Once the NixOS system has been rebuilt from this repo it will automatically include `ansible` and `python3`.

Then execute the playbook from the root:

```sh
git add . && git commit && git push origin HEAD && ansible-playbook -i src/inventory.yml src/playbook.yml --vault-password-file ~/.ansible/nixos_vault_password
```

> [!IMPORTANT]
> The `git` commands are important as the playbook will check to see if there are any uncommitted changes to the repository, or local changesets. This ensures that if you do push a change that destroys the local machine you don't lose any progress. Additionally, the commit message is used to generate a NixOS Label for Grub.

### Running with Podman

You can also obtain a ready-to-run environment with Podman:

```sh
podman build -q -t nixos_devenv
```

Then run the container with:

```sh
podman run --rm -it --userns=keep-id -v "$(pwd):/workspace" -v ~/.ansible:/root/.ansible:ro nixos_devenv -c zsh
```

## Reference

### Secret Management

Secrets are managed through Ansible Vault, they are variously deployed to machines either by pushing the secret through Ansible; or by using `agenix` for inclusion in NixOS's `configuration.nix` and modules.

By default, private SSH identity keys are **not** deployed to target machines to minimize risk. If a host requires its private key (e.g., for git operations), set `secrets_deploy_private_key: true` for that host.

### Service Configuration

This repository increasingly uses **OpenTofu** (or Terraform) for declarative management of service-level state (e.g., Authentik applications, providers, and entitlements) after the base NixOS system is provisioned. This is handled automatically by the `authentik-config` role.

### Ingesting Metrics into Mimir

Mimir on `habiki` exposes an authenticated remote-write endpoint that accepts writes from machines on the network without requiring a browser session:

```
POST https://metrics.net.scetrov.live/mimir/api/v1/push
Basic-Auth user: metric-writer
```

The write password is stored in the vault as `mimir_write_token`. Retrieve it (without printing it) and export it into the process environment of the pushing service:

```sh
ansible-vault view src/secrets.yml --vault-password-file ~/.ansible/nixos_vault_password | grep '^mimir_write_token:'
```

Example [Grafana Alloy](https://grafana.com/docs/alloy/latest/) configuration that scrapes a local target and forwards the metrics to Mimir over the authenticated endpoint:

```alloy
// Scrape a local target (adjust targets/job to the host you are running on).
// `forward_to` lives on the scrape (the source) and points at the
// remote_write component's `receiver` export.
prometheus.scrape "host" {
  targets = [{
    __address__ = "127.0.0.1:9100",
  }]

  job_name = "example-host"

  forward_to = [ prometheus.remote_write.mimir.receiver ]
}

// Forward scraped metrics to Mimir. The endpoint is Caddy-protected with
// basic_auth; the password is injected from the environment so it is not
// committed to the repository.
prometheus.remote_write "mimir" {
  endpoint {
    url = "https://metrics.net.scetrov.live/mimir/api/v1/push"

    basic_auth {
      username   = "metric-writer"
      password   = env("MIMIR_WRITE_TOKEN")
    }

    queue_config {
      max_samples_per_send = 500
      capacity             = 1000
    }
  }
}
```

> [!NOTE]
> The `env()` stdlib function is deprecated in current Alloy releases (it still works but logs a warning). The remote-write WAL is managed by Alloy under its `--storage.path` (e.g. `/var/lib/grafana/alloy`) rather than a per-component `wal` block.


> [!NOTE]
> The `/mimir/api/v1/push` route is intentionally excluded from the Authentik `forward_auth` matcher and guarded by `basic_auth` against an aged secret, mirroring the existing `/loki/api/v1/push` convention. Only the shared key is required to write.

### Deployment Quality Control

The playbook includes a linting phase (`nixos-lint`) that verifies Nix syntax and ensures the repository is in a clean state (no unstaged changes or unpushed commits) before deployment.

- To bypass these checks during active development, use: `-e nixos_force_deploy=true`.
- To format Nix files locally, use `nixfmt` (the linting role uses `nixfmt --check` to avoid unintended modifications).
- To apply the repository formatting rules to all supported files, run `pre-commit install` once and then `pre-commit run --all-files` (the VS Code task `Format all files` runs the same command).

### Performance Optimization

The deployment process is optimized for speed and determinism:

- **Synchronized Configuration**: NixOS modules are synchronized recursively with optimized permission handling.
- **Deterministic Rebuilds**: `nixos-rebuild switch` is used without the `--upgrade` flag to avoid redundant channel checks across multiple hosts in a single run.

### Ansible Directory Structure

#### Root Directories

- **`inventories/`** → Stores inventory files (e.g., `production`, `staging`)
- **`group_vars/`** → Contains group-specific variables
- **`host_vars/`** → Contains host-specific variables
- **`roles/`** → Stores all role definitions
- **`playbooks/`** → Contains playbook YAML files
- **`library/`** → Custom Ansible modules
- **`templates/`** → Global Jinja2 templates
- **`files/`** → Global static files
- **`ansible.cfg`** → Configuration file (e.g., inventory location, SSH settings)
- **`inventory.yml`** → The main inventory file
- **`site.yml`** → The main playbook entry point

---

#### Role Structure (`roles/my_role/`)

- **`tasks/`** → Main YAML files with tasks to execute
  - `main.yml`
- **`handlers/`** → Defines handlers (e.g., service restarts)
  - `main.yml`
- **`templates/`** → Stores Jinja2 templates
- **`files/`** → Stores static files
- **`vars/`** → Stores role-specific variables (higher precedence)
  - `main.yml`
- **`defaults/`** → Stores default variables (lower precedence)
  - `main.yml`
- **`meta/`** → Role metadata (e.g., dependencies)
  - `main.yml`

---

#### Example Tree Structure

```plaintext
ansible-project/
│-- inventories/
│-- group_vars/
│-- host_vars/
│-- roles/
│   ├── common/
│   │   ├── tasks/
│   │   │   ├── main.yml
│   │   ├── handlers/
│   │   │   ├── main.yml
│   │   ├── templates/
│   │   ├── files/
│   │   ├── vars/
│   │   │   ├── main.yml
│   │   ├── defaults/
│   │   │   ├── main.yml
│   │   ├── meta/
│   │   │   ├── main.yml
│-- playbooks/
│-- library/
│-- templates/
│-- files/
│-- ansible.cfg
│-- inventory.yml
│-- site.yml
```
