"""Disposable integration-only OIDC issuer and feed fixtures. Never deploy."""
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sys
import time
from urllib.parse import parse_qs, urlencode, urlsplit


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def number(value):
    return b64(value.to_bytes((value.bit_length() + 7) // 8, "big"))


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not log OAuth codes, tokens or fixture request arguments.

    def respond(self, value, content_type="application/json", status=200):
        data = json.dumps(value).encode() if content_type == "application/json" else value
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlsplit(self.path).path
        issuer = self.server.issuer
        if path == "/.well-known/openid-configuration":
            self.respond({"issuer": issuer, "authorization_endpoint": issuer + "/authorize",
                          "token_endpoint": issuer + "/token", "jwks_uri": issuer + "/jwks",
                          "userinfo_endpoint": issuer + "/userinfo", "response_types_supported": ["code"],
                          "subject_types_supported": ["public"], "id_token_signing_alg_values_supported": ["RS256"]})
        elif path == "/jwks":
            self.respond({"keys": [{"kty": "RSA", "use": "sig", "kid": "disposable",
                                    "alg": "RS256", "n": number(self.server.n), "e": "AQAB"}]})
        elif path == "/authorize":
            query = parse_qs(urlsplit(self.path).query)
            self.server.nonce = query.get("nonce", [""])[0]
            self.send_response(302)
            self.send_header("Location", query["redirect_uri"][0] + "?" + urlencode({"code": "fixture-code", "state": query["state"][0]}))
            self.end_headers()
        elif path == "/userinfo":
            self.respond(self.profile())
        elif path in ("/feed", "/large-feed"):
            count = 500 if path == "/large-feed" else 2
            # Exercise real parser/body limits without implementing a feed client.
            content = "x" * 20000 if count == 500 else "fixture"
            items = "".join(f"<item><guid>{i}</guid><title>Article {i}</title><link>https://example.invalid/{i}</link><description>{content}</description></item>" for i in range(count))
            self.respond(("<rss version='2.0'><channel><title>Fixture</title><link>https://example.invalid</link><description>Test</description>" + items + "</channel></rss>").encode(), "application/rss+xml")
        else:
            self.respond(b"not a feed", "text/plain", 404)

    def profile(self):
        return {"sub": "disposable-reader", "preferred_username": "test-reader",
                "email": "test-reader@example.invalid", "email_verified": True, "name": "test-reader"}

    def do_POST(self):
        if self.path != "/token":
            self.respond({}, status=404)
            return
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        claims = dict(self.profile(), iss=self.server.issuer, aud="fixture-client", iat=int(time.time()), exp=int(time.time()) + 300)
        if self.server.nonce:
            claims["nonce"] = self.server.nonce
        message = (b64(json.dumps({"alg": "RS256", "kid": "disposable"}).encode()) + "." + b64(json.dumps(claims).encode())).encode()
        # Test fixture only: PKCS#1 v1.5 signing with an ephemeral OpenSSL key.
        digest = bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(message).digest()
        size = (self.server.n.bit_length() + 7) // 8
        encoded = b"\x00\x01" + b"\xff" * (size - len(digest) - 3) + b"\x00" + digest
        signature = pow(int.from_bytes(encoded, "big"), self.server.d, self.server.n).to_bytes(size, "big")
        self.respond({"access_token": "disposable-access", "token_type": "Bearer", "expires_in": 300,
                      "id_token": message.decode() + "." + b64(signature)})


if __name__ == "__main__":
    port = int(sys.argv[1])
    key = json.loads(Path(sys.argv[2]).read_text())
    server = HTTPServer(("0.0.0.0", port), Fixture)
    server.issuer = f"http://127.0.0.1:{port}"
    server.n, server.d = key["n"], key["d"]
    server.nonce = ""
    server.serve_forever()
