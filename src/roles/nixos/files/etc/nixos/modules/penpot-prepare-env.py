#!/usr/bin/env python3
"""Render root-only Penpot container env files from systemd credentials."""
import os
from pathlib import Path
import tempfile


def render(state_dir: Path, credentials: Path) -> None:
    values = {}
    for name in ("penpot_db_password", "penpot_secret_key", "penpot_oidc_client_id", "penpot_oidc_client_secret"):
        value = (credentials / name).read_text().strip()
        if (not value or any(c in value for c in "\r\n\x00")
                or value.lower() in {"null", "placeholder", "changeme", "change-me", "replace-me"}
                or value.lower().endswith("_placeholder")):
            raise ValueError(f"Invalid credential: {name}")
        values[name] = value

    files = {
        "postgres.env": {"POSTGRES_PASSWORD": values["penpot_db_password"]},
        "backend.env": {
            "PENPOT_DATABASE_PASSWORD": values["penpot_db_password"],
            "PENPOT_SECRET_KEY": values["penpot_secret_key"],
            "PENPOT_OIDC_CLIENT_ID": values["penpot_oidc_client_id"],
            "PENPOT_OIDC_CLIENT_SECRET": values["penpot_oidc_client_secret"],
        },
        "frontend.env": {"PENPOT_OIDC_CLIENT_ID": values["penpot_oidc_client_id"]},
        "exporter.env": {"PENPOT_SECRET_KEY": values["penpot_secret_key"]},
    }
    for name, entries in files.items():
        with tempfile.NamedTemporaryFile(mode="w", dir=state_dir, delete=False) as handle:
            temporary = Path(handle.name)
            for key, value in entries.items():
                handle.write(f"{key}={value}\n")
        temporary.chmod(0o600)
        temporary.replace(state_dir / name)


if __name__ == "__main__":
    render(Path("/var/lib/penpot"), Path(os.environ["CREDENTIALS_DIRECTORY"]))
