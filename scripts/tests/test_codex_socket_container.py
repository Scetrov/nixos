"""RUN_CODEX_CONTAINER_TESTS=1 after loading the repository-built Codex image."""
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.environ.get("RUN_CODEX_CONTAINER_TESTS") == "1", "explicit rootless container test")
class CodexSocketIntegration(unittest.TestCase):
    def test_host_can_probe_exported_socket_without_container_symlink(self):
        root = Path(tempfile.mkdtemp(prefix="codex-socket-regression-"))
        state = root / "state"
        state.mkdir(mode=0o700)
        runtime = root / "runtime"
        runtime.mkdir()
        runtime.chmod(0o2750)
        name = f"codex-socket-regression-{os.getpid()}"
        try:
            subprocess.run([
                "podman", "run", "-d", "--name", name, "--network=none",
                "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                "--userns=keep-id:uid=10001,gid=10001", "--group-add=keep-groups",
                "--user=10001:10001", "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=16m",
                "-v", f"{state}:/var/lib/codex-app-server:rw",
                "-v", f"{runtime}:/run/codex-app-server:rw",
                "codex-app-server:0.162.0",
            ], check=True, capture_output=True)
            probe = subprocess.run([
                "python3", str(ROOT / "src/roles/nixos/files/etc/nixos/pkgs/codex-app-server-readiness.py"),
                "--socket", str(runtime / "control.sock"), "--timeout", "60",
            ], capture_output=True, text=True, timeout=65)
            self.assertEqual(probe.returncode, 0, probe.stdout + probe.stderr)
            socket = runtime / "control.sock"
            self.assertFalse(socket.is_symlink())
            self.assertTrue(stat.S_ISSOCK(socket.stat().st_mode))
            self.assertEqual(stat.S_IMODE(socket.stat().st_mode), 0o660)
        finally:
            subprocess.run(["podman", "rm", "-f", name], capture_output=True, check=False)
            subprocess.run(["podman", "unshare", "rm", "-rf", str(root)], check=True)


if __name__ == "__main__":
    unittest.main()
