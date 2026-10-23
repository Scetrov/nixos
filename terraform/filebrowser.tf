# Shared with host/application reconciliation; UUIDs, never mutable login names,
# are the enrollment authority. No default profile scope may override this claim.
locals {
  filebrowser_enrollments = jsondecode(file("${path.module}/../src/filebrowser-enrollments.json"))
  filebrowser_directory_records = {
    for enrollment in local.filebrowser_enrollments : enrollment.identity_uuid => enrollment
  }
  filebrowser_usernames = {
    for enrollment in local.filebrowser_enrollments :
    enrollment.identity_uuid => enrollment.unix_username
  }
}

resource "authentik_property_mapping_provider_scope" "filebrowser_profile" {
  name       = "Filebrowser enrolled username"
  scope_name = "profile"
  expression = <<-EOT
    usernames = ${jsonencode(local.filebrowser_usernames)}
    username = usernames.get(str(request.user.uuid))
    if username is None:
        raise Exception("Identity is not enrolled for Filebrowser")
    return {"preferred_username": username}
  EOT

  lifecycle {
    precondition {
      condition = (
        length(local.filebrowser_enrollments) == length(toset(values(local.filebrowser_usernames))) &&
        alltrue([
          for id, username in local.filebrowser_usernames :
          can(regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", id)) &&
          can(regex("^[a-z_][a-z0-9_-]{0,31}$", username))
        ])
      )
      error_message = "Filebrowser enrollment requires unique immutable UUIDs and unique exact lowercase Unix usernames."
    }
  }
}

# A PK is only a directory locator. Verify the immutable UUID before its numeric
# ID can affect group membership; renamed/reused usernames cannot inherit access.
data "authentik_user" "filebrowser" {
  for_each = local.filebrowser_directory_records
  pk       = each.value.authentik_pk

  lifecycle {
    postcondition {
      condition     = self.uuid == each.key
      error_message = "Filebrowser directory locator no longer matches its reviewed immutable identity."
    }
  }
}

resource "authentik_group" "filebrowser_users" {
  name  = "Filebrowser Documents"
  users = [for user in data.authentik_user.filebrowser : user.id]
}

resource "authentik_policy_expression" "filebrowser_enrolled" {
  name       = "Filebrowser immutable enrollment"
  expression = "return str(request.user.uuid) in ${jsonencode(keys(local.filebrowser_usernames))}"
}

resource "random_id" "filebrowser_client_id" {
  byte_length = 20
}

resource "random_password" "filebrowser_client_secret" {
  length  = 40
  special = false
}

resource "authentik_provider_oauth2" "filebrowser" {
  name               = "Filebrowser Quantum"
  client_id          = random_id.filebrowser_client_id.hex
  client_secret      = random_password.filebrowser_client_secret.result
  client_type        = "confidential"
  signing_key        = data.authentik_certificate_key_pair.default.id
  authorization_flow = data.authentik_flow.default_authorization.id
  invalidation_flow  = data.authentik_flow.default_invalidation.id
  grant_types        = ["authorization_code", "refresh_token"]
  allowed_redirect_uris = [{
    url               = "https://files.net.scetrov.live/api/auth/oidc/callback"
    matching_mode     = "strict"
    redirect_uri_type = "authorization"
  }]
  property_mappings = [
    data.authentik_property_mapping_provider_scope.openid.id,
    authentik_property_mapping_provider_scope.filebrowser_profile.id,
    data.authentik_property_mapping_provider_scope.email.id,
  ]
}

resource "authentik_application" "filebrowser" {
  name               = "Filebrowser Quantum"
  slug               = "filebrowser"
  protocol_provider  = authentik_provider_oauth2.filebrowser.id
  policy_engine_mode = "all"
  meta_launch_url    = "https://files.net.scetrov.live"
}

resource "authentik_policy_binding" "filebrowser_group" {
  target  = authentik_application.filebrowser.uuid
  group   = authentik_group.filebrowser_users.id
  order   = 0
  enabled = true
}

resource "authentik_policy_binding" "filebrowser_enrollment" {
  target  = authentik_application.filebrowser.uuid
  policy  = authentik_policy_expression.filebrowser_enrolled.id
  order   = 1
  enabled = true
}

# Non-interactive administration stays in Authentik, separate from ordinary
# OIDC users. Only this provider emits the private machine-role claims.
resource "authentik_user" "filebrowser_reconciler" {
  username  = "filebrowser-reconciler"
  name      = "Filebrowser scope reconciler"
  path      = "service-accounts"
  type      = "service_account"
  is_active = true
}

data "authentik_user" "filebrowser_reconciler" {
  pk = tonumber(authentik_user.filebrowser_reconciler.id)
}

resource "authentik_token" "filebrowser_reconciler" {
  identifier   = "filebrowser-reconciler"
  user         = authentik_user.filebrowser_reconciler.id
  intent       = "app_password"
  expiring     = false
  retrieve_key = true
  description  = "Vault-delivered Filebrowser reconciliation credential"
}

resource "authentik_property_mapping_provider_scope" "filebrowser_machine" {
  name       = "Filebrowser private machine claims"
  scope_name = "profile"
  expression = <<-EOT
    if str(request.user.uuid) != "${data.authentik_user.filebrowser_reconciler.uuid}":
        raise Exception("Not the Filebrowser reconciliation identity")
    return {"filebrowser_machine_username": "filebrowser-reconciler", "filebrowser_machine_groups": ["filebrowser-reconciler"]}
  EOT
}

resource "random_id" "filebrowser_machine_client_id" {
  byte_length = 20
}

resource "random_password" "filebrowser_machine_client_secret" {
  length  = 40
  special = false
}

resource "authentik_provider_oauth2" "filebrowser_reconciler" {
  name                  = "Filebrowser reconciler"
  client_id             = random_id.filebrowser_machine_client_id.hex
  client_secret         = random_password.filebrowser_machine_client_secret.result
  client_type           = "confidential"
  signing_key           = data.authentik_certificate_key_pair.default.id
  authorization_flow    = data.authentik_flow.default_authorization.id
  invalidation_flow     = data.authentik_flow.default_invalidation.id
  grant_types           = ["client_credentials"]
  access_token_validity = "minutes=2"
  property_mappings     = [authentik_property_mapping_provider_scope.filebrowser_machine.id]
}

resource "authentik_application" "filebrowser_reconciler" {
  name               = "Filebrowser reconciliation"
  slug               = "filebrowser-reconciler"
  protocol_provider  = authentik_provider_oauth2.filebrowser_reconciler.id
  policy_engine_mode = "all"
  meta_hide          = true
  meta_launch_url    = "blank://blank"
}

resource "authentik_policy_expression" "filebrowser_machine" {
  name       = "Filebrowser reconciler identity only"
  expression = "return str(request.user.uuid) == \"${data.authentik_user.filebrowser_reconciler.uuid}\""
}

resource "authentik_policy_binding" "filebrowser_machine" {
  target  = authentik_application.filebrowser_reconciler.uuid
  policy  = authentik_policy_expression.filebrowser_machine.id
  order   = 0
  enabled = true
}

output "filebrowser_reconciler_client_id" {
  value     = authentik_provider_oauth2.filebrowser_reconciler.client_id
  sensitive = true
}

output "filebrowser_reconciler_app_password" {
  value     = authentik_token.filebrowser_reconciler.key
  sensitive = true
}

output "filebrowser_reconciler_public_key" {
  value = data.authentik_certificate_key_pair.default.certificate_data
}

output "filebrowser_oidc_client_id" {
  value     = authentik_provider_oauth2.filebrowser.client_id
  sensitive = true
}

output "filebrowser_oidc_client_secret" {
  value     = authentik_provider_oauth2.filebrowser.client_secret
  sensitive = true
}
