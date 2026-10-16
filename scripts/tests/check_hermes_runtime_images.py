"""Disposable, network-isolated checks against the configured WebUI digest.

No credentials, persistent state, or host directories are mounted. Optionally
mount only the Nix-built static gh executable to test container compatibility.
"""

import argparse
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gh", type=Path, help="Nix-built static gh executable")
    arguments = parser.parse_args()
    module = (ROOT / "src/roles/nixos/files/etc/nixos/modules/hermes.nix").read_text()
    image = re.search(r'default = "(ghcr.io/nesquena/hermes-webui:[^"]+)"', module).group(1)
    base = [
        "podman", "run", "--rm", "--network=none", "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
    ]
    check = (
        "import os; assert 'HERMES_WEBUI_PASSWORD' not in os.environ; "
        "from api.auth import is_password_auth_enabled, is_auth_enabled; "
        "assert not is_password_auth_enabled(); assert not is_auth_enabled(); "
        "print('PASS: no password variable or authentication in fresh state')"
    )
    subprocess.run(base + [
        "--env", "HERMES_WEBUI_STATE_DIR=/tmp/hermes-auth-smoke",
        "--entrypoint", "python", image, "-c", check,
    ], check=True)
    if arguments.gh:
        executable = arguments.gh.resolve(strict=True)
        if not executable.is_file() or not str(executable).startswith("/nix/store/"):
            parser.error("--gh must name a Nix-store executable, not a host directory")
        cli = base + [
            "--volume", f"{executable}:/usr/local/bin/gh:ro",
            "--env", "GH_TELEMETRY=false", "--env", "GH_CONFIG_DIR=/tmp/hermes-gh-smoke",
            "--entrypoint", "/usr/local/bin/gh", image,
        ]
        subprocess.run(cli + ["--version"], check=True)
        result = subprocess.run(cli + ["auth", "status"], capture_output=True, text=True, check=False)
        assert result.returncode == 1, "Unexpected gh authentication status"
        assert "not logged into any GitHub hosts" in result.stderr, "Unexpected gh authentication error"
        print("PASS: gh remains available without GitHub credentials")


if __name__ == "__main__":
    main()
