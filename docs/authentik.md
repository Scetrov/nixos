# Authentik

This document describes the Authentik installation and API behavior that is
proven to work in this repository.

It is based on the current NixOS module, the `authentik-config` Ansible role,
and live validation against the running instance on `habiki`.

## Scope

This document covers:

- how Authentik is installed in this repo
- how first boot and steady-state API automation work
- the Authentik API endpoints that are proven to work here
- the managed-blueprint flow that is actually used
- the service-account and long-lived token workflow that now works
- known API quirks and endpoints that should not be used in this repo

It does not try to document all of Authentik. It only records behavior that was
verified in this environment.

## Version And Runtime Model

The current deployment uses:

- Authentik image: `ghcr.io/goauthentik/server:2025.10`
- Live API/schema version observed: `2025.10.4`
- PostgreSQL image: `postgres:16-alpine`

Auth configuration is split across two layers:

- NixOS module: installs and runs the Authentik containers and runtime env
- Ansible `authentik-config` role: performs controller-side API configuration after the service is reachable

The NixOS module is in [src/roles/nixos/files/etc/nixos/modules/authentik.nix](/home/scetrov/source/nixos/src/roles/nixos/files/etc/nixos/modules/authentik.nix).
The API automation lives in [src/roles/authentik-config/tasks/main.yml](/home/scetrov/source/nixos/src/roles/authentik-config/tasks/main.yml) and [src/roles/authentik-config/tasks/deploy-blueprint.yml](/home/scetrov/source/nixos/src/roles/authentik-config/tasks/deploy-blueprint.yml).

## Installation Model

### Container layout

The NixOS module creates and runs:

- `authentik-postgresql`
- `authentik-server`
- `authentik-worker`

State is stored under `/var/lib/authentik` on the target host.

Important paths:

- env file: `/var/lib/authentik/authentik.env`
- Authentik data: `/var/lib/authentik/data`
- local blueprint mount root: `/var/lib/authentik/templates`
- PostgreSQL data: `/var/lib/authentik/postgresql-data`

### Secret inputs

The NixOS module consumes these secrets and writes them into the Authentik env file:

- `authentik_bootstrap_password`
- `authentik_bootstrap_email`
- `authentik_bootstrap_token`
- `authentik_api_token`
- `authentik_postgresql_password`
- `authentik_secret_key`
- `grafana_authentik_client_id` (Automated)
- `grafana_authentik_client_secret` (Automated)

The controller-side `authentik-config` role separately consumes these persisted
recovery credentials:

- `authentik_admin_user`
- `authentik_admin_password`

That split is intentional. Upstream Authentik bootstrap settings only seed the
default `akadmin` account on first startup. The repo's managed human admin
account is reconciled later over the API and must not be conflated with the
bootstrap password/token path.

### Blueprint directory behavior

The deployment must keep Authentik's packaged `/blueprints` tree intact.

This repo now sets:

- `AUTHENTIK_BLUEPRINTS_DIR=/blueprints`
- local custom files mounted at `/blueprints/custom`

That matters because mounting local files over `/blueprints` or pointing `AUTHENTIK_BLUEPRINTS_DIR` at a replacement directory breaks Authentik's packaged defaults, including bootstrap objects such as the default brand and authentication flow.

### Install and deploy sequence

The normal deployment flow is:

1. The `nixos` role installs or updates the NixOS system and Authentik containers.
2. Authentik becomes reachable on `https://identity.net.scetrov.live`.
3. The `authentik-config` role waits for readiness.
4. The `authentik-config` role reconciles the managed human admin account.
5. The same role reconciles the automation service account and durable API token.
6. Once both are healthy, the same role disables the upstream bootstrap account.
7. The same role configures Grafana OAuth provider, application, and entitlements.

## Repository Defaults

The Authentik role defaults are defined in [src/roles/authentik-config/defaults/main.yml](/home/scetrov/source/nixos/src/roles/authentik-config/defaults/main.yml).

Important values:

- base URL: `https://identity.net.scetrov.live`
- API base URL: `https://identity.net.scetrov.live/api/v3`
- readiness URL: `https://identity.net.scetrov.live/-/health/ready/`
- unauthenticated config probe: `https://identity.net.scetrov.live/api/v3/root/config/`
- upstream bootstrap username: `akadmin`
- managed human admin username: `authentik_admin_user`
- automation username: `api-automation`
- primary-admin blueprint name: `primary-admin`
- service-account blueprint name: `service-account-api`
- Grafana application slug: `grafana`

## Working Bootstrap Model

This repo treats the vaulted `authentik_api_token` as the source-of-truth token value.

That means steady-state automation does not accept a generated token from Authentik. Instead, the role ensures that the token inside Authentik matches the pre-existing vaulted secret exactly.

Upstream Authentik only documents bootstrap settings for the default `akadmin`
account on first startup. There is no repo-supported bootstrap username
override. The working sequence is therefore:

1. The NixOS module seeds `AUTHENTIK_BOOTSTRAP_PASSWORD`, optional `AUTHENTIK_BOOTSTRAP_EMAIL`, and `AUTHENTIK_BOOTSTRAP_TOKEN` for Authentik's upstream bootstrap path.
2. The role checks whether the durable `authentik_api_token` already works against `/api/v3/core/users/me/`.
3. If it does not, the role resolves repair auth in this order: bootstrap token, then persisted managed-admin login.
4. With whichever repair credential works, the role reconciles the managed human admin account and verifies that account can log in through the flow executor.
5. If the durable automation token is still missing, the role creates the `api-automation` service-account user through `/api/v3/core/users/service_account/` and applies a managed blueprint that grants admin-group membership and sets the exact token key.
6. The role re-verifies the vaulted `authentik_api_token` against `/api/v3/core/users/me/`.
7. Only after both the managed admin login and durable automation token work does the role disable the upstream bootstrap account.

This hybrid approach is deliberate.

The service-account creation action is used only to create the user. The deterministic token key still has to be reconciled through a blueprint because the service-account API generates a token rather than accepting a caller-supplied API key.

The managed human admin account is also deliberate. In this repo, that account
is the expected steady-state recovery login. The upstream `akadmin` account is
treated as a first-boot bootstrap artifact, not the long-term administrator
identity.

## Proven API Surface

The raw OpenAPI schema is available at:

- `GET /api/v3/schema/`

The following endpoints are proven to work in this repository.

### Readiness And Discovery

#### `GET /-/health/ready/`

Use this to wait for Authentik readiness before API configuration.

Observed behavior:

- returns `200` when the service is ready

#### `GET /api/v3/root/config/`

Use this as the unauthenticated API probe.

Observed behavior:

- returns `200`
- returns JSON

Do not use `/api/v3/core/info/` here. On the live instance it returned `404`.

#### `GET /api/v3/schema/`

Use this to inspect the live API surface for the deployed build.

Observed behavior:

- returns OpenAPI YAML
- accurately reflects route shapes such as `/core/applications/{slug}/`

### Identity And Session Checks

#### `GET /api/v3/core/users/me/`

Primary token validation endpoint.

Observed behavior:

- bearer token returns `200` for valid token
- bearer token returns `403` for invalid or expired token
- used for both the bootstrap token and the durable automation token

### Service Accounts

#### `POST /api/v3/core/users/service_account/`

This is the supported way in this repo to create the automation service-account user.

Working request shape:

```json
{
  "name": "api-automation",
  "create_group": false,
  "expiring": false
}
```

Observed behavior:

- returns `200` when the service account is created
- may return `400` when the service account already exists
- creates a `service_account` user
- does not solve the deterministic API-token-key requirement by itself

This endpoint is used by the role before blueprint reconciliation.

### Flow Executor Recovery

#### `GET /api/v3/flows/executor/{flow_slug}/?query=`

#### `POST /api/v3/flows/executor/{flow_slug}/?query=`

These routes are used by [src/roles/authentik-config/files/authentik_login.py](/home/scetrov/source/nixos/src/roles/authentik-config/files/authentik_login.py) to recover an authenticated admin session when the bootstrap token is no longer valid.

Observed behavior:

- this is the working login path for browser-session recovery
- the helper must follow the challenge loop returned by Authentik
- the older shortcut login assumptions were not valid

### Managed Blueprints

#### `GET /api/v3/managed/blueprints/`

Used to:

- find stale temporary blueprint instances by name
- reload a created instance by name

#### `POST /api/v3/managed/blueprints/`

Used to create a temporary managed blueprint instance with inline `content`.

Working request shape:

```json
{
  "name": "ansible-service-account-api",
  "enabled": true,
  "content": "...rendered blueprint yaml..."
}
```

Observed behavior:

- returns `201`
- on this build the response body may be empty
- the role must treat the result as status-only and then reload the instance by name

#### `POST /api/v3/managed/blueprints/{instance_uuid}/apply/`

Used to apply a managed blueprint instance once.

Observed behavior:

- returns `200`
- on this build the response body may be empty
- the role must treat the result as status-only and then reload the instance by UUID to inspect `status`, `last_applied`, and `managed_models`

#### `GET /api/v3/managed/blueprints/{instance_uuid}/`

Used after apply to inspect the actual instance state.

Observed useful fields:

- `status`
- `last_applied`
- `managed_models`

#### `DELETE /api/v3/managed/blueprints/{instance_uuid}/`

Used to remove temporary blueprint instances after reconciliation.

### OAuth Scope Mappings

#### `GET /api/v3/propertymappings/provider/scope/?managed=...`

Used to resolve the built-in managed OAuth scope mappings needed by the Grafana provider.

Working managed identifiers used in this repo:

- `goauthentik.io/providers/oauth2/scope-openid`
- `goauthentik.io/providers/oauth2/scope-profile`
- `goauthentik.io/providers/oauth2/scope-email`
- `goauthentik.io/providers/oauth2/scope-entitlements`

### Flow Instance Reads

#### `GET /api/v3/flows/instances/{slug}/`

Used to read the provider authorization and invalidation flows needed for the Grafana OAuth provider.

Working slugs in this repo:

- `default-provider-authorization-implicit-consent`
- `default-provider-invalidation-flow`

### OAuth Providers

The Grafana OAuth provider management in this repo is proven through:

- `GET /api/v3/providers/oauth2/?client_id=...&page_size=100`
- `POST /api/v3/providers/oauth2/`
- `PATCH /api/v3/providers/oauth2/{id}/`

The current role persists the provider primary key from the list or create response and uses that ID for updates.

### Applications

The Grafana application management in this repo is proven through:

- `GET /api/v3/core/applications/?slug=...&page_size=100`
- `POST /api/v3/core/applications/`
- `PATCH /api/v3/core/applications/{slug}/`

Important: Authentik application detail routes are keyed by `slug`, not by the list response `pk`.

This was a real bug in the role and caused `404 No Application matches the given query` until the update path was changed to use the application slug.

### Application Entitlements

The Grafana entitlements are proven through:

- `GET /api/v3/core/application_entitlements/?app=...&name=...&page_size=100`
- `POST /api/v3/core/application_entitlements/`

## Working Blueprint Content Model

The service-account reconciliation blueprint currently lives at [src/roles/authentik-config/templates/blueprint-service-account.yaml.j2](/home/scetrov/source/nixos/src/roles/authentik-config/templates/blueprint-service-account.yaml.j2).

It does two things:

- grants the existing `api-automation` user membership in `authentik Admins`
- creates or reconciles the `ak-api-token-automation` token with the exact vaulted key

Current structure:

```yaml
version: 1
metadata:
  name: service-account-api
entries:
  - model: authentik_core.user
    id: service-account-api-user
    identifiers:
      username: "api-automation"
    attrs:
      name: API Automation
      groups:
        - !Find [authentik_core.group, [name, authentik Admins]]

  - model: authentik_core.token
    id: service-account-api-token
    identifiers:
      identifier: ak-api-token-automation
    attrs:
      intent: api
      expiring: false
      expires: null
      key: "<vaulted token>"
      user: !KeyOf service-account-api-user
```

## Blueprint Rules That Are Proven Here

These rules matter in this environment.

### Use `!KeyOf` for same-blueprint references

For references between entries in the same blueprint, use `!KeyOf`.

Example:

```yaml
user: !KeyOf service-account-api-user
```

### Use `!Find` for existing objects

For references to pre-existing Authentik objects, use `!Find`.

Example:

```yaml
groups:
  - !Find [authentik_core.group, [name, authentik Admins]]
```

### Do not use `!Ref`

On the live `2025.10.4` build, the managed blueprint API validator rejected `!Ref`.

The failure surfaced as:

- an Authentik server-side `system_exception`
- a misleading HTTP `405` from `POST /api/v3/managed/blueprints/`

If a managed blueprint create unexpectedly returns `405`, check the Authentik server logs before assuming the endpoint itself is wrong.

### The temporary managed blueprint instance must be enabled

The role creates temporary blueprint instances with `enabled: true`.

Using `enabled: false` caused the instance to apply without useful reconciliation state, leaving `managed_models` empty.

## Proven Service-Account Workflow

The working service-account flow in this repo is:

1. Verify whether the durable `authentik_api_token` already authenticates.
2. If it does not, authenticate with the bootstrap token or recover an admin session.
3. Create the `api-automation` service-account user through `/api/v3/core/users/service_account/`.
4. Apply the reconciliation blueprint.
5. Verify the durable bearer token via `/api/v3/core/users/me/`.

This is proven by live validation on `habiki`.

Final observed state after a successful run:

- user `api-automation` exists as `service_account`
- token `ak-api-token-automation` exists
- token is non-expiring
- the vaulted `authentik_api_token` authenticates successfully against the API

## Known Good Role Behavior

The working automation patterns are:

- use `ansible.builtin.uri` for normal JSON API calls
- use `curl` for managed blueprint create/apply because this path was easier to control during diagnosis
- treat managed blueprint create/apply as status-only operations on this Authentik build
- reload created blueprint instances explicitly instead of trusting response bodies
- use the local Authentik endpoint `http://127.0.0.1:9000/api/v3` when mutating managed blueprints with the bootstrap token on the host

## Endpoints And Patterns To Avoid

These are known bad or misleading in this repo.

### Do not use `POST /api/v3/managed/blueprints/import/`

This older one-shot multipart import path is not available on the deployed `2025.10.x` build used here.

The current role does not use it.

### Do not use `/api/v3/core/info/` as the readiness API probe

Use `/api/v3/root/config/` instead.

### Do not update Authentik applications by `pk`

Use `/api/v3/core/applications/{slug}/`.

### Do not rely on generic `authentik_core.user` blueprint creation for service accounts here

That approach did not reconcile correctly on the live instance.

The working pattern is:

- create the service-account user with `/core/users/service_account/`
- then reconcile admin-group membership and token key through a blueprint

## Operator Runbook

### Full deploy

```sh
ANSIBLE_VAULT_PASSWORD_FILE="$HOME/.ansible/nixos_vault_password" \
ansible-playbook -i src/inventory.yml src/playbook.yml --limit habiki
```

### Narrow Authentik replay

```sh
ANSIBLE_VAULT_PASSWORD_FILE="$HOME/.ansible/nixos_vault_password" \
ansible-playbook -i src/inventory.yml src/playbook.yml \
  --limit habiki \
  --start-at-task "Check whether the service-account token already works"
```

### Validate the durable token manually

```sh
curl -H "Authorization: Bearer <authentik_api_token>" \
  https://identity.net.scetrov.live/api/v3/core/users/me/
```

### Inspect the live schema

```sh
ssh scetrov@10.229.10.2 \
  'curl --silent http://127.0.0.1:9000/api/v3/schema/'
```

## Files To Read First

When working on Authentik in this repo, start here:

- [src/roles/authentik-config/tasks/main.yml](/home/scetrov/source/nixos/src/roles/authentik-config/tasks/main.yml)
- [src/roles/authentik-config/tasks/deploy-blueprint.yml](/home/scetrov/source/nixos/src/roles/authentik-config/tasks/deploy-blueprint.yml)
- [src/roles/authentik-config/templates/blueprint-service-account.yaml.j2](/home/scetrov/source/nixos/src/roles/authentik-config/templates/blueprint-service-account.yaml.j2)
- [src/roles/authentik-config/files/authentik_login.py](/home/scetrov/source/nixos/src/roles/authentik-config/files/authentik_login.py)
- [src/roles/nixos/files/etc/nixos/modules/authentik.nix](/home/scetrov/source/nixos/src/roles/nixos/files/etc/nixos/modules/authentik.nix)

## Summary

The proven model for this repository is:

- install Authentik with the NixOS module
- keep packaged `/blueprints` intact
- use `/api/v3/root/config/` and `/-/health/ready/` for readiness
- create the automation service-account user with `/api/v3/core/users/service_account/`
- reconcile admin membership and the deterministic API token key through a managed blueprint
- verify the durable token with `/api/v3/core/users/me/`
- manage Grafana provider/application/entitlements through the documented API routes, with application updates keyed by slug

## Automated OIDC Secret Management

This repository uses a "Compute and Capture" pattern for OIDC credentials to eliminate manual vaulting steps.

### Workflow

1.  **Generation**: OpenTofu (via the `random` provider) generates stable `client_id` and `client_secret` values for each provider.
2.  **Capture**: `scripts/tofu.sh` executes `tofu apply`, then uses `tofu output -json` and `jq` to extract the credentials.
3.  **Persistence**: The extracted values are written to `src/generated-secrets.yml`.
4.  **Encryption**: `scripts/tofu.sh` immediately encrypts the file using `ansible-vault`.
5.  **Consumption**: The main `src/playbook.yml` is configured to optionally include `generated-secrets.yml`.

### Proven Safety Rules

- **Avoid Special Characters**: Use `special = false` in `random_password` resources. This prevents shell interpolation or YAML parsing errors when secrets are moved between Tofu, Bash, and Ansible.
- **Stable Identifiers**: Use `random_id` for client IDs to ensure they remain consistent across infrastructure updates.

## OIDC Integration Patterns

The following patterns are proven to work for OIDC-enabled services (e.g., Dependency Track, Grafana) behind the local Caddy proxy.

### Single Page Applications (SPA)

For services where the frontend performs the authentication redirect (like Dependency Track):

- **Client Type**: `public` (or `confidential` if the API server handles the back-channel token exchange).
- **Flow**: `code` (Authorization Code Flow with PKCE).
- **Issuer Consistency**: The `OIDC_ISSUER` URL must be identical across the provider, the frontend, and the API server. In this repo, the format `https://identity.net.scetrov.live/application/o/slug/` (with trailing slash) is standard.
- **CORS**: The API server must have CORS enabled (`ALPINE_CORS_ENABLED=true`) and explicitly allow the frontend origin.

### Container Connectivity

OCI containers must be able to reach the Authentik discovery endpoint at startup.

- **Networking**: Move application containers to the `authentik` Podman network.
- **DNS Mapping**: Use `--add-host` flags to map `identity.net.scetrov.live` to the network gateway IP (typically `10.89.0.1`). This ensures the container can reach the host-based Caddy proxy even if external DNS is unreachable.
- **Validation**: Verified through `GET /api/v1/oidc/available` returning `true`.
