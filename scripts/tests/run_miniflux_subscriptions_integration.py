#!/usr/bin/env python3
"""OPT-IN Podman integration test. Needs approved runtime/network + OpenSSL.

Uses disposable OIDC, memory-only PostgreSQL and loopback-published ports.
Never accepts a production endpoint or credentials. Removes its own pod on exit.
Run: nix-shell -p openssl --run 'python3 scripts/tests/run_miniflux_subscriptions_integration.py'
"""
from http.cookiejar import CookieJar
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPCookieProcessor, ProxyHandler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import miniflux_subscriptions as sync

IMAGES = {
    "app": "docker.io/miniflux/miniflux:2.3.3@sha256:49d7b60987616387c306a8023087b31f2c9b7b21288b523026cb04058e8b6dbb",
    "db": "docker.io/library/postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24",
    "fixture": "docker.io/library/python:3.14-alpine@sha256:f6a589d43c42b9e7f7dc67a12d37132491f362859a5d750607710cc56da3bc72",
}


def run(*args, data=None):
    result = subprocess.run(args, input=data, capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed (details suppressed to protect test credentials)")
    return result.stdout


def integers(der):
    def item(offset):
        tag, length = der[offset], der[offset + 1]
        offset += 2
        if length & 128:
            count = length & 127
            length = int.from_bytes(der[offset:offset + count], "big")
            offset += count
        return tag, offset, offset + length
    _, offset, end = item(0)
    values = []
    while offset < end:
        tag, start, offset = item(offset)
        assert tag == 2
        values.append(int.from_bytes(der[start:offset], "big"))
    return values


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Inputs(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.fields = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and "name" in attrs:
            self.fields[attrs["name"]] = attrs.get("value", "")


def bootstrap(base, credential):
    browser = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))
    browser.open(base + "/oauth2/oidc/redirect", timeout=30).read()
    form = browser.open(base + "/keys/create", timeout=30).read().decode()
    fields = Inputs(form).fields
    fields["description"] = "Disposable integration test"
    page = browser.open(Request(base + "/keys/save", data=urlencode(fields).encode()), timeout=30).read().decode()
    for candidate in set(re.findall(r"\b[0-9a-f]{64}\b", page)):
        credential.write_text(candidate)
        credential.chmod(0o600)
        try:
            client = sync.API(base, credential)
            me = client.request("GET", "/v1/me")
            assert not me["is_admin"]
            return client, me["username"]
        except sync.SyncError:
            pass
    raise RuntimeError("OIDC personal-token bootstrap failed (no credentials printed)")


def wait_ready(url):
    for _ in range(90):
        try:
            build_opener(ProxyHandler({})).open(url, timeout=2).close()
            return
        except (OSError, HTTPError, URLError):
            time.sleep(1)
    raise RuntimeError("disposable service readiness failed")


def main():
    name = "miniflux-subscriptions-test-" + secrets.token_hex(4)
    app_port, fixture_port = free_port(), free_port()
    base = f"http://127.0.0.1:{app_port}"
    issuer = f"http://127.0.0.1:{fixture_port}"
    evidence = {"images": IMAGES, "checks": {}, "publisher_ingestion": {}}
    quiet = print  # Reconciler emits only sanitized catalogue diagnostics.
    with tempfile.TemporaryDirectory(prefix=name) as directory:
        directory = Path(directory)
        pem = run("openssl", "genrsa", "-traditional", "2048")
        der = run("openssl", "rsa", "-traditional", "-outform", "DER", data=pem)
        _, n, _, d, *_ = integers(der)
        (directory / "key.json").write_text(json.dumps({"n": n, "d": d}))
        (directory / "key.json").chmod(0o600)
        fixture = Path(__file__).with_name("miniflux_test_identity.py")
        (directory / "fixture.py").write_bytes(fixture.read_bytes())
        try:
            run("podman", "pod", "create", "--name", name,
                "--publish", f"127.0.0.1:{app_port}:{app_port}",
                "--publish", f"127.0.0.1:{fixture_port}:{fixture_port}")
            run("podman", "run", "-d", "--name", name + "-fixture", "--pod", name,
                "--volume", f"{directory}:/fixture:ro,Z", IMAGES["fixture"],
                "python", "/fixture/fixture.py", str(fixture_port), "/fixture/key.json")
            wait_ready(issuer + "/.well-known/openid-configuration")

            def start_reader():
                run("podman", "run", "-d", "--name", name + "-db", "--pod", name,
                    "--tmpfs", "/var/lib/postgresql/data:rw,size=256m",
                    "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "-e", "POSTGRES_DB=miniflux",
                    IMAGES["db"], "postgres", "-c", "listen_addresses=127.0.0.1")
                for _ in range(60):
                    ready = subprocess.run(["podman", "exec", name + "-db", "pg_isready", "-q"], capture_output=True)
                    if ready.returncode == 0:
                        break
                    time.sleep(1)
                run("podman", "run", "-d", "--name", name + "-app", "--pod", name,
                    "-e", "DATABASE_URL=postgres://postgres@127.0.0.1/miniflux?sslmode=disable",
                    "-e", f"LISTEN_ADDR=0.0.0.0:{app_port}", "-e", f"BASE_URL={base}",
                    "-e", "RUN_MIGRATIONS=1", "-e", "CREATE_ADMIN=0", "-e", "DISABLE_LOCAL_AUTH=1",
                    "-e", "OAUTH2_PROVIDER=oidc", "-e", "OAUTH2_CLIENT_ID=fixture-client",
                    "-e", "OAUTH2_CLIENT_SECRET=disposable-fixture-only",
                    "-e", f"OAUTH2_OIDC_DISCOVERY_ENDPOINT={issuer}",
                    "-e", f"OAUTH2_REDIRECT_URL={base}/oauth2/oidc/callback",
                    # Loopback fixtures only: never copy this override into production.
                    "-e", "FETCHER_ALLOW_PRIVATE_NETWORKS=1",
                    "-e", "OAUTH2_USER_CREATION=1", "-e", "LOG_LEVEL=error", IMAGES["app"])
                wait_ready(base + "/healthcheck")

            start_reader()
            credential = directory / "token"
            client, operator = bootstrap(base, credential)
            evidence["checks"]["oidc_non_admin_bootstrap"] = True
            entries = [{"title": "Fixture", "category": "Integration", "url": issuer + "/feed", "enabled": True}]
            assert sync.reconcile(client, entries, operator, apply=False, emit=quiet) == 0
            assert client.request("GET", "/v1/feeds") == []
            initial_result = sync.reconcile(client, entries, operator, apply=True, emit=quiet)
            if initial_result:
                # This pod contains only generated test identity data, never production credentials.
                logged = subprocess.run(["podman", "logs", name + "-app"], capture_output=True, text=True, timeout=15)
                logs = (logged.stdout + logged.stderr).replace(client.token, "<redacted>")
                print(logs[-4000:])
            assert initial_result == 0
            before = client.request("GET", "/v1/feeds")
            assert len(before) == 1
            calls = []
            request = client.request
            def recorded(method, path, payload=None):
                calls.append(method)
                return request(method, path, payload)
            client.request = recorded
            assert sync.reconcile(client, entries, operator, apply=True, emit=quiet) == 0
            assert set(calls) == {"GET"}
            evidence["checks"]["initial_creation_and_repeat_zero_writes"] = True
            mixed = [dict(entries[0], url=issuer + "/missing"), dict(entries[0], url=issuer + "/large-feed")]
            assert sync.reconcile(client, mixed, operator, apply=True, emit=quiet) == 1
            assert len(client.request("GET", "/v1/feeds")) == 2
            evidence["checks"]["partial_failure_and_large_10mb_feed"] = True
            exported = sync.export_opml(entries)
            req = Request(base + "/v1/import", data=exported, method="POST",
                          headers={"X-Auth-Token": client.token, "Content-Type": "text/xml"})
            build_opener(ProxyHandler({}), sync.RefuseRedirect()).open(req, timeout=90).read()
            evidence["checks"]["opml_import"] = True
            catalogue = sync.load_catalogue(Path(__file__).resolve().parents[2] / "config/miniflux/feeds.json")
            for feed in (e for e in catalogue if e["category"] == "Podcasts"):
                result = sync.reconcile(client, [feed], operator, apply=True, emit=quiet)
                evidence["publisher_ingestion"][feed["url"]] = "created" if result == 0 else "failed; no TLS bypass or substitution"
            old_token = credential.read_text()
            run("podman", "rm", "-f", name + "-app", name + "-db")
            start_reader()  # Fresh tmpfs database; old personal token must fail.
            try:
                sync.API(base, credential).request("GET", "/v1/me")
                raise AssertionError("old token survived database loss")
            except sync.FatalError:
                pass
            replacement, operator = bootstrap(base, credential)
            assert credential.read_text() != old_token
            assert sync.reconcile(replacement, entries, operator, apply=True, emit=quiet) == 0
            evidence["checks"]["database_loss_replacement_oidc_token_restore"] = True
            print(json.dumps(evidence, indent=2))
        finally:
            run("podman", "pod", "rm", "-f", name)


if __name__ == "__main__":
    main()
