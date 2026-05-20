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

resource "authentik_property_mapping_provider_scope" "groups" {
  name       = "groups"
  scope_name = "groups"
  expression = "return {'groups': [group.name for group in request.user.ak_groups]}"
}

# --- Flows ---

data "authentik_property_mapping_provider_scope" "entitlements" {
  managed = "goauthentik.io/providers/oauth2/scope-entitlements"
}

# --- Flows ---
data "authentik_flow" "default_authentication" {
  slug = "default-authentication-flow"
}

data "authentik_flow" "default_authorization" {
  slug = "default-provider-authorization-implicit-consent"
}

data "authentik_flow" "default_invalidation" {
  slug = "default-provider-invalidation-flow"
}

# --- Random Credentials ---
resource "random_id" "grafana_client_id" {
  byte_length = 20
}

resource "random_password" "grafana_client_secret" {
  length  = 40
  special = false
}

resource "random_id" "dtrack_client_id" {
  byte_length = 20
}

resource "random_password" "dtrack_client_secret" {
  length  = 40
  special = false
}

# --- Certificates ---
data "authentik_certificate_key_pair" "default" {
  name = "authentik Self-signed Certificate"
}

# --- Grafana OAuth2 Provider ---
resource "authentik_provider_oauth2" "grafana" {
  name          = "Grafana"
  client_id     = random_id.grafana_client_id.hex
  client_secret = random_password.grafana_client_secret.result
  signing_key   = data.authentik_certificate_key_pair.default.id
  
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
    authentik_property_mapping_provider_scope.groups.id,
    data.authentik_property_mapping_provider_scope.entitlements.id,
  ]
}

resource "authentik_application" "grafana" {
  name              = "Grafana"
  slug              = "grafana"
  protocol_provider = authentik_provider_oauth2.grafana.id
  meta_icon         = "https://raw.githubusercontent.com/grafana/grafana/main/public/img/grafana_icon.svg"
}

resource "authentik_application_entitlement" "grafana_admins" {
  name        = "Grafana Admins"
  application = authentik_application.grafana.uuid
}

resource "authentik_policy_binding" "grafana_admins_binding" {
  target = authentik_application_entitlement.grafana_admins.id
  group  = data.authentik_group.admins.id
  order  = 0
}

resource "authentik_application_entitlement" "grafana_editors" {
  name        = "Grafana Editors"
  application = authentik_application.grafana.uuid
}

resource "authentik_policy_binding" "grafana_editors_binding" {
  target = authentik_application_entitlement.grafana_editors.id
  group  = authentik_group.all_applications.id
  order  = 0
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
  meta_icon         = "https://raw.githubusercontent.com/scetrov/hermes/main/public/img/hermes_icon.svg"
}

# --- Dependency Track OIDC Provider ---
resource "authentik_provider_oauth2" "dependency_track" {
  name          = "Dependency Track"
  client_id     = random_id.dtrack_client_id.hex
  client_secret = random_password.dtrack_client_secret.result
  client_type   = "public"
  signing_key   = data.authentik_certificate_key_pair.default.id

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
    authentik_property_mapping_provider_scope.groups.id,
  ]
}

resource "authentik_application" "dependency_track" {
  name              = "Dependency Track"
  slug              = "dependency-track"
  protocol_provider = authentik_provider_oauth2.dependency_track.id
}

data "authentik_group" "admins" {
  name = "authentik Admins"
}

data "authentik_user" "scetrov" {
  username = "scetrov"
}

resource "authentik_group" "all_applications" {
  name = "All Applications"
  users = [
    data.authentik_user.scetrov.id
  ]
}

resource "authentik_policy_binding" "dependency_track_access" {
  target = authentik_application.dependency_track.uuid
  group  = authentik_group.all_applications.id
  order  = 0
}

# --- Metrics Proxy Provider ---
resource "authentik_provider_proxy" "metrics" {
  name               = "Metrics"
  external_host      = "https://metrics.net.scetrov.live"
  authorization_flow = data.authentik_flow.default_authorization.id
  invalidation_flow  = data.authentik_flow.default_invalidation.id
  mode               = "forward_single"
}

resource "authentik_application" "metrics" {
  name              = "Metrics"
  slug              = "metrics"
  protocol_provider = authentik_provider_proxy.metrics.id
  meta_launch_url   = "blank://blank"
}

# --- Branding ---
resource "authentik_brand" "default" {
  domain         = "."
  default        = true
  branding_title = "scetrov.live Identity"
  
  branding_logo    = "/static/dist/branding/logo.png"
  branding_favicon = "/static/dist/branding/logo.png"
  
  branding_default_flow_background = "/static/dist/branding/background.jpg"
  
  branding_custom_css = <<-EOT
    :root {
        --ak-flow-background: url('/static/dist/branding/background.jpg') !important;
    }
    .pf-c-background-image {
        --pf-c-background-image--BackgroundImage: url('/static/dist/branding/background.jpg') !important;
        --pf-c-background-image--Filter: none !important;
    }
    .pf-c-login__main {
        background-color: rgba(0, 0, 0, 0.4) !important;
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        border-radius: 12px;
        color: white !important;
    }
    .pf-c-title {
        color: white !important;
    }
    .pf-c-form__label-text {
        color: #eee !important;
    }
    /* Ensure the background image covers the whole screen */
    .pf-c-background-image::before {
        background-image: url('/static/dist/branding/background.jpg') !important;
    }
  EOT

  flow_authentication = data.authentik_flow.default_authentication.id
}

# --- Outpost ---
# This manages the embedded outpost that provides forward_auth for Caddy.
resource "authentik_outpost" "proxy" {
  name = "authentik Embedded Outpost"
  type = "proxy"
  
  protocol_providers = [
    authentik_provider_proxy.hermes.id,
    authentik_provider_proxy.metrics.id
  ]
  
  config = jsonencode({
    authentik_host = "https://identity.net.scetrov.live"
  })
}
