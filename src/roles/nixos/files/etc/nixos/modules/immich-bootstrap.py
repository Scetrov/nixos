#!/usr/bin/env python3
"""Bootstrap/verify local Immich recovery using protected systemd credentials.

Use only Immich 3.3.1's native loopback APIs. Never reset an initialized instance,
rotate a password, print a response body, or pass credentials in arguments.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

BASE_URL = "http://127.0.0.1:3000/api"
# Do not inherit HTTP proxy settings for requests carrying recovery credentials.
OPENER = build_opener(ProxyHandler({}))


def request(path: str, body: dict | None = None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None if body is None else json.dumps(body).encode()
    with OPENER.open(Request(BASE_URL + path, data=data, headers=headers), timeout=10) as response:
        raw = response.read()
    return json.loads(raw) if raw else None


def credential(name: str) -> str:
    value = (Path(os.environ["CREDENTIALS_DIRECTORY"]) / name).read_text().strip()
    if not value or value.lower() in {"null", "placeholder", "changeme", "change-me", "replace-me"} or value.lower().endswith("_placeholder"):
        raise ValueError("invalid credential")
    return value


def bootstrap() -> None:
    email = credential("admin-email")
    password = credential("admin-password")
    if email != "git@scetrov.live" or len(password) < 32:
        raise ValueError("invalid recovery identity")
    config = None
    for attempt in range(60):
        try:
            config = request("/server/config")
            break
        except (URLError, TimeoutError):
            if attempt == 59:
                raise
            time.sleep(2)
    if not isinstance(config, dict) or not isinstance(config.get("isInitialized"), bool):
        raise ValueError("invalid server configuration response")
    if not config["isInitialized"]:
        request("/auth/admin-sign-up", {"email": email, "name": "Recovery Administrator", "password": password})
    # An existing mismatched administrator is an error, not authority to reset.
    login = request("/auth/login", {"email": email, "password": password})
    if not isinstance(login, dict) or login.get("isAdmin") is not True or login.get("userEmail") != email:
        raise ValueError("recovery account is not the expected administrator")
    request("/auth/logout", {}, token=login["accessToken"])


def main() -> int:
    try:
        bootstrap()
    except (OSError, ValueError, KeyError, TypeError, HTTPError, URLError, TimeoutError):
        print("Immich recovery bootstrap/verification failed; inspect local account state without resetting storage.", file=sys.stderr)
        return 1
    print("Immich local administrator recovery verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
