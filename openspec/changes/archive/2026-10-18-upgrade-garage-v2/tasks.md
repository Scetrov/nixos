## 1. Package selection

- [x] 1.1 Set `services.garage.package` to `pkgs.garage_2` in `garage.nix`
- [x] 1.2 Assert package version `2.4.1` in the existing Garage evaluation without weakening its current checks
- [x] 1.3 Run the Garage evaluation and make the smallest compatible adjustment only if 2.4.1 rejects an existing setting or layout command

## 2. Deployment

- [x] 2.1 Deploy the Garage package change to Habiki through the existing targeted NixOS path and confirm the service is active
