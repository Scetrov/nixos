variable "authentik_token" {
  type      = string
  sensitive = true
}

variable "grafana_client_id" {
  type = string
}

variable "grafana_client_secret" {
  type      = string
  sensitive = true
}

variable "hermes_external_host" {
  type    = string
  default = "https://hermes.net.scetrov.live"
}
