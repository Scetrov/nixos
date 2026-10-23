"""POSIX ACL transformation shared by provisioning and disposable contract tests.

Changing a mask must not activate previously masked unrelated permissions.
This module performs no filesystem traversal or privilege escalation.
"""


def permissions(value):
    return sum(bit for char, bit in zip(value, (4, 2, 1)) if char != "-")


def format_permissions(value):
    return "".join(char if value & bit else "-" for char, bit in zip("rwx", (4, 2, 1)))


def parse_acl(text):
    entries = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split(":")
        default = parts[0] == "default"
        if default:
            parts = parts[1:]
        if len(parts) != 3 or len(parts[2]) != 3:
            raise ValueError("Invalid numeric POSIX ACL")
        key = (default, parts[0], parts[1])
        if key in entries:
            raise ValueError("Duplicate ACL entry")
        entries[key] = permissions(parts[2])
    return entries


def render_acl(entries):
    # setfacl accepts arbitrary entry order; sorting makes convergence visible.
    return "\n".join(
        ("default:" if default else "") + tag + ":" + qualifier + ":" + format_permissions(value)
        for (default, tag, qualifier), value in sorted(entries.items())
    ) + "\n"


def managed_acl(original, *, service_uid, unix_uid, inode_uid, directory, executable=False):
    """Return exact ACL text granting the two managed principals rwX.

    Clamp unrelated mask-governed entries to their *old effective* permissions
    before widening the mask. Preserve other:: and unrelated owning-user access.
    Default ACLs allow either managed principal to own newly created content.
    Callers must snapshot the original ACL and inode before applying this result.
    """
    if service_uid == unix_uid or min(service_uid, unix_uid) <= 0:
        raise ValueError("Managed principals must be distinct non-root UIDs")
    entries = parse_acl(original)
    managed = {str(service_uid), str(unix_uid)}
    for default in ((False, True) if directory else (False,)):
        if default and not any(key[0] for key in entries):
            # New defaults inherit existing unrelated effective directory rights.
            mask = entries.get((False, "mask", ""), 7)
            for tag in ("user", "group", "other"):
                value = entries[(False, tag, "")]
                if tag == "group":
                    value &= mask
                entries[(True, tag, "")] = value
        mask = entries.get((default, "mask", ""), 7)
        for key, value in list(entries.items()):
            scope, tag, qualifier = key
            if scope != default:
                continue
            if tag == "group" or (tag == "user" and qualifier and qualifier not in managed):
                entries[key] = value & mask
        grant = 7 if directory or executable else 6
        for uid in managed:
            entries[(default, "user", uid)] = grant
        # The owner entry takes precedence over an equivalent named-user ACL.
        if default or str(inode_uid) in managed:
            entries[(default, "user", "")] = grant
        entries[(default, "mask", "")] = grant
    return render_acl(entries)
