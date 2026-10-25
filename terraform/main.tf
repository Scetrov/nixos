terraform {
  backend "pg" {
    # Pass via -backend-config="conn_str=..."
  }

  required_providers {
    authentik = {
      source = "goauthentik/authentik"
      # Keep the provider SDK on the deployed Authentik 2026.8 release line.
      # Server 2026.8.3 and provider 2026.8.0 share the same API contract.
      version = "2026.8.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "3.9.1"
    }
    caddy = {

      source  = "conradludgate/caddy"
      version = "0.2.8"
    }
    grafana = {
      source  = "grafana/grafana"
      version = "4.50.0"
    }
    garage = {
      source  = "xenOs76/garage"
      version = "0.1.1"
    }
  }
}
provider "authentik" {
  url   = "https://identity.net.scetrov.live"
  token = var.authentik_token
}

provider "caddy" {
  host = "http://10.229.10.2:2019"
}

provider "grafana" {
  url  = "https://metrics.net.scetrov.live/grafana"
  auth = var.grafana_token
}
