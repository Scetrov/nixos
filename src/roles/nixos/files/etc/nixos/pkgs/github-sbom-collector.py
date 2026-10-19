#!/usr/bin/env python3
"""Download explicitly trusted GitHub SBOM artifacts and upload them to DTrack.

Completion means HTTP upload acceptance, not verified internal BOM processing.
Downloaded content is never extracted to the filesystem or executed.
"""

import argparse
import base64
import datetime as dt
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import ssl
import stat
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from jsonschema import Draft7Validator
from referencing import Registry, Resource


COMPRESSED_LIMIT = 10 * 1024 * 1024
EXPANDED_LIMIT = 50 * 1024 * 1024
API_LIMIT = 5 * 1024 * 1024
SCHEMA_VERSION = "1.6"


class Failure(Exception):
    """Only fixed, credential-free reason codes may be emitted to the journal."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def event(status, **fields):
    print(json.dumps({"service": "github-sbom-collector", "status": status, **fields}), flush=True)


def atomic_write(path, data, mode=0o600):
    path = Path(path)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            os.fchmod(handle.fileno(), mode)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def json_document(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Failure("duplicate_json_key")
            result[key] = value
        return result

    def constant(_):
        raise Failure("invalid_json_number")

    try:
        document = json.loads(data, object_pairs_hook=unique, parse_constant=constant)
        stack = [(document, 0)]
        nodes = 0
        while stack:
            item, depth = stack.pop()
            nodes += 1
            if depth > 64 or nodes > 500000:
                raise Failure("json_complexity_limit")
            if isinstance(item, dict):
                stack.extend((v, depth + 1) for v in item.values())
            elif isinstance(item, list):
                stack.extend((v, depth + 1) for v in item)
        return document
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise Failure("invalid_json") from exc


def validator(schema_dir):
    # No automatic remote retrieval: only these three packaged resources exist.
    registry = Registry()
    schemas = {}
    for name in ("bom-1.6.schema.json", "spdx.schema.json", "jsf-0.82.schema.json"):
        document = json.loads((Path(schema_dir) / name).read_bytes())
        schemas[name] = document
        resource = Resource.from_contents(document)
        registry = registry.with_resource(document["$id"], resource)
    return Draft7Validator(schemas["bom-1.6.schema.json"], registry=registry)


def payload(archive, source, schema):
    digest = "sha256:" + hashlib.sha256(archive).hexdigest()
    if len(archive) > COMPRESSED_LIMIT:
        raise Failure("compressed_limit")
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            members = bundle.infolist()
            if len(members) != 1:
                raise Failure("archive_member_count")
            member = members[0]
            path = PurePosixPath(member.filename)
            mode = member.external_attr >> 16
            if (member.filename != source["path"] or path.is_absolute()
                    or ".." in path.parts or "\\" in member.filename
                    or member.is_dir() or member.flag_bits & 1
                    or stat.S_IFMT(mode) not in (0, stat.S_IFREG)):
                raise Failure("unsafe_archive_member")
            if member.file_size > EXPANDED_LIMIT:
                raise Failure("expanded_limit")
            with bundle.open(member) as handle:
                data = handle.read(EXPANDED_LIMIT + 1)
            if len(data) > EXPANDED_LIMIT:
                raise Failure("expanded_limit")
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError) as exc:
        raise Failure("invalid_archive") from exc
    document = json_document(data)
    if not isinstance(document, dict) or document.get("bomFormat") != "CycloneDX" or document.get("specVersion") != SCHEMA_VERSION:
        raise Failure("unsupported_bom")
    try:
        if not schema.is_valid(document):
            raise Failure("schema_rejected")
    except Failure:
        raise
    except Exception as exc:
        # Never expose schema validation messages containing artifact content.
        raise Failure("schema_validation_failed") from exc
    return data, digest


class GitHubApp:
    """Dedicated App credentials; installation tokens exist only in memory."""

    def __init__(self, config, sources, private_key):
        self.app_id = config.get("appId")
        installation_ids = config.get("installationIds")
        if (type(self.app_id) is not int or self.app_id <= 0
                or not isinstance(installation_ids, list) or not installation_ids
                or any(type(i) is not int or i <= 0 for i in installation_ids)
                or len(set(installation_ids)) != len(installation_ids)):
            raise Failure("invalid_app_configuration")
        self.installation_ids = set(installation_ids)
        self.repositories = {}
        for source in sources:
            name = source["repository"].lower()
            previous = self.repositories.get(name)
            if previous and previous[1] != source["repositoryId"]:
                raise Failure("conflicting_repository_identity")
            self.repositories[name] = (source["repository"], source["repositoryId"])
        try:
            self.key = serialization.load_pem_private_key(private_key, password=None)
        except (ValueError, TypeError) as exc:
            raise Failure("invalid_app_private_key") from exc
        if not isinstance(self.key, rsa.RSAPrivateKey) or self.key.key_size < 2048:
            raise Failure("invalid_app_private_key")
        self.cache = {}

    def jwt(self):
        def encode(value):
            return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

        now = int(time.time())
        header = encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
        claims = encode(json.dumps({"iat": now - 60, "exp": now + 540, "iss": str(self.app_id)}).encode())
        message = (header + "." + claims).encode("ascii")
        # GitHub's RS256 JWT contract requires PKCS1v15 signature padding.
        signature = self.key.sign(message, padding.PKCS1v15(), hashes.SHA256())
        return message.decode("ascii") + "." + encode(signature)

    def token(self, repository, request):
        name = repository.lower()
        if name not in self.repositories:
            raise Failure("unconfigured_repository")
        cached = self.cache.get(name)
        if cached and cached[1] > time.time() + 60:
            return cached[0]
        canonical, repo_id = self.repositories[name]

        def api(path, method="GET", body=None):
            status, _, data = request("https://api.github.com" + path, {
                "Authorization": "Bearer " + self.jwt(),
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            }, API_LIMIT, method=method, body=json.dumps(body).encode() if body is not None else None)
            if status != (201 if method == "POST" else 200):
                raise Failure("github_app_request_failed")
            result = json_document(data)
            if not isinstance(result, dict):
                raise Failure("invalid_app_response")
            return result

        installation = api(f"/repos/{canonical}/installation")
        installation_id = installation.get("id")
        if (type(installation_id) is not int or installation_id not in self.installation_ids
                or installation.get("app_id") != self.app_id or installation.get("suspended_at")):
            raise Failure("unapproved_or_suspended_installation")
        # Construct endpoints locally. Never follow access_tokens_url or other
        # URLs returned by metadata, and never mint a default all-repository token.
        result = api(f"/app/installations/{installation_id}/access_tokens", "POST", {
            "repository_ids": [repo_id], "permissions": {"actions": "read"},
        })
        permissions = result.get("permissions")
        if (not isinstance(permissions, dict) or permissions.get("actions") != "read"
                or permissions.get("metadata", "read") != "read"
                or any(k not in ("actions", "metadata") and v != "none" for k, v in permissions.items())):
            raise Failure("unexpected_installation_permissions")
        token = result.get("token")
        try:
            expiry = dt.datetime.strptime(result["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp()
        except (KeyError, TypeError, ValueError) as exc:
            raise Failure("invalid_installation_expiry") from exc
        if not isinstance(token, str) or not token or any(c.isspace() for c in token) or expiry <= time.time() + 60:
            raise Failure("invalid_or_expired_installation_token")
        self.cache[name] = (token, expiry)
        return token


class Http:
    def __init__(self, github_token, dtrack_token, dtrack_url):
        parsed = urllib.parse.urlsplit(dtrack_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            raise Failure("invalid_dtrack_origin")
        self.github_token = github_token
        self.dtrack_token = dtrack_token
        self.dtrack_url = dtrack_url.rstrip("/")
        self.opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))

    def request(self, url, headers, limit, method="GET", body=None):
        # Retries apply to read-only requests. Upload attempts are checkpointed
        # separately so an ambiguous acceptance cannot be retried indefinitely.
        for attempt in range(3 if method == "GET" else 1):
            try:
                req = urllib.request.Request(url, headers=headers, data=body, method=method)
                with self.opener.open(req, timeout=30) as response:
                    data = response.read(limit + 1)
                    if len(data) > limit:
                        raise Failure("response_size_limit")
                    return response.status, response.headers, data
            except urllib.error.HTTPError as exc:
                if exc.code in (301, 302, 303, 307, 308):
                    return exc.code, exc.headers, b""
                if method == "GET" and exc.code in (403, 429, 500, 502, 503, 504) and attempt < 2:
                    delay = exc.headers.get("Retry-After", "")
                    # Long rate limits defer to the next timer invocation.
                    if delay.isdigit() and int(delay) > 30:
                        raise Failure("rate_limited") from exc
                    time.sleep(max(2 ** attempt, int(delay) if delay.isdigit() else 0))
                    continue
                if exc.code in (404, 410):
                    raise Failure("artifact_or_target_missing") from exc
                raise Failure("http_" + str(exc.code)) from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if method == "GET" and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise Failure("network_error") from exc
        raise Failure("request_failed")

    def github(self, path):
        if not path.startswith("/repos/"):
            raise Failure("invalid_github_path")
        repository = "/".join(path.split("/")[2:4])
        token = (self.github_token.token(repository, self.request)
                 if isinstance(self.github_token, GitHubApp) else self.github_token)
        return self.request("https://api.github.com" + path, {
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
        }, API_LIMIT)

    def pages(self, path, field):
        # Construct page URLs ourselves; never follow untrusted Link URLs.
        for page in range(1, 21):
            separator = "&" if "?" in path else "?"
            status, _, data = self.github(path + separator + f"per_page=100&page={page}")
            if status != 200:
                raise Failure("unexpected_github_status")
            document = json_document(data)
            rows = document.get(field)
            if not isinstance(rows, list):
                raise Failure("invalid_github_response")
            yield from rows
            if len(rows) < 100:
                return
        raise Failure("pagination_limit")

    def download(self, repo, artifact_id):
        # A GitHub redirect is required. Never forward credentials to storage.
        status, headers, data = self.github(f"/repos/{repo}/actions/artifacts/{int(artifact_id)}/zip")
        if status != 302:
            raise Failure("missing_artifact_redirect")
        url = headers.get("Location", "")
        parsed = urllib.parse.urlsplit(url)
        host = parsed.hostname or ""
        if (parsed.scheme != "https" or parsed.username or parsed.password
                or parsed.port not in (None, 443)
                or not (host.endswith(".blob.core.windows.net") or host.endswith(".actions.githubusercontent.com"))):
            raise Failure("unapproved_artifact_origin")
        status, _, data = self.request(url, {}, COMPRESSED_LIMIT)
        if status != 200:
            raise Failure("unexpected_download_status")
        return data

    def upload(self, project, data):
        body = json.dumps({"project": project, "autoCreate": False,
                           "bom": base64.b64encode(data).decode("ascii")}).encode()
        status, _, response = self.request(self.dtrack_url + "/api/v1/bom", {
            "X-Api-Key": self.dtrack_token, "Content-Type": "application/json",
        }, API_LIMIT, method="PUT", body=body)
        if status not in (200, 201, 202):
            raise Failure("upload_not_accepted")
        result = json_document(response)
        try:
            return str(uuid.UUID(result["token"]))
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise Failure("accepted_without_valid_token") from exc


def validate_config(config):
    targets = set()
    for source in config["sources"]:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", source["repository"]):
            raise Failure("invalid_repository")
        if source["event"] != "push" or not source["branch"] or not source["artifact"]:
            raise Failure("invalid_producer_policy")
        path = PurePosixPath(source["path"])
        if path.is_absolute() or ".." in path.parts or "\\" in source["path"]:
            raise Failure("invalid_payload_path")
        for key in ("repositoryId", "workflowId"):
            if type(source[key]) is not int or source[key] <= 0:
                raise Failure("invalid_producer_identity")
        project = str(uuid.UUID(source["project"]))
        if project in targets or not source["version"]:
            raise Failure("duplicate_or_unversioned_target")
        targets.add(project)


def trusted(run, source):
    return (run.get("repository", {}).get("id") == source["repositoryId"]
            and run.get("head_repository", {}).get("id") == source["repositoryId"]
            and run.get("workflow_id") == source["workflowId"]
            and run.get("status") == "completed" and run.get("conclusion") == "success"
            and run.get("event") == source["event"] and run.get("head_branch") == source["branch"]
            and not run.get("pull_requests")
            and bool(re.fullmatch(r"[0-9a-f]{40}", run.get("head_sha", "")))
            and all(type(run.get(k)) is int and run[k] > 0 for k in ("id", "run_number", "run_attempt")))


def artifact_matches(artifact, run, source):
    provenance = artifact.get("workflow_run", {})
    return (artifact.get("name") == source["artifact"]
            and provenance.get("id") == run["id"]
            and provenance.get("repository_id") == source["repositoryId"]
            and provenance.get("head_repository_id") == source["repositoryId"]
            and provenance.get("head_sha") == run["head_sha"]
            and provenance.get("head_branch") == source["branch"]
            # Artifacts from previous attempts must not be reused on a rerun.
            and artifact.get("created_at", "") >= run["run_started_at"])


TRANSFER_BACKLOG = {
    "upload_retry_exhausted", "upload_not_accepted", "accepted_without_valid_token",
    "network_error", "rate_limited", "request_failed", "artifact_or_target_missing",
    "missing_artifact_redirect", "unexpected_download_status", "unexpected_github_status",
    "unapproved_artifact_origin", "response_size_limit", "invalid_github_path",
    "invalid_github_response", "pagination_limit",
}


def artifact_age(now, artifact):
    created = artifact.get("created_at", "")
    try:
        stamp = dt.datetime.fromisoformat(str(created).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return 0
    return max(0, int((now - stamp).total_seconds()))


def collect(config, state, save, http, schema, report_only=False, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    cutoff = (now - dt.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    state.setdefault("accepted", {})
    state.setdefault("attempts", {})
    counts = {
        "uploaded": 0, "skipped": 0, "failed": 0, "eligible": 0,
        "rejected": 0, "expired": 0, "backlog": 0, "backlog_age_seconds": 0,
    }
    for source in config["sources"]:
        repo = source["repository"]
        pending = None
        try:
            query = urllib.parse.urlencode({"event": source["event"], "branch": source["branch"], "status": "success", "created": ">=" + cutoff})
            runs = list(http.pages(f"/repos/{repo}/actions/workflows/{source['workflowId']}/runs?{query}", "workflow_runs"))
            for run in sorted((r for r in runs if trusted(r, source)), key=lambda r: (r["run_number"], r["run_attempt"])):
                pending = None
                target = source["project"]
                order = [run["run_number"], run["run_attempt"]]
                previous = state["accepted"].get(target)
                identity = [source["repositoryId"], source["workflowId"]]
                if previous and (previous["producer"] != identity or previous["version"] != source["version"]):
                    raise Failure("target_policy_changed")
                if previous and order <= previous["order"]:
                    counts["skipped"] += 1
                    continue
                artifacts = [a for a in http.pages(f"/repos/{repo}/actions/runs/{run['id']}/artifacts", "artifacts") if artifact_matches(a, run, source)]
                if not artifacts:
                    # Older CI runs may predate the producer job; late artifacts
                    # remain discoverable on the next poll until a newer upload.
                    counts["failed"] += 1
                    event("failed", reason="missing_artifact", run=run["id"])
                    continue
                if len(artifacts) != 1:
                    raise Failure("ambiguous_artifact")
                artifact = artifacts[0]
                counts["eligible"] += 1
                if artifact.get("expired"):
                    raise Failure("retention_gap")
                if not 0 < artifact.get("size_in_bytes", 0) <= COMPRESSED_LIMIT:
                    raise Failure("compressed_limit")
                if report_only:
                    counts["backlog"] += 1
                    counts["backlog_age_seconds"] = max(counts["backlog_age_seconds"], artifact_age(now, artifact))
                    event("eligible", run=run["id"], artifact=artifact["id"])
                    continue
                pending = artifact
                key = f"{target}:{run['id']}:{run['run_attempt']}:{artifact['id']}"
                attempt = state["attempts"].get(key, 0)
                if attempt >= 3:
                    raise Failure("upload_retry_exhausted")
                archive = http.download(repo, artifact["id"])
                actual = "sha256:" + hashlib.sha256(archive).hexdigest()
                if artifact.get("digest") and artifact["digest"] != actual:
                    raise Failure("artifact_digest_mismatch")
                data, digest = payload(archive, source, schema)
                state["attempts"][key] = attempt + 1
                save(state)  # Durable attempt budget before potentially ambiguous acceptance.
                token = http.upload(target, data)
                state["accepted"][target] = {
                    "producer": identity, "order": order, "run": run["id"],
                    "attempt": run["run_attempt"], "artifact": artifact["id"],
                    "digest": digest, "version": source["version"], "token": token,
                    "uploaded_at": int(now.timestamp()),
                }
                # Retain failed/ambiguous evidence; remove this accepted attempt.
                state["attempts"].pop(key)
                save(state)
                pending = None
                counts["uploaded"] += 1
                event("uploaded", run=run["id"], artifact=artifact["id"], target=target)
        except Failure as exc:
            reason = str(exc)
            counts["failed"] += 1
            if reason == "retention_gap":
                counts["expired"] += 1
            else:
                counts["rejected"] += 1
            if pending is not None and (reason in TRANSFER_BACKLOG or reason.startswith("http_")):
                counts["backlog"] += 1
                counts["backlog_age_seconds"] = max(counts["backlog_age_seconds"], artifact_age(now, pending))
            event("failed", reason=reason)
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--schemas", required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--metrics-file")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    directory = Path(args.state_dir)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (directory / "lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            event("locked")
            return 0
        try:
            config = json.loads(Path(args.config).read_bytes())
            validate_config(config)
            credentials = Path(os.environ["CREDENTIALS_DIRECTORY"])
            auth = GitHubApp(config["githubApp"], config["sources"],
                             (credentials / "github-app-key").read_bytes())
            http = Http(auth, (credentials / "dtrack").read_text().strip(), config["dtrackUrl"])
            state_file = directory / "state.json"
            state = json.loads(state_file.read_bytes()) if state_file.exists() else {}
            counts = collect(config, state, lambda s: atomic_write(state_file, json.dumps(s).encode()),
                             http, validator(args.schemas), args.report_only)
            metrics = "".join(f"github_sbom_collector_{k} {v}\n" for k, v in counts.items())
            metrics += f"github_sbom_collector_last_poll_timestamp_seconds {int(time.time())}\n"
            last = max((r["uploaded_at"] for r in state.get("accepted", {}).values()), default=0)
            metrics += f"github_sbom_collector_last_upload_timestamp_seconds {last}\n"
            metrics_path = Path(args.metrics_file) if args.metrics_file else directory / "collector.prom"
            atomic_write(metrics_path, metrics.encode(), mode=0o644)
            event("poll_complete", **counts)
            return int(bool(counts["failed"]))
        except Exception:
            # Never serialize response bodies, URLs, tokens, or payload exceptions.
            event("failed", reason="collector_configuration_or_state_error")
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
