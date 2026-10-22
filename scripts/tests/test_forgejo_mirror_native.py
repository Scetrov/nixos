"""Opt-in disposable native Forgejo contract fixture (no production credentials).

Set FORGEJO_MIRROR_TEST_IMAGE to a fully qualified digest-pinned Forgejo image.
Requires rootless Podman. Checks native Git/LFS, unchanged submodule URLs and token scopes.
"""
import base64
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import unittest
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("mirrors_native", ROOT / "src/roles/nixos/files/etc/nixos/modules/forgejo-mirrors.py")
mirrors = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mirrors)


@unittest.skipUnless(os.environ.get("FORGEJO_MIRROR_TEST_IMAGE"), "Set FORGEJO_MIRROR_TEST_IMAGE for native containers")
class NativeMirrorTests(unittest.TestCase):
    def test_non_admin_native_public_private_branches_tags_and_restart(self):
        image = os.environ["FORGEJO_MIRROR_TEST_IMAGE"]
        self.assertRegex(image, r"^[a-z0-9.-]+/[a-z0-9_./-]+@sha256:[0-9a-f]{64}$")
        prefix = "forgejo-mirrors-fixture-" + uuid.uuid4().hex[:12]
        network = prefix + "-network"
        containers = []
        sensitive = []
        namespace = "gh-fixture"

        def command(args, timeout=90):
            result = subprocess.run(["podman", *args], capture_output=True, text=True, timeout=timeout)
            self.assertEqual(result.returncode, 0, "Disposable container command failed; sensitive output suppressed")
            return (result.stdout + (result.stderr if args[0] == "logs" else "")).strip()

        def token(name, scopes, username="fixture"):
            value = command(["exec", name, "forgejo", "--config", "/var/lib/gitea/custom/conf/app.ini",
                             "admin", "user", "generate-access-token", "--username", username,
                             "--token-name", uuid.uuid4().hex, "--scopes", scopes, "--raw"]).splitlines()[-1]
            self.assertTrue(re.fullmatch(r"[a-f0-9]{40}", value), "Unexpected fixture token output")
            sensitive.append(value)
            return value

        def lfs(api, name, data, upload):
            oid = hashlib.sha256(data).hexdigest()
            origin = api.base.removesuffix("/api/v1")
            batch_path = f"/fixture/{name}.git/info/lfs/objects/batch" if upload else f"/{namespace}/{name}.git/info/lfs/objects/batch"
            headers = {"Authorization": "Basic " + base64.b64encode(("fixture:" + api.token).encode()).decode(),
                       "Accept": "application/vnd.git-lfs+json", "Content-Type": "application/vnd.git-lfs+json"}
            opener = urllib.request.build_opener(mirrors.NoRedirect)
            body = json.dumps({"operation": "upload" if upload else "download", "transfers": ["basic"],
                               "objects": [{"oid": oid, "size": len(data)}]}).encode()
            with opener.open(urllib.request.Request(origin + batch_path, body, headers, method="POST"), timeout=15) as response:
                batch = json.load(response)
            item = batch["objects"][0]
            if not upload and item.get("error", {}).get("code") == 404:
                return None
            self.assertNotIn("error", item, "Native LFS object unavailable")
            action = item.get("actions", {}).get("upload" if upload else "download")
            if action:
                # Server advertises its container origin; host client uses only its
                # path on this fixture's loopback-published endpoint. Never forward
                # auth to an arbitrary response-supplied origin.
                parsed = urllib.parse.urlsplit(action["href"])
                self.assertIn(parsed.netloc, ["upstream:3000", "target:3000"])
                url = origin + parsed.path + ("?" + parsed.query if parsed.query else "")
                req = urllib.request.Request(url, data if upload else None,
                                             {"Authorization": headers["Authorization"], "Content-Type": "application/octet-stream"},
                                             method="PUT" if upload else "GET")
                with opener.open(req, timeout=15) as response:
                    if not upload:
                        self.assertEqual(response.read(), data)
            return f"version https://git-lfs.github.com/spec/v1\noid sha256:{oid}\nsize {len(data)}\n".encode()

        def start(suffix, private):
            name = prefix + "-" + suffix
            args = ["run", "--detach", "--rm", "--name", name, "--network", network,
                    "--network-alias", suffix, "--publish", "127.0.0.1::3000"]
            for key, value in {
                "security__INSTALL_LOCK": "true", "database__DB_TYPE": "sqlite3",
                "server__DISABLE_SSH": "true", "server__LFS_START_SERVER": "true",
                "server__ROOT_URL": f"http://{suffix}:3000/",
                "repository__DEFAULT_BRANCH": "main", "repository__FORCE_PRIVATE": str(private).lower(),
                "service__DISABLE_REGISTRATION": "true", "service__REQUIRE_SIGNIN_VIEW": str(private).lower(),
                "service__ENABLE_BASIC_AUTHENTICATION": "false",
                # FIXTURE ONLY: local upstream and accelerated automatic polling.
                "migrations__ALLOW_LOCALNETWORKS": "true", "migrations__ALLOWED_DOMAINS": "*",
                "mirror__MIN_INTERVAL": "1m", "mirror__DEFAULT_INTERVAL": "1m",
                "cron.update_mirrors__SCHEDULE": "@every 1s",
            }.items():
                args += ["--env", "FORGEJO__" + key + "=" + value]
            command([*args, image], timeout=180)
            containers.append(name)
            port = command(["port", name, "3000/tcp"]).rsplit(":", 1)[1]
            api = mirrors.API("http://127.0.0.1:" + port + "/api/v1", sleep=lambda _: None)
            deadline = time.monotonic() + 45
            while True:
                try:
                    api.request("GET", "/version")
                    break
                except mirrors.MirrorError as error:
                    # Private API returns 403 once the installed service is ready.
                    if str(error) == "http_403":
                        break
                    self.assertLess(time.monotonic(), deadline, "Container readiness timed out")
                    time.sleep(0.2)
            command(["exec", name, "forgejo", "--config", "/var/lib/gitea/custom/conf/app.ini", "admin", "user", "create",
                     "--username", "fixture", "--email", "fixture@example.invalid", "--random-password"])
            api.token = token(name, "all")  # Non-admin bootstrap token, disposable only.
            return name, api

        info = json.loads(command(["info", "--format", "json"]))
        self.assertTrue(info["host"]["security"]["rootless"], "Refusing non-rootless fixture runtime")
        command(["network", "create", network])
        try:
            upstream_name, upstream = start("upstream", False)
            target_name, target = start("target", True)
            if os.environ.get("FORGEJO_MIRROR_PROVISION_TEST") == "1":
                from scripts.tests.forgejo_mirror_provision_fixture import exercise
                provisioned = exercise(self, target_name, target, command)
                target = mirrors.API(provisioned.base, provisioned.token)
                sensitive.append(target.token)
                namespace = "gh-Scetrov"
                org = target.request("GET", "/orgs/" + namespace)
            else:
                org = target.request("POST", "/orgs", {"username": namespace, "visibility": "private"})
                target.token = token(target_name, "write:repository,read:organization")
            self.assertIsInstance(org["id"], int)
            self.assertEqual(target.request("GET", "/orgs/" + namespace)["id"], org["id"])
            upstream_read_token = token(upstream_name, "read:repository")
            command(["exec", target_name, "forgejo", "--config", "/var/lib/gitea/custom/conf/app.ini",
                     "admin", "user", "create", "--username", "outsider",
                     "--email", "outsider@example.invalid", "--random-password"])
            outsider = mirrors.API(target.base, token(target_name, "read:repository", "outsider"), sleep=lambda _: None)
            for private in [False, True]:
                name = "private" if private else "public"
                upstream.request("POST", "/user/repos", {"name": name, "private": private, "auto_init": True})
                initial_data = b"initial native LFS fixture\n"
                pointer = lfs(upstream, name, initial_data, True)
                initial_object = upstream.request("POST", f"/repos/fixture/{name}/contents/object.bin", {
                    "content": base64.b64encode(pointer).decode(), "message": "initial LFS pointer"})
                submodule = b'[submodule "dependency"]\n\tpath = dependency\n\turl = https://github.com/example/dependency.git\n'
                for filename, data in [(".gitmodules", submodule), (".gitattributes", b"*.bin filter=lfs diff=lfs merge=lfs -text\n")]:
                    upstream.request("POST", f"/repos/fixture/{name}/contents/{filename}", {
                        "content": base64.b64encode(data).decode(), "message": "fixture references"})
                payload = {"service": "git", "clone_addr": f"http://upstream:3000/fixture/{name}.git",
                           "repo_owner": namespace, "repo_name": name, "private": True,
                           "mirror": True, "mirror_interval": "1m", "lfs": True,
                           "description": "disposable-mirror-contract"}
                if private:
                    payload.update(auth_username="fixture", auth_password=upstream_read_token)
                repo = target.request("POST", "/repos/migrate", payload)
                self.assertTrue(repo["mirror"] and repo["private"])
                self.assertEqual(repo["original_url"], payload["clone_addr"])
                self.assertNotIn(upstream.token, json.dumps(repo))
                self.assertNotIn(upstream_read_token, json.dumps(repo))
                original_id = repo["id"]
                self.assertIsNotNone(lfs(target, name, initial_data, False), "Initial LFS import incomplete")
                later_data = b"later native LFS fixture\n"
                later_pointer = lfs(upstream, name, later_data, True)
                # The contents API applies .gitattributes: supply actual bytes,
                # not an already encoded pointer (which would create nested LFS).
                changed = upstream.request("PUT", f"/repos/fixture/{name}/contents/object.bin", {
                    "content": base64.b64encode(later_data).decode(),
                    "sha": initial_object["content"]["sha"], "message": "later LFS object"})
                blob = upstream.request("GET", f"/repos/fixture/{name}/git/blobs/" + changed["content"]["sha"])
                self.assertEqual(base64.b64decode(blob["content"]), later_pointer)
                upstream.request("POST", f"/repos/fixture/{name}/contents/later.txt", {
                    "content": base64.b64encode(b"later native mirror update\n").decode(), "message": "later commit"})
                upstream.request("POST", f"/repos/fixture/{name}/tags", {"tag_name": "fixture-tag", "target": "main"})
                expected = upstream.request("GET", f"/repos/fixture/{name}/branches/main")["commit"]["id"]
                deadline = time.monotonic() + 90
                while True:
                    branch = target.request("GET", f"/repos/{namespace}/{name}/branches/main")
                    tags = target.request("GET", f"/repos/{namespace}/{name}/tags")
                    if branch["commit"]["id"] == expected and any(t["name"] == "fixture-tag" for t in tags):
                        break
                    self.assertLess(time.monotonic(), deadline, "Native automatic branch/tag polling timed out")
                    time.sleep(0.3)
                # Git refs may be visible before the same native worker finishes LFS.
                while lfs(target, name, later_data, False) is None:
                    self.assertLess(time.monotonic(), deadline, "Later native LFS polling incomplete")
                    time.sleep(0.3)
                modules = target.request("GET", f"/repos/{namespace}/{name}/contents/.gitmodules")
                self.assertEqual(base64.b64decode(modules["content"]), submodule)
                anonymous = mirrors.API(target.base, sleep=lambda _: None)
                for unauthorized in [anonymous, outsider]:
                    try:
                        self.assertIsNone(unauthorized.request("GET", f"/repos/{namespace}/{name}"))
                    except mirrors.MirrorError as error:
                        self.assertEqual(str(error), "http_403")
                command(["restart", target_name])
                deadline = time.monotonic() + 30
                while True:
                    try:
                        persisted = target.request("GET", f"/repos/{namespace}/{name}")
                        break
                    except mirrors.MirrorError:
                        self.assertLess(time.monotonic(), deadline, "Target restart readiness timed out")
                        time.sleep(0.2)
                self.assertEqual(persisted["id"], original_id)
                self.assertTrue(persisted["private"] and persisted["mirror"])
            # Reproduce a native LFS-only failure: Git refs may advance while
            # a missing upstream object leaves the destination incomplete.
            missing_data = b"native LFS failure and recovery fixture\n"
            missing_oid = hashlib.sha256(missing_data).hexdigest()
            upstream.request("POST", "/repos/fixture/private/contents/missing.bin", {
                "content": base64.b64encode(missing_data).decode(), "message": "missing LFS fixture"})
            paths = command(["exec", upstream_name, "find", "/var/lib/gitea", "-type", "f"]).splitlines()
            missing_paths = [p for p in paths if p.replace("/", "").endswith(missing_oid)]
            self.assertEqual(len(missing_paths), 1, "Cannot locate disposable LFS object")
            command(["exec", upstream_name, "rm", "--", missing_paths[0]])
            target.request("POST", f"/repos/{namespace}/private/mirror-sync")
            deadline = time.monotonic() + 90
            while "Ignoring missing upstream LFS object" not in command(["logs", target_name]):
                if time.monotonic() >= deadline:
                    diagnostic = "\n".join(line for line in command(["logs", target_name]).splitlines()
                                           if "lfs" in line.lower())[-3000:]
                    for secret in sensitive:
                        diagnostic = diagnostic.replace(secret, "<REDACTED>")
                    self.fail("Native LFS failure was not observable; LFS diagnostics: " + diagnostic)
                time.sleep(0.3)
            self.assertIsNone(lfs(target, "private", missing_data, False))
            # Repair the deliberately removed storage bytes. A batch upload
            # may trust existing metadata and decline to upload them again.
            command(["exec", upstream_name, "sh", "-c",
                     'printf %s "$1" | base64 -d > "$2"', "fixture-lfs-repair",
                     base64.b64encode(missing_data).decode(), missing_paths[0]])
            target.request("POST", f"/repos/{namespace}/private/mirror-sync")
            deadline = time.monotonic() + 90
            while lfs(target, "private", missing_data, False) is None:
                self.assertLess(time.monotonic(), deadline, "Native LFS recovery incomplete")
                time.sleep(0.3)
            for name in containers:
                output = command(["logs", name])
                self.assertTrue(all(secret not in output for secret in sensitive), "Fixture console leaked a token")
        finally:
            for name in reversed(containers):
                command(["rm", "--force", "--volumes", name])
            command(["network", "rm", network])


if __name__ == "__main__":
    unittest.main()
