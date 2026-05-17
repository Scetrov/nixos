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
# We keep these but without imports if we want to just reconcile, 
# but they clash. For now, we'll comment out the clashy parts.
# resource "authentik_provider_oauth2" "grafana" { ... }
