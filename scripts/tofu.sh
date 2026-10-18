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
  scripts/tofu.sh -- fmt ...              Format caller-relative files without credentials/backend init
  scripts/tofu.sh -- validate             Validate installed providers locally without credentials/init
  scripts/tofu.sh --test-fixture-dir DIR -- COMMAND ...
                                          Disposable local test configuration only; never load vault,
                                          production backend, or refresh generated secrets
EOF
}

REFRESH_ONLY=false
FIXTURE_DIR=""
TOFU_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --refresh-generated-secrets)
            REFRESH_ONLY=true
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

# shellcheck source=/dev/null
source "$HOME/env/grafana.env"

SECRETS="$(ansible-vault view "$ROOT_DIR/src/secrets.yml" --vault-password-file "$VAULT_PASSWORD_FILE")"

extract_secret() {
    local key="$1"
    # Drain the input so printf cannot receive SIGPIPE under pipefail.
    printf '%s\n' "$SECRETS" | awk -v key="$key:" '$1 == key && !found {print $2; found=1}'
}

export TF_IN_AUTOMATION=true
export TF_VAR_authentik_token="$(extract_secret authentik_api_token)"
export TF_VAR_grafana_token="$GRAFANA_SERVICE_TOKEN"

PG_PASS="$(extract_secret authentik_postgresql_password)"
export PG_CONN_STR="postgres://terraform:${PG_PASS}@10.229.10.2:5433/terraform_state?sslmode=disable"

refresh_generated_secrets() {
    local json_outputs tmp_sec_file
    json_outputs="$(tofu -chdir="$TERRAFORM_DIR" output -json)"
    tmp_sec_file="$(mktemp /dev/shm/generated-secrets.XXXXXX)"
    chmod 0600 "$tmp_sec_file"
    # Clean the protected plaintext even if validation or encryption fails.
    trap 'rm -f "$tmp_sec_file"' EXIT

    # Render + validate through the shared, unit-tested renderer. It fails
    # closed (non-zero, nothing written) on missing/empty/null/placeholder
    # values, including the Forgejo additions. Keep the temp file 0600 and
    # never echo the manifest.
    python3 "$ROOT_DIR/scripts/render_generated_secrets.py" "$tmp_sec_file" <<< "$json_outputs"

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
tofu -chdir="$TERRAFORM_DIR" "${TOFU_ARGS[@]}"

if [[ " ${TOFU_ARGS[*]} " == *" apply "* ]]; then
    refresh_generated_secrets
fi
