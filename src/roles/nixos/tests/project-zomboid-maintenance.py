#!/usr/bin/env python3
"""Exercise rendered maintenance control flow without touching the live server.

Pass paths from `nix-build` of the launch and maintenance scripts rendered by
project-zomboid-eval.nix. All state and systemctl/SteamCMD calls are sandboxed.
"""

import pathlib
import re
import subprocess
import sys
import tempfile


def run(script: pathlib.Path, operation: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), operation, *args],
        text=True,
        capture_output=True,
        check=False,
    )


def main(maintenance: pathlib.Path, launch: pathlib.Path) -> None:
    assert "-adminpassword" not in launch.read_text(), "admin password exposed in argv"
    with tempfile.TemporaryDirectory(prefix="pz-maintenance-test-") as temporary:
        root = pathlib.Path(temporary)
        state = root / "state"
        for name in ("steam", "Zomboid", ".local", ".steam", "locks", "backups"):
            (state / name).mkdir(parents=True)
        (state / ".local" / "session").write_text("fake-session")
        mockbin = root / "bin"
        mockbin.mkdir()
        events = root / "events"
        (mockbin / "systemctl").write_text(
            f'#!/bin/sh\necho "$*" >> {events}\nexit 0\n'
        )
        (mockbin / "runuser").write_text(
            f'#!/bin/sh\necho "runuser $1 $2" >> {events}\n'
            'shift 3\nexec "$@"\n'
        )
        (mockbin / "steamcmd").write_text("#!/bin/sh\nexit 42\n")
        for path in mockbin.iterdir():
            path.chmod(0o755)

        source = maintenance.read_text().replace(
            "/var/lib/project-zomboid", str(state)
        )
        source = re.sub(r"/nix/store/[^\s:]+-systemd-[^\s:]+/bin", str(mockbin), source)
        source = re.sub(r"/nix/store/[^\s]+/bin/runuser", str(mockbin / "runuser"), source)
        source = source.replace("/bin/true", str(mockbin / "steamcmd"))
        harness = root / "maintenance"
        harness.write_text(source)

        result = run(harness, "backup")
        assert result.returncode == 0, result.stderr
        archives = list((state / "backups").glob("*.tar.gz"))
        assert len(archives) == 1
        listing = subprocess.check_output(["tar", "-tzf", str(archives[0])], text=True)
        assert all(path in listing for path in ("steam/", "Zomboid/", ".local/session"))

        # An incomplete archive must not become a selectable recovery point.
        (state / ".local" / "session").unlink()
        (state / ".local").rmdir()
        result = run(harness, "backup")
        assert result.returncode != 0
        assert list((state / "backups").glob("*.tar.gz")) == archives
        assert not list((state / "backups").glob(".incomplete.*"))
        (state / ".local").mkdir()

        events.write_text("")
        invalid = state / "backups" / "invalid.tar.gz"
        invalid.write_text("corrupt")
        result = run(harness, "restore", str(invalid))
        assert result.returncode != 0
        assert events.read_text() == "", "restore touched live service before validation"
        assert (state / "steam").is_dir() and (state / "Zomboid").is_dir()
        invalid.unlink()

        events.write_text("")
        result = run(harness, "update")
        assert result.returncode != 0
        recorded = events.read_text()
        assert "stop project-zomboid.service" in recorded
        assert "runuser -u project-zomboid" in recorded
        assert "start project-zomboid.service" not in recorded
        assert len(list((state / "backups").glob("*.tar.gz"))) == 2
        print("PASS: full-state backup, incomplete archive, invalid restore, failed update, non-root SteamCMD, no argv password")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: project-zomboid-maintenance.py MAINTENANCE_SCRIPT LAUNCH_SCRIPT")
    main(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
