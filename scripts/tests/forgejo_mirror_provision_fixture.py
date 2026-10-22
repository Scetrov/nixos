"""Disposable OpenTofu/bootstrap test; never loads production vault/backend."""
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exercise(test, container, target, container_command):
    provisioning = load("provisioning_fixture", ROOT / "scripts/provision_forgejo_mirrors.py")
    provider = load("provider_fixture", ROOT / "scripts/forgejo_provider.py")
    cli = lambda args: container_command(["exec", container, "forgejo", "--config",
                                          "/var/lib/gitea/custom/conf/app.ini", "admin", "user", *args])
    base = target.base.removesuffix("/api/v1")
    # Early failure must not leave its temporary admin behind.
    early_name = None
    with test.assertRaisesRegex(provisioning.ProvisionError, "synthetic failure"):
        with provisioning.bootstrap(cli, base, human="fixture") as (api, early_name):
            # Production already has a native OIDC human administrator. Match that
            # invariant: Forgejo correctly refuses deletion of its final admin.
            api.request("PATCH", "/admin/users/fixture", {"admin": True})
            raise provisioning.ProvisionError("synthetic failure")
    test.assertIsNone(target.request("GET", "/users/" + early_name))

    pinned = provider.prepare(ROOT / "terraform/forgejo-mirrors")
    with tempfile.TemporaryDirectory(prefix=".passkey-test-forgejo-", dir=ROOT / "terraform") as temporary:
        fixture = Path(temporary)
        text = (ROOT / "terraform/forgejo-mirrors/main.tf").read_text()
        text = text.replace('  backend "pg" {\n    schema_name = "forgejo_mirrors"\n  }\n', "")
        test.assertNotIn('backend "pg"', text)
        (fixture / "main.tf").write_text(text)
        env = os.environ.copy()
        env.update(TF_VAR_forgejo_host=base, TF_VAR_human_owner="fixture",
                   TF_VAR_mirror_password=secrets.token_hex(32), TF_CLI_CONFIG_FILE=str(pinned))
        for key in ["TF_LOG", "TF_LOG_PATH", "TF_LOG_PROVIDER", "TF_LOG_CORE"]:
            env.pop(key, None)
        wrapper = [str(ROOT / "scripts/tofu.sh"), "--test-fixture-dir", temporary, "--"]

        def tofu(args):
            result = subprocess.run(wrapper + args, env=env, capture_output=True, text=True, timeout=180)
            test.assertEqual(result.returncode, 0, "Disposable OpenTofu fixture failed; sensitive output suppressed")
            return result.stdout

        for iteration in range(2):
            with provisioning.bootstrap(cli, base, human="fixture") as (api, name):
                env["TF_VAR_forgejo_api_token"] = api.token
                if iteration == 0:
                    tofu(["init", "-backend=false", "-input=false"])
                    tofu(["plan", "-out=fixture.plan", "-input=false"])
                    tofu(["apply", "-input=false", "fixture.plan"])
                else:
                    tofu(["plan", "-detailed-exitcode", "-input=false"])
                outputs = json.loads(tofu(["output", "-json"]))
                provisioning.verify(api, outputs, human="fixture")
                if iteration == 0:
                    token = provisioning.issue_token(cli, "forgejo-mirrors", "fixture-service", provisioning.SERVICE_SCOPES)
                    worker = provisioning.API(target.base, token)
                    for org in provisioning.ORG_NAMES:
                        test.assertEqual(worker.request("GET", "/orgs/" + org)["visibility"], "private")
            test.assertIsNone(target.request("GET", "/users/" + name))
            for org in provisioning.ORG_NAMES:
                owners = provisioning.members(target, provisioning.owner_team(target, org))
                test.assertEqual(owners, {"fixture", "forgejo-mirrors"})
        return worker
