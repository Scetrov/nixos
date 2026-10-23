#!/usr/bin/env python3
"""Root-only, data-preserving Documents enrollment/ACL automation.

State contains private path/ACL metadata, never credentials or file contents.
All mutation paths are rooted at validated configured homes. Symlinks are never
followed during traversal; ACL operations use pinned file descriptors.
"""

import argparse
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys
import uuid

if __package__:
    from .filebrowser_acl import managed_acl, parse_acl, render_acl
else:
    from filebrowser_acl import managed_acl, parse_acl, render_acl


class EnrollmentError(ValueError):
    pass


def validate_enrollments(records):
    if not isinstance(records, list):
        raise EnrollmentError("Enrollment must be a list")
    names, identities = set(), set()
    for record in records:
        if not isinstance(record, dict) or not {"identity_uuid", "unix_username"} <= set(record) or set(record) - {"identity_uuid", "authentik_pk", "unix_username"}:
            raise EnrollmentError("Enrollment requires immutable UUID and Unix username, with an optional directory PK locator")
        if "authentik_pk" in record and (type(record["authentik_pk"]) is not int or record["authentik_pk"] <= 0):
            raise EnrollmentError("Invalid Authentik directory PK locator")
        name, identity = record["unix_username"], record["identity_uuid"]
        if not isinstance(name, str) or not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", name):
            raise EnrollmentError("Invalid exact lowercase Unix username")
        try:
            canonical = str(uuid.UUID(identity))
        except (ValueError, TypeError, AttributeError) as error:
            raise EnrollmentError("Invalid immutable identity UUID") from error
        if canonical != identity or identity in identities or name in names:
            raise EnrollmentError("Noncanonical or duplicate enrollment")
        names.add(name)
        identities.add(identity)
    return records


def validate_home(home, uid, *, allow_missing=False):
    path = Path(home)
    if not path.is_absolute() or len(path.parts) < 3 or any(p in (".", "..") for p in home.split("/")):
        raise EnrollmentError("Unsafe configured home")
    if str(path) != home or path == Path("/home"):
        raise EnrollmentError("Noncanonical configured home")
    for ancestor in (*reversed(path.parents), path, path / "Documents"):
        try:
            info = ancestor.lstat()
        except FileNotFoundError:
            if ancestor in (path, path / "Documents") and allow_missing:
                continue
            if ancestor == path / "Documents":
                continue
            raise EnrollmentError("Missing home ancestor") from None
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise EnrollmentError("Home/Documents must be real directories without symlink ancestors")
    if path.exists() and path.stat().st_uid != uid:
        raise EnrollmentError("Configured home is not owned by its Unix account")
    docs = path / "Documents"
    if docs.exists() and docs.stat().st_uid != uid:
        raise EnrollmentError("Documents root is not owned by its Unix account")
    return docs


def resolve_accounts(records, *, create_missing=False):
    planned = []
    for record in validate_enrollments(records):
        name = record["unix_username"]
        try:
            account = pwd.getpwnam(name)
        except KeyError:
            if not create_missing:
                raise EnrollmentError("Enrolled Unix account does not exist") from None
            home = "/home/" + name
            # Refuse pre-existing homes for an absent account, rather than
            # adopting personal data or recursively changing ownership.
            if os.path.lexists(home):
                raise EnrollmentError("Missing account has a pre-existing home")
            planned.append((record, None))
            continue
        if account.pw_uid == 0:
            raise EnrollmentError("Root cannot be enrolled")
        docs = validate_home(account.pw_dir, account.pw_uid)
        planned.append((record, (account, docs)))
    paths = [str(value[1]) for _, value in planned if value]
    if len(paths) != len(set(paths)) or any(a != b and a.startswith(b + "/") for a in paths for b in paths):
        raise EnrollmentError("Overlapping Documents roots")
    result = []
    for record, resolved in planned:
        if resolved is None:
            # Existing accounts are never passed to useradd/usermod. No
            # passwords, SSH keys, extra groups, or interactive shell are set.
            subprocess.run(["useradd", "--create-home", "--shell", "/run/current-system/sw/bin/nologin", "--password", "!", "--", record["unix_username"]], check=True, capture_output=True)
            account = pwd.getpwnam(record["unix_username"])
            docs = validate_home(account.pw_dir, account.pw_uid)
        else:
            account, docs = resolved
        if not docs.exists():
            home_fd = open_directory(account.pw_dir)
            try:
                os.mkdir("Documents", mode=0o700, dir_fd=home_fd)
                docs_fd = os.open("Documents", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=home_fd)
                try:
                    os.fchown(docs_fd, account.pw_uid, account.pw_gid)
                finally:
                    os.close(docs_fd)
            finally:
                os.close(home_fd)
        result.append({**record, "uid": account.pw_uid, "gid": account.pw_gid, "documents": str(docs)})
    return result


def open_directory(path):
    """Pin every ancestor, rejecting symlink swaps as well as symlink leaves."""
    if not Path(path).is_absolute():
        raise EnrollmentError("Directory must be absolute")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in Path(path).parts[1:]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def walk_descriptors(root):
    """Yield pinned regular files/directories. Never cross devices or symlinks."""
    root_fd = open_directory(root)
    device = os.fstat(root_fd).st_dev

    def visit(fd, relative):
        info = os.fstat(fd)
        if info.st_dev != device:
            raise EnrollmentError("Nested filesystems require separate review")
        if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise EnrollmentError("Hard-linked files require separate review")
        yield fd, relative, info
        if not stat.S_ISDIR(info.st_mode):
            return
        for name in sorted(os.listdir(fd)):
            try:
                child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            except OSError:
                # Only symlinks are intentionally skipped. Disappearing or
                # inaccessible entries fail closed, rather than partial grants.
                entry = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISLNK(entry.st_mode):
                    continue
                raise
            try:
                mode = os.fstat(child).st_mode
                if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                    raise EnrollmentError("Special files cannot be enrolled")
                yield from visit(child, str(Path(relative) / name))
            finally:
                os.close(child)

    try:
        yield from visit(root_fd, ".")
    finally:
        os.close(root_fd)


def acl_command(fd, *args, data=None):
    return subprocess.run([*args, "--", f"/proc/self/fd/{fd}"], input=data, capture_output=True, pass_fds=(fd,), check=True).stdout


def save_state(path, state):
    temporary = path.with_suffix(".new")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(state, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def apply_acl(record, service_uid, state, state_file):
    # Preflight the complete tree before changing its first ACL.
    for _ in walk_descriptors(record["documents"]):
        pass
    for fd, relative, info in walk_descriptors(record["documents"]):
        key = record["identity_uuid"] + ":" + relative
        original = acl_command(fd, "getfacl", "-cpn").decode()
        snapshot = state["acls"].get(key)
        inode = [info.st_dev, info.st_ino]
        if snapshot is None and record["identity_uuid"] not in state.get("initialized", []):
            state["acls"][key] = {"inode": inode, "acl": original, "uid": info.st_uid}
            save_state(state_file, state)
        desired = managed_acl(original, service_uid=service_uid, unix_uid=record["uid"], inode_uid=info.st_uid, directory=stat.S_ISDIR(info.st_mode), executable=bool(info.st_mode & 0o111))
        if parse_acl(original) != parse_acl(desired):
            acl_command(fd, "setfacl", "--no-mask", "--set-file=-", data=desired.encode())


def withdraw_acl(record, service_uid, state):
    # Caller must first revoke Authentik access and delete/verify the Quantum
    # account. This function is not exposed as an independent CLI operation.
    for fd, relative, info in walk_descriptors(record["documents"]):
        snapshot = state["acls"].get(record["identity_uuid"] + ":" + relative)
        current = acl_command(fd, "getfacl", "-cpn").decode()
        if snapshot and snapshot["inode"] == [info.st_dev, info.st_ino] and snapshot["uid"] == info.st_uid:
            desired = snapshot["acl"]
        else:
            # A new/replaced inode has no pre-service state. Preserve its Unix
            # owner's access to service-owned content while removing only the
            # service's named ACL entries, never chown or delete the data.
            entries = parse_acl(current)
            for default in (False, True):
                entries.pop((default, "user", str(service_uid)), None)
            desired = render_acl(entries)
        if stat.S_ISDIR(info.st_mode):
            acl_command(fd, "setfacl", "--remove-default")
        acl_command(fd, "setfacl", "--no-mask", "--set-file=-", data=desired.encode())


def prepare(enrollments, state_directory, service_user, create_missing=False):
    directory = Path(state_directory)
    if directory.is_symlink():
        raise EnrollmentError("State directory cannot be a symlink")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = open_directory(directory)
    try:
        if os.fstat(fd).st_uid != os.geteuid():
            raise EnrollmentError("State directory has an unexpected owner")
        os.fchmod(fd, 0o700)
        fcntl.flock(fd, fcntl.LOCK_EX)
        return _prepare(enrollments, state_directory, service_user, create_missing)
    finally:
        os.close(fd)


def _prepare(enrollments, state_directory, service_user, create_missing=False):
    records = validate_enrollments(enrollments)
    service_uid = pwd.getpwnam(service_user).pw_uid
    if service_uid == 0:
        raise EnrollmentError("Service must not run as root")
    directory = Path(state_directory)
    if directory.is_symlink():
        raise EnrollmentError("State directory cannot be a symlink")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    state_file = directory / "enrollment.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {"service_uid": service_uid, "enrollments": [], "acls": {}}
    if state["service_uid"] != service_uid:
        raise EnrollmentError("Service UID changed; review required")
    old = {r["identity_uuid"]: r for r in state["enrollments"]}
    new = {r["identity_uuid"]: r for r in records}
    if set(old) - set(new):
        raise EnrollmentError("Offboard removed identities before withdrawing host access")
    for identity in set(old) & set(new):
        if old[identity]["unix_username"] != new[identity]["unix_username"]:
            raise EnrollmentError("Identity reassignment requires explicit offboarding")
    resolved = resolve_accounts(records, create_missing=create_missing)
    for record in resolved:
        if record["uid"] == service_uid:
            raise EnrollmentError("Service identity cannot be an ordinary enrollment")
        previous = old.get(record["identity_uuid"])
        if previous and (previous["uid"] != record["uid"] or previous["documents"] != record["documents"]):
            raise EnrollmentError("Unix UID or home changed; review required")
    if len({record["uid"] for record in resolved}) != len(resolved):
        raise EnrollmentError("Unix UID aliases cannot be separately enrolled")
    # Validate every tree before granting the first one, not one tree at a time.
    for record in resolved:
        for _ in walk_descriptors(record["documents"]):
            pass
    state["enrollments"] = resolved
    save_state(state_file, state)
    for record in resolved:
        apply_acl(record, service_uid, state, state_file)
        initialized = state.setdefault("initialized", [])
        if record["identity_uuid"] not in initialized:
            initialized.append(record["identity_uuid"])
            save_state(state_file, state)
    print("Documents enrollment/ACL preparation converged")
    return state


def rollback(state_directory):
    Path("/run/filebrowser/ready").unlink(missing_ok=True)
    active = subprocess.run(["systemctl", "is-active", "--quiet", "podman-filebrowser.service"], capture_output=True, check=False)
    running = subprocess.run(["podman", "inspect", "--format", "{{.State.Running}}", "filebrowser"], capture_output=True, check=False)
    if active.returncode == 0 or (running.returncode == 0 and running.stdout.strip() == b"true"):
        raise EnrollmentError("Stop Quantum before withdrawing ACLs")
    directory = Path(state_directory)
    fd = open_directory(directory)
    try:
        if os.fstat(fd).st_uid != os.geteuid():
            raise EnrollmentError("Unexpected state owner")
        fcntl.flock(fd, fcntl.LOCK_EX)
        state = json.loads((directory / "enrollment.json").read_text())
        for record in state["enrollments"]:
            account = pwd.getpwnam(record["unix_username"])
            if account.pw_uid != record["uid"] or str(validate_home(account.pw_dir, account.pw_uid)) != record["documents"]:
                raise EnrollmentError("Rollback account/home mismatch")
            for _ in walk_descriptors(record["documents"]):
                pass
        for record in state["enrollments"]:
            withdraw_acl(record, state["service_uid"], state)
        print("Managed service ACLs withdrawn; Unix data and owner access preserved")
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enrollments")
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument("--state-directory", required=True)
    parser.add_argument("--service-user", default="filebrowser")
    parser.add_argument("--create-missing", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("Host enrollment requires root")
    try:
        if args.rollback:
            rollback(args.state_directory)
        else:
            if not args.enrollments:
                raise EnrollmentError("Enrollment file is required")
            prepare(json.loads(Path(args.enrollments).read_text()), args.state_directory, args.service_user, args.create_missing)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        # Do not leak personal paths or raw command output into journald.
        print("Documents enrollment failed; inspect protected enrollment state", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
