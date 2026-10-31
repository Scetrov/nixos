# Native Penpot authentication: browser OIDC only; MCP uses Penpot's own keys.
resource "random_id" "penpot_client_id" {
  byte_length = 20
}

resource "random_password" "penpot_client_secret" {
  length  = 40
  special = false
}

resource "random_password" "penpot_db_password" {
  length  = 48
  special = false
}

resource "random_password" "penpot_secret_key" {
  length  = 86
  special = false
}

resource "authentik_provider_oauth2" "penpot" {
  name               = "Penpot"
  client_id          = random_id.penpot_client_id.hex
  client_secret      = random_password.penpot_client_secret.result
  client_type        = "confidential"
  signing_key        = data.authentik_certificate_key_pair.default.id
  authorization_flow = data.authentik_flow.default_authorization.id
  invalidation_flow  = data.authentik_flow.default_invalidation.id
  grant_types        = ["authorization_code", "refresh_token"]

  allowed_redirect_uris = [{
    url               = "https://penpot.net.scetrov.live/api/auth/oidc/callback"
    matching_mode     = "strict"
    redirect_uri_type = "authorization"
  }]

  property_mappings = [
    data.authentik_property_mapping_provider_scope.openid.id,
    data.authentik_property_mapping_provider_scope.profile.id,
    data.authentik_property_mapping_provider_scope.email.id,
  ]
}

resource "authentik_application" "penpot" {
  name              = "Penpot"
  slug              = "penpot"
  protocol_provider = authentik_provider_oauth2.penpot.id
  meta_launch_url   = "https://penpot.net.scetrov.live"
}

resource "authentik_policy_binding" "penpot_access" {
  target = authentik_application.penpot.uuid
  group  = authentik_group.all_applications.id
  order  = 0
}

output "penpot_db_password" {
  value     = random_password.penpot_db_password.result
  sensitive = true
}

output "penpot_secret_key" {
  value     = random_password.penpot_secret_key.result
  sensitive = true
}

output "penpot_oidc_client_id" {
  value     = random_id.penpot_client_id.hex
  sensitive = true
}

output "penpot_oidc_client_secret" {
  value     = random_password.penpot_client_secret.result
  sensitive = true
}
