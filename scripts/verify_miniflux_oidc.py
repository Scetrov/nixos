#!/usr/bin/env python3
"""Compare runtime credential files with authoritative OpenTofu JSON on stdin.

Run on the consumer with permission to read its systemd credential files.
Never pass secret values as arguments. Outputs only a redacted pass/fail result.
All OpenTofu output retrieval must use scripts/tofu.sh.
"""
from __future__ import annotations

import argparse
import hmac
import json
import sys
from pathlib import Path

from render_generated_secrets import RenderError, _scalar


def check(outputs: dict, client_id: Path, client_secret: Path) -> bool:
    for key, path in (("miniflux_oidc_client_id", client_id),
                      ("miniflux_oidc_client_secret", client_secret)):
        expected = _scalar(outputs[key]["value"])
        actual = _scalar(path.read_text(encoding="utf-8"))
        if not hmac.compare_digest(expected.encode(), actual.encode()):
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-id-file", required=True, type=Path)
    parser.add_argument("--client-secret-file", required=True, type=Path)
    args = parser.parse_args()
    try:
        matches = check(json.load(sys.stdin), args.client_id_file, args.client_secret_file)
    except (OSError, ValueError, KeyError, TypeError, RenderError):
        # Do not disclose file contents, paths, JSON input or exception details.
        matches = False
    print("Miniflux OIDC: " + ("OK match=true" if matches else "FAIL match=false"))
    return 0 if matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
