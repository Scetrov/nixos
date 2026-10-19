"""Native scheduling acceptance probe; run on stdin inside the agent container.

No model calls or external delivery. Create one uniquely named bounded script
job, verify it across restarts/rebuilds, then remove only the owned fixture.
Example: sudo podman exec -i --user hermes hermes-agent python3 - health \
    < scripts/tests/check_hermes_scheduling.py
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time


PREFIX = "opsx-schedule-"


def fresh_status(home):
    status = json.loads((home / "gateway_state.json").read_text())
    assert isinstance(status.get("updated_at"), str), "Gateway metadata not ready"
    updated = datetime.fromisoformat(status["updated_at"])
    assert updated.tzinfo is not None, "Gateway timestamp has no timezone"
    age = (datetime.now(timezone.utc) - updated).total_seconds()
    assert status.get("gateway_state") == "running", "Gateway is not running"
    assert -120 <= age <= 120, f"Gateway metadata stale: age={age:.1f}s"
    return status["updated_at"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["health", "create", "verify", "cleanup"])
    parser.add_argument("--fixture", help="Unique test-owned suffix, retained across checks")
    parser.add_argument("--minimum-runs", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=150)
    args = parser.parse_args()
    home = Path(os.environ.get("HERMES_HOME", "/home/hermes/.hermes"))
    if args.action == "health":
        first = None
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            try:
                current = fresh_status(home)
            except (AssertionError, FileNotFoundError, ValueError):
                time.sleep(5)
                continue
            if first is None:
                first = current
            elif current != first:
                print("PASS: native gateway metadata is fresh and advancing")
                return
            time.sleep(5)
        raise AssertionError("Gateway metadata did not become fresh and advance")

    if not args.fixture or not re.fullmatch(r"[a-z0-9-]{8,48}", args.fixture):
        parser.error("--fixture must be a unique 8–48 character lowercase/digit/hyphen suffix")
    sys.path.insert(0, "/opt/hermes")
    from cron.jobs import create_job, list_jobs, remove_job

    name = PREFIX + args.fixture
    directory = home / "scripts"
    script = directory / (name + ".sh")
    marker = directory / (name + ".txt")
    jobs = [job for job in list_jobs(include_disabled=True) if job.get("name") == name]
    assert len(jobs) <= 1, "Ambiguous fixture ownership"
    if args.action == "create":
        assert not jobs and not script.exists() and not marker.exists(), "Fixture already exists"
        directory.mkdir(exist_ok=True)
        # Only append a timestamp to a test-owned local marker. No inference.
        script.write_text('#!/bin/sh\nset -eu\ndate -u +%s >> "$(dirname "$0")/' + marker.name + '"\nprintf "native scheduling acceptance OK\\n"\n')
        script.chmod(0o700)
        job = create_job(prompt="", schedule="every 1m", name=name, repeat=12,
                         script=str(script), no_agent=True, deliver="local")
        print(json.dumps({"fixture": name, "job_id": job["id"], "maximum_runs": 12}))
    elif args.action == "verify":
        assert jobs, "Native fixture job missing"
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            try:
                fresh_status(home)
            except (AssertionError, FileNotFoundError, ValueError):
                time.sleep(5)
                continue
            runs = len(marker.read_text().splitlines()) if marker.exists() else 0
            if runs >= args.minimum_runs:
                current = next(job for job in list_jobs(include_disabled=True) if job["id"] == jobs[0]["id"])
                if current.get("last_status") == "ok":
                    print(json.dumps({"job_id": current["id"], "marker_runs": runs, "status": "ok"}))
                    return
            time.sleep(5)
        raise AssertionError("Native scheduled job did not execute before deadline")
    else:
        if jobs:
            assert jobs[0].get("script") == str(script) and jobs[0].get("no_agent") is True, "Fixture ownership mismatch"
            remove_job(jobs[0]["id"])
        script.unlink(missing_ok=True)
        marker.unlink(missing_ok=True)
        print("PASS: removed only test-owned job, script and marker; native history retained")


if __name__ == "__main__":
    main()
