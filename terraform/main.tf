terraform {
  backend "pg" {
    # Pass via -backend-config="conn_str=..."
  }

  required_providers {
    authentik = {
      source = "goauthentik/authentik"
      # Match the deployed Authentik 2026.5.x API. Newer SDKs require pbm_uuid.
      # 2026.5.2 released 2026-10-02; deferred under the seven-day update policy.
      version = "2026.5.1"
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
      version = "4.46.0"
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
