"""Offline checks for the locally served Authentik application icons."""

import hashlib
from pathlib import Path
import re
import struct
import unittest
import xml.etree.ElementTree as ET


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
        for app, filename in [
            ("forgejo", "authentik.tf"),
            ("miniflux", "miniflux.tf"),
            ("hermes", "authentik.tf"),
        ]:
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

    def test_hermes_svg_is_self_contained(self):
        svg = ET.parse(BRANDING / "sources/hermes.svg").getroot()
        ns = {"svg": "http://www.w3.org/2000/svg"}
        self.assertEqual(svg.attrib["viewBox"], "0 0 64 64")
        self.assertEqual(svg.attrib["aria-label"], "Hermes caduceus")
        stops = svg.findall("svg:defs/svg:linearGradient/svg:stop", ns)
        self.assertEqual(
            [(stop.attrib["offset"], stop.attrib["stop-color"]) for stop in stops],
            [("0", "#08EBF1"), ("1", "#3889FD")],
        )
        group = svg.find("svg:g", ns)
        self.assertEqual(
            group.attrib["transform"], "translate(-24.93 -29.13) scale(0.09075)"
        )
        path = group.find("svg:path", ns)
        self.assertEqual(path.attrib["fill"], "url(#hermes-mark)")
        self.assertEqual(path.attrib["fill-rule"], "evenodd")
        self.assertEqual(path.attrib["d"].count(" Z"), 7)
        allowed_tags = {"svg", "defs", "linearGradient", "stop", "g", "path"}
        for element in svg.iter():
            self.assertIn(element.tag.removeprefix(f"{{{ns['svg']}}}"), allowed_tags)
            self.assertFalse(any(
                name.startswith("on") or "href" in name or name in {"class", "style"}
                for name in element.attrib
            ))
        # The PNG renderer retains an alpha channel for transparent backgrounds.
        self.assertEqual((BRANDING / "hermes.png").read_bytes()[25], 6)

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
