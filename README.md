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

## Reference

### Secret Management

Secrets are managed through Ansible Vault, they are variously deployed to machines either by pushing the secret through Ansible; or by using `agenix` for inclusion in NixOS's `configuration.nix` and modules.

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
