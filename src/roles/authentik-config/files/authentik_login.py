#!/usr/bin/env python3
"""Authenticate to modern Authentik via flow-executor and return api_key + pk."""

import http.cookiejar
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

def main():
    if len(sys.argv) != 4:
        print("Usage: authentik_login.py <api_base_url> <username> <password>", file=sys.stderr)
        sys.exit(1)

    api_base = sys.argv[1].rstrip('/')
    username = sys.argv[2]
    password = sys.argv[3]
    flow_url = f"{api_base}/flows/executor/default-authentication-flow/"
    me_url = f"{api_base}/core/users/me/"
    insecure = os.environ.get("AUTHENTIK_LOGIN_INSECURE", "0") == "1"
    ssl_context = ssl._create_unverified_context() if insecure else None

    # Set up cookie jar for session persistence
    cj = http.cookiejar.CookieJar()
    handlers = [urllib.request.HTTPCookieProcessor(cj)]
    if ssl_context is not None:
        handlers.append(urllib.request.HTTPSHandler(context=ssl_context))
    opener = urllib.request.build_opener(*handlers)

    headers = {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
    }

    # Stage 1: Identification
    data = json.dumps({"uid_field": username}).encode()
    req = urllib.request.Request(flow_url, data=data, headers=headers, method='POST')
    resp = opener.open(req)
    resp.read()

    # Stage 2: Password
    data = json.dumps({"password": password}).encode()
    req = urllib.request.Request(flow_url, data=data, headers=headers, method='POST')
    resp = opener.open(req)
    resp.read()

    # Stage 3: Get user info + API key
    req = urllib.request.Request(me_url, headers=headers, method='GET')
    resp = opener.open(req)
    body = json.loads(resp.read().decode())

    api_key = body.get('api_key', '')
    pk = body.get('pk', '')
    if not api_key or not pk:
        print(json.dumps({"error": "Missing api_key or pk in response", "keys": list(body.keys())}))
        sys.exit(1)

    print(json.dumps({"api_key": api_key, "pk": pk}))

if __name__ == '__main__':
    try:
        main()
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode(errors="replace")
        print(json.dumps({"error": f"HTTP {exc.code}", "body": response_body}), file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
