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
                           - nixos            : Host configuration & linting
                           - authentik        : Authentik applications & OpenTofu
                           - hermes           : Hermes service, secrets & SSO setup
                           - dependency-track : Dependency Track deployment & configuration
                           - secrets          : Secrets generation and deployment
  -h, --help             Show this help message and exit

Examples:
  $0                                      # Run full deployment on all hosts
  $0 --limit habiki                       # Deploy everything on habiki only
  $0 --tags hermes                        # Run Hermes config across all relevant hosts
  $0 --limit habiki --tags hermes         # Targeted deploy of Hermes on habiki
  $0 --limit habiki --tags nixos          # Rebuild NixOS only on habiki

EOF
}

# Default values
LIMIT=""
TAGS=""
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

# Build Ansible arguments
ANSIBLE_ARGS=("-i" "src/inventory.yml" "src/playbook.yml" "--vault-password-file" "$HOME/.ansible/nixos_vault_password")

if [[ -n "$LIMIT" ]]; then
    ANSIBLE_ARGS+=("--limit" "$LIMIT")
fi

if [[ -n "$TAGS" ]]; then
    ANSIBLE_ARGS+=("--tags" "$TAGS")
fi

if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
    ANSIBLE_ARGS+=("${EXTRA_ARGS[@]}")
fi

echo "Running deploy with command:"
echo "  ansible-playbook ${ANSIBLE_ARGS[*]}"
echo "Remember to review and commit your changes selectively."
echo ""

exec ansible-playbook "${ANSIBLE_ARGS[@]}"
