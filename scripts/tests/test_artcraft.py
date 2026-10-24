"""Regression checks for verified release inputs and safe ArtCraft publication."""

import hashlib
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock
import zipfile

from scripts import artcraft


class ArtcraftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "published"
        self.site = self.base / "candidate"
        self.site.mkdir()
        (self.site / "index.html").write_text('<script src="./app.js"></script>')
        (self.site / "app.js").write_text("// local application")
        (self.site / "app.wasm").write_bytes(b"\0asm\x01\0\0\0")
        self.keys = [hashlib.sha256(str(i).encode()).hexdigest() for i in range(3)]

    def publish(self, index):
        return artcraft.publish(self.root, "photocraft", self.keys[index], self.site)

    def test_validate_complete_local_site(self):
        self.assertEqual(set(artcraft.validate_site(self.site)), {"index.html", "app.js", "app.wasm"})

    def test_reject_missing_asset_or_root_absolute_url(self):
        for url in ("missing.js", "/photocraft/app.js", "../app.js", "%2fetc/passwd"):
            with self.subTest(url=url):
                (self.site / "index.html").write_text(f'<script src="{url}"></script>')
                with self.assertRaises(ValueError):
                    artcraft.validate_site(self.site)

    def test_reject_symlink_and_hidden_file(self):
        (self.site / "link").symlink_to(self.base)
        with self.assertRaises(ValueError):
            artcraft.validate_site(self.site)
        (self.site / "link").unlink()
        (self.site / ".env").touch()
        with self.assertRaises(ValueError):
            artcraft.validate_site(self.site)

    def test_reject_invalid_wasm(self):
        (self.site / "app.wasm").write_text("not WASM")
        with self.assertRaises(ValueError):
            artcraft.validate_site(self.site)

    def test_publication_reuse(self):
        self.assertTrue(self.publish(0))
        self.assertFalse(self.publish(0))
        self.assertEqual((self.root / "photocraft").resolve().name, self.keys[0])
        self.assertFalse((self.root / "previous" / "photocraft").exists())

    def test_failure_keeps_working_version(self):
        self.publish(0)
        (self.site / "app.wasm").unlink()
        with self.assertRaises(ValueError):
            self.publish(1)
        self.assertEqual((self.root / "photocraft").resolve().name, self.keys[0])

    def test_failed_copy_keeps_working_version(self):
        self.publish(0)
        with mock.patch.object(artcraft.shutil, "copytree", side_effect=OSError("simulated disk failure")):
            with self.assertRaises(OSError):
                self.publish(1)
        self.assertEqual((self.root / "photocraft").resolve().name, self.keys[0])

    def test_key_cannot_be_reused_for_different_output(self):
        self.publish(0)
        (self.site / "app.js").write_text("changed")
        with self.assertRaises(ValueError):
            self.publish(0)

    def test_publication_retains_only_one_previous_and_rollback_swaps(self):
        for i in range(3):
            (self.site / "app.js").write_text(str(i))
            self.publish(i)
        versions = self.root / "versions" / "photocraft"
        self.assertEqual({p.name for p in versions.iterdir()}, set(self.keys[1:]))
        self.assertTrue(artcraft.publish(self.root, "photocraft", rollback=True))
        self.assertEqual((self.root / "photocraft").resolve().name, self.keys[1])
        self.assertEqual((self.root / "previous" / "photocraft").resolve().name, self.keys[2])

    def test_missing_previous_cannot_change_current(self):
        self.publish(0)
        with self.assertRaises(ValueError):
            artcraft.publish(self.root, "photocraft", rollback=True)
        self.assertEqual((self.root / "photocraft").resolve().name, self.keys[0])

    def test_reject_unmanaged_publication(self):
        (self.root / "photocraft").mkdir(parents=True)
        with self.assertRaises(ValueError):
            self.publish(0)

    def test_extract_complete_package_without_hosting_helpers(self):
        archive = self.base / "package.zip"
        with zipfile.ZipFile(archive, "w") as package:
            for path in self.site.iterdir():
                package.write(path, "editor/" + path.name)
            package.writestr("editor/fonts/font.ttf", b"font")
            package.writestr("editor/.htaccess", "upstream config")
            package.writestr("editor/_headers", "upstream headers")
        result = artcraft.unpack_package(archive, self.base / "unpacked")
        self.assertIn("fonts/font.ttf", result)
        self.assertNotIn(".htaccess", result)
        self.assertNotIn("_headers", result)

    def test_reject_archive_traversal(self):
        archive = self.base / "bad.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("editor/../../escape", "bad")
        with self.assertRaises(ValueError):
            artcraft.unpack_package(archive, self.base / "unpacked")
        self.assertFalse((self.base / "escape").exists())

    def release(self):
        work = self.base / "downloads-work"
        downloads = work / "downloads"
        downloads.mkdir(parents=True)
        archive = downloads / "photocraft-web-1.0.zip"
        with zipfile.ZipFile(archive, "w") as package:
            for path in self.site.iterdir():
                package.write(path, "editor/" + path.name)
        editor = {"slug": "photocraft", "asset": archive.name, "sha256": artcraft.sha256(archive)}
        return work, archive, editor

    def test_checksum_failure_preserves_publication(self):
        self.publish(0)
        work, archive, editor = self.release()
        archive.write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            artcraft.prepare(work, editor)
        self.assertEqual((self.root / "photocraft").resolve().name, self.keys[0])
        self.assertFalse((work / "packages").exists())

    def test_missing_download_preserves_publication(self):
        self.publish(0)
        work, archive, editor = self.release()
        archive.unlink()
        with self.assertRaises(FileNotFoundError):
            artcraft.prepare(work, editor)
        self.assertEqual((self.root / "photocraft").resolve().name, self.keys[0])

    def test_reject_archive_links_special_files_and_duplicates(self):
        for mode in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR):
            with self.subTest(mode=mode):
                archive = self.base / "bad.zip"
                with zipfile.ZipFile(archive, "w") as package:
                    entry = zipfile.ZipInfo("editor/link")
                    entry.external_attr = (mode | 0o777) << 16
                    package.writestr(entry, "/etc/passwd")
                with self.assertRaises(ValueError):
                    artcraft.unpack_package(archive, self.base / "unpacked")
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("editor/a", "first")
            package.writestr("editor/./a", "second")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            artcraft.unpack_package(archive, self.base / "unpacked")
        self.assertFalse((self.base / "unpacked").exists())

    def test_missing_inline_boot_or_module_is_rejected(self):
        for code in ('import("./missing.js")', 'fetch("./boot.bin")',
                     'import init from "./missing.js"', 'new URL("./missing.wasm", location.href)'):
            with self.subTest(code=code):
                (self.site / "index.html").write_text("<script>" + code + "</script>")
                with self.assertRaises(ValueError):
                    artcraft.validate_site(self.site)

    def test_ansible_does_not_parse_success_json_on_failure(self):
        tasks = Path(__file__).resolve().parents[2] / "src/roles/artcraft/tasks/editor.yml"
        conditions = [line.strip() for line in tasks.read_text().splitlines() if "changed_when:" in line]
        self.assertEqual(len(conditions), 3)
        for condition in conditions:
            self.assertRegex(condition, r"\.rc == 0 and .*from_json")

    def test_unchanged_download_reuses_verified_output(self):
        work, archive, editor = self.release()
        first = artcraft.prepare(work, editor)
        self.assertTrue(first["changed"])
        with mock.patch.object(artcraft, "unpack_package") as unpack:
            second = artcraft.prepare(work, editor)
        unpack.assert_not_called()
        self.assertFalse(second["changed"])
        self.assertEqual(first["key"], second["key"])
        (Path(first["site"]) / "app.js").write_text("corrupt")
        with self.assertRaisesRegex(ValueError, "cached package"):
            artcraft.prepare(work, editor)

    def test_invalid_candidate_preserves_publication(self):
        self.publish(0)
        (self.site / "app.wasm").unlink()
        work, archive, editor = self.release()
        with self.assertRaises(ValueError):
            artcraft.prepare(work, editor)
        self.assertEqual((self.root / "photocraft").resolve().name, self.keys[0])

    def test_release_inventory_covers_thirteen_versioned_assets(self):
        inventory = Path(__file__).resolve().parents[2] / "config/artcraft.yml"
        text = inventory.read_text()
        self.assertEqual(text.count("  - slug:"), 13)
        self.assertEqual(text.count("    sha256:"), 13)
        self.assertEqual(text.count("    icon_sha256:"), 13)
        self.assertEqual(text.count("https://github.com/storytold/"), 13)
        self.assertNotIn("/latest/", text)
        self.assertNotIn("artcraft_toolchain", text)
        self.assertNotIn("source_sha256", text)


if __name__ == "__main__":
    unittest.main()
