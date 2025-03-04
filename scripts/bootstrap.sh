#!/usr/bin/env bash

ansible-playbook -i src/bootstrap-inventory.yml src/bootstrap-playbook.yml --vault-password-file ~/.ansible/nixos_vault_password
