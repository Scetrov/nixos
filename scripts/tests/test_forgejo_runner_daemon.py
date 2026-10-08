"""Opt-in real daemon-mode job fixture; no live credentials or services.

Set FORGEJO_TEST_BINARY, FORGEJO_RUNNER_TEST_BINARY and FORGEJO_JOB_TEST_IMAGE
(fully qualified digest-pinned). Requires registry access for the isolated image pull.
Uses disposable SQLite,
loopback-only Forgejo, separate rootless Podman graph/run storage, and cleans up
only that fixture runtime. This tests daemon settings, NOT `runner exec` flags.
"""
import base64
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
import urllib.request

from scripts.tests.forgejo_docker_fixture import RootlessDockerFixture

MODULE = Path(__file__).resolve().parents[2] / "src/roles/nixos/files/etc/nixos/modules/forgejo-runner-register.py"
spec = importlib.util.spec_from_file_location("registration", MODULE)
registration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registration)
ENABLED = all(os.environ.get(key) for key in (
    "FORGEJO_TEST_BINARY", "FORGEJO_RUNNER_TEST_BINARY", "FORGEJO_JOB_TEST_IMAGE"))


def cleanup_runtime(root, runtime, env):
    """Dispose only the exact temporary graph, including subordinate-owned files.

    Do not use system reset: it also removes machines outside graph storage.
    A failed cleanup is a test failure, not a silently leaked fixture.
    """
    root = Path(root)
    expected = ["podman", "--cgroup-manager=systemd", "--root", str(root / "storage"),
                "--runroot", str(root / "run")]
    if (runtime != expected or root.is_symlink() or not root.is_dir()
            or root.parent.resolve() != Path(tempfile.gettempdir()).resolve()
            or not root.name.startswith("forgejo-daemon-fixture-")):
        raise ValueError("Refusing cleanup outside disposable fixture storage")
    # Removing containers releases their rootless networks; network definitions
    # live in this graph and are deleted below. `network rm --all` is unsupported.
    for args in (["rm", "--all", "--force"], ["rmi", "--all", "--force"]):
        result = subprocess.run([*runtime, *args], env=env, capture_output=True, timeout=60)
        if result.returncode:
            raise RuntimeError("Disposable Podman cleanup failed: " + args[0])
    # An interrupted pull can leave subordinate-owned partial layers. Overlay's
    # namespace bind mount must be released inside the same rootless namespace
    # before deleting the graph. Never follow symlinked graph/run directories.
    script = """
import os, pathlib, shutil, subprocess, sys
root = pathlib.Path(sys.argv[1])
for name in ('storage', 'run'):
    path = root / name
    if path.is_symlink():
        raise RuntimeError('Refusing symlinked fixture storage')
overlay = root / 'storage' / 'overlay'
# ismount() misses same-filesystem bind mounts. Use the namespace's mount table.
mounts = pathlib.Path('/proc/self/mountinfo').read_text().splitlines()
if any(line.split()[4] == str(overlay) for line in mounts):
    subprocess.run(['umount', '--', str(overlay)], check=True)
for name in ('storage', 'run'):
    path = root / name
    if path.exists():
        shutil.rmtree(path)
"""
    result = subprocess.run([*runtime, "unshare", sys.executable, "-c", script, str(root)],
                            env=env, capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError("Disposable Podman image-storage cleanup failed")


@unittest.skipUnless(ENABLED, "Set Forgejo/runner binary and pinned image fixture variables")
class DaemonJobTests(unittest.TestCase):
    def test_daemon_enforces_job_limits_and_socket_mount_boundary(self):
        self.assertTrue(shutil.which("podman"), "Rootless Podman is required")
        image = os.environ["FORGEJO_JOB_TEST_IMAGE"]
        self.assertRegex(image, r"^[a-z0-9.-]+/[a-z0-9_./-]+@sha256:[0-9a-f]{64}$")
        acceptance = os.environ.get("FORGEJO_ACCEPTANCE_TEST") == "1"
        forgejo = os.environ["FORGEJO_TEST_BINARY"]
        runner = os.environ["FORGEJO_RUNNER_TEST_BINARY"]
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        with tempfile.TemporaryDirectory(prefix="forgejo-daemon-fixture-") as directory:
            root = Path(directory)
            os.chmod(root, 0o700)
            control, workspace = root / "control", root / "workspace"
            control.mkdir(mode=0o700)
            workspace.mkdir(mode=0o700)
            api_socket = root / "podman.sock"
            runtime = ["podman", "--cgroup-manager=systemd", "--root", str(root / "storage"), "--runroot", str(root / "run")]
            runtime_env = os.environ.copy()
            runtime_env["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=" + os.environ["XDG_RUNTIME_DIR"] + "/bus"
            docker_fixture = None
            if os.environ.get("FORGEJO_DOCKER_TEST_BINARY"):
                docker_fixture = RootlessDockerFixture(root, os.environ["FORGEJO_DOCKER_TEST_BINARY"], runtime_env)
                runtime = docker_fixture.client
                runtime_env = docker_fixture.env
            config = root / "app.ini"
            url = f"http://127.0.0.1:{port}/"
            config.write_text(f"""[database]
DB_TYPE = sqlite3
PATH = {root}/forgejo.db
[security]
INSTALL_LOCK = true
[server]
APP_DATA_PATH = {root}/data
HTTP_ADDR = 127.0.0.1
HTTP_PORT = {port}
ROOT_URL = {f'http://host.containers.internal:{port}/' if acceptance else url}
DISABLE_SSH = true
[repository]
ROOT = {root}/repositories
FORCE_PRIVATE = true
[service]
DISABLE_REGISTRATION = true
REQUIRE_SIGNIN_VIEW = true
ENABLE_INTERNAL_SIGNIN = false
ENABLE_BASIC_AUTHENTICATION = false
[actions]
ENABLED = true
[log]
MODE = console
LEVEL = Error
""")
            base = [forgejo, "--config", str(config), "--work-path", directory]
            processes, logs = [], []
            sensitive = []

            def command(args, **kwargs):
                if args[0] in ("podman", runtime[0]):
                    kwargs.setdefault("env", runtime_env)
                timeout = kwargs.pop("timeout", 90)
                result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, **kwargs)
                diagnostic = result.stderr[-2000:] if args[0] == "podman" else "diagnostics suppressed"
                self.assertEqual(result.returncode, 0, "Fixture setup command failed: " + diagnostic)
                return result.stdout

            def request(path, data=None, method=None):
                body = None if data is None else json.dumps(data).encode()
                req = urllib.request.Request(url.rstrip("/") + path, body, method=method,
                    headers={"Authorization": "token " + token, "Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=5) as response:
                    return json.load(response)

            def start(args, name, **kwargs):
                log = open(root / (name + ".log"), "w+")
                logs.append(log)
                process = subprocess.Popen(args, stdout=log, stderr=log, **kwargs)
                processes.append(process)
                return process

            try:
                if docker_fixture:
                    docker_fixture.start()  # Validates rootless, isolated graph and cgroups.
                else:
                    info = json.loads(command(["podman", "info", "--format", "json"]))
                    self.assertTrue(info["host"]["security"]["rootless"], "Never run this fixture rootfully")
                # A direct digest pull preserves the registry manifest. Saving a
                # multiarch cached reference as OCI can rewrite its manifest and
                # fail digest validation on import. Never share job graph storage.
                command([*runtime, "pull", image], timeout=600)
                direct_limits = command([*runtime, "run", "--rm", "--cpus", "2", "--memory", "2g",
                                         image, "sh", "-c", "cat /sys/fs/cgroup/memory.max /sys/fs/cgroup/cpu.max"])
                self.assertEqual(direct_limits.splitlines(), ["2147483648", "200000 100000"],
                                 "Dedicated runtime must enforce direct Podman limits before testing the runner")
                command([*base, "migrate"])
                command([*base, "admin", "user", "create", "--username", "fixture",
                         "--email", "fixture@example.invalid", "--admin", "--random-password"])
                token = command([*base, "admin", "user", "generate-access-token", "--username", "fixture",
                                 "--token-name", "daemon-fixture", "--scopes", "all", "--raw"]).strip().splitlines()[-1]
                sensitive.append(token)
                web = start([*base, "web"], "forgejo")
                deadline = time.monotonic() + 30
                while True:
                    try:
                        request("/api/v1/version")
                        break
                    except OSError:
                        self.assertIsNone(web.poll(), "Fixture Forgejo exited")
                        self.assertLess(time.monotonic(), deadline, "Forgejo readiness timed out")
                        time.sleep(0.1)
                if not docker_fixture:
                    start([*runtime, "system", "service", "--time=0", "unix://" + str(api_socket)], "podman", env=runtime_env)
                deadline = time.monotonic() + 30
                while not api_socket.exists():
                    self.assertLess(time.monotonic(), deadline, "Podman API readiness timed out")
                    time.sleep(0.1)
                template = root / "template.json"
                settings = json.loads(MODULE.with_name("forgejo-runner-config.json").read_text())
                settings["runner"].update(labels=[("forgejo-build" if acceptance else "fixture") + ":docker://" + image],
                                          timeout="5m" if acceptance else "2m", shutdown_timeout="5s")
                if docker_fixture and acceptance:
                    settings["container"]["options"] += " --add-host=host.containers.internal:10.0.2.2"
                template.write_text(json.dumps(settings))
                registration.register(forgejo, str(config), directory, control, template, url, "fixture")
                sensitive.append((control / "token").read_text())
                env = os.environ.copy()
                env["DOCKER_HOST"] = "unix://" + str(api_socket)
                env["XDG_CACHE_HOME"] = str(root / "action-cache")
                env["FORGEJO_FIXTURE_CONTROL_SENTINEL"] = "host-only-fixture-sentinel"
                daemon = start([runner, "--config", str(control / "config.yaml"), "daemon"], "runner",
                               cwd=workspace, env=env)
                request("/api/v1/user/repos", {"name": "daemon-fixture", "private": True, "auto_init": True})
                request("/api/v1/repos/fixture/daemon-fixture", {"has_actions": True}, method="PATCH")
                script = textwrap.dedent(f"""
          echo MEMORY_LIMIT=$(cat /sys/fs/cgroup/memory.max)
          echo CPU_LIMIT=$(cat /sys/fs/cgroup/cpu.max)
          grep -E '^(CapEff|NoNewPrivs):' /proc/self/status
          test "$(cat /sys/fs/cgroup/memory.max)" = 2147483648
          test "$(cat /sys/fs/cgroup/cpu.max)" = "200000 100000"
          test ! -S /var/run/docker.sock
          test ! -S /run/podman/podman.sock
          test ! -e '{control}/token'
          test ! -e /fixture-control/token
          test -z "${{FORGEJO_FIXTURE_CONTROL_SENTINEL:-}}"
          grep -Eq '^CapEff:[[:space:]]+0000000000000000$' /proc/self/status
          grep -Eq '^NoNewPrivs:[[:space:]]+1$' /proc/self/status
          sleep 5
          echo DAEMON_LIMITS_AND_BOUNDARY_OK
""")
                # A second independently eligible job requests prohibited privilege,
                # a host credential mount and a larger CPU limit. The selected
                # engine's job-option whitelist and valid_volumes must prevent it.
                workflow = "name: daemon-limits\non: [push]\njobs:\n"
                for job_name in ("limits", "overrides"):
                    workflow += f"  {job_name}:\n    runs-on: fixture\n"
                    if job_name == "overrides":
                        options = json.dumps(f"--privileged --cpus 8 --volume {control}:/fixture-control:ro")
                        workflow += f"    container:\n      image: {image}\n      options: {options}\n"
                    workflow += "    steps:\n      - shell: sh\n        run: |\n" + textwrap.indent(script.strip(), "          ") + "\n"
                if acceptance:
                    example = MODULE.parents[7] / "examples/forgejo-acceptance"
                    for name in ("acceptance.test.mjs", "build.mjs"):
                        request("/api/v1/repos/fixture/daemon-fixture/contents/" + name, {
                            "content": base64.b64encode((example / name).read_bytes()).decode(),
                            "message": "Fixture acceptance source",
                        })
                    workflow = (example / ".forgejo/workflows/acceptance.yml").read_text()
                    # The fixture label and example must use the same pinned image.
                    self.assertIn(image, workflow)
                request("/api/v1/repos/fixture/daemon-fixture/contents/.forgejo/workflows/limits.yml", {
                    "content": base64.b64encode(workflow.encode()).decode(), "message": "Fixture limits job",
                })
                deadline = time.monotonic() + (240 if acceptance else 100)
                observed_running = False
                while True:
                    self.assertIsNone(daemon.poll(), "Runner daemon exited")
                    payload = request("/api/v1/repos/fixture/daemon-fixture/actions/runs")
                    runs = payload.get("workflow_runs", [])
                    if runs:
                        jobs = request(f"/api/v1/repos/fixture/daemon-fixture/actions/runs/{runs[0]['id']}/jobs")
                        running = sum(job.get("status") == "running" for job in jobs)
                        self.assertLessEqual(running, 1, "capacity=1 must queue, not run simultaneous jobs")
                        observed_running |= running == 1
                    if runs and runs[0].get("status") in ("completed", "success", "failure", "cancelled", "skipped"):
                        if (runs[0].get("conclusion") or runs[0].get("status")) != "success":
                            jobs = request(f"/api/v1/repos/fixture/daemon-fixture/actions/runs/{runs[0]['id']}/jobs")
                            for job in jobs:
                                req = urllib.request.Request(url + f"api/v1/repos/fixture/daemon-fixture/actions/jobs/{job['id']}/logs",
                                    headers={"Authorization": "token " + token})
                                try:
                                    with urllib.request.urlopen(req, timeout=5) as response:
                                        diagnostic = response.read().decode(errors="replace")[-5000:]
                                except urllib.error.HTTPError as error:
                                    diagnostic = f"Job logs unavailable (HTTP {error.code}); status={job.get('status')}"
                                for value in sensitive:
                                    diagnostic = diagnostic.replace(value, "[REDACTED]")
                                print("Fixture job logs:\n" + diagnostic)
                        self.assertEqual(runs[0].get("conclusion") or runs[0].get("status"), "success", "Daemon limits job failed")
                        self.assertEqual(len(jobs), 2)
                        self.assertTrue(observed_running, "Fixture must observe running jobs to test queuing")
                        break
                    if time.monotonic() + 1 > deadline:
                        print("Run response keys:", list(payload), "statuses:",
                              [(item.get("id"), item.get("status"), item.get("conclusion")) for item in runs])
                    self.assertLess(time.monotonic(), deadline, "Daemon job did not complete")
                    time.sleep(0.5)
                # The runner must not expose an auxiliary cache/job TCP listener.
                socket_inodes = set()
                for descriptor in Path(f"/proc/{daemon.pid}/fd").iterdir():
                    try:
                        target = os.readlink(descriptor)
                    except FileNotFoundError:
                        continue
                    if target.startswith("socket:["):
                        socket_inodes.add(target[8:-1])
                for family in ("tcp", "tcp6"):
                    entries = Path(f"/proc/{daemon.pid}/net/{family}").read_text().splitlines()[1:]
                    self.assertFalse(any(line.split()[3] == "0A" and line.split()[9] in socket_inodes for line in entries),
                                     "cache.enabled=false must leave no runner TCP listener")
                # No unpinned fallback image may have been pulled into the isolated graph.
                if docker_fixture:
                    images = command([*runtime, "images", "--quiet", "--no-trunc"]).splitlines()
                    self.assertEqual(len(set(images)), 1)
                    digests = json.loads(command([*runtime, "image", "inspect", image]))[0]["RepoDigests"]
                else:
                    images = json.loads(command([*runtime, "images", "--format", "json"]))
                    self.assertEqual(len(images), 1)
                    digests = images[0].get("RepoDigests", []) or [images[0].get("Digest", "")]
                self.assertTrue(any(value.endswith(image.split("@", 1)[1]) for value in digests))
            except Exception:
                # Only disposable fixtures are logged; redact their credentials too.
                for log in logs:
                    log.flush()
                    log.seek(0)
                    diagnostic = log.read()[-4000:]
                    for value in sensitive:
                        diagnostic = diagnostic.replace(value, "[REDACTED]")
                    print(Path(log.name).name + ":\n" + diagnostic)
                raise
            finally:
                for process in reversed(processes):
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=15)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
                for log in logs:
                    log.close()
                if docker_fixture:
                    docker_fixture.close()
                else:
                    cleanup_runtime(root, runtime, runtime_env)


if __name__ == "__main__":
    unittest.main()
