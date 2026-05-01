{ pkgs, ... }:

{
  systemd.tmpfiles.rules = [
    "d /var/lib/oncall 0750 root root - -"
  ];

  systemd.services.oncall-bootstrap = {
    description = "Prepare Grafana OnCall runtime environment";
    wantedBy = [ "multi-user.target" ];
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
      ${pkgs.coreutils}/bin/install -d -m 0750 /var/lib/oncall
      if [ ! -f /var/lib/oncall/oncall.env ]; then
        secret="$(${pkgs.openssl}/bin/openssl rand -hex 32)"
        umask 077
        ${pkgs.coreutils}/bin/cat > /var/lib/oncall/oncall.env <<EOF
DATABASE_TYPE=sqlite3
BROKER_TYPE=redis
BASE_URL=https://metrics.net.scetrov.live/oncall
SECRET_KEY=$secret
FEATURE_PROMETHEUS_EXPORTER_ENABLED=False
PROMETHEUS_EXPORTER_SECRET=
REDIS_URI=redis://oncall-redis:6379/0
DJANGO_SETTINGS_MODULE=settings.hobby
CELERY_WORKER_QUEUE=default,critical,long,slack,telegram,mattermost,webhook,retry,celery,grafana
CELERY_WORKER_CONCURRENCY=1
CELERY_WORKER_MAX_TASKS_PER_CHILD=100
CELERY_WORKER_SHUTDOWN_INTERVAL=65m
CELERY_WORKER_BEAT_ENABLED=True
GRAFANA_API_URL=http://host.containers.internal:3000
EOF
      fi
    '';
  };

  systemd.services.oncall-migrate = {
    description = "Run Grafana OnCall database migrations";
    after = [
      "oncall-bootstrap.service"
      "podman-oncall-redis.service"
    ];
    requires = [
      "oncall-bootstrap.service"
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
      ExecStart = ''
        ${pkgs.podman}/bin/podman run --rm \
          --network=podman \
          --env-file=/var/lib/oncall/oncall.env \
          -v /var/lib/oncall:/var/lib/oncall:U \
          docker.io/grafana/oncall:latest \
          sh -ceu 'python manage.py migrate --noinput && python manage.py collectstatic --noinput'
      '';
    };
  };

  systemd.services.podman-oncall-engine = {
    after = [ "oncall-migrate.service" ];
    requires = [ "oncall-migrate.service" ];
  };

  systemd.services.podman-oncall-celery = {
    after = [ "oncall-migrate.service" ];
    requires = [ "oncall-migrate.service" ];
  };

  virtualisation.oci-containers.containers = {
    oncall-redis = {
      image = "docker.io/redis:7-alpine";
      autoStart = true;
      extraOptions = [ "--network=podman" ];
    };

    oncall-engine = {
      image = "docker.io/grafana/oncall:latest";
      autoStart = true;
      cmd = [ "sh" "-ceu" "uwsgi --ini uwsgi.ini" ];
      environmentFiles = [ "/var/lib/oncall/oncall.env" ];
      extraOptions = [ "--network=podman" ];
      ports = [ "127.0.0.1:18080:8080" ];
      volumes = [ "/var/lib/oncall:/var/lib/oncall:U" ];
    };

    oncall-celery = {
      image = "docker.io/grafana/oncall:latest";
      autoStart = true;
      cmd = [ "sh" "-ceu" "./celery_with_exporter.sh" ];
      environmentFiles = [ "/var/lib/oncall/oncall.env" ];
      extraOptions = [ "--network=podman" ];
      volumes = [ "/var/lib/oncall:/var/lib/oncall:U" ];
    };
  };
}