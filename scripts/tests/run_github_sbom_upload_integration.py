#!/usr/bin/env python3
"""Disposable DTrack upload check; never connects to production or verifies ingestion.

Run from repository root with Python + jsonschema + cryptography:
  python3 -m scripts.tests.run_github_sbom_upload_integration

The only default password used is the upstream public bootstrap password, in a
new loopback-only container with temporary data. All generated credentials stay
in memory and are destroyed with the container.
"""
import argparse
import copy
import io
import json
import secrets
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from unittest.mock import patch

from scripts.tests.test_github_sbom_collector import BOM, SOURCE, FakeHttp, collector

IMAGE = "docker.io/dependencytrack/apiserver:4.14.5@sha256:4d41f29ce886a7fcb94a424b3eb2bfd17497ba92d48d43896c48e87a69bcf335"


def bootstrap(request):
    """Honor the real first-login contract, rather than treating all 401s alike."""
    password = "admin"  # Public upstream default, used only on fresh fixture data.
    for attempt in range(60):
        try:
            _, token = request("/api/v1/user/login", "POST", {
                "username": "admin", "password": password,
            }, form=True)
            return token
        except urllib.error.HTTPError as exc:
            body = exc.read(4096).decode(errors="replace").strip()
            if exc.code == 401 and body == "FORCE_PASSWORD_CHANGE":
                password = secrets.token_urlsafe(32)
                status, _ = request("/api/v1/user/forceChangePassword", "POST", {
                    "username": "admin", "password": "admin",
                    "newPassword": password, "confirmPassword": password,
                }, form=True)
                if status != 200:
                    raise RuntimeError("fixture_password_change_failed") from None
                print("Required bootstrap password change: HTTP 200")
                continue
            if exc.code not in (401, 503):
                raise RuntimeError("fixture_login_http_" + str(exc.code)) from None
        except (urllib.error.URLError, TimeoutError, ConnectionResetError):
            pass
        time.sleep(2)
    raise RuntimeError("fixture_login_timeout")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", choices=("podman", "docker"), default="podman")
    args = parser.parse_args()
    name = "sbom-upload-check-" + secrets.token_hex(4)
    started = False
    try:
        result = subprocess.run([
            args.runtime, "run", "-d", "--name", name, "--memory=2g", "--cpus=2",
            "-p", "127.0.0.1::8080", "--tmpfs", "/data:rw,size=1g,mode=1777", IMAGE,
        ], capture_output=True, timeout=180)
        if result.returncode:
            raise RuntimeError("fixture_container_start_failed")
        started = True
        result = subprocess.run([args.runtime, "port", name, "8080"], capture_output=True, text=True, check=True)
        base = "http://127.0.0.1:" + result.stdout.strip().rsplit(":", 1)[1]

        def request(path, method="GET", body=None, token=None, form=False):
            headers = {}
            if token:
                headers["Authorization"] = "Bearer " + token
            if body is not None:
                headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
                body = urllib.parse.urlencode(body).encode() if form else json.dumps(body).encode()
            req = urllib.request.Request(base + path, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read(1024 * 1024)
                try:
                    value = json.loads(data)
                except ValueError:
                    value = data.decode()
                return response.status, value

        token = bootstrap(request)
        print("Bootstrap login: HTTP 200 (token redacted)")
        projects = []
        for suffix in ("main", "isolated"):
            _, project = request("/api/v1/project", "PUT", {"name": name + "-" + suffix, "version": "main"}, token)
            projects.append(project["uuid"])
        _, team = request("/api/v1/team", "PUT", {"name": name}, token)
        request("/api/v1/permission/BOM_UPLOAD/team/" + team["uuid"], "POST", token=token)
        _, key = request("/api/v1/team/" + team["uuid"] + "/key", "PUT", token=token)
        api_key = key.get("key") or key.get("apiKey")
        if not api_key:
            raise RuntimeError("fixture_api_key_missing")
        print("Dedicated fixture team: BOM_UPLOAD only; API key created (redacted)")

        class FixtureDTrack(collector.Http):
            def request(self, url, *positional, **keyword):
                # The production transport still requires HTTPS. Only this
                # disposable loopback fixture substitutes its local HTTP origin.
                if not url.startswith("https://dtrack.fixture/"):
                    raise RuntimeError("unexpected_fixture_origin")
                return super().request(base + url.removeprefix("https://dtrack.fixture"), *positional, **keyword)

        transport = FixtureDTrack("unused-github-fixture-token", api_key, "https://dtrack.fixture")
        http = FakeHttp()
        uploads = []

        def upload(project, data):
            result = transport.upload(project, data)
            uploads.append(project)
            return result

        http.upload = upload
        sources = [dict(copy.deepcopy(SOURCE), project=project) for project in projects]
        config = {"sources": sources}
        schema = collector.Draft7Validator({"type": "object", "required": list(BOM)})
        state = {}
        saved = []
        with patch("sys.stdout", io.StringIO()):
            counts = collector.collect(config, state, lambda s: saved.append(copy.deepcopy(s)), http, schema)
            assert counts["uploaded"] == 2 and counts["failed"] == 0
            assert uploads == projects
            state = json.loads(json.dumps(saved[-1]))
            counts = collector.collect(config, state, lambda s: saved.append(copy.deepcopy(s)), http, schema)
            assert counts["uploaded"] == 0 and len(uploads) == 2
            bad = FakeHttp(data=b"not a zip archive")
            bad.upload = upload
            counts = collector.collect(config, {}, lambda s: None, bad, schema)
            assert counts["failed"] == 2 and len(uploads) == 2
        print("Real collector uploads to two configured fixture targets: accepted, tokens persisted")
        print("Restart/repeat: zero extra uploads; malformed archives: rejected before upload")
        print("PASS: upload acceptance only; no processing-token polling or inventory read-back")
        return 0
    except Exception as exc:
        # Do not print response bodies, credentials or tracebacks.
        print("FAIL:", type(exc).__name__, "(details redacted)")
        return 1
    finally:
        if started:
            result = subprocess.run([args.runtime, "rm", "-f", name], capture_output=True, timeout=30)
            print("Disposable cleanup:", "complete" if result.returncode == 0 else "FAILED")


if __name__ == "__main__":
    raise SystemExit(main())
