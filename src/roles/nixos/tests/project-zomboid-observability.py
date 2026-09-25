#!/usr/bin/env python3
"""Check rendered Build 42 telemetry configuration and Alloy identity."""

import pathlib
import re
import sys


def main(initialise: pathlib.Path, alloy: pathlib.Path) -> None:
    script = initialise.read_text()
    config = alloy.read_text()
    assert '"-DprometheusPort=' in script
    assert 'map(select(startswith("-DprometheusPort=") | not))' in script
    assert 'set_sandbox_value CharacterFreePoints 100' in script
    assert 'set_sandbox_value MultiHitZombies true' in script
    assert 'RCONPort=0' in script
    assert 'RCONPassword=' in script
    assert not re.search(r'RCONPassword=\S+', script)
    assert 'regex         = "project-zomboid\\\\.service"' in config
    assert 'replacement   = "project-zomboid"' in config
    assert 'target_label  = "service"' in config
    assert '__address__ = "127.0.0.1:9105"' in config
    assert 'service     = "project-zomboid"' in config
    assert 'host    = "${config.networking.hostName}"' in config
    print("PASS: native JVM argument, no RCON, private scrape, metric/log service and host identities")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: project-zomboid-observability.py INIT_SCRIPT ALLOY_MODULE")
    main(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
