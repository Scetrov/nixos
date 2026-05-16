source ~/env/grafana.env
export TF_VAR_authentik_token=$(ansible-vault view src/secrets.yml --vault-password-file ~/.ansible/nixos_vault_password | grep authentik_api_token | awk "{print \$2}")
export PG_PASS=$(ansible-vault view src/secrets.yml --vault-password-file ~/.ansible/nixos_vault_password | grep authentik_postgresql_password | awk "{print \$2}")

cd terraform
tofu init -backend-config="conn_str=postgres://terraform:$PG_PASS@10.229.10.2:5433/terraform_state?sslmode=disable"
tofu plan
