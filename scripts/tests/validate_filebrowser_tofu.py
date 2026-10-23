#!/usr/bin/env python3
"""Validate Filebrowser against real provider schemas without production state.

Uses the existing wrapper's disposable fixture mode. Provider installation may
use the network; no vault, backend connection, plan, or apply is performed.
"""

from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    fixture = Path(tempfile.mkdtemp(prefix=".passkey-test-filebrowser-", dir=ROOT / "terraform"))
    try:
        source = (ROOT / "terraform/filebrowser.tf").read_text().replace("${path.module}/../src/filebrowser-enrollments.json", str(ROOT / "src/filebrowser-enrollments.json"))
        (fixture / "filebrowser.tf").write_text(source)
        (fixture / "fixture.tf").write_text('''terraform {
  required_providers {
    authentik = { source = "goauthentik/authentik", version = "2026.8.0" }
    random = { source = "hashicorp/random", version = "3.9.1" }
  }
}
provider "authentik" {
  url = "https://fixture.invalid"
  token = "synthetic-fixture-not-a-real-credential"
}
data "authentik_certificate_key_pair" "default" { name = "fixture" }
data "authentik_flow" "default_authorization" { slug = "fixture-auth" }
data "authentik_flow" "default_invalidation" { slug = "fixture-invalidation" }
data "authentik_property_mapping_provider_scope" "openid" { managed = "goauthentik.io/providers/oauth2/scope-openid" }
data "authentik_property_mapping_provider_scope" "email" { managed = "goauthentik.io/providers/oauth2/scope-email" }
''')
        for args in (("init", "-backend=false", "-no-color"), ("validate", "-no-color")):
            result = subprocess.run([str(ROOT / "scripts/tofu.sh"), "--test-fixture-dir", str(fixture), "--", *args], cwd=ROOT, capture_output=True, text=True, timeout=180)
            print(args[0] + ": " + ("PASS" if result.returncode == 0 else "FAIL"))
            if result.returncode:
                print(result.stdout + result.stderr)
                return result.returncode
            if args[0] == "init":
                print("Provider checksums verified by OpenTofu; Authentik registry has no GPG signing keys, so publisher signature verification is unavailable.")
        return 0
    finally:
        shutil.rmtree(fixture)


if __name__ == "__main__":
    raise SystemExit(main())
