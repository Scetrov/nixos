"""Exercise the exact application-specific claim expression without credentials."""

import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[2]


class FilebrowserIdentityTests(unittest.TestCase):
    def setUp(self):
        self.enrollments = json.loads((ROOT / "src/filebrowser-enrollments.json").read_text())
        self.names = {e["identity_uuid"]: e["unix_username"] for e in self.enrollments}
        source = (ROOT / "terraform/filebrowser.tf").read_text()
        expression = re.search(r"expression = <<-EOT\n(.*?)\n  EOT", source, re.S).group(1)
        expression = expression.replace("${jsonencode(local.filebrowser_usernames)}", json.dumps(self.names))
        self.claim = compile("def claim(request):\n" + expression + "\n", "filebrowser-profile", "exec")

    def emit(self, identity, username="RENAMED"):
        namespace = {}
        exec(self.claim, namespace)
        return namespace["claim"](SimpleNamespace(user=SimpleNamespace(uuid=identity, username=username)))

    def test_enrollment_is_unique_and_canonical(self):
        self.assertEqual(len(self.enrollments), len(self.names))
        self.assertEqual(len(self.names), len(set(self.names.values())))
        self.assertEqual(set(self.names.values()), {"scetrov", "pinkgiraffes", "flyingfire"})
        for identity, name in self.names.items():
            self.assertEqual(str(uuid.UUID(identity)), identity)
            self.assertRegex(name, r"^[a-z_][a-z0-9_-]{0,31}$")

    def test_claim_uses_uuid_not_mutable_username(self):
        for identity, name in self.names.items():
            self.assertEqual(self.emit(identity), {"preferred_username": name})
            self.assertEqual(self.emit(identity, "a-different-login"), {"preferred_username": name})

    def test_unenrolled_identity_cannot_reuse_username(self):
        for name in self.names.values():
            with self.assertRaisesRegex(Exception, "not enrolled"):
                self.emit("00000000-0000-0000-0000-000000000000", name)

    def test_case_changed_identity_fails_closed(self):
        for identity in self.names:
            with self.assertRaisesRegex(Exception, "not enrolled"):
                self.emit(identity.upper())


if __name__ == "__main__":
    unittest.main()
