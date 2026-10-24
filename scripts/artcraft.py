#!/usr/bin/env python3
"""Verify official ArtCraft release packages and atomically publish checked sites."""

import argparse
import fcntl
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
from urllib.parse import unquote, urlsplit
import zipfile


SLUG = re.compile(r"[a-z]+craft\Z")
KEY = re.compile(r"[a-f0-9]{64}\Z")
def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_member(name):
    path = PurePosixPath(name)
    if not path.parts or path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError(f"unsafe archive member: {name!r}")
    return path


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "src" in attrs:
            self.urls.append(attrs["src"])
        if tag == "link" and "href" in attrs:
            self.urls.append(attrs["href"])


def validate_site(site):
    site = Path(site)
    if site.is_symlink() or not site.is_dir():
        raise ValueError("site must be a real directory")
    files = {}
    wasm = 0
    for path in site.rglob("*"):
        if path.is_symlink():
            raise ValueError("site contains a symlink")
        if path.is_dir():
            continue
        if not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError("site contains a special or multiply-linked file")
        relative = path.relative_to(site).as_posix()
        if any(part.startswith(".") for part in path.relative_to(site).parts):
            raise ValueError("site contains a hidden file")
        files[relative] = sha256(path)
        if path.suffix == ".wasm":
            with path.open("rb") as stream:
                if stream.read(4) != b"\0asm":
                    raise ValueError("invalid WASM payload")
            wasm += 1
    if "index.html" not in files or not wasm:
        raise ValueError("site needs index.html and a WASM payload")
    parser = Assets()
    html = (site / "index.html").read_text()
    parser.feed(html)
    # Include inline module imports and explicit boot/font payload URLs.
    parser.urls.extend(re.findall(
        r"""(?:from\s*|import\s*\(|new URL\(|fetch\(|module_or_path:\s*)\s*["']([^"']+)["']""",
        html,
    ))
    for url in parser.urls:
        parsed = urlsplit(url)
        if parsed.scheme or parsed.netloc:
            continue  # Remote links are checked separately in browser acceptance.
        relative = unquote(parsed.path)
        if not relative:
            continue
        safe_member(relative)
        if not (site / relative).is_file():
            raise ValueError(f"missing entrypoint asset: {relative!r}")
    return files


def unpack_package(archive, destination):
    destination = Path(destination)
    with zipfile.ZipFile(archive) as package:
        entries = package.infolist()
        roots = set()
        total = 0
        seen = set()
        for entry in entries:
            path = safe_member(entry.filename)
            roots.add(path.parts[0])
            canonical = path.as_posix()
            if canonical in seen:
                raise ValueError("duplicate package member")
            seen.add(canonical)
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                raise ValueError("package contains a special file")
            total += entry.file_size
        if len(roots) != 1 or total > 2 * 1024**3 or len(entries) > 10000:
            raise ValueError("invalid package root or package size exceeds 2 GiB")
        seen = set()
        for entry in entries:
            parts = safe_member(entry.filename).parts[1:]
            if not parts:
                continue
            relative = PurePosixPath(*parts).as_posix()
            if relative in seen:
                raise ValueError("duplicate package member")
            seen.add(relative)
            # These are upstream hosting instructions, not browser runtime inputs.
            if relative in ("_headers", ".htaccess"):
                continue
            target = destination.joinpath(*parts)
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with package.open(entry) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
    return validate_site(destination)


def prepare(work, editor):
    """Verify a downloaded release before extracting or reusing a checked site."""
    slug = editor["slug"]
    if not SLUG.fullmatch(slug) or not KEY.fullmatch(editor["sha256"]):
        raise ValueError("invalid release identity")
    asset = editor["asset"]
    if safe_member(asset).parts != (asset,) or not asset.endswith(".zip"):
        raise ValueError("invalid release asset filename")
    work = Path(work).resolve()
    archive = work / "downloads" / asset
    if sha256(archive) != editor["sha256"]:
        raise ValueError("release SHA-256 mismatch")
    # Validation changes invalidate previous prepared candidates too.
    key = hashlib.sha256(
        (editor["sha256"] + sha256(__file__)).encode()
    ).hexdigest()
    completed = work / "packages" / slug / key
    if completed.exists():
        files = validate_site(completed / "site")
        if files != json.loads((completed / "manifest.json").read_text()):
            raise ValueError("cached package integrity mismatch")
        return {"changed": False, "key": key, "site": str(completed / "site")}
    completed.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="candidate-", dir=completed.parent) as temp:
        candidate = Path(temp)
        files = unpack_package(archive, candidate / "site")
        (candidate / "manifest.json").write_text(json.dumps(files, sort_keys=True) + "\n")
        candidate.rename(completed)
    return {"changed": True, "key": key, "site": str(completed / "site")}


def replace_link(path, target):
    temporary = path.with_name("." + path.name + "." + os.urandom(8).hex())
    try:
        temporary.symlink_to(target)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def publication_target(root, slug, link):
    if not link.is_symlink():
        raise ValueError("publication must be a managed symlink")
    target = link.resolve(strict=True)
    versions = root / "versions" / slug
    if target.parent != versions or not KEY.fullmatch(target.name):
        raise ValueError("publication target outside managed versions")
    validate_site(target)
    return target


def publish(root, slug, key=None, candidate=None, rollback=False):
    if not SLUG.fullmatch(slug) or (not rollback and not KEY.fullmatch(key or "")):
        raise ValueError("invalid publication identity")
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".publication.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        versions = root / "versions" / slug
        previous = root / "previous" / slug
        current = root / slug
        versions.mkdir(parents=True, exist_ok=True)
        previous.parent.mkdir(parents=True, exist_ok=True)
        old = publication_target(root, slug, current) if current.is_symlink() else None
        if current.exists() and old is None:
            raise ValueError("refusing to replace an unmanaged publication")
        if rollback:
            target = publication_target(root, slug, previous)
        else:
            expected = validate_site(candidate)
            target = versions / key
            if not target.exists():
                with tempfile.TemporaryDirectory(prefix=".candidate-", dir=versions) as temp:
                    staged = Path(temp) / "site"
                    shutil.copytree(candidate, staged, symlinks=True)
                    if validate_site(staged) != expected:
                        raise ValueError("candidate changed during publication")
                    for path in staged.rglob("*"):
                        path.chmod(0o755 if path.is_dir() else 0o644)
                    staged.chmod(0o755)
                    staged.rename(target)
            elif validate_site(target) != expected:
                raise ValueError("publication key reused for different content")
        if old == target:
            return False
        # The live link is replaced last: errors before this point preserve it.
        if old is not None:
            replace_link(previous, os.path.relpath(old, previous.parent))
        replace_link(current, os.path.relpath(target, root))
        keep = {target, old}
        # Prune only checked managed versions, never arbitrary directories.
        for path in versions.iterdir():
            if path not in keep and KEY.fullmatch(path.name) and path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
        return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "publish", "rollback"))
    parser.add_argument("--inventory")
    parser.add_argument("--work")
    parser.add_argument("--root")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--key")
    parser.add_argument("--candidate")
    args = parser.parse_args()
    if args.action == "prepare":
        inventory = json.loads(Path(args.inventory).read_text())
        editor = next(e for e in inventory["artcraft_editors"] if e["slug"] == args.slug)
        print(json.dumps(prepare(args.work, editor)))
    else:
        changed = publish(args.root, args.slug, args.key, args.candidate, args.action == "rollback")
        print(json.dumps({"changed": changed}))


if __name__ == "__main__":
    main()
