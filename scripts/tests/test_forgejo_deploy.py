"""Focused deployment routing and explicit phase/scope guards."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class FocusedDeployTests(unittest.TestCase):
    def test_wrapper_routes_without_shared_secret_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "ansible-playbook"
            binary.write_text('#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n')
            binary.chmod(0o700)
            env = os.environ.copy()
            env["PATH"] = directory + ":" + env["PATH"]
            result = subprocess.run([str(ROOT / "scripts/play.sh"), "--limit", "habiki", "--tags", "forgejo-mirrors", "--", "--list-tasks"],
                                    cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            args = json.loads(result.stdout.splitlines()[-1])
            self.assertIn("src/forgejo-mirrors.yml", args)
            self.assertNotIn("Refreshing OpenTofu", result.stdout)

    def test_wrapper_rejects_scope_widening(self):
        for args in [["--limit", "fyne", "--tags", "forgejo-mirrors"],
                     ["--limit", "habiki", "--tags", "forgejo-mirrors,nixos"],
                     ["--limit", "habiki", "--tags", "forgejo-mirrors", "--", "--limit", "all"]]:
            result = subprocess.run([str(ROOT / "scripts/play.sh"), *args], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)

    def test_focused_play_guards_imports_and_avoids_broad_roles(self):
        text = (ROOT / "src/forgejo-mirrors.yml").read_text()
        self.assertIn("c.reportOnly && !c.importApproved", text)
        self.assertIn("forgejo_mirrors_imports_approved | default(false)", text)
        self.assertIn("approved && !c.reportOnly && c.importApproved && c.lfsVerified", text)
        self.assertIn("host.services.forgejo.lfs.enable", text)
        self.assertIn("!c.githubCredential && !c.privateAuthVerified", text)
        self.assertIn('namespace = "gh-Scetrov"; namespaceId = 6;', text)
        self.assertIn('namespace = "gh-RichardSlater"; namespaceId = 4;', text)
        self.assertIn('namespace = "gh-storytold"; namespaceId = 3;', text)
        self.assertIn("500 * 1024**3", text)
        self.assertIn("!p.includePrivate && !p.includeForks && !p.includeArchived", text)
        self.assertIn("forgejo_mirrors_apply | default(false)", text)
        self.assertIn("always:", text)
        self.assertNotIn("include_role:", text)
        self.assertNotIn("nix-channel", text)
        self.assertNotIn("podman-frontier-indexer.service", text)
        alloy = (ROOT / "src/roles/nixos/files/etc/nixos/modules/alloy.nix").read_text()
        self.assertIn('discovery.relabel "forgejo_mirrors"', alloy)
        self.assertIn('targets = discovery.relabel.forgejo_mirrors.output', alloy)
        self.assertIn('replacement = "forgejo-mirrors"', alloy)


if __name__ == "__main__":
    unittest.main()
