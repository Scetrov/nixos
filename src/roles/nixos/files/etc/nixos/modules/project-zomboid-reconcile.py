#!/usr/bin/env python3
"""Safely reconcile the allowlisted Project Zomboid server profile settings."""

from __future__ import annotations

import argparse
import os
import re
import stat
import tempfile
from pathlib import Path

DEFAULT_SPAWN_ITEMS = "Base.Bag_DuffelBag,Base.CannedChili,Base.TinOpener,Base.WaterBottle,Base.HandAxe"


def atomic_write(path: Path, text: str, mode: int | None = None) -> None:
    existing_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, existing_mode if mode is None else mode)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def reconcile_ini(path: Path, values: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for key, value in values.items():
        pattern = re.compile(rf"^{re.escape(key)}=")
        matches = [index for index, line in enumerate(lines) if pattern.match(line)]
        if len(matches) > 1:
            raise ValueError(f"ambiguous INI key: {key}")
        replacement = f"{key}={value}\n"
        if matches:
            lines[matches[0]] = replacement
        else:
            lines.append(replacement)
    atomic_write(path, "".join(lines), mode=0o600)


def brace_delta(line: str) -> int:
    """Count table braces after stripping Lua line comments and quoted strings."""
    code = re.sub(r"--.*$", "", line)
    code = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', "", code)
    return code.count("{") - code.count("}")


def table_bounds(lines: list[str], table_name: str) -> tuple[int, int]:
    root = [
        index
        for index, line in enumerate(lines)
        if re.match(r"^\s*SandboxVars\s*=\s*\{\s*$", line.rstrip())
    ]
    if len(root) != 1:
        raise ValueError("ambiguous or malformed SandboxVars root table")

    root_depth = 0
    candidates: list[tuple[int, int]] = []
    index = root[0]
    while index < len(lines):
        line = lines[index]
        if root_depth == 1 and re.match(rf"^\s*{re.escape(table_name)}\s*=\s*\{{\s*$", line.rstrip()):
            depth = brace_delta(line)
            end = index + 1
            while depth > 0 and end < len(lines):
                depth += brace_delta(lines[end])
                end += 1
            if depth != 0:
                raise ValueError(f"malformed SandboxVars.{table_name} table")
            candidates.append((index, end - 1))
        root_depth += brace_delta(line)
        if root_depth == 0:
            break
        if root_depth < 0:
            raise ValueError("malformed SandboxVars root table")
        index += 1
    if root_depth != 0 or len(candidates) != 1:
        raise ValueError(f"ambiguous or missing SandboxVars.{table_name} table")
    return candidates[0]


def set_nested_value(lines: list[str], table_name: str, key: str, value: str) -> None:
    start, end = table_bounds(lines, table_name)
    depth = 1
    matches: list[int] = []
    pattern = re.compile(rf"^(\s*){re.escape(key)}\s*=.*$")
    for index in range(start + 1, end):
        if depth == 1 and pattern.match(lines[index].rstrip("\n")):
            matches.append(index)
        depth += brace_delta(lines[index])
    if depth != 1 or len(matches) > 1:
        raise ValueError(f"ambiguous or malformed SandboxVars.{table_name}.{key}")
    if matches:
        indent = re.match(r"^(\s*)", lines[matches[0]]).group(1)
        lines[matches[0]] = f"{indent}{key} = {value},\n"
    else:
        indent = re.match(r"^(\s*)", lines[end]).group(1) + "    "
        lines.insert(end, f"{indent}{key} = {value},\n")


def reconcile_sandbox(path: Path, values: dict[str, dict[str, str]]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for table_name, values in values.items():
        for key, value in values.items():
            set_nested_value(lines, table_name, key, value)
    atomic_write(path, "".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ini", type=Path, required=True)
    parser.add_argument("--sandbox", type=Path, required=True)
    parser.add_argument("--pvp", choices=("true", "false"), default="false")
    parser.add_argument("--map-remote-player-visibility", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--spawn-items", default=DEFAULT_SPAWN_ITEMS)
    parser.add_argument("--allow-mini-map", choices=("true", "false"), default="true")
    parser.add_argument("--zombie-transmission", type=int, choices=range(1, 5), default=2)
    parser.add_argument("--global-xp-multiplier", type=float, default=1.5)
    arguments = parser.parse_args()

    if not arguments.ini.is_file():
        raise ValueError(f"missing INI profile: {arguments.ini}")
    reconcile_ini(
        arguments.ini,
        {
            "PVP": arguments.pvp,
            "MapRemotePlayerVisibility": str(arguments.map_remote_player_visibility),
            "SpawnItems": arguments.spawn_items,
        },
    )
    if arguments.sandbox.exists():
        if not arguments.sandbox.is_file():
            raise ValueError(f"sandbox profile is not a regular file: {arguments.sandbox}")
        reconcile_sandbox(
            arguments.sandbox,
            {
                "Map": {"AllowMiniMap": arguments.allow_mini_map},
                "ZombieLore": {"Transmission": str(arguments.zombie_transmission)},
                "MultiplierConfig": {
                    "Global": str(arguments.global_xp_multiplier),
                    "GlobalToggle": "true",
                },
            },
        )


if __name__ == "__main__":
    main()
