provider "garage" {
  endpoint = "https://garage-admin.net.scetrov.live"
  token    = var.garage_authentik_token
}

resource "garage_bucket" "minecraft" {
  count        = var.garage_resources_enabled ? 1 : 0
  global_alias = "minecraft"

  lifecycle {
    prevent_destroy = true
  }
}

resource "garage_key" "minecraft" {
  count               = var.garage_resources_enabled ? 1 : 0
  name                = "minecraft-backup"
  never_expires       = true
  allow_create_bucket = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "garage_bucket_permission" "minecraft" {
  count         = var.garage_resources_enabled ? 1 : 0
  bucket_id     = garage_bucket.minecraft[0].id
  access_key_id = garage_key.minecraft[0].access_key_id
  read          = true
  write         = true
  owner         = false

  lifecycle {
    prevent_destroy = true
  }
}

output "garage_minecraft_access_key_id" {
  value     = var.garage_resources_enabled ? garage_key.minecraft[0].access_key_id : ""
  sensitive = true
}

output "garage_minecraft_secret_access_key" {
  value     = var.garage_resources_enabled ? garage_key.minecraft[0].secret_access_key : ""
  sensitive = true
}
