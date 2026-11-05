"""Exercise the actual Ansible cleanup tasks against a local Authentik API stub."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest


ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / "src/roles/authentik-config/tasks/deploy-blueprint.yml"


@unittest.skipUnless(shutil.which("ansible-playbook"), "ansible-playbook required")
class BlueprintCleanupTests(unittest.TestCase):
    def run_cleanup(self, statuses, bearer=True):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_DELETE(self):
                requests.append((self.path, dict(self.headers)))
                status = statuses[min(len(requests) - 1, len(statuses) - 1)]
                self.send_response(status)
                self.end_headers()

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            # Include the production cleanup, not a reimplementation of its retry logic.
            source = TASKS.read_text().split("\n  always:\n", 1)[1]
            cleanup = source.split(
                "    - name: Remove the temporary blueprint file from the controller", 1
            )[0]
            cleanup = "\n".join(line[4:] for line in cleanup.splitlines()) + "\n"
            with tempfile.TemporaryDirectory() as directory:
                task_file = Path(directory) / "cleanup.yml"
                task_file.write_text(cleanup)
                play_file = Path(directory) / "play.json"
                play_file.write_text(json.dumps([{
                    "hosts": "localhost",
                    "gather_facts": False,
                    "vars": {
                        "ansible_connection": "local",
                        "authentik_config_blueprint_api_token": "test-token" if bearer else "",
                        "authentik_config_blueprint_cookie_header": "session=test-session",
                        "authentik_config_blueprint_csrf_token": "test-csrf",
                        "authentik_config_blueprint_delegate_host": "localhost",
                        "authentik_config_blueprint_api_base_url_effective":
                            f"http://127.0.0.1:{server.server_port}/api/v3",
                        "authentik_config_api_base_url": "http://unused.invalid",
                        "authentik_config_blueprint_validate_certs_effective": True,
                        "authentik_config_blueprint_instance_json": {"pk": "test-instance"},
                    },
                    "tasks": [{"ansible.builtin.include_tasks": str(task_file)}],
                }]))
                result = subprocess.run(
                    ["ansible-playbook", "-i", "localhost,", str(play_file)],
                    cwd=directory, capture_output=True, text=True, timeout=90,
                    env={**os.environ, "ANSIBLE_NOCOLOR": "1"},
                )
            return result, requests
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_retries_transient_server_failure_for_both_auth_methods(self):
        for bearer in (True, False):
            with self.subTest(bearer=bearer):
                result, requests = self.run_cleanup([500, 204], bearer)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(len(requests), 2)
                path, headers = requests[-1]
                self.assertEqual(path, "/api/v3/managed/blueprints/test-instance/")
                if bearer:
                    self.assertEqual(headers["Authorization"], "Bearer test-token")
                else:
                    self.assertEqual(headers["Cookie"], "session=test-session")
                    self.assertEqual(headers["X-Csrftoken"], "test-csrf")

    def test_success_does_not_retry(self):
        result, requests = self.run_cleanup([204])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(requests), 1)

    def test_missing_instance_is_already_clean(self):
        result, requests = self.run_cleanup([404])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(requests), 1)

    def test_persistent_server_failure_is_not_hidden(self):
        result, requests = self.run_cleanup([500])
        self.assertNotEqual(result.returncode, 0)
        self.assertGreater(len(requests), 1)
        self.assertLessEqual(len(requests), 6)
        self.assertNotIn("test-token", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
