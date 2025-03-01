#!/usr/bin/env bash

ansible-vault edit src/secrets.yml --vault-password-file ~/.ansible/nixos_vault_password
