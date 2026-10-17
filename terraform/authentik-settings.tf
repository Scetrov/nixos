# Adopt the existing singleton rather than applying provider defaults blindly.
# Baseline read from the live API before promotion: no existing footer links;
# core_default_app_access=true is deliberately retained, not reset to false.
import {
  to = authentik_system_settings.default
  id = "system_settings"
}

resource "authentik_system_settings" "default" {
  avatars                      = "gravatar,initials"
  default_token_duration       = "minutes=30"
  default_token_length         = 60
  default_user_change_email    = false
  default_user_change_name     = true
  default_user_change_username = false
  event_retention              = "days=365"
  gdpr_compliance              = true
  impersonation                = true
  pagination_default_page_size = 20
  pagination_max_page_size     = 100
  reputation_lower_limit       = -5
  reputation_upper_limit       = 5
  flags = jsonencode({
    core_default_app_access                = true
    enterprise_audit_include_expanded_diff = false
    flows_continuous_login                 = false
    flows_refresh_others                   = false
  })

  # Native tenant-wide footer: visible even when WebAuthn is cancelled or times
  # out. Stay in the same plan so its validated original destination survives.
  footer_links = [{
    name = "Use username/password instead"
    href = "/if/flow/passkey-first-candidate/?use_password=1"
  }]
}
