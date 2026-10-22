"""Discover GitHub sources and reconcile private native Forgejo pull mirrors.

Standard library only. Never print HTTP bodies, URLs, exception details or tokens.
Namespaces must be explicitly authorized by stable Forgejo organization ID.
"""

import argparse
import datetime
import fcntl
import fnmatch
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request


class MirrorError(Exception):
    """Only fixed, non-sensitive diagnostic codes belong in this exception."""

    def __init__(self, code, age=None):
        super().__init__(code)
        self.age = age


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class API:
    def __init__(self, base, token="", sleep=time.sleep):
        self.base = base.rstrip("/")
        self.token = token
        self.sleep = sleep
        self.opener = urllib.request.build_opener(NoRedirect)

    def request(self, method, path, payload=None):
        if not path.startswith("/") or path.startswith("//"):
            raise MirrorError("invalid_api_path")
        headers = {"Accept": "application/json", "User-Agent": "forgejo-mirrors"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode()
        # Never blindly retry POST: an import may have committed despite timeout.
        attempts = 3 if method == "GET" else 1
        for attempt in range(attempts):
            req = urllib.request.Request(self.base + path, data, headers, method=method)
            try:
                with self.opener.open(req, timeout=30) as response:
                    body = response.read(16 * 1024 * 1024 + 1)
                    if len(body) > 16 * 1024 * 1024:
                        raise MirrorError("response_too_large")
                    return json.loads(body) if body else None
            except urllib.error.HTTPError as error:
                status = error.code
                limited = status == 429 or (status == 403 and (
                    error.headers.get("X-RateLimit-Remaining") == "0"
                    or error.headers.get("Retry-After") is not None))
                retry = limited or status in (500, 502, 503, 504)
                delay = 2 ** attempt
                try:
                    delay = max(delay, float(error.headers.get("Retry-After", "0")))
                    if limited and error.headers.get("X-RateLimit-Reset"):
                        delay = max(delay, float(error.headers["X-RateLimit-Reset"]) - time.time())
                except ValueError:
                    delay = 61
                error.close()
                if status == 404:
                    return None
                if not retry or attempt == attempts - 1 or delay > 60:
                    raise MirrorError("rate_limited" if limited else "http_" + str(status)) from None
                self.sleep(delay)
            except (OSError, urllib.error.URLError):
                if attempt == attempts - 1:
                    raise MirrorError("transport_failure") from None
                self.sleep(2 ** attempt)
            except (ValueError, UnicodeError):
                raise MirrorError("invalid_json") from None
        raise MirrorError("request_failed")

    def pages(self, path):
        result = []
        separator = "&" if "?" in path else "?"
        for page in range(1, 1001):
            chunk = self.request("GET", f"{path}{separator}per_page=100&page={page}")
            if not isinstance(chunk, list):
                raise MirrorError("incomplete_discovery")
            result.extend(chunk)
            if len(chunk) < 100:
                return result
        raise MirrorError("pagination_limit")


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", value) or value in (".", ".."):
        raise MirrorError("invalid_identifier")
    return value


def snapshot(repo):
    return {
        "id": int(repo["id"]), "ownerId": int(repo["owner"]["id"]),
        "owner": identifier(repo["owner"]["login"]), "name": identifier(repo["name"]),
        "private": bool(repo["private"]), "fork": bool(repo["fork"]),
        "archived": bool(repo["archived"]),
    }


def atomic_write(path, content, mode=0o600):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_state(path):
    if not Path(path).exists():
        return {"version": 1, "sources": {}, "lastSuccess": 0}
    try:
        state = json.loads(Path(path).read_text())
        if state["version"] != 1 or not isinstance(state["sources"], dict):
            raise ValueError
        for key, entry in state["sources"].items():
            if str(entry["source"]["id"]) != key or not entry["marker"].startswith("managed-github-mirror:"):
                raise ValueError
            if not isinstance(entry["namespaceId"], int):
                raise ValueError
        return state
    except (KeyError, TypeError, ValueError):
        raise MirrorError("invalid_state") from None


class Reconciler:
    def __init__(self, config, github, forgejo, state, save, now=None):
        self.config, self.github, self.forgejo = config, github, forgejo
        self.state, self.save = state, save
        self.now = time.time() if now is None else now
        self.report_only = config.get("reportOnly", True)
        self.rows = []
        self.errors = 0
        self.sizes = {}

    def row(self, source, destination, status, **extra):
        row = {"source": source, "destination": destination, "status": status, **extra}
        self.rows.append(row)
        if status not in ("excluded", "planned", "healthy", "created"):
            self.errors += 1

    def discover(self):
        found = {}
        for policy in self.config["policies"]:
            owner = identifier(policy["owner"])
            namespace = identifier(policy["namespace"])
            try:
                user = self.github.request("GET", "/users/" + owner)
                if not user or user["id"] != policy["ownerId"]:
                    raise MirrorError("owner_identity_changed")
                if policy.get("includePrivate", False) and user["type"] != "Organization":
                    # /users/{owner}/repos never supplies private user repositories.
                    repos = self.github.pages("/user/repos?affiliation=owner,collaborator,organization_member")
                else:
                    kind = "orgs" if user["type"] == "Organization" else "users"
                    repos = self.github.pages(f"/{kind}/{owner}/repos?type=owner")
                for repo in repos:
                    source = snapshot(repo)
                    if source["ownerId"] != policy["ownerId"]:
                        continue
                    source_id = str(source["id"])
                    self.sizes[source_id] = max(0, int(repo.get("size", 0)))
                    if source_id in found:
                        raise MirrorError("duplicate_source_policy")
                    destination = namespace + "/" + source["name"]
                    reasons = []
                    if not fnmatch.fnmatchcase(source["name"].casefold(), policy["pattern"].casefold()):
                        reasons.append("pattern")
                    for field, option in [("private", "includePrivate"), ("fork", "includeForks"), ("archived", "includeArchived")]:
                        if source[field] and not policy.get(option, False):
                            reasons.append(field)
                    found[source_id] = (source, policy, reasons)
                    if reasons:
                        self.row(source, destination, "excluded", reasons=reasons,
                                 sizeKiB=self.sizes[source_id])
            except MirrorError as error:
                self.row({"owner": owner}, namespace, str(error))
        return found

    def check_destination(self, entry, repo):
        if not repo:
            raise MirrorError("destination_missing_review")
        if (not repo.get("private") or not repo.get("mirror")
                or repo.get("owner", {}).get("id") != entry["namespaceId"]):
            raise MirrorError("destination_boundary_review")
        if entry.get("destinationId"):
            if repo["id"] != entry["destinationId"]:
                raise MirrorError("destination_identity_review")
        elif repo.get("description") != entry["marker"]:
            raise MirrorError("destination_collision")
        # Compare a credential-free canonical source URL, not an authenticated remote.
        source = entry["source"]
        expected = f"https://github.com/{source['owner']}/{source['name']}.git"
        if repo.get("original_url", "").removesuffix(".git").casefold() != expected.removesuffix(".git").casefold():
            raise MirrorError("destination_source_review")

    def freshness(self, repo):
        try:
            stamp = datetime.datetime.fromisoformat(repo["mirror_updated"].replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                raise ValueError
            age = max(0, self.now - stamp.timestamp())
        except (KeyError, ValueError, TypeError):
            raise MirrorError("mirror_status_unknown") from None
        if age > self.config["staleAfterSeconds"]:
            raise MirrorError("mirror_stale", age)
        return age

    def converge(self, source, policy):
        key = str(source["id"])
        destination = policy["namespace"] + "/" + source["name"]
        entry = self.state["sources"].get(key)
        if entry:
            destination = entry["destination"]
            if entry["source"] != source or destination != policy["namespace"] + "/" + source["name"]:
                raise MirrorError("source_lifecycle_review")
            if entry["namespaceId"] != policy.get("namespaceId"):
                raise MirrorError("namespace_identity_review")
        org = self.forgejo.request("GET", "/orgs/" + identifier(policy["namespace"]))
        if (not org or not policy.get("namespaceId") or org["id"] != policy["namespaceId"]
                or org.get("visibility") != "private"):
            raise MirrorError("namespace_not_authorized")
        path = "/repos/" + destination
        repo = self.forgejo.request("GET", path)
        if repo:
            if not entry:
                raise MirrorError("destination_collision")
            self.check_destination(entry, repo)
            if not entry.get("destinationId") and not self.report_only:
                entry["destinationId"] = repo["id"]
                self.save()
            age = self.freshness(repo)
            self.row(source, destination, "healthy", ageSeconds=age)
            return
        if entry and entry.get("destinationId"):
            raise MirrorError("destination_missing_review")
        if self.report_only:
            self.row(source, destination, "planned")
            return
        if not self.config.get("lfsVerified", False):
            raise MirrorError("lfs_unverified")
        if source["private"] and not self.config.get("privateAuthVerified", False):
            raise MirrorError("private_auth_unverified")
        if entry:
            # A prior POST may still be importing. Never re-POST uncertain ownership.
            raise MirrorError("pending_import_review")
        entry = {
            "source": source, "destination": destination, "namespaceId": org["id"],
            "marker": "managed-github-mirror:" + secrets.token_hex(24),
        }
        self.state["sources"][key] = entry
        self.save()  # Durable intent BEFORE the only remote mutation.
        payload = {
            "service": "git", "clone_addr": f"https://github.com/{source['owner']}/{source['name']}.git",
            "repo_owner": policy["namespace"], "repo_name": source["name"],
            "private": True, "mirror": True, "mirror_interval": self.config["mirrorInterval"],
            "lfs": True, "description": entry["marker"],
        }
        if source["private"]:
            # Runtime secret in request body only, never URL, state, report or argv.
            if not self.github.token:
                raise MirrorError("private_token_missing")
            payload.update(auth_username="x-access-token", auth_password=self.github.token)
        repo = self.forgejo.request("POST", "/repos/migrate", payload)
        self.check_destination(entry, repo)
        entry["destinationId"] = repo["id"]
        self.save()
        self.row(source, destination, "created", ageSeconds=self.freshness(repo))

    def run(self):
        found = self.discover()
        # Managed sources absent from complete discovery are inspected by stable ID.
        # No source disappearance can authorize deletion or recreation.
        for key, entry in list(self.state["sources"].items()):
            if key not in found:
                status = "source_missing_or_inaccessible_review"
                try:
                    repo = self.github.request("GET", "/repositories/" + key)
                    if repo:
                        status = ("source_lifecycle_review" if snapshot(repo) != entry["source"]
                                  else "source_policy_review")
                except MirrorError:
                    status = "source_lookup_failed"
                self.row(entry["source"], entry["destination"], status)
            elif found[key][2]:
                self.row(entry["source"], entry["destination"], "source_eligibility_review")
        destinations = {}
        for key, (source, policy, reasons) in found.items():
            if reasons:
                continue
            target = (policy["namespace"] + "/" + source["name"]).casefold()
            destinations.setdefault(target, []).append(key)
        for key, (source, policy, reasons) in found.items():
            if reasons:
                continue
            destination = policy["namespace"] + "/" + source["name"]
            if len(destinations[destination.casefold()]) != 1:
                self.row(source, destination, "planned_destination_collision")
                continue
            try:
                self.converge(source, policy)
            except MirrorError as error:
                saved = self.state["sources"].get(key, {})
                extra = {"ageSeconds": error.age} if error.age is not None else {}
                self.row(source, saved.get("destination", destination), str(error), **extra)
        if not self.errors and not self.report_only:
            self.state["lastSuccess"] = self.now
            self.save()
        for row in self.rows:
            key = str(row["source"].get("id", ""))
            if key in self.sizes:
                row["sizeKiB"] = self.sizes[key]
        return {"reportOnly": self.report_only, "errors": self.errors, "rows": self.rows,
                "eligibleSizeKiB": sum(self.sizes[key] for key, (_, _, reasons) in found.items() if not reasons),
                "sizeCaveat": "GitHub reported size excludes unknown LFS, import workspace and growth overhead"}


def metrics(report, state, now):
    lines = [f"forgejo_mirrors_last_run_timestamp_seconds {now}",
             f"forgejo_mirrors_last_success_timestamp_seconds {state.get('lastSuccess', 0)}",
             f"forgejo_mirrors_errors {report['errors']}",
             f"forgejo_mirrors_report_only {int(report['reportOnly'])}"]
    for row in report["rows"]:
        # Only validated identifiers, not arbitrary upstream text, enter labels.
        destination = row["destination"]
        if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", destination):
            labels = '{destination="' + destination + '"}'
            if "ageSeconds" in row:
                lines.append("forgejo_mirrors_sync_age_seconds" + labels + " " + str(row["ageSeconds"]))
            if row["status"] != "excluded":
                lines.append("forgejo_mirrors_repository_error" + labels + " " + str(int(row["status"] not in ("healthy", "created", "planned"))))
    return "\n".join(lines) + "\n"


def credential(name, optional=False):
    path = Path(os.environ["CREDENTIALS_DIRECTORY"]) / name
    if optional and not path.exists():
        return ""
    value = path.read_text().strip()
    if not value or any(c.isspace() for c in value) or "placeholder" in value.lower():
        raise MirrorError("invalid_credential")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--metrics-file", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    state_dir = Path(args.state_dir)
    state = {"lastSuccess": 0}
    report = {"errors": 1, "reportOnly": True, "rows": []}
    try:
        with (state_dir / "lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print("Forgejo mirrors: concurrent run refused")
                return 1
            config = json.loads(Path(args.config).read_text())
            state_path = state_dir / "ownership.json"
            state = load_state(state_path)
            github = API("https://api.github.com", credential("github", optional=True))
            forgejo = API("http://127.0.0.1:3002/api/v1", credential("forgejo"))
            report = Reconciler(config, github, forgejo, state,
                                lambda: atomic_write(state_path, json.dumps(state))).run()
            atomic_write(state_dir / "report.json", json.dumps(report, indent=2) + "\n")
            atomic_write(args.metrics_file, metrics(report, state, time.time()), 0o640)
    except (MirrorError, OSError, ValueError, KeyError, TypeError):
        # A fatal run must replace old successful metrics, never expose diagnostics.
        report["errors"] = max(1, report["errors"])
        try:
            atomic_write(args.metrics_file, metrics(report, state, time.time()), 0o640)
        except OSError:
            pass
        print("Forgejo mirrors: fatal failure; sensitive diagnostics suppressed", file=sys.stderr)
        return 1
    for row in report["rows"]:
        print(json.dumps({"destination": row["destination"], "status": row["status"]}))
    print(json.dumps({"service": "forgejo-mirrors", "errors": report["errors"],
                      "repositories": len(report["rows"]), "reportOnly": report["reportOnly"]}))
    return int(bool(report["errors"]))


if __name__ == "__main__":
    sys.exit(main())
