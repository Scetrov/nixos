#!/usr/bin/env python3
"""Remove only dedicated runner transient children, as the runner user."""
import argparse
import os
from pathlib import Path
import shutil
import stat


def clean(root):
    # Open without following symlinks, then operate relative to pinned directory
    # descriptors. Never traverse a job-created link into another service's data.
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(root, flags)
    try:
        if os.fstat(fd).st_uid != os.geteuid():
            raise ValueError("Transient directory is not owned by this user")
        for name in ("workspace", "cache"):
            child = os.open(name, flags, dir_fd=fd)
            try:
                if os.fstat(child).st_uid != os.geteuid():
                    raise ValueError("Transient child is not owned by this user")
                for entry in os.listdir(child):
                    mode = os.stat(entry, dir_fd=child, follow_symlinks=False).st_mode
                    if stat.S_ISDIR(mode):
                        shutil.rmtree(entry, dir_fd=child)
                    else:
                        os.unlink(entry, dir_fd=child)
            finally:
                os.close(child)
    finally:
        os.close(fd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transient-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        clean(args.transient_dir)
    except (OSError, ValueError):
        # Do not emit filenames or job-controlled error text into the journal.
        parser.exit(1, "Runner transient cleanup failed; refusing startup\n")
