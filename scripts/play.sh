#!/usr/bin/env bash

git add . && git commit && git push origin HEAD && ansible-playbook -i src/inventory.yml src/playbook.yml --vault-password-file ~/.ansible/nixos_vault_password
