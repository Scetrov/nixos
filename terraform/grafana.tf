resource "grafana_service_account" "oncall" {
  name = "oncall-service-account"
  role = "Admin"
}

resource "grafana_service_account_token" "oncall" {
  name               = "oncall-token"
  service_account_id = grafana_service_account.oncall.id
}

output "grafana_oncall_token" {
  value     = grafana_service_account_token.oncall.key
  sensitive = true
}
