## Abstract

This repository stores the NixOS configuration and an Ansible Playbook used to push configuration to a machine, predominantly expected to be run locally but can be run against a remote target.

## Running

Ansible needs to be installed and you will need access to the vault password, which can be done initially with:

```
nix-shell -p ansible python3
echo "[INSERT PASSWORD]" > ~/.ansible/nixos_vault_password
```

> [!TIP]
> Once the NixOS system has been rebuilt from this repo it will automatically include `ansible` and `python3`.

Then execute the playbook from the root:

```
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
