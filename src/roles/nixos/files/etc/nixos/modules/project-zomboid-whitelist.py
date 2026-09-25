#!/usr/bin/env python3
"""Preserve only the approved Build 42 whitelist rows across a managed reset."""

from __future__ import annotations

import argparse
import os
import sqlite3
import stat
import tempfile
from pathlib import Path

USERNAMES = ("FlyingFire", "Scetrov")


def connect_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def columns(connection: sqlite3.Connection) -> list[str]:
    found = [row[1] for row in connection.execute("PRAGMA table_info(whitelist)")]
    if not found or "username" not in found:
        raise ValueError("Build 42 whitelist table is missing or malformed")
    return found


def rows(connection: sqlite3.Connection, names: tuple[str, ...]) -> list[tuple[object, ...]]:
    placeholders = ", ".join("?" for _ in names)
    result = connection.execute(
        f"SELECT * FROM whitelist WHERE username IN ({placeholders}) ORDER BY username", names
    ).fetchall()
    user_index = columns(connection).index("username")
    if len(result) != len(names) or [row[user_index] for row in result] != list(names):
        raise ValueError("each requested whitelist username must have exactly one record")
    return result


def snapshot(source: Path, destination: Path) -> None:
    if destination.exists():
        raise ValueError("refusing to overwrite whitelist preservation data")
    source_db = connect_readonly(source)
    try:
        source_columns = columns(source_db)
        source_rows = rows(source_db, USERNAMES)
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".whitelist-reset.", dir=destination.parent)
        os.close(fd)
        try:
            os.chmod(temporary, 0o600)
            destination_db = sqlite3.connect(temporary)
            placeholders = ", ".join("?" for _ in source_columns)
            destination_db.execute(
                "CREATE TABLE whitelist (" + ", ".join(f'"{column}"' for column in source_columns) + ")"
            )
            destination_db.executemany(
                "INSERT INTO whitelist VALUES (" + placeholders + ")", source_rows
            )
            destination_db.commit()
            destination_db.close()
            os.replace(temporary, destination)
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
    finally:
        source_db.close()


def ready(database: Path) -> None:
    connection = connect_readonly(database)
    try:
        columns(connection)
        count = connection.execute("SELECT count(*) FROM whitelist WHERE username = ?", ("admin",)).fetchone()[0]
        if count != 1:
            raise ValueError("fresh Build 42 administrator bootstrap is incomplete")
    finally:
        connection.close()


def restore(target: Path, source: Path) -> None:
    source_db = connect_readonly(source)
    target_db = sqlite3.connect(target)
    try:
        source_columns = columns(source_db)
        target_columns = columns(target_db)
        if source_columns != target_columns:
            raise ValueError("Build 42 whitelist schema changed; refusing to restore records")
        source_rows = rows(source_db, USERNAMES)
        username_index = source_columns.index("username")
        if [row[username_index] for row in source_rows] != list(USERNAMES):
            raise ValueError("whitelist preservation data does not contain exactly the requested records")
        placeholders = ", ".join("?" for _ in source_columns)
        with target_db:
            target_db.execute(
                "DELETE FROM whitelist WHERE username IN (?, ?)", USERNAMES
            )
            target_db.executemany(
                "INSERT INTO whitelist VALUES (" + placeholders + ")", source_rows
            )
        if len(rows(target_db, USERNAMES)) != len(USERNAMES):
            raise ValueError("restored whitelist records could not be verified")
    finally:
        target_db.close()
        source_db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    for command in (commands.add_parser("snapshot"), commands.add_parser("restore")):
        command.add_argument("--source", type=Path, required=True)
        command.add_argument("--destination", type=Path, required=True)
    ready_command = commands.add_parser("ready")
    ready_command.add_argument("--database", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "snapshot":
        snapshot(arguments.source, arguments.destination)
    elif arguments.command == "restore":
        restore(arguments.destination, arguments.source)
    else:
        ready(arguments.database)


if __name__ == "__main__":
    main()
