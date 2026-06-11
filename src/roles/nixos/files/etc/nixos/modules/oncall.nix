{
  config,
  pkgs,
  lib,
  ...
}:

let
  stateDir = "/var/lib/oncall";
  oncallEnvFile = "${stateDir}/oncall.env";
  oncallDatabasePasswordPath = config.age.secrets.oncall_postgresql_password.path;
  oncallMigrateScript = pkgs.writeShellScript "oncall-migrate" ''
        set -euo pipefail

        deadline=$((SECONDS + 60))
        while ! ${pkgs.podman}/bin/podman exec --user postgres oncall-postgres \
          psql -v ON_ERROR_STOP=1 -U oncall -d postgres -tAc 'select 1' >/dev/null 2>&1; do
          if [ "$SECONDS" -ge "$deadline" ]; then
            echo "Timed out waiting for oncall-postgres" >&2
            exit 1
          fi
          sleep 1
        done

        db_pass=$(cat ${oncallDatabasePasswordPath})
        ${pkgs.podman}/bin/podman exec --user postgres --env DB_PASS="$db_pass" oncall-postgres \
          sh -ceu "
            psql -v ON_ERROR_STOP=1 -U oncall -d postgres -c \"ALTER ROLE oncall WITH PASSWORD '\$DB_PASS';\"
          "

        ${pkgs.podman}/bin/podman run --rm \
          --network=podman \
          --env-file=${oncallEnvFile} \
          -v ${stateDir}:${stateDir}:U \
          docker.io/grafana/oncall:latest \
          sh -ceu 'python - <<PY
    import socket
    import time

    deadline = time.monotonic() + 60
    while True:
        try:
            with socket.create_connection(("oncall-postgres", 5432), timeout=2):
                break
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(1)
    PY
          python manage.py migrate --noinput && python manage.py collectstatic --noinput'
  '';
in
{
  age.secrets.oncall_secret_key.file = /root/secrets/oncall_secret_key.age;
  age.secrets.grafana_oncall_api_key.file = /root/secrets/grafana_oncall_api_key.age;
  age.secrets.oncall_postgresql_password.file = /root/secrets/oncall_postgresql_password.age;

  systemd.tmpfiles.rules = [
    "d ${stateDir} 0750 root root - -"
  ];

  systemd.services.oncall-prepare-env = {
    description = "Prepare Grafana OnCall environment file";
    wantedBy = [ "multi-user.target" ];
    restartTriggers = [
      config.age.secrets.oncall_secret_key.file
      config.age.secrets.grafana_oncall_api_key.file
      config.age.secrets.oncall_postgresql_password.file
    ];
    before = [
      "oncall-migrate.service"
      "podman-oncall-engine.service"
      "podman-oncall-celery.service"
    ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
    };
    script = ''
            set -euo pipefail
            ${pkgs.coreutils}/bin/install -d -m 0750 ${stateDir}

            secret_key=$(cat ${config.age.secrets.oncall_secret_key.path})
            grafana_api_key=$(cat ${config.age.secrets.grafana_oncall_api_key.path})
            database_password=$(cat ${oncallDatabasePasswordPath})

            cat > ${oncallEnvFile} <<EOF
      DATABASE_TYPE=postgresql
      DATABASE_HOST=oncall-postgres
      DATABASE_PORT=5432
      DATABASE_NAME=oncall
      DATABASE_USER=oncall
      DATABASE_PASSWORD=$database_password
      BROKER_TYPE=redis
      BASE_URL=https://metrics.net.scetrov.live/oncall
      SECRET_KEY=$secret_key
      FEATURE_PROMETHEUS_EXPORTER_ENABLED=False
      PROMETHEUS_EXPORTER_SECRET=
      REDIS_URI=redis://oncall-redis:6379/0
      DJANGO_SETTINGS_MODULE=settings.hobby
      CELERY_WORKER_QUEUE=default,critical,long,slack,telegram,mattermost,webhook,retry,celery,grafana
      CELERY_WORKER_CONCURRENCY=1
      CELERY_WORKER_MAX_TASKS_PER_CHILD=100
      CELERY_WORKER_SHUTDOWN_INTERVAL=65m
      CELERY_WORKER_BEAT_ENABLED=True
      GRAFANA_API_URL=http://host.containers.internal:3005
      GRAFANA_API_KEY=$grafana_api_key
      EOF
            chmod 0600 ${oncallEnvFile}
    '';
  };

  systemd.services.oncall-migrate = {
    description = "Run Grafana OnCall database migrations";
    after = [
      "oncall-prepare-env.service"
      "podman-oncall-postgres.service"
      "podman-oncall-redis.service"
    ];
    requires = [
      "oncall-prepare-env.service"
      "podman-oncall-postgres.service"
      "podman-oncall-redis.service"
    ];
    before = [
      "podman-oncall-engine.service"
      "podman-oncall-celery.service"
    ];
    wantedBy = [ "multi-user.target" ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      ExecStart = oncallMigrateScript;
    };
    restartTriggers = [ config.age.secrets.oncall_postgresql_password.file ];
  };

  systemd.services.podman-oncall-engine = {
    after = [
      "oncall-migrate.service"
      "oncall-prepare-env.service"
      "podman-oncall-postgres.service"
    ];
    requires = [
      "oncall-migrate.service"
      "oncall-prepare-env.service"
      "podman-oncall-postgres.service"
    ];
  };

  systemd.services.podman-oncall-celery = {
    after = [
      "oncall-migrate.service"
      "oncall-prepare-env.service"
      "podman-oncall-postgres.service"
    ];
    requires = [
      "oncall-migrate.service"
      "oncall-prepare-env.service"
      "podman-oncall-postgres.service"
    ];
  };

  virtualisation.oci-containers.containers = {
    oncall-postgres = {
      image = "docker.io/postgres:16-alpine";
      autoStart = true;
      extraOptions = [ "--network=podman" ];
      environment = {
        POSTGRES_USER = "oncall";
        POSTGRES_DB = "oncall";
        POSTGRES_PASSWORD_FILE = "${oncallDatabasePasswordPath}";
      };
      volumes = [
        "oncall-postgres-data:/var/lib/postgresql/data"
        "${oncallDatabasePasswordPath}:${oncallDatabasePasswordPath}:ro"
      ];
    };

    oncall-redis = {
      image = "docker.io/redis:7-alpine";
      autoStart = true;
      extraOptions = [ "--network=podman" ];
    };

    oncall-engine = {
      image = "docker.io/grafana/oncall:latest";
      autoStart = true;
      cmd = [
        "sh"
        "-ceu"
        "uwsgi --ini uwsgi.ini"
      ];
      environmentFiles = [ oncallEnvFile ];
      extraOptions = [ "--network=podman" ];
      ports = [ "127.0.0.1:18080:8080" ];
      volumes = [ "${stateDir}:${stateDir}:U" ];
      dependsOn = [
        "oncall-postgres"
        "oncall-redis"
      ];
    };

    oncall-celery = {
      image = "docker.io/grafana/oncall:latest";
      autoStart = true;
      cmd = [
        "sh"
        "-ceu"
        "./celery_with_exporter.sh"
      ];
      environmentFiles = [ oncallEnvFile ];
      extraOptions = [ "--network=podman" ];
      volumes = [ "${stateDir}:${stateDir}:U" ];
      dependsOn = [
        "oncall-postgres"
        "oncall-redis"
      ];
    };
  };
}
