resource "grafana_service_account" "oncall" {
  name = "oncall-service-account"
  role = "Admin"
}

locals {
  grafana_portal = {
    source_root = "${path.module}/dashboards"
    folders = {
      platform = {
        title = "Operations / Platform"
        uid   = "ops-platform"
      }
      services = {
        title = "Operations / Services"
        uid   = "ops-services"
      }
    }
  }
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

resource "grafana_service_account" "mcp" {
  name = "mcp-service-account"
  role = "Admin"
}

resource "grafana_service_account_token" "mcp" {
  name               = "mcp-token"
  service_account_id = grafana_service_account.mcp.id
}

output "grafana_mcp_token" {
  value     = grafana_service_account_token.mcp.key
  sensitive = true
}


output "grafana_oidc_client_id" {
  value = authentik_provider_oauth2.grafana.client_id
}

output "grafana_oidc_client_secret" {
  value     = authentik_provider_oauth2.grafana.client_secret
  sensitive = true
}

output "dtrack_oidc_client_id" {
  value = authentik_provider_oauth2.dependency_track.client_id
}

output "dtrack_oidc_client_secret" {
  value     = authentik_provider_oauth2.dependency_track.client_secret
  sensitive = true
}

output "flyingfire_initial_password" {
  value     = random_password.flyingfire_password.result
  sensitive = true
}

output "pinkgiraffes_initial_password" {
  value     = random_password.pinkgiraffes_password.result
  sensitive = true
}

resource "grafana_folder" "operations_platform" {
  title = local.grafana_portal.folders.platform.title
  uid   = local.grafana_portal.folders.platform.uid
}

resource "grafana_folder" "operations_services" {
  title = local.grafana_portal.folders.services.title
  uid   = local.grafana_portal.folders.services.uid
}

resource "grafana_dashboard" "platform_overview" {
  folder      = grafana_folder.operations_platform.uid
  config_json = file("${local.grafana_portal.source_root}/platform-overview.json")
  overwrite   = true
}

resource "grafana_dashboard" "service_catalog" {
  folder      = grafana_folder.operations_platform.uid
  config_json = file("${local.grafana_portal.source_root}/service-catalog.json")
  overwrite   = true
}

resource "grafana_dashboard" "frontier_indexer_service" {
  folder      = grafana_folder.operations_services.uid
  config_json = file("${local.grafana_portal.source_root}/frontier-indexer-service.json")
  overwrite   = true
}

resource "grafana_dashboard" "dependency_track_service" {
  folder      = grafana_folder.operations_services.uid
  config_json = file("${local.grafana_portal.source_root}/dependency-track-service.json")
  overwrite   = true
}

resource "grafana_dashboard" "oncall_service" {
  folder      = grafana_folder.operations_services.uid
  config_json = file("${local.grafana_portal.source_root}/oncall-service.json")
  overwrite   = true
}

resource "grafana_dashboard" "hermes_service" {
  folder      = grafana_folder.operations_services.uid
  config_json = file("${local.grafana_portal.source_root}/hermes-service.json")
  overwrite   = true
}

resource "grafana_dashboard" "home_assistant_service" {
  folder      = grafana_folder.operations_services.uid
  config_json = file("${local.grafana_portal.source_root}/home-assistant-service.json")
  overwrite   = true
}

resource "grafana_dashboard" "home_assistant_environment" {
  folder      = grafana_folder.operations_services.uid
  config_json = file("${local.grafana_portal.source_root}/home-assistant-environment.json")
  overwrite   = true
}

resource "grafana_dashboard" "home_assistant_house_overview" {
  folder      = grafana_folder.operations_services.uid
  config_json = file("${local.grafana_portal.source_root}/home-assistant-house-overview.json")
  overwrite   = true
}

resource "grafana_dashboard" "unifi_network_logs" {
  folder      = grafana_folder.operations_services.uid
  config_json = file("${local.grafana_portal.source_root}/unifi-network-logs.json")
  overwrite   = true
}

resource "grafana_dashboard" "frontier_indexer" {
  folder      = grafana_folder.operations_services.uid
  config_json = file("${local.grafana_portal.source_root}/frontier-indexer.json")
  overwrite   = true
}

resource "grafana_dashboard" "system_resources" {
  folder      = grafana_folder.operations_platform.uid
  config_json = file("${local.grafana_portal.source_root}/system-resources.json")
  overwrite   = true
}
