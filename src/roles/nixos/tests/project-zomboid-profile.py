#!/usr/bin/env python3
"""Offline fixtures for Project Zomboid profile and reset reconciliation."""

import pathlib
import sqlite3
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
RECONCILE = ROOT / "files/etc/nixos/modules/project-zomboid-reconcile.py"
WHITELIST = ROOT / "files/etc/nixos/modules/project-zomboid-whitelist.py"
ITEMS = (
    "Base.Bag_DuffelBag",
    "Base.CannedChili",
    "Base.TinOpener",
    "Base.WaterBottle",
    "Base.HandAxe",
)


def invoke(*arguments: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *map(str, arguments)], text=True, capture_output=True)


def database(path: pathlib.Path, names: tuple[str, ...]) -> None:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE whitelist (id INTEGER, world TEXT, username TEXT, password TEXT, role INTEGER)")
    for index, name in enumerate(names):
        connection.execute("INSERT INTO whitelist VALUES (?, ?, ?, ?, ?)", (index, "pz-server", name, "hash", 0))
    connection.commit()
    connection.close()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="pz-profile-test-") as temporary:
        root = pathlib.Path(temporary)
        ini = root / "pz-server.ini"
        sandbox = root / "pz-server_SandboxVars.lua"
        ini.write_text("PVP=true\nOpen=false\nPublic=false\nRCONPort=0\nMods=unchanged\nSpawnItems=\nMapRemotePlayerVisibility=1\n")
        sandbox.write_text("""SandboxVars = {
    StarterKit = false,
    Map = { AllowMiniMap = false, },
    ZombieLore = { Transmission = 1, },
    MultiplierConfig = { Global = 1.0, GlobalToggle = true, },
    Unrelated = 42,
}
""")
        # Expanded fixture uses unambiguous multiline tables required by the safe parser.
        sandbox.write_text("""SandboxVars = {
    StarterKit = false,
    Map = {
        AllowMiniMap = false,
    },
    ZombieLore = {
        Transmission = 1,
    },
    MultiplierConfig = {
        Global = 1.0,
        GlobalToggle = true,
    },
    Unrelated = 42,
}
""")
        for _ in range(2):
            result = invoke(RECONCILE, "--ini", ini, "--sandbox", sandbox)
            assert result.returncode == 0, result.stderr
        assert oct(ini.stat().st_mode & 0o777) == "0o600"
        text = ini.read_text()
        assert "PVP=false\n" in text and "MapRemotePlayerVisibility=4\n" in text
        assert "SpawnItems=" + ",".join(ITEMS) in text and "Mods=unchanged\n" in text
        text = sandbox.read_text()
        for expected in ("AllowMiniMap = true,", "Transmission = 2,", "Global = 1.5,", "GlobalToggle = true,", "Unrelated = 42,"):
            assert expected in text
        malformed = root / "malformed.lua"
        malformed.write_text("SandboxVars = {\n    Map = {\n")
        result = invoke(RECONCILE, "--ini", ini, "--sandbox", malformed)
        assert result.returncode != 0

        old, new, preserve = root / "old.db", root / "new.db", root / "preserve.db"
        database(old, ("Scetrov", "FlyingFire", "Other"))
        database(new, ())
        assert invoke(WHITELIST, "snapshot", "--source", old, "--destination", preserve).returncode == 0
        assert oct(preserve.stat().st_mode & 0o777) == "0o600"
        assert invoke(WHITELIST, "restore", "--source", preserve, "--destination", new).returncode == 0
        connection = sqlite3.connect(new)
        assert connection.execute("SELECT username FROM whitelist ORDER BY username").fetchall() == [("FlyingFire",), ("Scetrov",)]
        connection.close()
        duplicate = root / "duplicate.db"
        database(duplicate, ("Scetrov", "Scetrov", "FlyingFire"))
        assert invoke(WHITELIST, "snapshot", "--source", duplicate, "--destination", root / "bad.db").returncode != 0
    print("PASS: profile reconciliation, idempotence, malformed input, permissions, and whitelist reset fixtures")


if __name__ == "__main__":
    main()
