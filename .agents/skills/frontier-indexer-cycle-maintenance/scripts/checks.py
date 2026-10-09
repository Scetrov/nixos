#!/usr/bin/env python3
"""Run bounded local checks; reduce all CLI/build/test output to compact JSON."""
import argparse
import json
from pathlib import Path
import re
import sys

from common import MaintenanceError, capture, emit, pinned_image, repository, source_fingerprint


CHAIN = ["frontier-indexer-wait-for-db", "frontier-indexer-db-preflight",
         "frontier-indexer-schema-reset", "podman-frontier-indexer"]


def validate_fixture(fixture, image, generation, checkpoint):
    settings = fixture["settings"]
    expected = {"indexerImage": image, "resetSchemaGeneration": generation,
                "firstCheckpoint": str(checkpoint), "suiNetwork": "testnet", "ingestConcurrencyMax": 2}
    mismatches = [key for key, value in expected.items() if settings.get(key) != value]
    if mismatches:
        raise MaintenanceError("Declared Habiki settings mismatch: " + ", ".join(mismatches))
    services = fixture["services"]
    graph = {name: set() for name in services}
    for name, unit in services.items():
        graph[name].update(value.removesuffix(".service") for value in unit["after"]
                           if value.removesuffix(".service") in services)
        for following in unit["before"]:
            following = following.removesuffix(".service")
            if following in graph:
                graph[following].add(name)
    remaining = dict(graph)
    ordered = []
    while remaining:
        ready = sorted(name for name, dependencies in remaining.items() if not dependencies.intersection(remaining))
        if not ready:
            raise MaintenanceError("Generated service dependency cycle")
        ordered.extend(ready)
        for name in ready:
            del remaining[name]
    for earlier, later in zip(CHAIN, CHAIN[1:]):
        if earlier + ".service" not in services[later]["requires"] or earlier not in graph[later]:
            raise MaintenanceError("Missing authenticated/fail-closed startup dependency")
    return {"startup_order": [name for name in ordered if name in CHAIN], "settings_match": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo")
    parser.add_argument("--image", required=True)
    parser.add_argument("--generation", type=int, required=True)
    parser.add_argument("--checkpoint", type=int, required=True)
    parser.add_argument("--integration", action="store_true")
    parser.add_argument("--old-image")
    parser.add_argument("--old-checkpoint", type=int)
    parser.add_argument("--database-image")
    args = parser.parse_args()
    results = []
    try:
        root = repository(args.repo)
        pinned_image(args.image)
        if not 1 <= args.generation <= 2**63 - 1 or args.checkpoint < 0:
            raise MaintenanceError("Cycle tests require generation >= 1 and nonnegative checkpoint")
        if args.integration:
            if None in [args.old_image, args.old_checkpoint, args.database_image] or args.old_checkpoint < 0:
                raise MaintenanceError("Integration requires pinned --old-image, --database-image and nonnegative --old-checkpoint")
            pinned_image(args.old_image)
            pinned_image(args.database_image)
        fingerprint = source_fingerprint(root)
        expression = "let t = import ./tests/frontier-indexer-eval.nix; in { inherit (t) services settings; }"
        evaluated, elapsed = capture(["nix-instantiate", "--eval", "--strict", "--json", "-E", expression], cwd=root)
        results.append({"name": "nixos_fixture", "exit": evaluated.returncode, "seconds": elapsed})
        if evaluated.returncode:
            raise MaintenanceError("NixOS fixture evaluation failed; raw output suppressed")
        fixture = validate_fixture(json.loads(evaluated.stdout), args.image, args.generation, args.checkpoint)
        commands = [
            ("reset_regressions", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_frontier_indexer_reset.py"], 90),
            ("skill_regressions", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_frontier_cycle_skill.py"], 90),
            ("generated_scripts", ["nix-build", "tests/frontier-indexer-eval.nix", "-A", "scripts", "--no-out-link"], 180),
            ("ansible_syntax", ["ansible-playbook", "-i", "src/inventory.yml", "src/playbook.yml", "--vault-password-file",
                                str(Path.home() / ".ansible/nixos_vault_password"), "--limit", "habiki", "--tags", "frontier-indexer", "--syntax-check"], 90),
        ]
        if args.integration:
            commands.append(("isolated_containers", [sys.executable, "tests/frontier_indexer_container_check.py",
                             "--old-image", args.old_image, "--old-checkpoint", str(args.old_checkpoint),
                             "--database-image", args.database_image], 900))
        commands.extend([
            ("pre_commit", ["pre-commit", "run"], 180),
            ("staged_whitespace", ["git", "diff", "--cached", "--check"], 30),
        ])
        for name, command, timeout in commands:
            result, elapsed = capture(command, cwd=root, timeout=timeout)
            entry = {"name": name, "exit": result.returncode, "seconds": elapsed}
            results.append(entry)
            if result.returncode:
                raise MaintenanceError(f"{name} failed; inspect the named check locally (raw output suppressed)")
            if name in {"reset_regressions", "skill_regressions"}:
                count = re.search(r"Ran ([0-9]+) tests?\b", result.stderr + result.stdout)
                if not count or int(count[1]) == 0:
                    raise MaintenanceError(f"{name} executed no tests; check suite discovery")
                entry["tests"] = int(count[1])
        if fingerprint != source_fingerprint(root):
            raise MaintenanceError("Deployment sources changed during checks (possibly hook formatting); review/restage and rerun")
        emit({"ok": True, "checks": results, "fixture": fixture,
              "expected": {"image": args.image, "generation": args.generation, "checkpoint": args.checkpoint},
              "source_fingerprint": fingerprint, "integration_ran": args.integration,
              "scope": "Frontier settings/dependencies, not a full host toplevel build"})
        return 0
    except (MaintenanceError, KeyError, ValueError, OSError) as error:
        message = str(error) if isinstance(error, MaintenanceError) else "Invalid input or changed fixture format"
        emit({"ok": False, "checks": results, "error": message})
        return 1


if __name__ == "__main__":
    sys.exit(main())
