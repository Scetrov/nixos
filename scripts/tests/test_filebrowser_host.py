"""Host enrollment validation tests; no privileged commands or personal paths."""

import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import filebrowser_host as host

ALICE = {"identity_uuid": "11111111-1111-4111-8111-111111111111", "unix_username": "alice"}


class EnrollmentTests(unittest.TestCase):
    def test_invalid_and_duplicate_identity_records_fail(self):
        bad = [
            [ALICE, ALICE],
            [{**ALICE, "unix_username": "Alice"}],
            [{**ALICE, "unix_username": "../alice"}],
            [{**ALICE, "identity_uuid": "alice"}],
            [{**ALICE, "documents": "/etc"}],
            [ALICE, {**ALICE, "unix_username": "bob"}],
            [ALICE, {**ALICE, "identity_uuid": "22222222-2222-4222-8222-222222222222"}],
        ]
        for records in bad:
            with self.subTest(records=records), self.assertRaises(host.EnrollmentError):
                host.validate_enrollments(records)

    def test_existing_account_is_not_modified_and_contents_survive(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "alice"
            docs = home / "Documents"
            docs.mkdir(parents=True)
            (docs / "keep").write_text("personal-fixture")
            account = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_dir=str(home))
            with patch.object(host.pwd, "getpwnam", return_value=account), patch.object(host.subprocess, "run") as run:
                result = host.resolve_accounts([ALICE], create_missing=True)
                run.assert_not_called()
            self.assertEqual(result[0]["documents"], str(docs))
            self.assertEqual((docs / "keep").read_text(), "personal-fixture")

    def test_missing_documents_is_created_without_changing_home(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "alice"
            home.mkdir()
            mode = home.stat().st_mode
            account = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_dir=str(home))
            # Non-root developer processes can fchown to their current UID/GID.
            with patch.object(host.pwd, "getpwnam", return_value=account):
                host.resolve_accounts([ALICE])
            self.assertTrue((home / "Documents").is_dir())
            self.assertEqual(home.stat().st_mode, mode)

    def test_missing_account_requires_explicit_creation(self):
        with patch.object(host.pwd, "getpwnam", side_effect=KeyError), self.assertRaises(host.EnrollmentError):
            host.resolve_accounts([ALICE])

    def test_new_account_has_locked_password_and_noninteractive_shell(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "alice"
            home.mkdir()
            (home / "Documents").mkdir()
            account = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_dir=str(home))
            with patch.object(host.pwd, "getpwnam", side_effect=[KeyError(), account]), patch.object(host.os.path, "lexists", return_value=False), patch.object(host.subprocess, "run") as run:
                host.resolve_accounts([ALICE], create_missing=True)
                argv = run.call_args.args[0]
                self.assertEqual(argv[0], "useradd")
                self.assertEqual(argv[argv.index("--password") + 1], "!")
                self.assertTrue(argv[argv.index("--shell") + 1].endswith("/nologin"))

    def test_unsafe_homes_and_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "alice"
            home.mkdir()
            for value in ("/", "/home", "relative/home", str(home) + "/../alice", str(home) + "/.", str(home) + "/"):
                with self.subTest(value=value), self.assertRaises(host.EnrollmentError):
                    host.validate_home(value, os.getuid())
            (home / "Documents").symlink_to(temporary)
            with self.assertRaises(host.EnrollmentError):
                host.validate_home(str(home), os.getuid())
            alias = Path(temporary) / "alias"
            alias.symlink_to(home)
            with self.assertRaises(OSError):
                host.open_directory(alias)

    def test_walk_skips_symlinks_and_rejects_hardlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "file").write_text("fixture")
            (root / "escape").symlink_to("/etc")
            self.assertEqual({rel for _, rel, _ in host.walk_descriptors(root)}, {".", "file"})
            os.link(root / "file", root / "hardlink")
            with self.assertRaises(host.EnrollmentError):
                list(host.walk_descriptors(root))

    def test_reassignment_and_offboarding_fail_before_account_or_acl_mutations(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = {"service_uid": 62001, "enrollments": [{**ALICE, "uid": 62002, "documents": "/fixture/alice/Documents"}], "acls": {}}
            (Path(temporary) / "enrollment.json").write_text(json.dumps(state))
            with patch.object(host.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=62001)), patch.object(host, "resolve_accounts") as resolve:
                for records in ([], [{**ALICE, "unix_username": "bob"}]):
                    with self.assertRaises(host.EnrollmentError):
                        host.prepare(records, temporary, "filebrowser")
                resolve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
