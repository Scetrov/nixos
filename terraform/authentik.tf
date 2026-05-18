# --- Property Mappings ---
data "authentik_property_mapping_provider_scope" "openid" {
  managed = "goauthentik.io/providers/oauth2/scope-openid"
}

data "authentik_property_mapping_provider_scope" "profile" {
  managed = "goauthentik.io/providers/oauth2/scope-profile"
}

data "authentik_property_mapping_provider_scope" "email" {
  managed = "goauthentik.io/providers/oauth2/scope-email"
}

data "authentik_property_mapping_provider_scope" "entitlements" {
  managed = "goauthentik.io/providers/oauth2/scope-entitlements"
}

# --- Flows ---
data "authentik_flow" "default_authorization" {
  slug = "default-provider-authorization-implicit-consent"
}

data "authentik_flow" "default_invalidation" {
  slug = "default-provider-invalidation-flow"
}

# --- Grafana OAuth2 Provider ---
resource "authentik_provider_oauth2" "grafana" {
  name          = "Grafana"
  client_id     = var.grafana_client_id
  client_secret = var.grafana_client_secret
  
  authorization_flow = data.authentik_flow.default_authorization.id
  invalidation_flow  = data.authentik_flow.default_invalidation.id

  allowed_redirect_uris = [
    {
      url           = "https://metrics.net.scetrov.live/grafana/login/generic_oauth"
      matching_mode = "strict"
    }
  ]
  
  property_mappings = [
    data.authentik_property_mapping_provider_scope.openid.id,
    data.authentik_property_mapping_provider_scope.profile.id,
    data.authentik_property_mapping_provider_scope.email.id,
  ]
}

resource "authentik_application" "grafana" {
  name              = "Grafana"
  slug              = "grafana"
  protocol_provider = authentik_provider_oauth2.grafana.id
}

# --- Hermes Proxy Provider ---
resource "authentik_provider_proxy" "hermes" {
  name               = "Hermes"
  external_host      = var.hermes_external_host
  authorization_flow = data.authentik_flow.default_authorization.id
  invalidation_flow  = data.authentik_flow.default_invalidation.id
  mode               = "forward_single"
}

resource "authentik_application" "hermes" {
  name              = "Hermes"
  slug              = "hermes"
  protocol_provider = authentik_provider_proxy.hermes.id
}

# --- Dependency Track OIDC Provider ---
resource "authentik_provider_oauth2" "dependency_track" {
  name          = "Dependency Track"
  
  authorization_flow = data.authentik_flow.default_authorization.id
  invalidation_flow  = data.authentik_flow.default_invalidation.id

  allowed_redirect_uris = [
    {
      url           = "https://dtrack.net.scetrov.live/static/oidc-callback.html"
      matching_mode = "strict"
    }
  ]
  
  property_mappings = [
    data.authentik_property_mapping_provider_scope.openid.id,
    data.authentik_property_mapping_provider_scope.profile.id,
    data.authentik_property_mapping_provider_scope.email.id,
  ]
}

resource "authentik_application" "dependency_track" {
  name              = "Dependency Track"
  slug              = "dependency-track"
  protocol_provider = authentik_provider_oauth2.dependency_track.id
}

# --- Outpost ---
# This manages the embedded outpost that provides forward_auth for Caddy.
resource "authentik_outpost" "proxy" {
  name = "authentik Embedded Outpost"
  type = "proxy"
  
  protocol_providers = [
    authentik_provider_proxy.hermes.id
  ]
  
  config = jsonencode({
    authentik_host = "https://identity.net.scetrov.live"
  })
}
