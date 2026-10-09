#!/usr/bin/env python3
"""Verify release/source/registry consistency and print only a compact report."""
import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import tomllib
import urllib.error
import urllib.request

from common import MaintenanceError, emit

REPOSITORY = "Algo-Net/Frontier-Indexer"
REGISTRY_REPOSITORY = "algo-net/frontier-indexer"
MEDIA_TYPES = ",".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])


def fetch(url, headers=None):
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "frontier-cycle-maintenance", **(headers or {})})
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except (OSError, urllib.error.URLError) as error:
        raise MaintenanceError(f"Upstream request failed ({type(error).__name__}); retry after checking connectivity/rate limits") from error


def github(path):
    return json.loads(fetch(f"https://api.github.com/repos/{REPOSITORY}/{path}"))


def digest(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


def registry_object(path, headers, expected=None):
    if expected and not re.fullmatch(r"sha256:[a-f0-9]{64}", expected):
        raise MaintenanceError("Registry returned an unsupported digest")
    body = fetch(f"https://ghcr.io/v2/{REGISTRY_REPOSITORY}/{path}", headers)
    actual = digest(body)
    if expected and actual != expected:
        raise MaintenanceError("Registry content failed SHA256 verification")
    return json.loads(body), actual


def source(commit, path):
    return fetch(f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{path}").decode("utf-8")


def inspect_release(tag, asset, world, checkpoint, architecture="amd64", now=None):
    release = github(f"releases/tags/{tag}")
    latest = github("releases/latest")
    reference = github(f"git/ref/tags/{tag}")["object"]
    for _ in range(5):
        if reference["type"] != "tag":
            break
        reference = github("git/tags/" + reference["sha"])["object"]
    if reference["type"] != "commit" or not re.fullmatch(r"[a-f0-9]{40}", reference["sha"]):
        raise MaintenanceError("Release tag does not resolve to a supported commit")
    commit = reference["sha"]
    token = json.loads(fetch(f"https://ghcr.io/token?service=ghcr.io&scope=repository:{REGISTRY_REPOSITORY}:pull"))["token"]
    headers = {"Authorization": "Bearer " + token, "Accept": MEDIA_TYPES}
    manifest, manifest_digest = registry_object("manifests/" + tag, headers)
    image_manifest = manifest
    if "manifests" in manifest:
        matches = [item for item in manifest["manifests"]
                   if item.get("platform", {}).get("os") == "linux"
                   and item.get("platform", {}).get("architecture") == architecture]
        if len(matches) != 1:
            raise MaintenanceError("Release must contain exactly one image for the requested Linux architecture")
        image_manifest, _ = registry_object("manifests/" + matches[0]["digest"], headers, matches[0]["digest"])
    config_digest = image_manifest["config"]["digest"]
    config, _ = registry_object("blobs/" + config_digest, headers, config_digest)
    labels = config.get("config", {}).get("Labels") or {}
    library = source(commit, "src/lib.rs")
    packages = re.search(r"const\s+TESTNET_WORLD_PACKAGES\s*:[^=]+?=\s*&\[(.*?)\];", library, re.S)
    if not packages:
        raise MaintenanceError("World-package declaration changed; inspect upstream before proceeding")
    addresses = re.findall(r'"(0x[0-9a-fA-F]+)"', packages[1])
    sample = source(commit, ".env.sample")
    start = re.search(r"^FIRST_CHECKPOINT=([0-9]+)\s*$", sample, re.M)
    settings = source(commit, "src/config.rs")
    main = source(commit, "src/main.rs")
    pipelines = tomllib.loads(source(commit, "pipelines.toml")).get("pipelines", {})
    published = dt.datetime.fromisoformat(release["published_at"].replace("Z", "+00:00"))
    observed = now or dt.datetime.now(dt.timezone.utc)
    age_days = (observed - published).total_seconds() / 86400
    checks = {
        "stable_release": not release.get("draft") and not release.get("prerelease"),
        "latest_release": latest["tag_name"] == tag,
        "seven_day_policy": age_days >= 7,
        "platform": config.get("os") == "linux" and config.get("architecture") == architecture,
        "source_revision": labels.get("org.opencontainers.image.revision") == commit,
        "source_repository": labels.get("org.opencontainers.image.source", "").lower() == f"https://github.com/{REPOSITORY}".lower(),
        "version_label": labels.get("org.opencontainers.image.version") == tag,
        "contracts": asset != world and asset in addresses and world in addresses,
        "checkpoint": bool(start and int(start[1]) == checkpoint),
        "environment_keys": all(re.search(r'\benv\s*=\s*"' + key + '"', settings)
                                for key in ["SUI_NETWORK", "PACKAGES", "FIRST_CHECKPOINT", "INGEST_CONCURRENCY_MAX", "DB_SCHEMA"]),
        "all_pipelines": bool(pipelines) and all(value is True for value in pipelines.values()),
        "pipeline_file_loaded": "PipelineConfig::from_file" in main and "./pipelines.toml" in main,
        "schema_search_path": "search_path%3D" in main and "run_migrations" in main,
    }
    return {
        "ok": all(checks.values()), "checks": checks, "tag": tag,
        "latest_tag": latest["tag_name"], "published_at": release["published_at"], "observed_at": observed.isoformat(),
        "age_days": round(age_days, 2), "commit": commit, "architecture": architecture,
        "image": f"ghcr.io/{REGISTRY_REPOSITORY}:{tag}@{manifest_digest}",
        "asset": asset, "world": world, "checkpoint": checkpoint,
        "enabled_pipeline_count": sum(value is True for value in pipelines.values()),
        "provenance": "OCI/source metadata consistency and registry byte hashes; not signature or attestation verification",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--asset", required=True)
    parser.add_argument("--world", required=True)
    parser.add_argument("--checkpoint", type=int, required=True)
    parser.add_argument("--architecture", choices=["amd64", "arm64"], default="amd64")
    args = parser.parse_args()
    try:
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", args.tag):
            raise MaintenanceError("Invalid registry tag")
        if args.checkpoint < 0 or any(not re.fullmatch(r"0x[0-9a-fA-F]{1,64}", address) for address in [args.asset, args.world]):
            raise MaintenanceError("Expected nonnegative checkpoint and valid Sui package addresses")
        report = inspect_release(args.tag, args.asset, args.world, args.checkpoint, args.architecture)
        emit(report)
        return 0 if report["ok"] else 1
    except (MaintenanceError, KeyError, ValueError, TypeError) as error:
        message = str(error) if isinstance(error, MaintenanceError) else "Upstream format changed; review manually"
        emit({"ok": False, "error": message})
        return 1


if __name__ == "__main__":
    sys.exit(main())
