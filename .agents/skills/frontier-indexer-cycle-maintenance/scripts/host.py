#!/usr/bin/env python3
"""Read-only SSH inventory/verification; emit compact JSON, never raw logs/secrets."""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import sys

from common import MaintenanceError, capture, emit, pinned_image, repository


def dashboard_metrics(root):
    text = (root / "terraform/dashboards/frontier-indexer.json").read_text()
    return sorted(name for name in set(re.findall(r"\bfrontier_indexer_[A-Za-z0-9_]+", text))
                  if not name.startswith("frontier_indexer_chain_head_"))


def remote(target, parameters, timeout):
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.:@\[\]-]*", target):
        raise MaintenanceError("Invalid SSH target")
    payload = "CONFIG = " + repr(parameters) + "\n" + Path(__file__).with_name("remote_host.py").read_text()
    result, _ = capture(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "ConnectionAttempts=1",
                         "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2", target, "sudo -n python3 -"],
                        input_text=payload, timeout=timeout)
    try:
        report = json.loads(result.stdout)
        if not isinstance(report, dict) or not isinstance(report.get("ok"), bool) or (result.returncode and report["ok"]):
            raise ValueError("Inconsistent remote report")
        return report
    except ValueError as error:
        raise MaintenanceError(f"SSH/access or remote-protocol failure (exit {result.returncode}); raw output suppressed") from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["inventory", "verify"])
    parser.add_argument("--ssh-target", default="scetrov@10.229.10.2")
    parser.add_argument("--repo")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--generation", type=int)
    parser.add_argument("--checkpoint", type=int)
    parser.add_argument("--image")
    parser.add_argument("--since", help="UTC/offset ISO-8601 timestamp at the beginning of cutover")
    args = parser.parse_args()
    try:
        parameters = {"mode": args.mode}
        if args.timeout <= 0:
            raise MaintenanceError("Timeout must be positive")
        if args.mode == "verify":
            if None in [args.generation, args.checkpoint, args.image, args.since]:
                raise MaintenanceError("verify requires --generation, --checkpoint, --image and --since")
            if not 0 <= args.generation <= 2**63 - 1 or args.checkpoint < 0:
                raise MaintenanceError("Expected nonnegative checkpoint and a supported generation")
            since = dt.datetime.fromisoformat(args.since.replace("Z", "+00:00"))
            if since.tzinfo is None:
                raise MaintenanceError("--since must include a timezone")
            parameters.update(generation=args.generation, checkpoint=args.checkpoint,
                              image=pinned_image(args.image),
                              since=since.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                              dashboard_metrics=dashboard_metrics(repository(args.repo)))
        report = remote(args.ssh_target, parameters, args.timeout)
        emit(report)
        return 0 if report.get("ok") else 1
    except (MaintenanceError, ValueError, OSError) as error:
        message = str(error) if isinstance(error, MaintenanceError) else "Invalid input or inaccessible local resource"
        emit({"ok": False, "error": message})
        return 1


if __name__ == "__main__":
    sys.exit(main())
