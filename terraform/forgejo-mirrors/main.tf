terraform {
  backend "pg" {
    schema_name = "forgejo_mirrors"
  }
  required_providers {
    forgejo = {
      source  = "svalabs/forgejo"
      version = "1.6.1"
    }
  }
}

variable "forgejo_host" {
  type    = string
  default = "https://source.net.scetrov.live"
}
variable "forgejo_api_token" {
  type      = string
  sensitive = true
}
variable "mirror_password" {
  type      = string
  sensitive = true
}
variable "human_owner" {
  type    = string
  default = "scetrov"
}

provider "forgejo" {
  host      = var.forgejo_host
  api_token = var.forgejo_api_token
}

resource "forgejo_user" "mirrors" {
  login                     = "forgejo-mirrors"
  email                     = "forgejo-mirrors@source.net.scetrov.live"
  password                  = var.mirror_password
  full_name                 = "GitHub mirror discovery"
  description               = "Managed outbound discovery; non-admin machine identity, not interactive human access."
  admin                     = false
  active                    = true
  restricted                = true
  visibility                = "private"
  allow_create_organization = false
  allow_git_hook            = false
  allow_import_local        = false
  must_change_password      = false
  deactivate_on_destroy     = true
  lifecycle { prevent_destroy = true }
}

resource "forgejo_organization" "sources" {
  for_each    = toset(["gh-Scetrov", "gh-RichardSlater", "gh-storytold"])
  name        = each.value
  visibility  = "private"
  description = "Managed GitHub mirrors for ${trimprefix(each.value, "gh-")}; no platform metadata migration."
  lifecycle { prevent_destroy = true }
}

data "forgejo_team" "owners" {
  for_each     = forgejo_organization.sources
  organization = each.value.name
  name         = "Owners"
}
resource "forgejo_team_member" "human_owner" {
  for_each = data.forgejo_team.owners
  team_id  = each.value.id
  user     = var.human_owner
  lifecycle { prevent_destroy = true }
}
# Native /repos/migrate requires organization ownership, not merely a write
# team with can_create_org_repo. Operator approved ownership of these three
# private namespaces only; the service token has no organization-write scope.
resource "forgejo_team_member" "discovery" {
  for_each = data.forgejo_team.owners
  team_id  = each.value.id
  user     = forgejo_user.mirrors.login
}

output "namespace_ids" {
  value = { for name, org in forgejo_organization.sources : name => org.id }
}
output "owner_team_ids" {
  value = { for name, team in data.forgejo_team.owners : name => team.id }
}
