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
  name               = "Grafana"
  client_id          = var.grafana_client_id
  client_secret      = var.grafana_client_secret
  authorization_flow = data.authentik_flow.default_authorization.id
  invalidation_flow  = data.authentik_flow.default_invalidation.id
  
  property_mappings = [
    data.authentik_property_mapping_provider_scope.openid.id,
    data.authentik_property_mapping_provider_scope.profile.id,
    data.authentik_property_mapping_provider_scope.email.id,
    data.authentik_property_mapping_provider_scope.entitlements.id,
  ]

  redirect_uris = [
    {
      url           = "https://metrics.net.scetrov.live/grafana/login/generic_oauth"
      matching_mode = "strict"
    }
  ]
}

resource "authentik_application" "grafana" {
  name              = "Grafana"
  slug              = "grafana"
  provider_id       = authentik_provider_oauth2.grafana.id
  meta_launch_url   = "https://metrics.net.scetrov.live/grafana"
  open_in_new_tab   = false
}

resource "authentik_application_entitlement" "grafana_admins" {
  name        = "Grafana Admins"
  application = authentik_application.grafana.uuid
}

resource "authentik_application_entitlement" "grafana_editors" {
  name        = "Grafana Editors"
  application = authentik_application.grafana.uuid
}

resource "authentik_application_entitlement" "grafana_viewers" {
  name        = "Grafana Viewers"
  application = authentik_application.grafana.uuid
}

# --- Hermes Proxy Provider ---
resource "authentik_provider_proxy" "hermes" {
  name               = "Hermes"
  internal_host      = "http://127.0.0.1:8787"
  external_host      = var.hermes_external_host
  mode               = "forward_single"
  authorization_flow = data.authentik_flow.default_authorization.id
  invalidation_flow  = data.authentik_flow.default_invalidation.id
}

resource "authentik_application" "hermes" {
  name        = "Hermes"
  slug        = "hermes"
  provider_id = authentik_provider_proxy.hermes.id
}

# --- Outpost Assignment ---
data "authentik_outposts" "embedded" {
  managed = "goauthentik.io/outposts/embedded"
}

# Note: We use a local-exec or similar if we want to just patch, 
# but managing the whole outpost is safer if we import it.
# For now, we'll define it and the user might need to import it if it already exists.
resource "authentik_outpost" "embedded" {
  name               = data.authentik_outposts.embedded.outposts[0].name
  type               = data.authentik_outposts.embedded.outposts[0].type
  service_connection = data.authentik_outposts.embedded.outposts[0].service_connection
  
  protocol_providers = [
    authentik_provider_proxy.hermes.id
  ]
}
