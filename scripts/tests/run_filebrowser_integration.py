#!/usr/bin/env python3
"""Disposable Quantum contract test. Run as root on Habiki, never on personal data.

Uses the approved digest, loopback HTTP, synthetic OIDC, unallocated numeric UIDs,
and a temporary tree. No production credentials, accounts, or routes are used.
"""

import base64
import http.cookiejar
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import shutil
import socket
import sys
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import io
import zipfile

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

IMAGE = "ghcr.io/gtsteffaniak/filebrowser@sha256:989e2dc6c491bda3c8bb82b27cd7798924ff3025cabdcad2444eb42f774836f6"
SERVICE, ALICE, BOB, UNRELATED = 62001, 62002, 62003, 62004


def command(*args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, **kwargs).stdout


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Fixture:
    def __init__(self, root):
        self.root = root
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.oidc = ThreadingHTTPServer(("127.0.0.1", 0), self.handler())
        self.issuer = f"http://127.0.0.1:{self.oidc.server_port}"
        self.name = "filebrowser-fixture-" + uuid.uuid4().hex[:12]
        self.username = "alice"
        self.codes = {}
        self.tokens = {}
        self.browser_done = threading.Event()
        self.browser_ok = False
        self.control_nonce = secrets.token_urlsafe(32)
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        modulus = self.key.public_key().public_numbers().n.to_bytes(256, "big")
        self.jwk = {"kty": "RSA", "use": "sig", "kid": "fixture", "alg": "RS256", "n": b64(modulus), "e": "AQAB"}
        self.thread = threading.Thread(target=self.oidc.serve_forever, daemon=True)
        self.thread.start()
        self.issued_sessions = []
        self.proxy = None

    def handler(self):
        fixture = self

        class OIDC(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def reply(self, value):
                body = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = urllib.parse.urlsplit(self.path)
                if path.path == "/.well-known/openid-configuration":
                    self.reply({"issuer": fixture.issuer, "authorization_endpoint": fixture.issuer + "/authorize", "token_endpoint": fixture.issuer + "/token", "jwks_uri": fixture.issuer + "/jwks", "userinfo_endpoint": fixture.issuer + "/userinfo", "response_types_supported": ["code"], "subject_types_supported": ["public"], "id_token_signing_alg_values_supported": ["RS256"]})
                elif path.path == "/jwks":
                    self.reply({"keys": [fixture.jwk]})
                elif path.path == "/authorize":
                    query = urllib.parse.parse_qs(path.query)
                    code = secrets.token_urlsafe(16)
                    fixture.codes[code] = (fixture.username, query.get("nonce", [None])[0])
                    callback = query["redirect_uri"][0]
                    assert callback == fixture.base + "/api/auth/oidc/callback"
                    self.send_response(302)
                    self.send_header("Location", callback + "?" + urllib.parse.urlencode({"code": code, "state": query["state"][0]}))
                    self.end_headers()
                elif path.path == "/fixture-browser-done":
                    if self.headers.get("X-Fixture-Control") != fixture.control_nonce:
                        self.send_error(403)
                        return
                    fixture.browser_ok = urllib.parse.parse_qs(path.query).get("ok") == ["1"]
                    fixture.browser_done.set()
                    self.reply({"accepted": True})
                elif path.path == "/userinfo":
                    token = self.headers.get("Authorization", "").removeprefix("Bearer ")
                    self.reply(fixture.claims(fixture.tokens[token]))
                else:
                    self.send_error(404)

            def do_POST(self):
                if self.path != "/token":
                    self.send_error(404)
                    return
                query = urllib.parse.parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
                username, nonce = fixture.codes.pop(query["code"][0])
                token = secrets.token_urlsafe(24)
                fixture.tokens[token] = username
                claims = fixture.claims(username)
                if nonce:
                    claims["nonce"] = nonce
                signing = (b64(json.dumps({"alg": "RS256", "kid": "fixture"}).encode()) + "." + b64(json.dumps(claims).encode())).encode()
                signature = fixture.key.sign(signing, padding.PKCS1v15(), hashes.SHA256())
                self.reply({"access_token": token, "token_type": "Bearer", "expires_in": 3600, "id_token": signing.decode() + "." + b64(signature)})

        return OIDC

    def claims(self, username):
        return {"iss": self.issuer, "sub": "immutable-" + username, "aud": "fixture", "exp": int(time.time()) + 3600, "iat": int(time.time()), "preferred_username": username, "groups": ["Fixture Operators" if username == "operator" else "Fixture Users"]}

    def configure(self):
        self.docs = {}
        self.host_state = {"acls": {}, "initialized": []}
        self.host_records = {}
        self.host_state_file = self.root / "host-state.json"
        for name, uid in (("alice", ALICE), ("bob", BOB)):
            docs = self.root / name / "Documents"
            docs.mkdir(parents=True)
            os.chown(docs, uid, uid)
            os.chmod(docs, 0o700)
            # Start with a masked unrelated ACL, then verify that widening
            # the managed mask does not activate its dormant write permission.
            command("setfacl", "-m", f"u:{UNRELATED}:rwx,m::r--", str(docs))
            original = command("getfacl", "-cpn", str(docs)).decode()
            from filebrowser_acl import managed_acl, parse_acl
            desired = managed_acl(original, service_uid=SERVICE, unix_uid=uid, inode_uid=uid, directory=True)
            command("setfacl", "--set-file=-", str(docs), input=desired.encode())
            current = command("getfacl", "-cpn", str(docs)).decode()
            assert parse_acl(current)[(False, "user", str(UNRELATED))] == 4
            assert parse_acl(managed_acl(current, service_uid=SERVICE, unix_uid=uid, inode_uid=uid, directory=True)) == parse_acl(current)
            # Non-destructive ACL rollback preserves the exact original ACL.
            command("setfacl", "--remove-default", str(docs))
            command("setfacl", "--set-file=-", str(docs), input=original.encode())
            assert parse_acl(command("getfacl", "-cpn", str(docs)).decode()) == parse_acl(original)
            from filebrowser_host import apply_acl
            record = {"identity_uuid": str(uuid.uuid4()), "unix_username": name, "uid": uid, "documents": str(docs)}
            apply_acl(record, SERVICE, self.host_state, self.host_state_file)
            self.host_state["initialized"].append(record["identity_uuid"])
            self.host_records[name] = record
            self.docs[name] = docs
        print("PASS ACL mask preservation, idempotence and snapshot restore", flush=True)
        state = self.root / "state"
        state.mkdir()
        os.chown(state, SERVICE, SERVICE)
        config = {"http": {"listen": "127.0.0.1", "port": self.port, "disableWebDAV": True, "externalUrl": self.base}, "server": {"cacheDir": str(state / "cache"), "sources": [{"name": name, "path": "/documents/" + name, "config": {"defaultEnabled": False, "private": True}} for name in self.docs], "logging": [{"levels": "error|warning", "apiFilter": "disabled"}]}, "auth": {"methods": {"password": {"enabled": False}, "oidc": {"enabled": True, "issuerUrl": self.issuer, "clientId": "fixture", "clientSecret": secrets.token_urlsafe(32), "userIdentifier": "preferred_username", "adminGroup": "Fixture Operators"}}}, "userDefaults": {"account": {"permissions": {"admin": False, "api": False, "share": False, "realtime": False}}}}
        # Database paths are mounted at the same location for easy assertion.
        config["server"]["database"] = {"path": str(state / "quantum.sqlite"), "activity": {"disabled": True}}
        config["server"]["filesystem"] = {"createFilePermission": "660", "createDirectoryPermission": "770"}
        from filebrowser_runtime import runtime_config
        key = self.key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        machine = runtime_config([], "fixture", "fixture", self.port, key)["auth"]["methods"]["jwt"]
        config["auth"]["methods"]["jwt"] = machine
        config["auth"]["methods"]["oidc"]["adminGroup"] = ""
        self.config = self.root / "config.yaml"
        self.config.write_text(json.dumps(config))
        os.chown(self.config, SERVICE, SERVICE)
        os.chmod(self.config, 0o600)

    def start(self):
        args = ["podman", "run", "--detach", "--name", self.name, "--userns=host", "--user", f"{SERVICE}:{SERVICE}", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--read-only", "--network=host", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m", "-v", f"{self.config}:/fixture/config.yaml:ro", "-v", f"{self.root / 'state'}:{self.root / 'state'}:rw"]
        slots = self.root / "mounts"
        slots.mkdir(mode=0o700)
        for name, docs in self.docs.items():
            slot = slots / name
            slot.symlink_to(docs)
            args += ["-v", f"{slot}:/documents/{name}:rw"]
        command(*args, IMAGE, "-c", "/fixture/config.yaml")
        for _ in range(60):
            try:
                with urllib.request.urlopen(self.base + "/health", timeout=2) as response:
                    if response.status == 200:
                        break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.5)
        else:
            # Fixture logs are retained privately, never dumped with tokens.
            (self.root / "failure.log").write_bytes(command("podman", "logs", self.name))
            raise AssertionError("Runtime did not become healthy; inspect private fixture failure.log")
        pid = command("podman", "inspect", "--format", "{{.State.Pid}}", self.name).decode().strip()
        status = Path(f"/proc/{pid}/status").read_text()
        uid_line = next(line for line in status.splitlines() if line.startswith("Uid:"))
        assert [int(v) for v in uid_line.split()[1:]] == [SERVICE] * 4, uid_line
        print("PASS non-root host UID mapping", flush=True)

    def login(self, username):
        self.username = username
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        with opener.open(self.base + "/api/auth/oidc/login", timeout=15) as response:
            response.read()
        tokens = [cookie.value for cookie in jar if "jwt" in cookie.name]
        assert len(tokens) == 1, "OIDC did not issue exactly one session cookie"
        self.issued_sessions.append(tokens[0])
        return tokens[0]

    def api(self, method, path, token=None, body=None):
        headers = {}
        if isinstance(token, dict):
            headers.update(token)
        elif token:
            headers["Authorization"] = "Bearer " + token
        if isinstance(body, dict):
            body = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def user(self, username, token):
        status, body = self.api("GET", "/api/users?username=" + username, token)
        assert status == 200, f"user lookup failed: {status}"
        return json.loads(body)

    def test(self):
        claims = {"filebrowser_machine_username": "filebrowser-reconciler", "filebrowser_machine_groups": ["filebrowser-reconciler"], "sub": "machine-fixture", "exp": int(time.time()) + 120}
        signing = (b64(json.dumps({"alg": "RS256", "kid": "fixture"}).encode()) + "." + b64(json.dumps(claims).encode())).encode()
        assertion = signing.decode() + "." + b64(self.key.sign(signing, padding.PKCS1v15(), hashes.SHA256()))
        operator = {"X-Filebrowser-Admin-Assertion": assertion}
        machine = self.user("self", operator)
        assert machine["username"] == "filebrowser-reconciler" and machine["permissions"]["admin"]
        print("PASS separate signed machine administration, no password authentication", flush=True)
        sessions = {name: self.login(name) for name in self.docs}
        for name, token in sessions.items():
            user = self.user(name, operator)
            assert user["username"] == name
            assert not user.get("scopes"), "OIDC user received a default source"
            assert not any(user["permissions"].get(p) for p in ("admin", "api", "share"))
            print("PASS", name, "OIDC creation with no scopes", flush=True)
        from filebrowser_reconcile import QuantumAPI, desired_scopes, reconcile
        records = [{"identity_uuid": record["identity_uuid"], "unix_username": name} for name, record in self.host_records.items()]
        api = QuantumAPI(self.base, assertion)
        status, _ = self.api("DELETE", "/api/users?username=bob", operator)
        assert status == 200
        assert reconcile(api, records, []) > 0
        assert reconcile(api, records, records) == 0
        sessions["bob"] = self.login("bob")
        # Repair both extra-source and administrator privilege drift.
        status, response = self.api("PATCH", "/api/users?username=alice", operator, {"which": ["scopes", "permissions"], "data": {"username": "alice", "scopes": desired_scopes("alice") + desired_scopes("bob"), "permissions": {"admin": True, "api": False, "share": False, "realtime": False}}})
        assert status in (200, 204), f"Fixture drift patch failed: {status}, {response!r}"
        assert reconcile(api, records, records) > 0
        assert reconcile(api, records, records) == 0
        print("PASS real API account creation, scope/privilege drift repair and idempotence", flush=True)
        for name, token in sessions.items():
            own = self.user(name, operator)
            assert len(own["scopes"]) == 1 and own["scopes"][0]["name"] == name
            for other in self.docs:
                status, _ = self.api("GET", "/api/resources?" + urllib.parse.urlencode({"source": other, "path": "/"}), token)
                assert (status == 200) == (other == name), f"scope access {name}->{other}: {status}"
            print("PASS", name, "explicit scope / cross-user denial", flush=True)
            self.file_operations(name, token)
        # Casing is exact: a differently cased OIDC claim creates a separate,
        # unassigned account, never inheriting the lowercase account's scopes.
        self.isolation_checks(sessions)
        command("podman", "restart", self.name)
        for _ in range(60):
            try:
                with urllib.request.urlopen(self.base + "/health", timeout=2) as response:
                    if response.status == 200:
                        break
            except urllib.error.URLError:
                time.sleep(0.2)
        else:
            raise AssertionError("Restart did not become healthy")
        for name, token in sessions.items():
            own = self.user("self", token)
            assert own["username"] == name and len(own["scopes"]) == 1 and own["scopes"][0]["name"] == name
        assert reconcile(api, records, records) == 0
        print("PASS restart preserves sessions and explicit private scopes without default grants", flush=True)
        self.proxy_checks(operator, sessions)
        mixed = self.login("Alice")
        assert not self.user("Alice", operator).get("scopes")
        status, _ = self.api("GET", "/api/resources?source=alice&path=/", mixed)
        assert status in (401, 403, 404)
        print("PASS exact OIDC username matching", flush=True)
        # Deleting an account must invalidate an already issued bearer token.
        status, _ = self.api("DELETE", "/api/users?username=alice", operator)
        assert status == 200, f"user deletion failed: {status}"
        status, _ = self.api("GET", "/api/users?username=self", sessions["alice"])
        assert status == 401, f"deleted user's token still accepted: {status}"
        print("PASS deleted-user bearer-token rejection", flush=True)
        # Repeat real host preparation over new/replaced inodes, then revoke
        # remaining fixture accounts before withdrawing managed host ACLs.
        from filebrowser_host import apply_acl, withdraw_acl
        from filebrowser_acl import parse_acl
        for name, record in self.host_records.items():
            if name != "alice":
                status, _ = self.api("DELETE", "/api/users?username=" + name, operator)
                assert status == 200
            apply_acl(record, SERVICE, self.host_state, self.host_state_file)
            withdraw_acl(record, SERVICE, self.host_state)
            retained = self.docs[name] / "retained.txt"
            uid = record["uid"]
            command("setpriv", f"--reuid={uid}", f"--regid={uid}", "--clear-groups", sys.executable, "-c", "from pathlib import Path; import sys; p=Path(sys.argv[1]); assert p.read_bytes()==b'retained-owner-access'; p.write_bytes(b'owner-after-withdrawal')", str(retained))
            for path in (self.docs[name], retained, self.docs[name] / "nested"):
                acl = parse_acl(command("getfacl", "-cpn", str(path)).decode())
                assert (False, "user", str(SERVICE)) not in acl
                assert (True, "user", str(SERVICE)) not in acl
        print("PASS real descriptor-based host ACL convergence and data-preserving withdrawal", flush=True)
        logs = command("podman", "logs", self.name)
        assert assertion.encode() not in logs
        assert all(token.encode() not in logs for token in self.issued_sessions)
        assert b"fixture-upload-payload" not in logs
        assert json.loads(self.config.read_text())["auth"]["methods"]["oidc"]["clientSecret"].encode() not in logs
        print("PASS logs exclude session credentials and fixture content", flush=True)

    def file_operations(self, name, token):
        def resource(method, path, body=None, **query):
            url = "/api/resources?" + urllib.parse.urlencode({"source": name, "path": path, **query})
            status, response = self.api(method, url, token, body)
            assert status == 200, f"{name} {method} resource failed: {status}"
            return response

        resource("POST", "/nested", isDir="true")
        resource("POST", "/nested/deep", isDir="true")
        resource("POST", "/nested/deep/upload.txt", b"fixture-upload-payload")
        uploaded = self.docs[name] / "nested/deep/upload.txt"
        assert uploaded.stat().st_uid == SERVICE
        uid = ALICE if name == "alice" else BOB
        # Local owner can read/edit/rename/delete service-owned results and
        # create a file in a service-owned nested directory.
        local = """from pathlib import Path
import sys
p = Path(sys.argv[1])
assert p.read_bytes() == b'fixture-upload-payload'
p.write_bytes(b'local-edit')
p.rename(p.with_name('renamed.txt'))
p.with_name('renamed.txt').unlink()
p.with_name('local.txt').write_bytes(b'local-created')
"""
        command("setpriv", f"--reuid={uid}", f"--regid={uid}", "--clear-groups", sys.executable, "-c", local, str(uploaded))
        resource("PUT", "/nested/deep/local.txt", b"browser-edit")
        resource("POST", "/nested/deep/local.txt", b"replacement", override="true")
        command("setpriv", f"--reuid={uid}", f"--regid={uid}", "--clear-groups", sys.executable, "-c", "from pathlib import Path; import sys; p=Path(sys.argv[1]); assert p.read_bytes()==b'replacement'; p.write_bytes(b'owner-after-replace')", str(uploaded.with_name("local.txt")))
        resource("POST", "/nested/deep/temporary.txt", b"renamed-replacement")
        status, response = self.api("PATCH", "/api/resources", token, {"action": "rename", "overwrite": True, "items": [{"fromSource": name, "fromPath": "/nested/deep/temporary.txt", "toSource": name, "toPath": "/nested/deep/local.txt"}]})
        assert status == 200 and not json.loads(response).get("failed"), f"overwrite-by-rename failed: {status}"
        replaced = uploaded.with_name("local.txt")
        assert replaced.stat().st_uid == SERVICE
        command("setpriv", f"--reuid={uid}", f"--regid={uid}", "--clear-groups", sys.executable, "-c", "from pathlib import Path; import sys; p=Path(sys.argv[1]); assert p.read_bytes()==b'renamed-replacement'; p.write_bytes(b'owner-after-rename')", str(replaced))
        resource("DELETE", "/nested/deep/local.txt")
        resource("POST", "/retained.txt", b"retained-owner-access")
        resource("POST", f"/{name}-private-needle.txt", (name + "-private-payload").encode())
        resource("POST", "/passwords", isDir="true")
        resource("POST", "/passwords/ordinary-fixture.txt", b"literal-tree-fixture")
        resource("GET", "/passwords")
        for action, source, destination in (("copy", "/retained.txt", "/nested/copied.txt"), ("move", "/nested/copied.txt", "/nested/deep/moved.txt")):
            status, response = self.api("PATCH", "/api/resources", token, {"action": action, "items": [{"fromSource": name, "fromPath": source, "toSource": name, "toPath": destination}]})
            assert status == 200 and len(json.loads(response).get("succeeded", [])) == 1, f"In-scope {action} failed"
        resource("DELETE", "/nested/deep/moved.txt")
        resource("POST", "/preview.png", base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aL1sAAAAASUVORK5CYII="))
        print("PASS", name, "uploads, nested ACL inheritance, overwrite-by-rename and local-owner interoperability", flush=True)

    def isolation_checks(self, sessions):
        for name, token in sessions.items():
            other = next(user for user in sessions if user != name)
            foreign_path = f"/{other}-private-needle.txt"
            (self.docs[name] / "escape.txt").symlink_to("/documents/" + other + foreign_path)
            (self.docs[name] / "escape.png").symlink_to("/documents/" + other + "/preview.png")
            (self.docs[name] / "config.png").symlink_to("/fixture/config.yaml")
            status, body = self.api("GET", "/api/resources/download?" + urllib.parse.urlencode({"source": name, "file": "/retained.txt"}), token)
            assert status == 200 and body == b"retained-owner-access", f"Positive download failed: {status}"
            status, _ = self.api("GET", "/api/resources/preview?" + urllib.parse.urlencode({"source": name, "path": "/preview.png", "size": "small"}), token)
            assert status == 200, f"Positive preview failed: {status}"
            cases = [
                ("/api/resources", {"source": other, "path": "/"}),
                ("/api/resources/download", {"source": other, "file": foreign_path}),
                ("/api/resources/preview", {"source": other, "path": "/preview.png", "size": "small"}),
                ("/api/resources/download", {"source": name, "file": "/escape.txt"}),
                ("/api/resources/preview", {"source": name, "path": "/escape.png", "size": "small"}),
                ("/api/resources/preview", {"source": name, "path": "/config.png", "size": "small"}),
                ("/api/resources", {"source": name, "path": "/../" + other + foreign_path}),
                ("/api/resources/download", {"source": name, "file": "/../" + other + foreign_path}),
            ]
            for endpoint, query in cases:
                status, body = self.api("GET", endpoint + "?" + urllib.parse.urlencode(query), token)
                assert status in (400, 401, 403, 404), f"Isolation denied read failed: {endpoint}, {status}"
                assert (other + "-private-payload").encode() not in body
            for method in ("POST", "PUT", "DELETE"):
                status, _ = self.api(method, "/api/resources?" + urllib.parse.urlencode({"source": name, "path": "/escape.txt", "override": "true"}), token, b"forbidden")
                if method == "DELETE" and status == 200:
                    # Removing the link itself is an in-scope operation; the
                    # foreign target must remain untouched (checked below).
                    assert not os.path.lexists(self.docs[name] / "escape.txt")
                else:
                    assert status in (400, 403, 404), f"Symlink mutation was not denied: {method}, {status}"
            for action in ("copy", "move"):
                status, body = self.api("PATCH", "/api/resources", token, {"action": action, "items": [{"fromSource": name, "fromPath": "/retained.txt", "toSource": other, "toPath": "/forbidden.txt"}]})
                assert not json.loads(body).get("succeeded"), f"Cross-source {action} succeeded"
                assert not (self.docs[other] / "forbidden.txt").exists()
            assert (self.docs[other] / foreign_path.lstrip("/")).read_bytes() == (other + "-private-payload").encode()
            # Prove indexing/search is working before checking for omissions.
            for _ in range(50):
                status, body = self.api("GET", "/api/tools/search?" + urllib.parse.urlencode({"sources": name, "terms": "private-needle"}), token)
                if status == 200 and (name + "-private-needle").encode() in body:
                    break
                time.sleep(0.1)
            else:
                raise AssertionError(f"Positive own-source search did not return the fixture: status={status}, response={body[:500]!r}")
            status, body = self.api("GET", "/api/tools/search?" + urllib.parse.urlencode({"sources": name + "," + other, "terms": "private-needle"}), token)
            assert status in (200, 400, 403)
            assert (other + "-private-needle").encode() not in body, "Search exposed another source's metadata"
            status, body = self.api("GET", "/api/resources/download?" + urllib.parse.urlencode({"source": name, "file": "/", "algo": "zip"}), token)
            assert status == 200, f"Positive archive download failed: {status}"
            with zipfile.ZipFile(io.BytesIO(body)) as archive:
                assert not any(other + "-private-needle" in item for item in archive.namelist())
                for item in archive.namelist():
                    assert (other + "-private-payload").encode() not in archive.read(item), "Archive followed an escaping symlink"
            status, _ = self.api("POST", "/api/users", token, {"data": {"username": "forbidden", "loginMethod": "oidc"}})
            assert status == 403
            basic = {"Authorization": "Basic " + base64.b64encode((name + ":" + token).encode()).decode()}
            status, body = self.api("PROPFIND", "/dav/" + name + "/", basic)
            assert status in (404, 405) or (status == 200 and b"<html" in body.lower()), f"WebDAV unexpectedly handled PROPFIND: {status}"
        status, _ = self.api("GET", "/api/resources?source=alice&path=/")
        assert status == 401
        print("PASS two-user API isolation: traversal, symlinks, search, previews, downloads, archives and cross-source writes", flush=True)

    def proxy_checks(self, operator, sessions):
        route = globals().get("CADDY_ROUTE")
        if not route:
            raise AssertionError("Run with --remote to include the evaluated Caddy route")
        gate = self.root / "public-gate"
        gate.mkdir()
        route = route.replace("/run/filebrowser", str(gate)).replace("127.0.0.1:8092", f"127.0.0.1:{self.port}")
        output = command("systemctl", "show", "caddy.service", "--property=ExecStart", "--value").decode()
        binary = re.search(r"path=(/nix/store/[^ ;]+/bin/caddy)", output).group(1)
        port = free_port()
        config = self.root / "Caddyfile"
        config.write_text("{\n admin off\n auto_https off\n persist_config off\n}\nhttp://127.0.0.1:" + str(port) + " {\n" + route + "\n}\n")
        env = {**os.environ, "XDG_CONFIG_HOME": str(self.root / "caddy-config"), "XDG_DATA_HOME": str(self.root / "caddy-data")}
        log = self.root / "caddy.log"
        fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as stream:
            self.proxy = subprocess.Popen([binary, "run", "--config", str(config), "--adapter", "caddyfile"], env=env, stdout=stream, stderr=stream)
        from filebrowser_reconcile import request
        base = f"http://127.0.0.1:{port}"
        for _ in range(40):
            try:
                status, _ = request(base + "/health", "GET")
                assert status == 503
                break
            except urllib.error.URLError:
                time.sleep(0.1)
        else:
            raise AssertionError("Fixture Caddy did not start; inspect protected caddy.log")
        (gate / "ready").write_text("ready\n")
        status, _ = request(base + "/health", "GET")
        assert status == 200, f"Verified route health failed: {status}"
        status, _ = request(base + "/api/users?username=self", "GET", headers=operator)
        assert status == 401, f"Public machine assertion was not stripped: {status}"
        status, _ = request(base + "/public/api/resources", "GET")
        assert status == 404
        status, _ = request(base + "/api/resources?source=alice&path=/", "GET", headers={"Authorization": "Bearer " + sessions["alice"]})
        assert status == 200
        if globals().get("BROWSER_TESTS"):
            # Private IPC to the --remote controller, not an operational log.
            # The controller consumes this line without echoing its tokens.
            print("FIXTURE_BROWSER " + json.dumps({"proxy_port": port, "control_port": self.oidc.server_port, "nonce": self.control_nonce, "sessions": sessions}), flush=True)
            assert self.browser_done.wait(70) and self.browser_ok, "Chromium fixture checks failed"
        (gate / "ready").unlink()
        status, _ = request(base + "/health", "GET")
        assert status == 503
        print("PASS evaluated Caddy readiness gate, machine-header stripping and public-share denial", flush=True)

    def close(self):
        if self.proxy:
            self.proxy.terminate()
            self.proxy.wait(timeout=10)
        subprocess.run(["podman", "rm", "--force", self.name], capture_output=True, check=False)
        self.oidc.shutdown()
        self.oidc.server_close()
        self.thread.join()


def local_browser_checks(host, handoff):
    public_port, control_port = free_port(), free_port()
    forward = subprocess.Popen(["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ExitOnForwardFailure=yes", "-N", "-L", f"127.0.0.1:{public_port}:127.0.0.1:{handoff['proxy_port']}", "-L", f"127.0.0.1:{control_port}:127.0.0.1:{handoff['control_port']}", "--", host], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = False
    try:
        base = f"http://127.0.0.1:{public_port}"
        for _ in range(50):
            try:
                with urllib.request.urlopen(base + "/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except urllib.error.URLError:
                time.sleep(0.1)
        else:
            raise AssertionError("Fixture SSH forwarding did not become ready")
        result = subprocess.run(["node", str(Path(__file__).with_name("filebrowser_browser.mjs"))], input=json.dumps({"base": base, "sessions": handoff["sessions"]}), capture_output=True, text=True, timeout=45)
        print(result.stdout, end="", flush=True)
        if result.returncode:
            print(result.stderr[-2000:], flush=True)
        ok = result.returncode == 0
    finally:
        try:
            url = f"http://127.0.0.1:{control_port}/fixture-browser-done?ok={int(ok)}"
            req = urllib.request.Request(url, headers={"X-Fixture-Control": handoff["nonce"]})
            with urllib.request.urlopen(req, timeout=5) as response:
                response.read()
        finally:
            forward.terminate()
            forward.wait(timeout=10)
    return ok


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--remote":
        # Send only this fixture and its ACL helper, not a repository checkout
        # or vault. SSH host verification is mandatory; no remote files remain.
        root = Path(__file__).resolve().parents[1]
        helper = (root / "filebrowser_acl.py").read_text()
        host_helper = (root / "filebrowser_host.py").read_text()
        runtime_helper = (root / "filebrowser_runtime.py").read_text()
        reconcile_helper = (root / "filebrowser_reconcile.py").read_text()
        evaluated = command("nix-instantiate", "--eval", "--strict", "--json", str(root.parent / "tests/filebrowser-eval.nix"), "--arg", "enable", "true")
        route = json.loads(evaluated)["caddyRoute"]
        preamble = "CADDY_ROUTE = " + repr(route) + "\nBROWSER_TESTS = True\nimport types, sys\nm = types.ModuleType('filebrowser_acl')\nexec(" + repr(helper) + ", m.__dict__)\nsys.modules['filebrowser_acl'] = m\nh = types.ModuleType('filebrowser_host')\nexec(" + repr(host_helper) + ", h.__dict__)\nsys.modules['filebrowser_host'] = h\nr = types.ModuleType('filebrowser_runtime')\nexec(" + repr(runtime_helper) + ", r.__dict__)\nsys.modules['filebrowser_runtime'] = r\nb = types.ModuleType('filebrowser_reconcile')\nexec(" + repr(reconcile_helper) + ", b.__dict__)\nsys.modules['filebrowser_reconcile'] = b\nsys.argv = ['fixture']\n"
        process = subprocess.Popen(["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "--", sys.argv[2], "sudo -n python3 -"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        process.stdin.write(preamble + Path(__file__).read_text())
        process.stdin.close()
        for line in process.stdout:
            if line.startswith("FIXTURE_BROWSER "):
                local_browser_checks(sys.argv[2], json.loads(line.removeprefix("FIXTURE_BROWSER ")))
            else:
                print(line, end="", flush=True)
        raise SystemExit(process.wait())
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    if os.geteuid() != 0:
        raise SystemExit("Run as root on a disposable-capable host; no personal paths are accepted")
    for uid in (SERVICE, ALICE, BOB, UNRELATED):
        try:
            pwd.getpwuid(uid)
        except KeyError:
            continue
        raise SystemExit(f"Fixture UID {uid} is allocated; refusing to run")
    root = Path(tempfile.mkdtemp(prefix="filebrowser-fixture-", dir="/var/tmp"))
    os.chmod(root, 0o755)
    fixture = None
    try:
        fixture = Fixture(root)
        fixture.configure()
        fixture.start()
        fixture.test()
    except Exception as error:
        print(f"FAIL {type(error).__name__}: {error}", flush=True)
        print(f"Private fixture retained at {root}; container will be removed", flush=True)
        raise
    else:
        fixture.close()
        fixture = None
        shutil.rmtree(root)
        print("PASS disposable fixture cleaned", flush=True)
    finally:
        if fixture:
            fixture.close()


if __name__ == "__main__":
    main()
