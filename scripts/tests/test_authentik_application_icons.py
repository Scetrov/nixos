"""Offline checks for the locally served Authentik application icons."""

import hashlib
from pathlib import Path
import re
import struct
import unittest


ROOT = Path(__file__).resolve().parents[2]
BRANDING = ROOT / "src/roles/nixos/files/etc/nixos/branding"


class ApplicationIconTests(unittest.TestCase):
    def test_visible_applications_have_icons(self):
        for source in (ROOT / "terraform").glob("*.tf"):
            for name, body in re.findall(
                r'resource "authentik_application" "([^"]+)"\s*\{([^}]+)\}',
                source.read_text(),
            ):
                with self.subTest(application=name):
                    if not re.search(r"meta_hide\s*=\s*true", body):
                        self.assertRegex(body, r'meta_icon\s*=\s*"[^"]+"')

    def test_new_icons_are_local_and_deployed(self):
        tasks = (ROOT / "src/roles/nixos/tasks/main.yml").read_text()
        self.assertIn("tags: [authentik-branding]", tasks)
        for app, filename in [("forgejo", "authentik.tf"), ("miniflux", "miniflux.tf")]:
            with self.subTest(application=app):
                source = (ROOT / "terraform" / filename).read_text()
                body = re.search(
                    rf'resource "authentik_application" "{app}"\s*\{{([^}}]+)\}}',
                    source,
                ).group(1)
                self.assertIn(f'"/static/dist/branding/{app}.png"', body)
                self.assertIn(f"    - {app}.png\n", tasks)
                image = (BRANDING / f"{app}.png").read_bytes()
                self.assertEqual(image[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(struct.unpack(">II", image[16:24]), (512, 512))

    def test_upstream_assets_match_recorded_hashes(self):
        expected = {
            "sources/forgejo.svg": "acfeda65446d1c17c5d8e62e18b70a6616ef20df81e7de93ff791a3b11d4be28",
            "miniflux.png": "5fcba35404ffcd8994d615df09653c00812f2b4d6539eb511df4f9e3cd4f8c5a",
        }
        for filename, checksum in expected.items():
            with self.subTest(asset=filename):
                self.assertEqual(hashlib.sha256((BRANDING / filename).read_bytes()).hexdigest(), checksum)


if __name__ == "__main__":
    unittest.main()
