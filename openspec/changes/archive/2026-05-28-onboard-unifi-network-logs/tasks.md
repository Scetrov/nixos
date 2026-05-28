# Onboard UniFi Network Logs

## 1. Receiver and parsing pipeline

- [x] 1.1 Add a dedicated NixOS module for the UniFi Vector syslog receiver, including the UDP `5514` listener and source restriction to `10.229.0.1`
- [x] 1.2 Configure the Vector pipeline to retain only firewall, threat or IDS, and warning-or-higher UniFi events and forward them to local Loki with stable `service` and `host` labels
- [x] 1.3 Enable the UniFi network log receiver on `habiki` without changing the existing Alloy-based local log path

## 2. Grafana portal updates

- [x] 2.1 Add a declarative Grafana dashboard JSON for UniFi network log visibility under `terraform/dashboards/`
- [x] 2.2 Register the UniFi dashboard in `terraform/grafana.tf` and add it to the operations service catalog

## 3. Documentation and validation

- [x] 3.1 Document the UniFi Network Application remote logging configuration and post-deploy validation workflow
- [x] 3.2 Run local validation for the changed OpenSpec, Nix, and Terraform artifacts and confirm the new files are staged for commit
