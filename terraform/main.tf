terraform {
  backend "pg" {
    # Pass via -backend-config="conn_str=..."
  }

  required_providers {
    authentik = {
      source = "goauthentik/authentik"
      version = "2024.12.0"
    }
    caddy = {
      source  = "conradludgate/caddy"
      version = "0.2.8"
    }
  }
}
\provider "authentik" {
  url   = "https://identity.net.scetrov.live"
  token = var.authentik_token
}

provider "caddy" {
  host = "http://10.229.10.2:2019"
}
