# One enforced hostname boundary; launcher applications are navigation only.
locals {
  artcraft_editors = {
    for editor in yamldecode(file("${path.module}/../config/artcraft.yml")).artcraft_editors :
    editor.slug => editor
  }
}

resource "authentik_provider_proxy" "artcraft" {
  name               = "ArtCraft"
  external_host      = "https://artcraft.net.scetrov.live"
  authorization_flow = data.authentik_flow.default_authorization.id
  invalidation_flow  = data.authentik_flow.default_invalidation.id
  mode               = "forward_single"
}

resource "authentik_application" "artcraft" {
  name               = "ArtCraft shared access"
  slug               = "artcraft"
  protocol_provider  = authentik_provider_proxy.artcraft.id
  policy_engine_mode = "all"
  meta_hide          = true
  meta_launch_url    = "blank://blank"
}

# Operator confirmed All Applications on 2026-10-24; no membership changes.
resource "authentik_policy_binding" "artcraft_access" {
  target  = authentik_application.artcraft.uuid
  group   = authentik_group.all_applications.id
  order   = 0
  enabled = true
}

resource "authentik_application" "artcraft_editor" {
  for_each = local.artcraft_editors

  name               = each.value.name
  slug               = each.key
  policy_engine_mode = "all"
  meta_launch_url    = "https://artcraft.net.scetrov.live/${each.key}/"
  meta_icon          = "/static/dist/branding/${each.key}-${substr(each.value.icon_sha256, 0, 12)}.png"
  meta_publisher     = "Storytold"
}

resource "authentik_policy_binding" "artcraft_editor_access" {
  for_each = local.artcraft_editors

  target  = authentik_application.artcraft_editor[each.key].uuid
  group   = authentik_group.all_applications.id
  order   = 0
  enabled = true
}
