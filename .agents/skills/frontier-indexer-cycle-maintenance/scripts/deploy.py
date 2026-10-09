#!/usr/bin/env python3
"""Explicitly gated targeted deployment, with bounded credential-free progress JSON."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from common import MaintenanceError, emit, pinned_image, repository, source_fingerprint
from host import remote

PHASES = {
    "PLAY [Deploy NixOS Configuration]": "preflight",
    "TASK [nixos : Stop Frontier Indexer writer before NixOS switch]": "stop_writer",
    "TASK [nixos : Apply NixOS configuration]": "switch",
    "TASK [nixos : Ensure Frontier Indexer starts through the new dependency chain]": "start_indexer",
    "TASK [nixos : Restart each Podman systemd service]": "host_container_restarts",
    "PLAY RECAP": "recap",
}
REQUIRED_CHECKS = {"nixos_fixture", "reset_regressions", "skill_regressions", "generated_scripts",
                   "ansible_syntax", "isolated_containers", "pre_commit", "staged_whitespace"}


def validate_evidence(report, root):
    if report.get("ok") is not True or report.get("integration_ran") is not True:
        raise MaintenanceError("Successful checks with isolated integration are required")
    checks = {item["name"]: item["exit"] for item in report.get("checks", [])}
    if not REQUIRED_CHECKS <= checks.keys() or any(checks[name] != 0 for name in REQUIRED_CHECKS):
        raise MaintenanceError("Required checks are missing or failed")
    if report.get("source_fingerprint") != source_fingerprint(root):
        raise MaintenanceError("Check evidence is stale; deployment sources changed")
    expected = report.get("expected", {})
    if type(expected.get("generation")) is not int or type(expected.get("checkpoint")) is not int or not expected.get("image"):
        raise MaintenanceError("Check evidence lacks the declared cycle settings")
    pinned_image(expected["image"])
    if not 1 <= expected["generation"] <= 2**63 - 1 or expected["checkpoint"] < 0:
        raise MaintenanceError("Unsupported generation or checkpoint in evidence")
    return expected


def validate_release(report, expected, now=None):
    checks = report.get("checks", {})
    required = {"stable_release", "latest_release", "seven_day_policy", "platform", "source_revision",
                "source_repository", "version_label", "contracts", "checkpoint", "environment_keys",
                "all_pipelines", "pipeline_file_loaded", "schema_search_path"}
    if report.get("ok") is not True or not required <= checks.keys() or any(checks[key] is not True for key in required):
        raise MaintenanceError("Successful release/source/registry checks are required")
    if report.get("architecture") not in {"amd64", "arm64"}:
        raise MaintenanceError("Release evidence lacks a supported Linux architecture")
    if report.get("image") != expected["image"] or report.get("checkpoint") != expected["checkpoint"]:
        raise MaintenanceError("Release evidence does not match the planned deployment")
    observed = dt.datetime.fromisoformat(report["observed_at"])
    age = ((now or dt.datetime.now(dt.timezone.utc)) - observed).total_seconds()
    if not 0 <= age <= 86400:
        raise MaintenanceError("Release evidence expired; revalidate upstream within 24 hours of deployment")


def run_wrapper(root):
    # Never emit Ansible debug payloads, environment values, failure bodies, or raw logs.
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    emit({"phase": "begin", "cutover_since": started, "host": "habiki"})
    sys.stdout.flush()
    process = subprocess.Popen([str(root / "scripts/play.sh"), "--limit", "habiki", "--tags", "frontier-indexer"],
                               cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                               env=dict(os.environ, ANSIBLE_NOCOLOR="1", ANSIBLE_FORCE_COLOR="0"))
    phase = "begin"
    recap = None
    for line in process.stdout:
        for prefix, name in PHASES.items():
            if line.startswith(prefix) and name != phase:
                phase = name
                emit({"phase": phase})
                sys.stdout.flush()
        if phase == "recap" and line.startswith("habiki "):
            recap = {key: int(value) for key, value in re.findall(r"(ok|changed|unreachable|failed|skipped|rescued|ignored)=([0-9]+)", line)}
    status = process.wait()
    emit({"ok": status == 0 and recap is not None and recap.get("failed") == 0 and recap.get("unreachable") == 0,
          "exit": status, "last_phase": phase, "recap": recap, "cutover_since": started,
          "next": "Run host.py verify with the recorded cutover timestamp; do not roll back old reset code"})
    return status if status else (0 if recap is not None and recap.get("failed") == 0 and recap.get("unreachable") == 0 else 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo")
    parser.add_argument("--checks-report", required=True, help="JSON from checks.py; must include successful integration")
    parser.add_argument("--release-report", required=True, help="Successful release.py JSON no older than 24 hours")
    parser.add_argument("--execute", action="store_true", help="Without this flag only validate evidence and show the plan")
    parser.add_argument("--approve-cycle-reset", action="store_true")
    parser.add_argument("--approve-host-wide-restarts", action="store_true")
    args = parser.parse_args()
    try:
        root = repository(args.repo)
        evidence = json.loads(Path(args.checks_report).read_text())
        expected = validate_evidence(evidence, root)
        release_report = json.loads(Path(args.release_report).read_text())
        validate_release(release_report, expected)
        if not args.execute:
            emit({"ok": True, "execute": False, "expected": expected,
                  "command": "./scripts/play.sh --limit habiki --tags frontier-indexer",
                  "warning": "Advancing generation discards indexer data; the wrapper also restarts other active Habiki containers"})
            return 0
        if not args.approve_cycle_reset or not args.approve_host_wide_restarts:
            raise MaintenanceError("Execution requires explicit operator approval of cycle reset and host-wide restarts")
        report = remote("scetrov@10.229.10.2", {"mode": "inventory"}, 180)
        if not report.get("ok") or report.get("hostname") != "habiki" or report.get("review_required"):
            raise MaintenanceError("Live inventory/access needs review; automatic deletion or review bypass is not supported")
        architecture = {"x86_64": "amd64", "aarch64": "arm64"}.get(report.get("architecture"))
        if architecture != release_report["architecture"]:
            raise MaintenanceError("Release platform does not match the live host architecture")
        marker = report.get("marker", {})
        if not marker.get("valid") or marker.get("generation") is None:
            raise MaintenanceError("Missing/invalid cycle marker needs explicit manual review")
        if expected["generation"] < marker["generation"]:
            raise MaintenanceError("Stale configured generation refused")
        # Equal generation permits recovery with current safeguards, never another reset.
        validate_evidence(evidence, root)
        validate_release(release_report, expected)
        return run_wrapper(root)
    except (MaintenanceError, KeyError, ValueError, TypeError, OSError) as error:
        message = str(error) if isinstance(error, MaintenanceError) else "Invalid check evidence or unavailable resource"
        emit({"ok": False, "error": message})
        return 1


if __name__ == "__main__":
    sys.exit(main())
