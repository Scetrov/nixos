variable "authentik_token" {
  type      = string
  sensitive = true
}

variable "grafana_token" {
  type      = string
  sensitive = true
}

variable "hermes_external_host" {
  type    = string
  default = "https://hermes.net.scetrov.live"
}
