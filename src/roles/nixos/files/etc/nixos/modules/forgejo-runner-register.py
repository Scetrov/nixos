"""Protected, owner-scoped Forgejo runner registration (run by deployment).

No runner credential is passed in argv. Server registration consumes stdin;
runner config references its protected token file. Explicit recovery is required
when persisted credentials are rejected. Rotation preserves the UUID prefix,
so supported upstream registration updates the same record, not a duplicate.
"""
import argparse
import json
import os
from pathlib import Path
import grp
import re
import secrets
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid


class RegistrationError(Exception):
    pass


def atomic_write(path, content, owner=None):
    descriptor, temporary = tempfile.mkstemp(prefix=".registration-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            if owner is not None:
                os.fchown(stream.fileno(), *owner)
                os.fchmod(stream.fileno(), 0o640)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def authenticate(instance, runner_uuid, token, labels):
    request = urllib.request.Request(
        instance.rstrip("/") + "/api/actions/runner.v1.RunnerService/Declare",
        json.dumps({"version": "13.2.0", "labels": labels}).encode(),
        headers={"Content-Type": "application/json", "Connect-Protocol-Version": "1",
                 "x-runner-uuid": runner_uuid, "x-runner-token": token})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            json.load(response)
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise RegistrationError("Runner credentials rejected; explicit recovery required") from None
        raise RegistrationError("Runner validation failed; no registration changes made") from None
    except (OSError, ValueError):
        raise RegistrationError("Runner validation unavailable; no registration changes made") from None


def register(binary, server_config, work_path, directory, template, instance,
             scope, rotate=False, recover=False, run_as=None, file_owner=None):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", scope):
        raise RegistrationError("An explicit owner-user scope is required; global/repository scopes are not allowed")
    directory = Path(directory)
    if not directory.is_dir():
        raise RegistrationError("Protected control directory is missing")
    token_file = directory / "token"
    connection_file = directory / "config.yaml"
    runner_uuid_file = directory / "uuid"
    config = json.loads(Path(template).read_text())
    labels = config["runner"]["labels"]
    if not isinstance(labels, list) or any(not isinstance(label, str) for label in labels):
        raise RegistrationError("Invalid runner labels")
    token = token_file.read_text() if token_file.exists() else secrets.token_hex(20)
    # Persist a new identity before touching the server: a crash/network failure
    # must not generate a different UUID and duplicate first-deploy registration.
    if not token_file.exists():
        atomic_write(token_file, token, file_owner)
    if not re.fullmatch(r"[a-f0-9]{40}", token):
        raise RegistrationError("Invalid persisted runner credential")
    expected_uuid = str(uuid.UUID(bytes=token[:16].encode()))
    if runner_uuid_file.exists():
        if runner_uuid_file.read_text() != expected_uuid:
            raise RegistrationError("Persisted runner identity mismatch")
        # Do not re-grant deliberately revoked access on an ordinary deployment.
        if not recover:
            authenticate(instance, expected_uuid, token, labels)
    elif connection_file.exists():
        raise RegistrationError("Incomplete persisted runner identity; refusing registration")
    if rotate or recover:
        token = token[:16] + secrets.token_hex(12)
    command = [binary, "--config", server_config, "--work-path", work_path,
               "forgejo-cli", "actions", "register", "--scope", scope,
               "--secret-stdin", "true", "--name", "habiki-owner"]
    command += ["--labels", ",".join(labels)] if labels else ["--keep-labels"]
    kwargs = {} if run_as is None else {"user": run_as, "group": run_as, "extra_groups": []}
    try:
        result = subprocess.run(command, input=token, capture_output=True, text=True, timeout=90, **kwargs)
    except (OSError, subprocess.SubprocessError):
        raise RegistrationError("Scoped registration did not complete; diagnostics suppressed") from None
    if result.returncode:
        raise RegistrationError("Scoped registration failed; diagnostics suppressed")
    if result.stdout.strip() != expected_uuid:
        raise RegistrationError("Unexpected registration identity; diagnostics suppressed")
    authenticate(instance, expected_uuid, token, labels)
    config["server"] = {"connections": {"habiki": {
        "url": instance, "uuid": expected_uuid, "token_url": "file:" + str(token_file),
    }}}
    atomic_write(token_file, token, file_owner)
    atomic_write(runner_uuid_file, expected_uuid, file_owner)
    atomic_write(connection_file, json.dumps(config, indent=2) + "\n", file_owner)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("binary", "server-config", "work-path", "template", "instance"):
        parser.add_argument("--" + flag, required=True)
    parser.add_argument("--directory", default="/var/lib/forgejo-runner-control")
    parser.add_argument("--scope", default="scetrov")
    parser.add_argument("--rotate", action="store_true")
    parser.add_argument("--recover", action="store_true")
    args = parser.parse_args()
    try:
        if os.geteuid() != 0:
            raise RegistrationError("Deployment registration requires root")
        directory = Path(args.directory)
        metadata = directory.lstat()
        if directory.is_symlink() or not directory.is_dir() or metadata.st_uid != 0 or metadata.st_mode & 0o022:
            raise RegistrationError("Control directory must be root-owned and protected")
        register(args.binary, args.server_config, args.work_path, args.directory,
                 args.template, args.instance, args.scope, args.rotate, args.recover,
                 run_as="forgejo", file_owner=(0, grp.getgrnam("forgejo-runner").gr_gid))
    except (RegistrationError, OSError, ValueError, KeyError):
        print("Forgejo runner registration failed; check owner enrollment, connectivity, or explicit recovery", file=sys.stderr)
        return 1
    print("Forgejo owner-scoped runner reconciled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
