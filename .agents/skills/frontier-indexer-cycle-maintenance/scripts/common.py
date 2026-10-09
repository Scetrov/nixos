"""Small stdlib-only utilities. Never print subprocess output or credentials."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time


class MaintenanceError(Exception):
    pass


def emit(report):
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))


def repository(explicit=None):
    candidates = [Path(explicit).resolve()] if explicit else Path(__file__).resolve().parents
    for candidate in candidates:
        if (candidate / "src/roles/nixos/files/etc/nixos/modules/frontier-indexer.nix").is_file():
            return candidate
    raise MaintenanceError("Cannot locate the NixOS repository; supply --repo")


def source_fingerprint(root):
    """Bind check evidence to host deployment sources, never to plaintext secrets."""
    directories = [root / "src/roles/nixos/files", root / "src/roles/nixos/tasks",
                   root / "src/roles/secrets/tasks", root / "tests",
                   root / ".agents/skills/frontier-indexer-cycle-maintenance"]
    files = {path for directory in directories for path in directory.rglob("*")
             if path.is_file() and "__pycache__" not in path.parts}
    files.update(root / name for name in ["src/playbook.yml", "src/inventory.yml", "scripts/play.sh", ".pre-commit-config.yaml"])
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(str(path.relative_to(root)).encode() + b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def pinned_image(value):
    registry = value.split("/", 1)[0]
    if not re.fullmatch(r"[a-z0-9.-]+(?::[0-9]+)?/[A-Za-z0-9_./:-]+@sha256:[a-f0-9]{64}", value) or not (
        "." in registry or ":" in registry or registry == "localhost"
    ):
        raise MaintenanceError("Image must be fully qualified and SHA256-pinned")
    return value


def capture(command, *, cwd=None, timeout=90, input_text=None):
    start = time.monotonic()
    try:
        result = subprocess.run(command, cwd=cwd, input=input_text, text=True,
                                capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise MaintenanceError(f"Command unavailable or timed out: {command[0]} ({type(error).__name__})") from error
    return result, round(time.monotonic() - start, 2)


def require(command, **kwargs):
    result, _ = capture(command, **kwargs)
    if result.returncode:
        raise MaintenanceError(f"Command failed: {command[0]} (exit {result.returncode}); raw output suppressed")
    return result.stdout
