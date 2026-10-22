#!/usr/bin/env python3
"""Prepare a checksum-pinned, filesystem-only OpenTofu provider mirror.

1.7.0 was released 2026-10-15 17:40 UTC, still inside the seven-day deferral
at review. 1.6.1 (2026-09-18) is the newest eligible release for this rollout.
"""
import hashlib
import json
from pathlib import Path
import platform
import sys
import urllib.request

VERSION = "1.6.1"
SHA256 = "2a9bec6b5780b5b583a0b921c189d5b89761d6bd86b8df2497437756c4c84903"


def prepare(root):
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise RuntimeError("Only the reviewed linux_amd64 provider is authorized")
    root = Path(root).resolve()
    cache = root / ".terraform"
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    cache.chmod(0o700)  # Backend metadata may contain sensitive connection details.
    mirror = cache / "pinned-mirror"
    directory = mirror / "registry.opentofu.org/svalabs/forgejo"
    directory.mkdir(parents=True, exist_ok=True)
    name = f"terraform-provider-forgejo_{VERSION}_linux_amd64.zip"
    archive = directory / name
    if not archive.exists():
        url = f"https://github.com/svalabs/terraform-provider-forgejo/releases/download/v{VERSION}/{name}"
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read(64 * 1024 * 1024 + 1)
        if len(data) > 64 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != SHA256:
            raise RuntimeError("Provider archive integrity failure")
        archive.write_bytes(data)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError("Cached provider archive integrity failure")
    config = root / ".terraform" / "pinned-provider.tfrc"
    config.write_text('provider_installation {\n filesystem_mirror {\n  path = '
                      + json.dumps(str(mirror)) + '\n  include = ["registry.opentofu.org/svalabs/forgejo"]\n }\n}\n')
    return config


if __name__ == "__main__":
    try:
        print(prepare(sys.argv[1]))
    except Exception:
        print("Pinned Forgejo provider preparation failed", file=sys.stderr)
        sys.exit(1)
