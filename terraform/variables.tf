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

# Non-sensitive configuration input recording the owner's confirmed
# Authentik identity. Confirmed with the operator on 2026-10-08 that
# "scetrov" is the owner identity; it is the sole intended member of the
# Forgejo access group (see openspec change add-private-forgejo).
variable "forgejo_owner_username" {
  type    = string
  default = "scetrov"
}
