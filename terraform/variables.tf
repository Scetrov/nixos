variable "authentik_token" {
  type      = string
  sensitive = true
}

# Persistently select the accepted native flow after operator approval.
# Restore false for declarative rollback; the independent helper route stays intact.
variable "authentik_passkey_first_enabled" {
  description = "Select the accepted passkey-first candidate on the existing default brand."
  type        = bool
  default     = true
}

variable "grafana_token" {
  type      = string
  sensitive = true
}

# Authentik machine JWT for the Caddy broker. Never the native Garage token.
variable "garage_authentik_token" {
  type      = string
  sensitive = true
  default   = "bootstrap-unused"
}

variable "garage_resources_enabled" {
  type    = bool
  default = false
}

variable "hermes_external_host" {
  type    = string
  default = "https://hermes.net.scetrov.live"
}

# Non-sensitive configuration input recording the owner's confirmed
# Authentik identity. Confirmed with the operator on 2026-10-08 that
# "scetrov" is the owner identity; it is the sole intended member of the
# Forgejo access group (see docs/forgejo.md).
variable "forgejo_owner_username" {
  type    = string
  default = "scetrov"
}
