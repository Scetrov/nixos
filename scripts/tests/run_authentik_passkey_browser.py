#!/usr/bin/env python3
"""Run real candidate flows in disposable rootless Podman containers.

Operator-authorized integration entry point, not an automatic pre-commit hook.
Only localhost ports are published. No production vault or credentials are read.
OpenTofu operations always use scripts/tofu.sh's isolated fixture mode.
"""

import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import time
import traceback
import urllib.error
import urllib.request
import uuid


ROOT = Path(__file__).resolve().parents[2]
AUTHENTIK = "ghcr.io/goauthentik/server:2026.8.3@sha256:ab9b4e8cc4ab3f8d1198d2db6aeea66bafea1963b3f2843589e0d163f97d9849"
POSTGRES = "docker.io/library/postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24"


class FixtureError(RuntimeError):
    """Safe operation label, never a raw server response or command output."""


def run(args, *, env=None, timeout=300):
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise FixtureError(f"{Path(args[0]).name} {args[1]} failed (exit {result.returncode}); raw output suppressed")
    return result.stdout


def fetch_json(url, token):
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def resource(source, kind, name):
    match = re.search(rf'(?ms)^resource "{kind}" "{name}"\s*\{{.*?^\}}', source)
    if not match:
        raise FixtureError("Fixture resource extraction failed")
    return match.group(0)


def main():
    if os.environ.get("RUN_PASSKEY_BROWSER_TESTS") != "1":
        raise FixtureError("Set RUN_PASSKEY_BROWSER_TESTS=1 after operator approval for local containers/browser")
    suffix = uuid.uuid4().hex[:10]
    network = "passkey-test-" + suffix
    database, server, worker = [network + "-" + name for name in ("db", "server", "worker")]
    token, password, db_password, secret_key = [secrets.token_hex(32) for _ in range(4)]
    fixture = Path(tempfile.mkdtemp(prefix=".passkey-test-", dir=ROOT / "terraform"))
    os.chmod(fixture, 0o700)
    try:
        # Only reviewed, already repository-pinned image contracts are used.
        for image in (AUTHENTIK, POSTGRES):
            exists = subprocess.run(["podman", "image", "exists", image], capture_output=True)
            if exists.returncode:
                run(["podman", "pull", image], timeout=600)
        run(["podman", "network", "create", "--internal", network])
        run(["podman", "run", "-d", "--name", database, "--network", network,
             "--security-opt=no-new-privileges", "--env", "POSTGRES_USER=authentik",
             "--env", "POSTGRES_DB=authentik", "--env", "POSTGRES_PASSWORD=" + db_password, POSTGRES])
        environment = [
            "AUTHENTIK_POSTGRESQL__HOST=" + database,
            "AUTHENTIK_POSTGRESQL__USER=authentik",
            "AUTHENTIK_POSTGRESQL__NAME=authentik",
            "AUTHENTIK_POSTGRESQL__PASSWORD=" + db_password,
            "AUTHENTIK_SECRET_KEY=" + secret_key,
            "AUTHENTIK_BOOTSTRAP_TOKEN=" + token,
            "AUTHENTIK_BOOTSTRAP_PASSWORD=" + password,
            "AUTHENTIK_BOOTSTRAP_EMAIL=fixture@example.invalid",
            "AUTHENTIK_DISABLE_UPDATE_CHECK=true",
            "AUTHENTIK_ERROR_REPORTING__ENABLED=false",
            "AUTHENTIK_LOG_LEVEL=warning",
        ]
        env_args = [value for item in environment for value in ("--env", item)]
        for name, command in ((server, "server"), (worker, "worker")):
            port_args = ["--publish", "127.0.0.1::9000"] if command == "server" else []
            run(["podman", "run", "-d", "--name", name, "--network", network,
                 "--cap-drop=all", "--security-opt=no-new-privileges", *port_args, *env_args,
                 AUTHENTIK, command])
        port = run(["podman", "port", server, "9000/tcp"]).strip().rsplit(":", 1)[1]
        base = "http://localhost:" + str(int(port))
        deadline = time.monotonic() + 240
        brand_id = None
        while time.monotonic() < deadline:
            try:
                brands = fetch_json(base + "/api/v3/core/brands/", token)["results"]
                flows = fetch_json(base + "/api/v3/flows/instances/?slug=default-authentication-flow", token)["results"]
                if brands and flows:
                    brand_id = brands[0]["brand_uuid"]
                    # Ensure stage blueprint reconciliation is complete too.
                    stages = fetch_json(base + "/api/v3/stages/all/?search=default-authentication", token)["results"]
                    if len(stages) >= 4:
                        break
            except (OSError, KeyError, ValueError):
                pass
            time.sleep(2)
        else:
            raise FixtureError("Disposable Authentik bootstrap timed out")

        # Reuse production resource text, not an independently maintained blueprint.
        for filename in ("authentik-flows.tf", "authentik-settings.tf"):
            (fixture / filename).write_text((ROOT / "terraform" / filename).read_text())
        brand = resource((ROOT / "terraform/authentik.tf").read_text(), "authentik_brand", "default")
        settings_before = fetch_json(base + "/api/v3/admin/settings/", token)
        config = '''
terraform {
  required_providers {
    authentik = { source = "goauthentik/authentik", version = "2026.8.0" }
  }
}
variable "authentik_test_url" { type = string }
variable "authentik_test_token" {
  type = string
  sensitive = true
}
variable "authentik_test_password" {
  type = string
  sensitive = true
}
variable "authentik_passkey_first_enabled" {
  type = bool
  default = false
}
provider "authentik" {
  url = var.authentik_test_url
  token = var.authentik_test_token
}
data "authentik_flow" "default_authentication" { slug = "default-authentication-flow" }
# Fixture-only enrollment seeds a synthetic credential for browser acceptance.
# No demonstrated production compatibility gap requires a new enrollment path.
resource "authentik_flow" "passkey_enrollment_candidate" {
  name           = "Disposable fixture enrollment"
  slug           = "passkey-enrollment-candidate"
  title          = "Add a fixture passkey"
  designation    = "stage_configuration"
  authentication = "require_authenticated"
}
resource "authentik_stage_authenticator_webauthn" "passkey_enrollment_candidate" {
  name                     = "disposable-fixture-enrollment"
  friendly_name            = "Fixture passkey"
  resident_key_requirement = "required"
  user_verification        = "required"
}
resource "authentik_flow_stage_binding" "passkey_enrollment" {
  target = authentik_flow.passkey_enrollment_candidate.uuid
  stage  = authentik_stage_authenticator_webauthn.passkey_enrollment_candidate.id
  order  = 10
}
resource "authentik_user" "browser_fixture" {
  username = "passkey-browser-fixture"
  name = "Disposable browser fixture"
  password = var.authentik_test_password
  is_active = true
  path = "users"
}
'''
        (fixture / "main.tf").write_text(config + "\n" + brand + '\nimport {\n  to = authentik_brand.default\n  id = "' + str(uuid.UUID(brand_id)) + '"\n}\n')
        # Whitelist environment inputs: do not inherit production TF_VAR_* values.
        env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "SSL_CERT_FILE", "NIX_SSL_CERT_FILE") if k in os.environ}
        env.update(TF_VAR_authentik_test_url=base, TF_VAR_authentik_test_token=token,
                   TF_VAR_authentik_test_password=password)
        wrapper = [str(ROOT / "scripts/tofu.sh"), "--test-fixture-dir", str(fixture), "--"]
        plugins = ROOT / "terraform/.terraform/providers"
        run([*wrapper, "init", "-input=false", "-plugin-dir=" + str(plugins)], env=env)
        run([*wrapper, "apply", "-auto-approve", "-input=false"], env=env)
        settings_after = fetch_json(base + "/api/v3/admin/settings/", token)
        for key in ("base_url", "impersonation_require_reason"):
            if settings_after.get(key) != settings_before.get(key):
                raise FixtureError("Provider changed an unmanaged newer system setting")
        if settings_after["footer_links"] != [{"name": "Use username/password instead", "href": "/if/flow/passkey-first-candidate/?use_password=1"}]:
            raise FixtureError("Native fallback footer was not configured")
        print("PASS: native footer configured without changing unmanaged newer settings", flush=True)
        candidate = fetch_json(base + "/api/v3/flows/instances/?slug=passkey-first-candidate", token)["results"][0]["pk"]
        current = fetch_json(base + "/api/v3/core/brands/", token)["results"][0]
        if current["flow_authentication"] == candidate:
            raise FixtureError("Default-off selection failed in disposable fixture")
        print("PASS: isolated candidate provisioning leaves the existing route selected", flush=True)
        # Exercise activation only in the disposable fixture, never on Habiki.
        run([*wrapper, "apply", "-auto-approve", "-input=false", "-var=authentik_passkey_first_enabled=true"], env=env)
        print("PASS: isolated fixture activation through wrapper", flush=True)
        browser_env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG") if k in os.environ}
        browser_env.update(AUTHENTIK_BROWSER_TEST_URL=base,
                           AUTHENTIK_BROWSER_TEST_PASSWORD=password,
                           AUTHENTIK_BROWSER_TEST_FIXTURE="1")
        result = subprocess.run(["node", str(ROOT / "scripts/tests/authentik_passkey_browser.mjs")],
                                cwd=ROOT, env=browser_env, capture_output=True, text=True, timeout=300)
        # Browser harness prints only fixed test names/outcomes, not payloads.
        for line in result.stdout.splitlines():
            if line.startswith(("PASS:", "FAIL:", "SKIP:")):
                print(line, flush=True)
        if result.returncode:
            raise FixtureError("Disposable browser assertions failed; raw browser output suppressed")
        run([*wrapper, "apply", "-auto-approve", "-input=false", "-var=authentik_passkey_first_enabled=false"], env=env)
        restored = fetch_json(base + "/api/v3/core/brands/", token)["results"][0]
        if restored["flow_authentication"] != current["flow_authentication"]:
            raise FixtureError("Disposable declarative rollback did not restore prior selection")
        print("PASS: isolated declarative rollback restores the existing route", flush=True)
    finally:
        for name in (worker, server, database):
            subprocess.run(["podman", "rm", "-fv", name], capture_output=True, timeout=60)
        subprocess.run(["podman", "network", "rm", network], capture_output=True, timeout=30)
        shutil.rmtree(fixture)
        print("Fixture containers, network, synthetic state and credentials removed", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (FixtureError, subprocess.TimeoutExpired) as exc:
        # TimeoutExpired includes the command arguments (which can contain secrets).
        print("FAIL: " + (str(exc) if isinstance(exc, FixtureError) else "Fixture operation timed out"))
        raise SystemExit(1) from None
    except Exception as exc:  # noqa: BLE001
        # Print source locations, never exception strings with response payloads.
        frames = traceback.extract_tb(exc.__traceback__)
        locations = ", ".join(f"{Path(frame.filename).name}:{frame.lineno}" for frame in frames)
        print(f"FAIL: fixture {type(exc).__name__} at {locations}")
        raise SystemExit(1) from None
