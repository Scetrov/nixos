#!/usr/bin/env python3
"""Explicit, additive Miniflux subscription management (standard library only)."""
from __future__ import annotations

import argparse
import fcntl
from http.client import HTTPException
import json
import os
from pathlib import Path
import signal
import stat
import struct
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import re
import sys
from urllib.parse import parse_qsl, unquote, urlsplit
import xml.etree.ElementTree as ET


class SyncError(Exception):
    """A sanitized operator-facing error; never include remote response bodies."""


def public_url(value):
    """Validate public catalogue syntax, not outbound network reachability."""
    if not isinstance(value, str) or not value or re.search(r"[\s\x00-\x1f\x7f]", value):
        raise SyncError("invalid URL")
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.fragment or parsed.port == 0):
            raise ValueError
        # Public feeds have no need for bearer tokens, signed URLs or API keys.
        sensitive = re.compile(r"token|secret|password|passwd|credential|signature|api.?key|authorization|^key$|^auth$|^sig$|access.?key", re.I)
        if sensitive.search(unquote(parsed.path)) or any(
            sensitive.search(k) for k, _ in parse_qsl(parsed.query, keep_blank_values=True)
        ):
            raise ValueError
    except ValueError:
        raise SyncError("invalid or credential-bearing URL") from None
    return value


def load_catalogue(path):
    try:
        entries = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SyncError("cannot read valid catalogue JSON") from None
    if not isinstance(entries, list):
        raise SyncError("catalogue must be a list")
    owned = set()
    required = {"title", "category", "url", "enabled"}
    for number, entry in enumerate(entries, 1):
        try:
            if not isinstance(entry, dict) or not required <= entry.keys() or entry.keys() - required - {"aliases", "reason"}:
                raise SyncError("invalid fields")
            for field in ("title", "category"):
                value = entry[field]
                if (not isinstance(value, str) or not value.strip() or value != value.strip()
                        or any(ord(c) < 32 or ord(c) == 127 for c in value)):
                    raise SyncError("invalid title/category")
            if type(entry["enabled"]) is not bool:
                raise SyncError("enabled must be boolean")
            if "reason" in entry or not entry["enabled"]:
                if not isinstance(entry.get("reason"), str) or not entry["reason"].strip():
                    raise SyncError("disabled entries need a reason")
            aliases = entry.get("aliases", [])
            if not isinstance(aliases, list):
                raise SyncError("aliases must be a list")
            for url in [entry["url"], *aliases]:
                public_url(url)
                if url in owned:
                    raise SyncError("duplicate URL/alias ownership")
                owned.add(url)
        except SyncError as error:
            raise SyncError(f"entry {number}: {error}") from None
    return entries


def export_opml(entries):
    root = ET.Element("opml", version="2.0")
    ET.SubElement(ET.SubElement(root, "head"), "title").text = "Miniflux subscriptions"
    body = ET.SubElement(root, "body")
    enabled = [entry for entry in entries if entry["enabled"]]
    for category in sorted({entry["category"] for entry in enabled}):
        group = ET.SubElement(body, "outline", text=category, title=category)
        for entry in sorted((e for e in enabled if e["category"] == category), key=lambda e: (e["title"], e["url"])):
            ET.SubElement(group, "outline", type="rss", text=entry["title"], title=entry["title"], xmlUrl=entry["url"])
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


class FatalError(SyncError):
    """Configuration, authentication or inventory errors stop all writes."""


class RefuseRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise FatalError("API redirect refused")


def private_credential(descriptor, metadata):
    if not stat.S_ISREG(metadata.st_mode):
        return False
    if not metadata.st_mode & 0o077:
        return True
    # systemd LoadCredential retains root ownership and grants only the service
    # UID read access with a POSIX ACL. In that case 0440's group bits are the
    # ACL mask, not owning-group permissions. Do not accept ordinary group read.
    if stat.S_IMODE(metadata.st_mode) != 0o440 or metadata.st_uid != 0:
        return False
    undefined = 0xffffffff
    entries = [(1, 4, undefined), (2, 4, os.geteuid()), (4, 0, undefined),
               (16, 4, undefined), (32, 0, undefined)]
    expected = struct.pack("<I", 2) + b"".join(struct.pack("<HHI", *e) for e in entries)
    try:
        return os.getxattr(descriptor, "system.posix_acl_access") == expected
    except OSError:
        return False


class API:
    def __init__(self, base_url, credential_file, timeout=60):
        parsed = urlsplit(base_url)
        if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.path not in ("", "/")
                or parsed.query or parsed.fragment or parsed.username is not None):
            raise FatalError("API must use the IPv4 loopback HTTP endpoint")
        try:
            with Path(credential_file).open("rb") as credential:
                metadata = os.fstat(credential.fileno())
                if not private_credential(credential.fileno(), metadata):
                    raise FatalError("credential must be a private regular file")
                token = credential.read(4097).decode("ascii").strip()
            if not token or len(token) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token):
                raise ValueError
        except (OSError, ValueError):
            raise FatalError("cannot read a valid private API credential") from None
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        # Never inherit a proxy for the credential-bearing loopback connection.
        self.opener = build_opener(ProxyHandler({}), RefuseRedirect())

    def request(self, method, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(self.base_url + path, data=data, method=method,
                          headers={"X-Auth-Token": self.token, "Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                body = response.read(16 * 1024 * 1024 + 1)
                if len(body) > 16 * 1024 * 1024:
                    raise SyncError("API response exceeds limit")
                return json.loads(body)
        except HTTPError as error:
            if error.code in (401, 403):
                raise FatalError("API authentication rejected; sign in through OIDC and enroll a valid personal token") from None
            if 300 <= error.code < 400:
                raise FatalError("API redirect refused") from None
            raise SyncError(f"API request failed (HTTP {error.code})") from None
        except (URLError, OSError, ValueError, HTTPException):
            raise SyncError("API transport or JSON response failure") from None


def inventory(api, operator):
    try:
        me = api.request("GET", "/v1/me")
        if not isinstance(me, dict) or me.get("username") != operator:
            raise FatalError("API operator identity mismatch")
        categories = api.request("GET", "/v1/categories")
        feeds = api.request("GET", "/v1/feeds")
        for rows, field in ((categories, "title"), (feeds, "feed_url")):
            if not isinstance(rows, list) or any(
                not isinstance(row, dict) or type(row.get("id")) is not int
                or row["id"] <= 0 or not isinstance(row.get(field), str) for row in rows
            ):
                raise FatalError("invalid API inventory")
            if len({row["id"] for row in rows}) != len(rows):
                raise FatalError("duplicate API inventory IDs")
        return categories, feeds
    except SyncError as error:
        raise FatalError(str(error)) from None


def matches(entry, feeds):
    urls = {entry["url"], *entry.get("aliases", [])}
    return [feed for feed in feeds if feed["feed_url"] in urls]


def reconcile(api, entries, operator, apply=False, emit=print):
    categories, feeds = inventory(api, operator)
    failed = 0
    for entry in sorted((e for e in entries if e["enabled"]), key=lambda e: (e["category"], e["url"])):
        url = entry["url"]  # Only validated public catalogue data enters diagnostics.
        found = matches(entry, feeds)
        if len(found) > 1:
            emit(f"failed {url}: ambiguous existing subscriptions")
            failed += 1
            continue
        if found:
            emit(f"present {url}")
            continue
        if not apply:
            emit(f"missing {url}: would create feed and category if needed")
            continue
        try:
            category_matches = [c for c in categories if c["title"] == entry["category"]]
            if len(category_matches) > 1:
                raise SyncError("ambiguous existing categories")
            if not category_matches:
                try:
                    api.request("POST", "/v1/categories", {"title": entry["category"]})
                except FatalError:
                    raise
                except SyncError:
                    pass  # Never retry POST: establish the result by reading inventory.
                categories, feeds = inventory(api, operator)
                category_matches = [c for c in categories if c["title"] == entry["category"]]
                if len(category_matches) != 1:
                    raise SyncError("category creation unresolved; rerun after review")
            # A concurrent UI action may have added the feed during category creation.
            found = matches(entry, feeds)
            if len(found) > 1:
                raise SyncError("ambiguous existing subscriptions")
            if found:
                emit(f"present {url}")
                continue
            result = None
            try:
                result = api.request("POST", "/v1/feeds", {
                    "feed_url": url, "category_id": category_matches[0]["id"],
                })
            except FatalError:
                raise
            except SyncError:
                pass
            categories, feeds = inventory(api, operator)
            found = matches(entry, feeds)
            if len(found) == 1:
                emit(f"created {url}")
            elif isinstance(result, dict) and any(f["id"] == result.get("feed_id") for f in feeds):
                raise SyncError("unexpected stored canonical URL; review API inventory and add an explicit alias")
            else:
                raise SyncError("feed creation unresolved; inspect Miniflux and rerun after review")
        except FatalError:
            raise
        except SyncError as error:
            failed += 1
            emit(f"failed {url}: {error}")
    emit(f"summary: {failed} failed; mode={'apply' if apply else 'plan'}")
    return 1 if failed else 0


def deadline_expired(signum, frame):
    raise FatalError("execution deadline exceeded; review inventory before rerunning")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "export", "plan", "apply"))
    parser.add_argument("--catalogue", type=Path, default=Path(__file__).resolve().parents[1] / "config/miniflux/feeds.json")
    parser.add_argument("--credential-file", type=Path)
    parser.add_argument("--operator")
    parser.add_argument("--api-url", default="http://127.0.0.1:8091")
    parser.add_argument("--lock-file", type=Path, default=Path("/run/miniflux-subscriptions/sync.lock"))
    args = parser.parse_args()
    try:
        entries = load_catalogue(args.catalogue)
        if args.command == "export":
            sys.stdout.buffer.write(export_opml(entries))
        elif args.command == "validate":
            print(f"valid: {len(entries)} entries; {sum(e['enabled'] for e in entries)} enabled")
        else:
            if not args.credential_file or not args.operator:
                raise FatalError("plan/apply require --credential-file and --operator")
            # Shared lock and whole-run deadline apply equally to plan and apply.
            signal.signal(signal.SIGALRM, deadline_expired)
            signal.alarm(2400)
            try:
                with args.lock_file.open("a") as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return reconcile(API(args.api_url, args.credential_file), entries,
                                     args.operator, apply=args.command == "apply")
            except BlockingIOError:
                raise FatalError("another plan/apply is running") from None
            except OSError:
                raise FatalError("cannot open the shared plan/apply lock") from None
            finally:
                signal.alarm(0)
        return 0
    except SyncError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
