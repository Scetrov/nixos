#!/bin/bash
source ~/env/grafana.env
cd terraform

SECRETS=$(ansible-vault view ../src/secrets.yml --vault-password-file ~/.ansible/nixos_vault_password)

export TF_VAR_authentik_token=$(echo "$SECRETS" | grep authentik_api_token | awk '{print $2}')
export TF_VAR_grafana_token=$GRAFANA_SERVICE_TOKEN
export TF_VAR_grafana_client_id=$(echo "$SECRETS" | grep grafana_authentik_client_id | awk '{print $2}')
export TF_VAR_grafana_client_secret=$(echo "$SECRETS" | grep grafana_authentik_client_secret | awk '{print $2}')

export PG_PASS=$(echo "$SECRETS" | grep authentik_postgresql_password | awk '{print $2}')

tofu init -reconfigure -backend-config="conn_str=postgres://terraform:$PG_PASS@10.229.10.2:5433/terraform_state?sslmode=disable"
tofu plan
