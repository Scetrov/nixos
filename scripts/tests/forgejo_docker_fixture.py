"""Dedicated disposable rootless Docker; never use an ambient Docker socket."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


class RootlessDockerFixture:
    def __init__(self, root, binary, env):
        self.root = Path(root)
        self.binary = str(Path(binary).absolute())
        self.daemon = str(Path(self.binary).with_name("dockerd-rootless"))
        self.env = env.copy()
        self.env.pop("DOCKER_HOST", None)
        self.env["DOCKER_CONFIG"] = str(self.root / "docker-client")
        self.socket = self.root / "podman.sock"  # Existing fixture API socket path.
        self.client = [self.binary, "--host", "unix://" + str(self.socket)]
        self.unit = "forgejo-docker-fixture-" + self.root.name.rsplit("-", 1)[1]
        self.started = False

    def start(self):
        config = self.root / "docker-daemon.json"
        config.write_text(json.dumps({
            "hosts": ["unix://" + str(self.socket)],
            "data-root": str(self.root / "storage"),
            "exec-root": str(self.root / "run"),
            "pidfile": str(self.root / "docker.pid"),
            "exec-opts": ["native.cgroupdriver=systemd"],
        }))
        settings = {
            "DBUS_SESSION_BUS_ADDRESS": self.env["DBUS_SESSION_BUS_ADDRESS"],
            "DOCKERD_ROOTLESS_ROOTLESSKIT_STATE_DIR": str(self.root / "rootlesskit"),
            "DOCKERD_ROOTLESS_ROOTLESSKIT_NET": "slirp4netns",
            # FIXTURE ONLY: reach its disposable loopback HTTP Forgejo server.
            # Production uses private LAN HTTPS, with host loopback denied.
            "DOCKERD_ROOTLESS_ROOTLESSKIT_DISABLE_HOST_LOOPBACK": "false",
            "HOME": str(self.root),
            "PATH": "/run/wrappers/bin:/run/current-system/sw/bin",
        }
        cmd = ["systemd-run", "--user", "--unit", self.unit, "--collect",
               "--property=Delegate=yes", "--property=KillMode=mixed"]
        cmd += ["--setenv=" + key + "=" + value for key, value in settings.items()]
        result = subprocess.run(cmd + [self.daemon, "--config-file=" + str(config)],
                                env=self.env, capture_output=True, timeout=15)
        if result.returncode:
            raise RuntimeError("Disposable rootless Docker unit failed to start")
        self.started = True
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            result = subprocess.run(self.client + ["info", "--format", "{{json .}}"],
                                    env=self.env, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                info = json.loads(result.stdout)
                if ("name=rootless" not in info["SecurityOptions"]
                        or info["DockerRootDir"] != str(self.root / "storage")
                        or info["CgroupDriver"] != "systemd"
                        or info["CgroupVersion"] != "2"):
                    raise RuntimeError("Refusing Docker without isolated rootless cgroup-v2 storage")
                return
            time.sleep(0.2)
        raise RuntimeError("Disposable rootless Docker readiness timed out")

    def close(self):
        if self.started:
            result = subprocess.run(["systemctl", "--user", "stop", self.unit],
                                    env=self.env, capture_output=True, timeout=60)
            if result.returncode:
                raise RuntimeError("Disposable rootless Docker stop failed")
        # The stopped rootless namespace releases its mounts. Use the same host
        # subordinate ID mapping only to remove these exact disposable directories.
        script = """
import pathlib, shutil, sys
root = pathlib.Path(sys.argv[1])
for name in ('storage', 'run', 'rootlesskit'):
    path = root / name
    if path.is_symlink():
        raise RuntimeError('Refusing symlinked Docker fixture storage')
    if path.exists():
        shutil.rmtree(path)
"""
        result = subprocess.run(["podman", "unshare", sys.executable, "-c", script, str(self.root)],
                                env=self.env, capture_output=True, timeout=60)
        if result.returncode:
            raise RuntimeError("Disposable rootless Docker storage cleanup failed")
