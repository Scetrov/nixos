#!/usr/bin/env python3
"""Exercise rendered maintenance control flow without touching the live server.

Pass paths from `nix-build` of the launch and maintenance scripts rendered by
project-zomboid-eval.nix. All state and systemctl/SteamCMD calls are sandboxed.
"""

import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

WORKSHOP_APPID = "108600"


def run(script: pathlib.Path, operation: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), operation, *args],
        text=True,
        capture_output=True,
        check=False,
    )


def clear_archives(state: pathlib.Path) -> None:
    """Drop recovery points so repeated updates in one second do not collide."""

    for archive in (state / "backups").glob("*.tar.gz"):
        archive.unlink()


def declared_pairs(source: str) -> list[str]:
    """Read the Workshop manifest the rendered validator actually checks."""

    match = re.search(r"for pair in ([^;\n]+); do", source)
    assert match, "maintenance script does not validate a Workshop manifest"
    return match.group(1).split()


def install_mods(state: pathlib.Path, pairs: list[str], *, crlf: bool) -> None:
    """Stage mod.info metadata for every declared item, replacing any prior set."""

    content = state / "steam" / "steamapps" / "workshop" / "content" / WORKSHOP_APPID
    content = state / "steam" / "steamapps" / "workshop" / "content" / WORKSHOP_APPID
    shutil.rmtree(content, ignore_errors=True)
    ending = b"\r\n" if crlf else b"\n"
    for pair in pairs:
        item, mod = pair.split(":")
        info = content / item / "mods" / mod / "mod.info"
        info.parent.mkdir(parents=True)
        info.write_bytes(b"name=" + mod.encode() + ending + b"id=" + mod.encode() + ending)


def main(maintenance: pathlib.Path, launch: pathlib.Path) -> None:
    assert "-adminpassword" not in launch.read_text(), "admin password exposed in argv"
    if maintenance.is_dir():
        maintenance /= "bin/project-zomboid-maintenance"
    wrapper = maintenance.read_text()
    match = re.search(r"^exec (/[^\s]+project-zomboid-maintenance) ", wrapper, re.MULTILINE)
    assert match, "maintenance wrapper did not reference its generated script"
    maintenance = pathlib.Path(match.group(1))
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
        (mockbin / "steamcmd").write_text(
            f'#!/bin/sh\nprintf "steamcmd-cwd %s\\n" "$PWD" >> {events}\nexit 42\n'
        )
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
        assert f"steamcmd-cwd {state}" in recorded, "SteamCMD did not enter service-owned state"
        assert "start project-zomboid.service" not in recorded
        assert len(list((state / "backups").glob("*.tar.gz"))) == 2

        # SteamCMD completed, so the update may start, but Build 42 installs mod.info
        # with CRLF line endings. Validation must accept that or a fully updated
        # server is left stopped (2026-09-28 incident).
        (mockbin / "steamcmd").write_text(
            f'#!/bin/sh\nprintf "steamcmd-cwd %s\\n" "$PWD" >> {events}\nexit 0\n'
        )
        pairs = declared_pairs(source)
        install_mods(state, pairs, crlf=True)
        clear_archives(state)
        events.write_text("")
        result = run(harness, "update")
        assert result.returncode == 0, result.stderr
        assert "start project-zomboid.service" in events.read_text()

        # LF-only metadata is also valid and must not be treated as a failed update.
        install_mods(state, pairs, crlf=False)
        clear_archives(state)
        events.write_text("")
        result = run(harness, "update")
        assert result.returncode == 0, result.stderr

        # A declared item that is absent, or present under a different mod ID, must
        # fail with an actionable message and leave the service stopped.
        item, mod = sorted(pairs)[0].split(":")
        info = (
            state
            / "steam"
            / "steamapps"
            / "workshop"
            / "content"
            / WORKSHOP_APPID
            / item
            / "mods"
            / mod
            / "mod.info"
        )
        info.write_bytes(b"name=Renamed Mod\nid=RenamedMod\n")
        clear_archives(state)
        events.write_text("")
        result = run(harness, "update")
        assert result.returncode != 0
        assert item in result.stderr and mod in result.stderr
        assert "start project-zomboid.service" not in events.read_text()
        install_mods(state, pairs, crlf=True)
        print(
            "PASS: full-state backup, incomplete archive, invalid restore, failed update, "
            "non-root SteamCMD, no argv password, CRLF and LF Workshop validation, "
            "actionable mismatch rejection"
        )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: project-zomboid-maintenance.py MAINTENANCE_SCRIPT LAUNCH_SCRIPT")
    main(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
