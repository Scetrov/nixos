#!/usr/bin/env bash
set -euo pipefail

# Helper function to print usage
usage() {
    cat << EOF
Usage: $0 [options] [-- ansible-playbook-options]

Modular NixOS & Service Deployment Wrapper

Options:
  -l, --limit <host>     Limit deployment to a specific host (e.g., habiki, bullit, fyne)
  -t, --tags <tag>       Filter execution by tags/logical groups:
                           - database-upgrade : Explicit PG16→17/Redis maintenance on habiki
                                                Requires --limit habiki and -e upgrade_confirm=true
                           - nixos            : Host configuration & linting
                           - authentik        : Authentik applications & OpenTofu
                           - hermes           : Hermes service, secrets & SSO setup
                           - hermes-runtime   : Hermes-only secret/config/runtime deploy (requires --limit habiki;
                                                no channel updates, OpenTofu or blanket restarts)
                           - hermes-auth      : Proxy-only Hermes auth repair (requires --limit habiki;
                                                no channel updates or blanket container restarts)
                           - dependency-track : Dependency Track deployment & configuration
                           - miniflux         : Habiki feed reader: provision OIDC, refresh credentials,
                                                render secrets and rebuild (requires --limit habiki)
                           - immich           : Habiki native OIDC, protected recovery secrets and rebuild
                                                (requires --limit habiki; no channel updates)
                           - frontier-indexer : Frontier cycle transition, secrets & host configuration
                           - esphome          : ESPHome secret rendering, validation, build, and OTA deploy
                           - secrets          : Secrets generation and deployment
                           - local-dns        : Shared DNS aliases only (existing Fyne/Habiki config)
                           - forgejo          : Habiki Forgejo consumer deploy (generated-secret refresh,
                                                runtime secrets, NixOS rebuild; OIDC reconciliation
                                                happens at service start). First deploy requires a
                                                prior `scripts/tofu.sh` apply so generated outputs exist.
      --skip-generated-refresh
                         Skip pre-flight refresh of OpenTofu generated OIDC secrets.
  -h, --help             Show this help message and exit

Examples:
  $0                                      # Run full deployment on all hosts
  $0 --limit habiki                       # Deploy everything on habiki only
  $0 --tags hermes                        # Run Hermes config across all relevant hosts
  $0 --limit habiki --tags hermes         # Targeted deploy of Hermes on habiki
  $0 --limit habiki --tags nixos          # Rebuild NixOS only on habiki
  $0 --limit habiki --tags esphome        # Run ESPHome workflow owned by habiki
  $0 --limit fyne --tags local-dns        # DNS-only rollout; no Forgejo or secret refresh
  $0 --limit habiki --tags forgejo        # Targeted Forgejo consumer deploy on Habiki
  $0 --limit habiki --tags miniflux       # End-to-end Miniflux deployment on Habiki

EOF
}

# Default values
LIMIT=""
TAGS=""
SKIP_GENERATED_REFRESH=false
EXTRA_ARGS=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -l|--limit)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --limit requires a host argument." >&2
                exit 1
            fi
            LIMIT="$2"
            shift 2
            ;;
        -t|--tags)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --tags requires a tag argument." >&2
                exit 1
            fi
            TAGS="$2"
            shift 2
            ;;
        --skip-generated-refresh)
            SKIP_GENERATED_REFRESH=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            EXTRA_ARGS+=("$@")
            break
            ;;
        *)
            # Allow forwarding other arguments directly
            EXTRA_ARGS+=("$1")
            shift
            ;;
    esac
done

has_tag() {
    local requested="$1" tag
    local -a selected_tags=()
    IFS=',' read -ra selected_tags <<< "$TAGS"
    for tag in "${selected_tags[@]}"; do
        [[ "${tag// /}" != "$requested" ]] || return 0
    done
    return 1
}

MINIFLUX_DEPLOY=false
if has_tag miniflux; then
    if [[ "$LIMIT" != "habiki" ]]; then
        echo "Error: miniflux requires --limit habiki." >&2
        exit 1
    fi
    if [[ "$SKIP_GENERATED_REFRESH" == true ]]; then
        echo "Error: miniflux cannot skip authoritative generated-secret refresh." >&2
        exit 1
    fi
    MINIFLUX_DEPLOY=true
fi

IMMICH_DEPLOY=false
if has_tag immich; then
    if [[ "$LIMIT" != "habiki" || "$TAGS" != "immich" ]]; then
        echo "Error: immich requires --limit habiki and cannot be combined with other tags." >&2
        exit 1
    fi
    if [[ "$SKIP_GENERATED_REFRESH" == true ]]; then
        echo "Error: immich cannot skip authoritative generated-secret refresh." >&2
        exit 1
    fi
    IMMICH_DEPLOY=true
fi

# Introspection and check mode must not apply infrastructure or refresh secrets.
READ_ONLY=false
for argument in "${EXTRA_ARGS[@]}"; do
    case "$argument" in
        --syntax-check|--list-tasks|--list-tags|--list-hosts|--check|-C)
            READ_ONLY=true
            ;;
        --limit|--limit=*|-l|-l?*|--tags|--tags=*|-t|-t?*|--skip-tags|--skip-tags=*)
            if [[ "$MINIFLUX_DEPLOY" == true || "$IMMICH_DEPLOY" == true ]]; then
                echo "Error: targeted identity deploy target/tag overrides after -- are not supported." >&2
                exit 1
            fi
            ;;
    esac
done

# Database maintenance is deliberately separate from normal deployment roles.
PLAYBOOK="src/playbook.yml"
if has_tag hermes-runtime; then
    if [[ "$LIMIT" != "habiki" || "$TAGS" != "hermes-runtime" ]]; then
        echo "Error: hermes-runtime requires --limit habiki and cannot be combined with other tags." >&2
        exit 1
    fi
    for argument in "${EXTRA_ARGS[@]}"; do
        case "$argument" in
            --limit|--limit=*|-l|-l?*|--tags|--tags=*|-t|-t?*|--skip-tags|--skip-tags=*)
                echo "Error: hermes-runtime target/tag overrides after -- are not supported." >&2
                exit 1
                ;;
        esac
    done
    PLAYBOOK="src/hermes-runtime.yml"
fi
if has_tag hermes-auth; then
    if [[ "$LIMIT" != "habiki" || "$TAGS" != "hermes-auth" ]]; then
        echo "Error: hermes-auth requires --limit habiki and cannot be combined with other tags." >&2
        exit 1
    fi
    # Do not allow trailing arguments to widen the focused play's host/tag scope.
    for argument in "${EXTRA_ARGS[@]}"; do
        case "$argument" in
            --limit|--limit=*|-l|-l?*|--tags|--tags=*|-t|-t?*|--skip-tags|--skip-tags=*)
                echo "Error: hermes-auth target/tag overrides after -- are not supported." >&2
                exit 1
                ;;
        esac
    done
    PLAYBOOK="src/hermes-auth.yml"
fi
if [[ "$TAGS" == "database-upgrade" ]]; then
    if [[ "$LIMIT" != "habiki" ]]; then
        echo "Error: database-upgrade requires --limit habiki." >&2
        exit 1
    fi
    PLAYBOOK="src/upgrade-databases.yml"
fi

# Build Ansible arguments
ANSIBLE_ARGS=("-i" "src/inventory.yml" "$PLAYBOOK" "--vault-password-file" "$HOME/.ansible/nixos_vault_password")

if [[ -n "$LIMIT" ]]; then
    ANSIBLE_ARGS+=("--limit" "$LIMIT")
fi

if [[ -n "$TAGS" ]]; then
    ANSIBLE_ARGS+=("--tags" "$TAGS")
fi

if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
    ANSIBLE_ARGS+=("${EXTRA_ARGS[@]}")
fi

needs_generated_refresh() {
    local tags="$1"

    if [[ -z "$tags" ]]; then
        return 0
    fi

    IFS=',' read -ra tag_list <<< "$tags"
    for tag in "${tag_list[@]}"; do
        case "${tag// /}" in
            authentik|nixos|dependency-track|secrets|forgejo|miniflux|immich)
                return 0
                ;;
        esac
    done

    return 1
}

if [[ "$IMMICH_DEPLOY" == true && "$READ_ONLY" == false ]]; then
    echo "Provisioning Immich identity and refreshing credentials before Ansible loads vars_files..."
    "$(dirname "$0")/tofu.sh" -- apply -auto-approve -target=authentik_policy_binding.immich_access
    echo ""
elif [[ "$MINIFLUX_DEPLOY" == true && "$READ_ONLY" == false ]]; then
    echo "Provisioning Miniflux identity and refreshing credentials before Ansible loads vars_files..."
    # The binding's dependency graph includes its application/provider, group,
    # operator lookup and random credentials; do not apply unrelated resources.
    "$(dirname "$0")/tofu.sh" -- apply -auto-approve -target=authentik_policy_binding.miniflux_access
    echo ""
elif [[ "$READ_ONLY" == false && "$SKIP_GENERATED_REFRESH" == false ]] && needs_generated_refresh "$TAGS"; then
    echo "Refreshing OpenTofu generated OIDC secrets before Ansible loads vars_files..."
    "$(dirname "$0")/tofu.sh" --refresh-generated-secrets
    echo ""
fi

echo "Running deploy with command:"
echo "  ansible-playbook ${ANSIBLE_ARGS[*]}"
echo "Remember to review and commit your changes selectively."
echo ""

exec ansible-playbook "${ANSIBLE_ARGS[@]}"
