#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VAULT_PASSWORD_FILE="${VAULT_PASSWORD_FILE:-$HOME/.ansible/nixos_vault_password}"
AUTHENTIK_URL="${AUTHENTIK_URL:-https://identity.net.scetrov.live}"
GRAFANA_LOGIN_URL="${GRAFANA_LOGIN_URL:-https://metrics.net.scetrov.live/grafana/login/generic_oauth}"
DTRACK_CONFIG_URL="${DTRACK_CONFIG_URL:-https://dtrack.net.scetrov.live/static/config.json}"

SECRETS="$(ansible-vault view "$ROOT_DIR/src/secrets.yml" --vault-password-file "$VAULT_PASSWORD_FILE")"
AUTHENTIK_TOKEN="$(printf '%s\n' "$SECRETS" | awk '$1 == "authentik_api_token:" {print $2; exit}')"

fingerprint() {
    local value="$1"
    printf '%s' "$value" | sha256sum | awk '{print substr($1, 1, 12)}'
}

provider_client_id() {
    local provider_name="$1"
    curl -fsS "$AUTHENTIK_URL/api/v3/providers/oauth2/?page_size=100&search=$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))' "$provider_name")" \
        -H "Authorization: Bearer $AUTHENTIK_TOKEN" \
    | jq -r --arg name "$provider_name" '.results[] | select(.name == $name) | .client_id' \
    | head -n1
}

grafana_redirect_client_id() {
    local location
    location="$(curl -fsSIk -o /dev/null -w '%{redirect_url}' "$GRAFANA_LOGIN_URL" || true)"
    python3 -c 'import sys, urllib.parse; url=sys.argv[1]; print(urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("client_id", [""])[0])' "$location"
}

dtrack_config_client_id() {
    curl -fsS "$DTRACK_CONFIG_URL" | jq -r '.OIDC_CLIENT_ID // .oidc.clientId // ""'
}

check_match() {
    local label="$1" service_value="$2" provider_value="$3"

    if [[ -z "$service_value" || "$service_value" == "null" || "$service_value" == *_placeholder ]]; then
        echo "${label}: FAIL service client_id is missing/null/placeholder"
        return 1
    fi

    if [[ -z "$provider_value" || "$provider_value" == "null" ]]; then
        echo "${label}: FAIL Authentik provider client_id is missing"
        return 1
    fi

    if [[ "$service_value" == "$provider_value" ]]; then
        echo "${label}: OK match=true service_len=${#service_value} provider_len=${#provider_value} fingerprint=$(fingerprint "$service_value")"
        return 0
    fi

    echo "${label}: FAIL match=false service_len=${#service_value} service_fp=$(fingerprint "$service_value") provider_len=${#provider_value} provider_fp=$(fingerprint "$provider_value")"
    return 1
}

grafana_provider_id="$(provider_client_id "Grafana")"
dtrack_provider_id="$(provider_client_id "Dependency Track")"
grafana_service_id="$(grafana_redirect_client_id)"
dtrack_service_id="$(dtrack_config_client_id)"

status=0
check_match "Grafana" "$grafana_service_id" "$grafana_provider_id" || status=1
check_match "Dependency Track" "$dtrack_service_id" "$dtrack_provider_id" || status=1

exit "$status"
