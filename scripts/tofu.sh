#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/tofu.sh [--refresh-generated-secrets | --test-fixture-dir DIR] [--] [tofu args...]

Secure OpenTofu wrapper. It injects vault-backed credentials via environment
variables, runs OpenTofu, and writes encrypted generated outputs to
src/generated-secrets.yml without printing raw tokens or client secrets.

Modes:
  scripts/tofu.sh                         Run: tofu apply, then refresh generated secrets
  scripts/tofu.sh --refresh-generated-secrets
                                          Refresh src/generated-secrets.yml from current state only
  scripts/tofu.sh -- plan                 Run arbitrary tofu args, then refresh after apply only
  scripts/tofu.sh --forgejo-mirrors -- COMMAND ...
                                          Isolated Forgejo provisioning state/provider; bootstrap via
                                          scripts/provision_forgejo_mirrors.py, never enable password auth
  scripts/tofu.sh -- fmt ...              Format caller-relative files without credentials/backend init
  scripts/tofu.sh -- validate             Validate installed providers locally without credentials/init
  scripts/tofu.sh --test-fixture-dir DIR -- COMMAND ...
                                          Disposable local test configuration only; never load vault,
                                          production backend, or refresh generated secrets
EOF
}

REFRESH_ONLY=false
FIXTURE_DIR=""
FORGEJO_MIRRORS=false
TOFU_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --refresh-generated-secrets)
            REFRESH_ONLY=true
            shift
            ;;
        --forgejo-mirrors)
            FORGEJO_MIRRORS=true
            shift
            ;;
        --test-fixture-dir)
            [[ $# -ge 2 ]] || { echo "Missing fixture directory" >&2; exit 2; }
            FIXTURE_DIR="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            TOFU_ARGS+=("$@")
            break
            ;;
        *)
            TOFU_ARGS+=("$1")
            shift
            ;;
    esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TERRAFORM_DIR="$ROOT_DIR/terraform"
if [[ "$FORGEJO_MIRRORS" == true ]]; then
    [[ -z "$FIXTURE_DIR" && "$REFRESH_ONLY" == false ]] || {
        echo "Forgejo provisioning cannot use fixture/secret-refresh modes" >&2
        exit 2
    }
    TERRAFORM_DIR="$TERRAFORM_DIR/forgejo-mirrors"
fi
VAULT_PASSWORD_FILE="$HOME/.ansible/nixos_vault_password"
GENERATED_SECRETS_FILE="$ROOT_DIR/src/generated-secrets.yml"

# Test fixtures are generated under one ignored repository-local prefix. They
# use local state and synthetic TF_VAR_authentik_test_* inputs supplied by the
# runner, never production vault credentials or generated output capture.
if [[ -n "$FIXTURE_DIR" ]]; then
    [[ "$REFRESH_ONLY" == false && ${#TOFU_ARGS[@]} -gt 0 ]] || {
        echo "Fixture mode requires an explicit command and forbids secret refresh" >&2
        exit 2
    }
    FIXTURE_DIR="$(realpath -e -- "$FIXTURE_DIR")"
    case "$FIXTURE_DIR" in
        "$TERRAFORM_DIR"/.passkey-test-*) ;;
        *) echo "Fixture directory must be under terraform/.passkey-test-*" >&2; exit 2 ;;
    esac
    unset PG_CONN_STR TF_VAR_authentik_token TF_VAR_grafana_token
    export TF_IN_AUTOMATION=true
    exec tofu -chdir="$FIXTURE_DIR" "${TOFU_ARGS[@]}"
fi

# Local checks neither need credentials nor initialize/upgrade the remote
# backend. Keep pre-commit behind this wrapper without a hidden network action.
if [[ "$REFRESH_ONLY" == false ]]; then
    case "${TOFU_ARGS[0]:-}" in
        fmt)
            exec tofu "${TOFU_ARGS[@]}"
            ;;
        validate)
            exec tofu -chdir="$TERRAFORM_DIR" "${TOFU_ARGS[@]}"
            ;;
    esac
fi

SECRETS="$(ansible-vault view "$ROOT_DIR/src/secrets.yml" --vault-password-file "$VAULT_PASSWORD_FILE")"

extract_secret() {
    local key="$1"
    # Drain the input so printf cannot receive SIGPIPE under pipefail.
    printf '%s\n' "$SECRETS" | awk -v key="$key:" '$1 == key && !found {print $2; found=1}'
}

# Isolated state and a checksum-pinned provider; never initialize/apply the
# shared Authentik/Grafana stack for Forgejo application provisioning.
if [[ "$FORGEJO_MIRRORS" == true ]]; then
    unset TF_LOG TF_LOG_PATH TF_LOG_PROVIDER TF_LOG_CORE
    unset TF_CLI_ARGS TF_CLI_ARGS_plan TF_CLI_ARGS_apply
    unset FORGEJO_HOST FORGEJO_API_TOKEN FORGEJO_USERNAME FORGEJO_PASSWORD
    export TF_IN_AUTOMATION=true
    export TF_VAR_forgejo_host="https://source.net.scetrov.live"
    export TF_VAR_human_owner="scetrov"
    PG_PASS="$(extract_secret authentik_postgresql_password | python3 -c 'import sys; from urllib.parse import quote; print(quote(sys.stdin.read().rstrip("\n"), safe=""))')"
    export PG_CONN_STR="postgres://terraform:${PG_PASS}@habiki.net.scetrov.live:5433/terraform_state?sslmode=verify-full&sslrootcert=/etc/ssl/certs/ca-certificates.crt"
    export TF_VAR_mirror_password="$(extract_secret forgejo_mirrors_password)"
    if [[ "${TOFU_ARGS[0]:-}" == plan || "${TOFU_ARGS[0]:-}" == apply ]]; then
        [[ -n "${TF_VAR_forgejo_api_token:-}" && -n "$TF_VAR_mirror_password" ]] || {
            echo "Forgejo provisioning requires its temporary bootstrap credential and vault password" >&2
            exit 1
        }
    fi
    export TF_CLI_CONFIG_FILE="$(python3 "$ROOT_DIR/scripts/forgejo_provider.py" "$TERRAFORM_DIR")"
    tofu -chdir="$TERRAFORM_DIR" init -reconfigure >&2
    exec tofu -chdir="$TERRAFORM_DIR" "${TOFU_ARGS[@]}"
fi

# shellcheck source=/dev/null
source "$HOME/env/grafana.env"

export TF_IN_AUTOMATION=true
export TF_VAR_authentik_token="$(extract_secret authentik_api_token)"
export TF_VAR_grafana_token="$GRAFANA_SERVICE_TOKEN"
unset GARAGE_TOKEN GARAGE_ADMIN_TOKEN
export TF_VAR_garage_resources_enabled=false
export TF_VAR_garage_authentik_token="bootstrap-unused"

# URI-encode the existing password without placing it in process arguments.
PG_PASS="$(extract_secret authentik_postgresql_password | python3 -c 'import sys; from urllib.parse import quote; print(quote(sys.stdin.read().rstrip("\n"), safe=""))')"
export PG_CONN_STR="postgres://terraform:${PG_PASS}@habiki.net.scetrov.live:5433/terraform_state?sslmode=verify-full&sslrootcert=/etc/ssl/certs/ca-certificates.crt"

prepare_garage_broker() {
    local generated_plain token state_list
    [[ -f "$GENERATED_SECRETS_FILE" ]] || return 0
    generated_plain="$(mktemp /dev/shm/garage-broker.XXXXXX)"
    chmod 0600 "$generated_plain"
    if ! ansible-vault view "$GENERATED_SECRETS_FILE" --vault-password-file "$VAULT_PASSWORD_FILE" >"$generated_plain"; then
        rm -f "$generated_plain"
        echo "Unable to read generated secrets for Garage broker authentication" >&2
        exit 1
    fi
    state_list="$(tofu -chdir="$TERRAFORM_DIR" state list 2>/dev/null || true)"
    if ! token="$(python3 "$ROOT_DIR/scripts/garage_broker.py" prepare --generated "$generated_plain" --state-list "$state_list")"; then
        rm -f "$generated_plain"
        exit 1
    fi
    rm -f "$generated_plain"
    if [[ "$token" == "disabled" ]]; then
        return 0
    fi
    export TF_VAR_garage_resources_enabled=true
    export TF_VAR_garage_authentik_token="$token"
}

refresh_generated_secrets() {
    local json_outputs tmp_sec_file=""
    json_outputs="$(tofu -chdir="$TERRAFORM_DIR" output -json)"
    tmp_sec_file="$(mktemp /dev/shm/generated-secrets.XXXXXX)"
    chmod 0600 "$tmp_sec_file"
    # Clean the protected plaintext even if validation or encryption fails.
    trap 'rm -f "$tmp_sec_file"' EXIT

    # Persist before rendering so a generated-secret failure can still recover
    # the same state-held Minecraft pair on retry.
    python3 "$ROOT_DIR/scripts/garage_broker.py" persist-pair \
        --vault "$ROOT_DIR/src/secrets.yml" \
        --password-file "$VAULT_PASSWORD_FILE" <<< "$json_outputs" >&2

    # Render + validate through the shared, unit-tested renderer. It fails
    # closed (non-zero, nothing written) on missing/empty/null/placeholder
    # values, including the Forgejo additions. Keep the temp file 0600 and
    # never echo the manifest.
    if ! (set -o pipefail; python3 "$ROOT_DIR/scripts/render_generated_secrets.py" \
            "$tmp_sec_file" <<< "$json_outputs"); then
        local render_rc=${PIPESTATUS[1]}
        # The renderer's stderr is already on our stderr; fail closed so the
        # existing encrypted manifest is never truncated by a failed refresh.
        echo "render_generated_secrets: generated-secret refresh failed (renderer exit ${render_rc}); existing ${GENERATED_SECRETS_FILE} left untouched." >&2
        exit "$render_rc"
    fi

    ansible-vault encrypt "$tmp_sec_file" \
        --vault-password-file "$VAULT_PASSWORD_FILE" \
        --output "$GENERATED_SECRETS_FILE" >/dev/null
    rm -f "$tmp_sec_file"
    trap - EXIT
    echo "Refreshed encrypted generated secrets at src/generated-secrets.yml."
}

if [[ "$REFRESH_ONLY" == true ]]; then
    tofu -chdir="$TERRAFORM_DIR" init -reconfigure -upgrade >&2
    refresh_generated_secrets
    exit 0
fi

if [[ ${#TOFU_ARGS[@]} -eq 0 ]]; then
    TOFU_ARGS=(apply)
fi

# Keep command stdout machine-readable (e.g. output -raw) for Ansible callers.
tofu -chdir="$TERRAFORM_DIR" init -reconfigure -upgrade >&2

case "${TOFU_ARGS[0]}" in
    plan|apply|destroy|import|refresh)
        prepare_garage_broker
        ;;
esac

tofu -chdir="$TERRAFORM_DIR" "${TOFU_ARGS[@]}"

if [[ " ${TOFU_ARGS[*]} " == *" apply "* ]]; then
    refresh_generated_secrets
fi
