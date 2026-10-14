"""Regression for blueprint reconciliation overwriting OpenTofu-owned groups.

RUN_CONTAINER_TESTS=1 enables the real pinned Authentik importer against an
isolated, disposable Postgres database. No host ports or live credentials.
"""
import os
from pathlib import Path
import subprocess
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "src/roles/authentik-config/templates/blueprint-primary-admin.yaml.j2"
AUTHENTIK = "ghcr.io/goauthentik/server:2026.8.3@sha256:ab9b4e8cc4ab3f8d1198d2db6aeea66bafea1963b3f2843589e0d163f97d9849"
POSTGRES = "docker.io/library/postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24"


def render(username="fixture-admin"):
    # This template uses only simple substitutions; keep default tests stdlib-only.
    text = TEMPLATE.read_text()
    values = {
        "authentik_config_primary_admin_username": username,
        "authentik_config_primary_admin_name": "Fixture Admin",
        "authentik_config_primary_admin_email": "admin@example.invalid",
        "authentik_config_primary_admin_path": "users",
        "authentik_config_primary_admin_password": "disposable-test-password",
    }
    for key, value in values.items():
        text = text.replace("{{ " + key + " }}", value)
    assert "{{" not in text and "{%" not in text, "fixture needs a template renderer update"
    return text


class BlueprintOwnershipTests(unittest.TestCase):
    def test_only_creation_entries_assign_groups(self):
        # Fast ownership guard; the opt-in test exercises actual YAML/importer semantics.
        for username in ["fixture-admin", "scetrov"]:
            entries = render(username).split("  - model:")[1:]
            assignments = [entry for entry in entries if "      groups:" in entry]
            self.assertTrue(assignments, "fresh accounts still need admin access")
            for entry in assignments:
                self.assertIn("    state: created\n", entry,
                              "steady-state blueprint must not replace memberships")
            updates = [entry for entry in entries if "    state: created\n" not in entry]
            self.assertTrue(any("      password:" in e for e in updates),
                            "primary admin credentials must remain reconciled")


@unittest.skipUnless(os.environ.get("RUN_CONTAINER_TESTS") == "1",
                     "set RUN_CONTAINER_TESTS=1 for the pinned importer regression")
class BlueprintImporterTests(unittest.TestCase):
    def test_repeated_import_preserves_membership_and_bootstraps_admin(self):
        suffix = uuid.uuid4().hex[:12]
        network = "authentik-groups-" + suffix
        database = "authentik-groups-db-" + suffix
        app = "authentik-groups-app-" + suffix

        def run(*args, timeout=300):
            result = subprocess.run(["podman", *args], capture_output=True,
                                    text=True, timeout=timeout, check=False)
            self.assertEqual(result.returncode, 0,
                             (result.stdout + result.stderr)[-6000:])
            return result.stdout

        env = ["--env", "AUTHENTIK_POSTGRESQL__HOST=" + database,
               "--env", "AUTHENTIK_POSTGRESQL__USER=authentik",
               "--env", "AUTHENTIK_POSTGRESQL__PASSWORD=disposable-test-password",
               "--env", "AUTHENTIK_POSTGRESQL__NAME=authentik",
               "--env", "AUTHENTIK_SECRET_KEY=disposable-regression-fixture-key"]
        try:
            run("network", "create", "--internal", network)
            run("run", "-d", "--name", database, "--network", network,
                "--env", "POSTGRES_USER=authentik",
                "--env", "POSTGRES_PASSWORD=disposable-test-password", POSTGRES)
            # Authentik's bootstrap waits for Postgres readiness.
            run("run", "--rm", "--name", app, "--network", network,
                *env, "--entrypoint", "python", AUTHENTIK, "-c",
                "from lifecycle.wait_for_db import wait_for_db; wait_for_db(); "
                "from lifecycle.migrate import run_migrations; run_migrations()", timeout=600)
            code = '''
from authentik.core.models import Group, User
from authentik.blueprints.v1.importer import Importer
admins, _ = Group.objects.get_or_create(name="authentik Admins", defaults={"is_superuser": True})
expected = [admins]
for name in ["All Applications", "Forgejo Owners", "Unrelated Membership"]:
    group, _ = Group.objects.get_or_create(name=name)
    expected.append(group)
for username in ["fixture-admin", "scetrov"]:
    user, _ = User.objects.get_or_create(username=username)
    user.ak_groups.set(expected)

def apply(text):
    importer = Importer.from_string(text)
    assert importer.apply(), "blueprint import failed"

for text in BLUEPRINTS:
    for _ in range(3):
        apply(text)
        for username in ["fixture-admin", "scetrov"]:
            user = User.objects.get(username=username)
            assert set(user.ak_groups.all()) == set(expected), (username, list(user.ak_groups.values_list("name", flat=True)))
# First-boot admin creation must still work, then preserve added access too.
apply(FRESH_BLUEPRINT)
fresh = User.objects.get(username="fresh-admin")
assert admins in fresh.ak_groups.all(), "fresh admin lacks admin group"
assert fresh.check_password("disposable-test-password"), "password not reconciled"
fresh.ak_groups.set(expected)
apply(FRESH_BLUEPRINT)
fresh.refresh_from_db()
assert set(fresh.ak_groups.all()) == set(expected), "fresh admin loses subsequent memberships"
print("PASS: repeated imports preserve both users, shared identity, unrelated groups and fresh admin bootstrap")
'''
            code = ("BLUEPRINTS = " + repr([render(), render("scetrov")]) + "\n"
                    + "FRESH_BLUEPRINT = " + repr(render("fresh-admin")) + "\n" + code)
            output = run("run", "--rm", "--name", app, "--network", network,
                         *env, AUTHENTIK, "shell", "-c", code)
            self.assertIn("PASS: repeated imports", output)
        finally:
            for name in [app, database]:
                subprocess.run(["podman", "rm", "-fv", name], capture_output=True, check=False)
            subprocess.run(["podman", "network", "rm", network], capture_output=True, check=False)


if __name__ == "__main__":
    unittest.main()
