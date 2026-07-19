terraform {
  backend "pg" {
    # Pass via -backend-config="conn_str=..."
  }

  required_providers {
    authentik = {
      source  = "goauthentik/authentik"
      version = "2026.5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
    caddy = {

      source  = "conradludgate/caddy"
      version = "0.2.8"
    }
    grafana = {
      source  = "grafana/grafana"
      version = "3.18.2"
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
