#!/usr/bin/env python3
"""Compare an unsigned declared install tree; never execute or install its code."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import time
from pathlib import Path, PurePosixPath

MAX_ENTRIES = 16384
MAX_FILE = 256 * 1024 * 1024
MAX_TOTAL = 1024 * 1024 * 1024
MAX_MANIFEST = 4 * 1024 * 1024


class TreeError(ValueError):
    pass


def _state(info):
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_uid,
        info.st_gid,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _path(value):
    if (
        not isinstance(value, str)
        or len(value.encode()) > 1024
        or not re.fullmatch(r"[A-Za-z0-9._+\-]+(?:/[A-Za-z0-9._+\-]+)*", value)
        or any(part in {".", ".."} for part in value.split("/"))
        or len(value.split("/")) > 32
    ):
        raise TreeError("PATH_INVALID")
    return value


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TreeError("MANIFEST_INVALID")
        result[key] = value
    return result


def _reject_constant(_):
    raise TreeError("MANIFEST_INVALID")


def validate_manifest(value):
    try:
        if (
            not isinstance(value, dict)
            or set(value) != {"schema", "scope", "entries"}
            or type(value["schema"]) is not int
            or value["schema"] != 1
            or value["scope"] != "EXPECTED_INSTALLED_TREE"
            or not isinstance(value["entries"], list)
            or not 1 <= len(value["entries"]) <= MAX_ENTRIES
        ):
            raise TreeError("MANIFEST_INVALID")
        entries, names, total = {}, set(), 0
        for item in value["entries"]:
            if not isinstance(item, dict):
                raise TreeError("MANIFEST_INVALID")
            path = _path(item.get("path"))
            kind = item.get("kind")
            fields = {"path", "kind", "mode"}
            if kind == "file":
                fields |= {"size", "sha256"}
                if (
                    type(item.get("size")) is not int
                    or not 0 <= item["size"] <= MAX_FILE
                    or not isinstance(item.get("sha256"), str)
                    or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
                ):
                    raise TreeError("MANIFEST_INVALID")
                total += item["size"]
            elif kind != "directory":
                raise TreeError("MANIFEST_INVALID")
            if (
                set(item) != fields
                or type(item.get("mode")) is not int
                or not 0 <= item["mode"] <= 0o777
                or path.casefold() in names
                or total > MAX_TOTAL
            ):
                raise TreeError("MANIFEST_INVALID")
            names.add(path.casefold())
            entries[path] = {key: val for key, val in item.items() if key != "path"}
        for path in entries:
            for parent in PurePosixPath(path).parents:
                if str(parent) != "." and entries.get(str(parent), {}).get("kind") != "directory":
                    raise TreeError("MANIFEST_INVALID")
        return entries
    except (TypeError, KeyError, UnicodeError, RecursionError):
        raise TreeError("MANIFEST_INVALID") from None


def _canonical(path, *, directory):
    path = Path(path).absolute()
    if path.resolve() != path or (directory and not path.is_dir()):
        raise TreeError("ROOT_OR_ALIAS_INVALID")
    return path


def load_manifest(path):
    path = _canonical(path, directory=False)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or not 0 < before.st_size <= MAX_MANIFEST
        ):
            raise TreeError("MANIFEST_INVALID")
        raw = bytearray()
        while len(raw) <= MAX_MANIFEST:
            chunk = os.read(fd, min(65536, MAX_MANIFEST + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        if (
            len(raw) != before.st_size
            or _state(before) != _state(os.fstat(fd))
            or _state(before) != _state(path.lstat())
        ):
            raise TreeError("MANIFEST_CHANGED")
        try:
            parsed = json.loads(raw, object_pairs_hook=_unique, parse_constant=_reject_constant)
            return validate_manifest(parsed)
        except (ValueError, UnicodeError, RecursionError):
            raise TreeError("MANIFEST_INVALID") from None
    finally:
        os.close(fd)


def _check_time(deadline):
    if time.monotonic() >= deadline:
        raise TreeError("READ_BUDGET_EXCEEDED")


def _snapshot(root, deadline):
    entries, states, folded = {}, {}, set()
    total = 0
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    device = os.fstat(root_fd).st_dev

    def walk(directory, prefix):
        nonlocal total
        before = os.fstat(directory)
        states[prefix] = _state(before)
        with os.scandir(directory) as scan:
            for entry in scan:
                _check_time(deadline)
                path = _path(prefix + "/" + entry.name if prefix else entry.name)
                if len(entries) >= MAX_ENTRIES or path.casefold() in folded:
                    raise TreeError("TREE_BOUNDS_OR_ALIAS_INVALID")
                folded.add(path.casefold())
                info = os.stat(entry.name, dir_fd=directory, follow_symlinks=False)
                mode = stat.S_IMODE(info.st_mode)
                if info.st_dev != device or mode & 0o7000:
                    raise TreeError("TREE_KIND_OR_DEVICE_INVALID")
                if stat.S_ISDIR(info.st_mode):
                    entries[path] = dict(kind="directory", mode=mode)
                    child = os.open(
                        entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
                    )
                    try:
                        if _state(info) != _state(os.fstat(child)):
                            raise TreeError("TREE_CHANGED")
                        walk(child, path)
                    finally:
                        os.close(child)
                elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                    total += info.st_size
                    if info.st_size > MAX_FILE or total > MAX_TOTAL:
                        raise TreeError("TREE_BYTES_EXCEEDED")
                    file_fd = os.open(
                        entry.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
                    )
                    try:
                        if _state(info) != _state(os.fstat(file_fd)):
                            raise TreeError("TREE_CHANGED")
                        digest, size = hashlib.sha256(), 0
                        while True:
                            _check_time(deadline)
                            chunk = os.read(file_fd, 65536)
                            if not chunk:
                                break
                            size += len(chunk)
                            if size > info.st_size:
                                raise TreeError("TREE_CHANGED")
                            digest.update(chunk)
                        if size != info.st_size or _state(info) != _state(os.fstat(file_fd)):
                            raise TreeError("TREE_CHANGED")
                    finally:
                        os.close(file_fd)
                    entries[path] = dict(
                        kind="file", mode=mode, size=size, sha256=digest.hexdigest()
                    )
                    states[path] = _state(info)
                else:
                    raise TreeError("TREE_KIND_OR_DEVICE_INVALID")
                if _state(info) != _state(
                    os.stat(entry.name, dir_fd=directory, follow_symlinks=False)
                ):
                    raise TreeError("TREE_CHANGED")
        if _state(before) != _state(os.fstat(directory)):
            raise TreeError("TREE_CHANGED")

    def verify_states(directory, prefix, seen):
        _check_time(deadline)
        if _state(os.fstat(directory)) != states.get(prefix):
            raise TreeError("TREE_CHANGED")
        seen.add(prefix)
        with os.scandir(directory) as scan:
            for entry in scan:
                _check_time(deadline)
                path = _path(prefix + "/" + entry.name if prefix else entry.name)
                info = os.stat(entry.name, dir_fd=directory, follow_symlinks=False)
                if _state(info) != states.get(path):
                    raise TreeError("TREE_CHANGED")
                seen.add(path)
                if stat.S_ISDIR(info.st_mode):
                    child = os.open(
                        entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
                    )
                    try:
                        verify_states(child, path, seen)
                    finally:
                        os.close(child)
        if _state(os.fstat(directory)) != states.get(prefix):
            raise TreeError("TREE_CHANGED")

    try:
        walk(root_fd, "")
        seen = set()
        verify_states(root_fd, "", seen)
        if seen != set(states):
            raise TreeError("TREE_CHANGED")
        if _state(os.fstat(root_fd)) != _state(root.lstat()) or root.resolve() != root:
            raise TreeError("TREE_CHANGED")
    finally:
        os.close(root_fd)
    return entries, states, total


def _result(status, reason, entries=0, size=0):
    return dict(
        schema=1,
        scope="LOCAL_INSTALLED_TREE_COMPARISON",
        status=status,
        reason=reason,
        compared_entries=entries,
        compared_bytes=size,
        declared_tree_files_compared=status == "MATCHED",
        declaration_authenticated=False,
        runtime_closure_verified=False,
        continuous_immutability_verified=False,
        registration_verified=False,
        live_eligible=False,
        promotion_allowed=False,
        program_readiness="NOT_ASSESSED",
        orders_submitted=0,
    )


def compare(expected, installed, main):
    try:
        expected = _canonical(expected, directory=False)
        installed = _canonical(installed, directory=True)
        main = _canonical(main, directory=True)
        if (
            installed == main
            or installed.is_relative_to(main)
            or main.is_relative_to(installed)
            or installed.samefile(main)
            or expected.is_relative_to(installed)
            or expected.is_relative_to(main)
        ):
            raise TreeError("ROOT_OVERLAP_REFUSED")
        expected_state = _state(expected.lstat())
        manifest = load_manifest(expected)
        deadline = time.monotonic() + 120
        first = _snapshot(installed, deadline)
        second = _snapshot(installed, deadline)
        if (
            first != second
            or load_manifest(expected) != manifest
            or _state(expected.lstat()) != expected_state
        ):
            raise TreeError("TREE_OR_MANIFEST_CHANGED")
        status = "MATCHED" if first[0] == manifest else "MISMATCH"
        return _result(
            status,
            "DECLARED_TREE_ONLY" if status == "MATCHED" else "TREE_CONTENT_MISMATCH",
            len(first[0]),
            first[2],
        )
    except TreeError as exc:
        return _result("UNAVAILABLE", str(exc))
    except (OSError, ValueError, RecursionError):
        return _result("UNAVAILABLE", "READ_UNAVAILABLE")


class TreeParser(argparse.ArgumentParser):
    def error(self, message):
        print(json.dumps(_result("UNAVAILABLE", "ARGUMENTS_INVALID"), sort_keys=True))
        raise SystemExit(2)


def main():
    parser = TreeParser(description=__doc__)
    parser.add_argument("--expected", required=True)
    parser.add_argument("--installed", required=True)
    parser.add_argument("--main", required=True)
    args = parser.parse_args()
    result = compare(args.expected, args.installed, args.main)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "MATCHED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
