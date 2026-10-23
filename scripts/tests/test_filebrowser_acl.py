"""Offline ACL-mask regression checks; filesystem behavior is tested on Habiki."""

import unittest

from scripts.filebrowser_acl import managed_acl, parse_acl


class FilebrowserACLTests(unittest.TestCase):
    ORIGINAL = "user::rwx\nuser:62004:rwx\ngroup::rwx\ngroup:62005:rwx\nmask::r--\nother::---\n"

    def apply(self, text, directory=True):
        return managed_acl(text, service_uid=62001, unix_uid=62002, inode_uid=62002, directory=directory)

    def test_mask_widening_preserves_unrelated_effective_permissions(self):
        acl = parse_acl(self.apply(self.ORIGINAL))
        for tag, who in (("user", "62004"), ("group", ""), ("group", "62005")):
            self.assertEqual(acl[(False, tag, who)], 4)
        self.assertEqual(acl[(False, "mask", "")], 7)
        self.assertEqual(acl[(False, "other", "")], 0)

    def test_defaults_and_managed_owner_have_full_access(self):
        acl = parse_acl(self.apply(self.ORIGINAL))
        for default in (False, True):
            for uid in ("62001", "62002"):
                self.assertEqual(acl[(default, "user", uid)], 7)
            self.assertEqual(acl[(default, "user", "")], 7)

    def test_existing_default_mask_is_preserved_for_unrelated_entries(self):
        original = self.ORIGINAL + "default:user::rwx\ndefault:user:62004:rwx\ndefault:group::rwx\ndefault:mask::r-x\ndefault:other::---\n"
        acl = parse_acl(self.apply(original))
        self.assertEqual(acl[(True, "user", "62004")], 5)
        self.assertEqual(acl[(True, "group", "")], 5)

    def test_reapplication_is_idempotent(self):
        first = self.apply(self.ORIGINAL)
        self.assertEqual(first, self.apply(first))

    def test_regular_file_does_not_acquire_execute_or_defaults(self):
        result = parse_acl(self.apply(self.ORIGINAL, directory=False))
        self.assertEqual(result[(False, "user", "62001")], 6)
        self.assertFalse(any(key[0] for key in result))

    def test_unrelated_inode_owner_is_not_modified(self):
        original = "user::r--\ngroup::---\nother::---\n"
        acl = parse_acl(managed_acl(original, service_uid=62001, unix_uid=62002, inode_uid=62004, directory=False))
        self.assertEqual(acl[(False, "user", "")], 4)

    def test_root_or_same_principal_is_rejected(self):
        for service, unix in ((0, 62002), (62001, 0), (62001, 62001)):
            with self.assertRaises(ValueError):
                managed_acl(self.ORIGINAL, service_uid=service, unix_uid=unix, inode_uid=unix, directory=True)


if __name__ == "__main__":
    unittest.main()
