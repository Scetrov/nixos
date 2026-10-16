# Private native OIDC: membership in this group is the authorization boundary.
# Reuse the confirmed operator lookup; do not change any other memberships.
resource "random_id" "miniflux_client_id" {
  byte_length = 20
}

resource "random_password" "miniflux_client_secret" {
  length  = 40
  special = false
}

resource "authentik_provider_oauth2" "miniflux" {
  name               = "Miniflux"
  client_id          = random_id.miniflux_client_id.hex
  client_secret      = random_password.miniflux_client_secret.result
  client_type        = "confidential"
  signing_key        = data.authentik_certificate_key_pair.default.id
  authorization_flow = data.authentik_flow.default_authorization.id
  invalidation_flow  = data.authentik_flow.default_invalidation.id
  grant_types        = ["authorization_code", "refresh_token"]

  allowed_redirect_uris = [{
    url               = "https://feed.net.scetrov.live/oauth2/oidc/callback"
    matching_mode     = "strict"
    redirect_uri_type = "authorization"
  }]

  property_mappings = [
    data.authentik_property_mapping_provider_scope.openid.id,
    data.authentik_property_mapping_provider_scope.profile.id,
    data.authentik_property_mapping_provider_scope.email.id,
  ]
}

resource "authentik_application" "miniflux" {
  name               = "Miniflux"
  slug               = "miniflux"
  protocol_provider  = authentik_provider_oauth2.miniflux.id
  policy_engine_mode = "all"
  meta_launch_url    = "https://feed.net.scetrov.live"
}

resource "authentik_group" "miniflux_operator" {
  name  = "Miniflux Operator"
  users = [data.authentik_user.scetrov.id]
}

resource "authentik_policy_binding" "miniflux_access" {
  target  = authentik_application.miniflux.uuid
  group   = authentik_group.miniflux_operator.id
  order   = 0
  enabled = true
}

output "miniflux_oidc_client_id" {
  value     = authentik_provider_oauth2.miniflux.client_id
  sensitive = true
}

output "miniflux_oidc_client_secret" {
  value     = authentik_provider_oauth2.miniflux.client_secret
  sensitive = true
}
