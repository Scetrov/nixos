{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.scetrov.services.authentik;
  tlsDir = "/var/lib/authentik/postgresql-tls";
  hba = pkgs.writeText "shared-postgresql-pg_hba.conf" (
    if cfg.postgresqlTLSOnly then
      builtins.readFile ./postgresql-pg_hba.conf
    else
      builtins.replaceStrings [ "hostnossl all all all reject" ] [ "hostnossl all all all scram-sha-256" ]
        (builtins.readFile ./postgresql-pg_hba.conf)
  );
  prepare = pkgs.writeShellScript "postgresql-tls-prepare" ''
    set -euo pipefail
    ${pkgs.python3}/bin/python3 ${./postgresql-tls-prepare.py} \
      --source /var/lib/acme/scetrov.live \
      --target ${tlsDir} \
      --ca ${config.security.pki.caBundle} \
      --openssl ${pkgs.openssl}/bin/openssl
    # The service also runs before initial container startup; only signal an
    # already-running container. Reload failure is visible, never a downgrade.
    if [ "$(${pkgs.podman}/bin/podman inspect --format '{{.State.Running}}' authentik-postgresql 2>/dev/null || true)" = true ]; then
      ${pkgs.podman}/bin/podman kill --signal HUP authentik-postgresql
    fi
  '';
in
{
  options.scetrov.services.authentik.postgresqlTLSOnly = lib.mkOption {
    type = lib.types.bool;
    default = true;
    description = ''
      Reject plaintext TCP to the shared PostgreSQL instance. Set false ONLY
      during the planned cutover window, then restore true after verifying all
      clients; never use this as automatic rollback. See docs/postgresql-tls.md.
    '';
  };

  config = lib.mkIf cfg.enable {
    security.acme.certs."scetrov.live".reloadServices = [ "postgresql-tls-prepare.service" ];

    systemd.services.postgresql-tls-prepare = {
      description = "Validate and publish shared PostgreSQL TLS certificate pair";
      after = [ "acme-scetrov.live.service" ];
      requires = [ "acme-scetrov.live.service" ];
      before = [ "podman-authentik-postgresql.service" ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = prepare;
        # Renewal must reload, not restart this required dependency (which
        # could stop the database). systemd serializes start/reload jobs.
        ExecReload = prepare;
        UMask = "0077";
        # Podman inspect/signal needs its normal /var and /run runtime state.
        ProtectSystem = "full";
        ProtectHome = true;
        PrivateTmp = true;
        NoNewPrivileges = true;
      };
    };

    systemd.services.podman-authentik-postgresql = {
      after = [ "postgresql-tls-prepare.service" ];
      requires = [ "postgresql-tls-prepare.service" ];
    };

    # Command-line settings apply to populated clusters too; do not depend on
    # docker-entrypoint-initdb.d or overwrite files in the existing data volume.
    virtualisation.oci-containers.containers.authentik-postgresql = {
      cmd = [
        "postgres"
        "-c"
        "ssl=on"
        "-c"
        "ssl_cert_file=/run/postgresql-tls/current/fullchain.pem"
        "-c"
        "ssl_key_file=/run/postgresql-tls/current/key.pem"
        "-c"
        "hba_file=/etc/postgresql/pg_hba.conf"
      ];
      volumes = [
        "${tlsDir}:/run/postgresql-tls:ro"
        "${hba}:/etc/postgresql/pg_hba.conf:ro"
      ];
    };
  };
}
