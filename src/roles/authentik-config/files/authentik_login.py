#!/usr/bin/env python3
"""Authenticate to Authentik via the documented flow-executor challenge loop."""

import http.cookiejar
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_TIMEOUT = 30
MAX_CHALLENGE_STEPS = 8


def find_cookie(cookie_jar, name):
    for cookie in cookie_jar:
        if cookie.name == name:
            return cookie.value
    return ""


def build_cookie_header(cookie_jar):
    return "; ".join(f"{cookie.name}={cookie.value}" for cookie in cookie_jar)


def request_json(opener, url, method, headers, body=None):
    data = None
    if body is not None:
        data = json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with opener.open(request, timeout=DEFAULT_TIMEOUT) as response:
        payload = response.read().decode()
    return json.loads(payload) if payload else {}


def fail(error, **details):
    payload = {"error": error}
    payload.update(details)
    print(json.dumps(payload), file=sys.stderr)
    sys.exit(1)


def solve_challenge(challenge, username, password):
    component = challenge.get("component")
    if component == "ak-stage-identification":
        response = {
            "component": component,
            "uid_field": username,
        }
        if challenge.get("password_fields"):
            response["password"] = password
        return response
    if component == "ak-stage-password":
        return {
            "component": component,
            "password": password,
        }
    if component == "ak-stage-user-login":
        return {
            "component": component,
            "remember_me": True,
        }
    if component == "xak-flow-redirect":
        return None
    if component == "ak-stage-access-denied":
        fail("Authentication flow denied access")
    # Challenges and component names are server input, not safe diagnostics.
    # In particular, never echo assertions, recovery links or response_errors.
    fail("Unsupported authentication challenge; interactive authentication may be required")

def main():
    if len(sys.argv) not in (4, 5):
        print(
            "Usage: authentik_login.py <api_base_url> <username> <password> [flow_slug]",
            file=sys.stderr,
        )
        sys.exit(1)

    api_base = sys.argv[1].rstrip('/')
    username = sys.argv[2]
    password = sys.argv[3]
    flow_slug = sys.argv[4] if len(sys.argv) == 5 else "default-authentication-flow"
    escaped_flow_slug = urllib.parse.quote(flow_slug, safe="")
    flow_url = (
        f"{api_base}/flows/executor/{escaped_flow_slug}/"
        "?query="
    )
    me_url = f"{api_base}/core/users/me/"
    ui_base = api_base.rsplit('/api/v3', 1)[0]
    browser_flow_url = f"{ui_base}/if/flow/{escaped_flow_slug}/"
    insecure = os.environ.get("AUTHENTIK_LOGIN_INSECURE", "0") == "1"
    if insecure:
        print(
            "WARNING: AUTHENTIK_LOGIN_INSECURE=1 - TLS certificate verification is DISABLED; "
            "use only for local self-signed Authentik deployments",
            file=sys.stderr,
        )
    ssl_context = ssl._create_unverified_context() if insecure else None  # nosemgrep: unverified-ssl-context -- explicit opt-in for self-signed local Authentik; warned to stderr

    # Set up cookie jar for session persistence
    cj = http.cookiejar.CookieJar()
    handlers = [urllib.request.HTTPCookieProcessor(cj)]
    if ssl_context is not None:
        handlers.append(urllib.request.HTTPSHandler(context=ssl_context))
    opener = urllib.request.build_opener(*handlers)

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
    }

    challenge = request_json(opener, flow_url, 'GET', headers)
    for _ in range(MAX_CHALLENGE_STEPS):
        answer = solve_challenge(challenge, username, password)
        if answer is None:
            break
        challenge = request_json(opener, flow_url, 'POST', headers, body=answer)
    else:
        fail("Authentication flow exceeded maximum supported steps")

    body = request_json(opener, me_url, 'GET', headers)

    user = body.get('user', {})

    # A browser flow page will mint the CSRF cookie if the API executor path didn't.
    csrf_token = find_cookie(cj, 'authentik_csrf') or find_cookie(cj, 'csrftoken')
    if not csrf_token:
        browser_headers = {'Accept': 'text/html'}
        request = urllib.request.Request(browser_flow_url, headers=browser_headers, method='GET')
        with opener.open(request, timeout=DEFAULT_TIMEOUT) as response:
            response.read()
        csrf_token = find_cookie(cj, 'authentik_csrf') or find_cookie(cj, 'csrftoken')

    cookie_header = build_cookie_header(cj)
    if not cookie_header or not csrf_token or not user.get('pk'):
        fail("Missing session cookies, CSRF token, or authenticated user")

    print(json.dumps({
        "cookie_header": cookie_header,
        "csrf_token": csrf_token,
        "user": user,
        "flow_slug": flow_slug,
    }))

def run():
    """Keep command failures machine-readable without disclosing response data."""
    try:
        main()
    except urllib.error.HTTPError as exc:
        status = exc.code
        # Close without reading/logging the body. Python can otherwise emit a
        # ResourceWarning containing the HTTPError's untrusted reason string.
        exc.close()
        fail(f"Authentication request failed: HTTP {status}")
    except Exception:  # noqa: BLE001
        # Exception strings can contain request URLs, credentials or payloads.
        fail("Authentication request failed unexpectedly")


if __name__ == '__main__':
    run()
