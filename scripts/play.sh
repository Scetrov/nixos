#!/usr/bin/env bash

echo "Running deploy. Remember to review and commit your changes selectively."
ansible-playbook -i src/inventory.yml src/playbook.yml --vault-password-file ~/.ansible/nixos_vault_password "$@"
