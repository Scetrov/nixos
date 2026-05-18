resource "grafana_service_account" "oncall" {
  name = "oncall-service-account"
  role = "Admin"
}

resource "grafana_service_account_token" "oncall" {
  name               = "oncall-token"
  service_account_id = grafana_service_account.oncall.id
}

resource "grafana_service_account" "log_pusher" {
  name = "log-pusher"
  role = "Editor"
}

resource "grafana_service_account_token" "log_pusher" {
  name               = "log-pusher-token"
  service_account_id = grafana_service_account.log_pusher.id
}

output "grafana_oncall_token" {
  value     = grafana_service_account_token.oncall.key
  sensitive = true
}

output "grafana_log_pusher_token" {
  value     = grafana_service_account_token.log_pusher.key
  sensitive = true
}
