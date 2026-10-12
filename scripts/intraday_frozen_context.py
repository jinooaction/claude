#!/usr/bin/env python3
"""Read-only local layout comparison; never installs, registers, collects or orders."""

from __future__ import annotations

import argparse
import hashlib
import importlib.machinery
import importlib.metadata
import json
import os
import platform
import re
import stat
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryFile


class ContextError(ValueError):
    pass


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _state(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _read_regular(path, limit):
    path = Path(path).absolute()
    try:
        if path.resolve() != path:
            raise ContextError("FILE_ALIAS_REFUSED")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                    or not 0 < before.st_size <= limit):
                raise ContextError("FILE_BOUNDS_INVALID")
            raw = os.read(fd, limit + 1)
            if len(raw) != before.st_size or _state(before) != _state(os.fstat(fd)):
                raise ContextError("FILE_CHANGED")
            if _state(before) != _state(path.lstat()):
                raise ContextError("FILE_CHANGED")
            return raw
        finally:
            os.close(fd)
    except OSError:
        raise ContextError("FILE_UNAVAILABLE") from None


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContextError("EXPECTED_CONTEXT_INVALID")
        result[key] = value
    return result


def _validate(value):
    try:
        if (not isinstance(value, dict) or len(_encoded(value)) > 32768
                or set(value) != {"schema", "scope", "commit", "tree", "lock_sha256",
                                  "python_version", "modules", "dependencies"}
                or type(value["schema"]) is not int or value["schema"] != 1
                or value["scope"] != "EXPECTED_LOCAL_FROZEN_CONTEXT"):
            raise ValueError
        for key, size in (("commit", 40), ("tree", 40), ("lock_sha256", 64)):
            if not isinstance(value[key], str) or not re.fullmatch(
                "[0-9a-f]{" + str(size) + "}", value[key],
            ):
                raise ValueError
        if not isinstance(value["python_version"], str) or not re.fullmatch(
            r"3\.[0-9]{1,2}\.[0-9]{1,3}", value["python_version"],
        ):
            raise ValueError
        modules, dependencies = value["modules"], value["dependencies"]
        if (not isinstance(modules, list) or not 1 <= len(modules) <= 16
                or not isinstance(dependencies, list) or not 1 <= len(dependencies) <= 32):
            raise ValueError
        names = []
        for module in modules:
            if (not isinstance(module, dict) or set(module) != {"name", "relative_path", "sha256"}
                    or not isinstance(module["name"], str)
                    or not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]{0,63}", module["name"])
                    or module["relative_path"] not in {
                        f"src/{module['name']}/__init__.py", f"src/{module['name']}.py"}
                    or not isinstance(module["sha256"], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", module["sha256"])):
                raise ValueError
            names.append(module["name"])
        if len(set(names)) != len(names):
            raise ValueError
        names = []
        for dependency in dependencies:
            if (not isinstance(dependency, dict) or set(dependency) != {"name", "version"}
                    or not isinstance(dependency["name"], str)
                    or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}", dependency["name"])
                    or not isinstance(dependency["version"], str)
                    or not re.fullmatch(r"[a-zA-Z0-9.!+_-]{1,80}", dependency["version"])):
                raise ValueError
            names.append(re.sub(r"[-_.]+", "-", dependency["name"]).lower())
        if len(set(names)) != len(names):
            raise ValueError
        return value
    except (ValueError, TypeError, KeyError, RecursionError):
        raise ContextError("EXPECTED_CONTEXT_INVALID") from None


def load_expected(path):
    try:
        raw = _read_regular(path, 32768)
        return _validate(json.loads(raw, object_pairs_hook=_unique))
    except (ValueError, UnicodeError, RecursionError):
        raise ContextError("EXPECTED_CONTEXT_INVALID") from None


def _directory(path):
    path = Path(path).absolute()
    if path.resolve() != path or not path.is_dir():
        raise ContextError("ROOT_UNAVAILABLE_OR_ALIASED")
    return path


def _overlap(left, right):
    # Inode comparison also catches case aliases on a case-insensitive filesystem.
    return any(left.samefile(path) for path in (right, *right.parents)) or any(
        right.samefile(path) for path in left.parents)


def _git(root, *args, allow_one=False):
    try:
        with TemporaryFile() as output:
            result = subprocess.run(
                ["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
                 "-c", "core.untrackedCache=false", "-C", str(root), *args],
                stdout=output, stderr=subprocess.DEVNULL, timeout=3, check=False,
                env={"PATH": os.defpath, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
                     "GIT_CONFIG_GLOBAL": os.devnull, "GIT_OPTIONAL_LOCKS": "0"},
            )
            if (result.returncode not in ({0, 1} if allow_one else {0})
                    or output.tell() > 65536):
                raise ContextError("GIT_UNAVAILABLE")
            output.seek(0)
            return result.returncode, output.read(65537).decode().strip()
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        raise ContextError("GIT_UNAVAILABLE") from None


def _git_state(root):
    if Path(_git(root, "rev-parse", "--show-toplevel")[1]).resolve() != root:
        raise ContextError("GIT_ROOT_MISMATCH")
    return dict(commit=_git(root, "rev-parse", "HEAD")[1],
                tree=_git(root, "rev-parse", "HEAD^{tree}")[1],
                detached=_git(root, "symbolic-ref", "-q", "HEAD", allow_one=True)[0] == 1,
                clean=not _git(root, "status", "--porcelain=v1", "-uall",
                               "--ignore-submodules=none")[1])


def _module_origin(name):
    module = sys.modules.get(name)
    if module is not None:
        origin = getattr(module, "__file__", None)
    else:
        spec = importlib.machinery.PathFinder.find_spec(name, sys.path)
        origin = spec.origin if spec else None
    if not isinstance(origin, str):
        raise ContextError("MODULE_ORIGIN_UNAVAILABLE")
    return origin


def _runtime(expected):
    try:
        modules = {item["name"]: _module_origin(item["name"]) for item in expected["modules"]}
        dependencies = {}
        for item in expected["dependencies"]:
            distribution = importlib.metadata.distribution(item["name"])
            dependencies[item["name"]] = dict(
                version=distribution.version, root=str(distribution.locate_file("")),
            )
        loaded = {}
        for name, module in sys.modules.copy().items():
            if any(name == parent or name.startswith(parent + ".") for parent in modules):
                origin = getattr(module, "__file__", None)
                if isinstance(origin, str):
                    loaded[name] = origin
        return dict(prefix=sys.prefix, python_version=platform.python_version(), modules=modules,
                    dependencies=dependencies, loaded_modules=loaded)
    except (OSError, ValueError, importlib.metadata.PackageNotFoundError):
        raise ContextError("RUNTIME_METADATA_UNAVAILABLE") from None


def _result(status, issues, expected_digest=None):
    return dict(schema=1, scope="LOCAL_FROZEN_CONTEXT_PREFLIGHT", status=status,
                issues=sorted(set(issues)), expected_sha256=expected_digest,
                program_readiness="NOT_ASSESSED", declaration_authenticated=False,
                dependency_files_verified=False, continuous_immutability_verified=False,
                registration_verified=False, live_eligible=False, promotion_allowed=False,
                orders_submitted=0)


def check_context(expected, candidate, main):
    """Compare local inputs once. This result is never an authorization or a signed freeze."""
    try:
        expected = _validate(expected)
        expected_digest = _sha(_encoded(expected))
        candidate, main = _directory(candidate), _directory(main)
        if _overlap(candidate, main):
            raise ContextError("ROOTS_OVERLAP")
        if Path(_git(main, "rev-parse", "--show-toplevel")[1]).resolve() != main:
            raise ContextError("MAIN_GIT_ROOT_MISMATCH")
        before = _git_state(candidate)
        lock = _read_regular(candidate / "uv.lock", 2097152)
        source = {item["name"]: _read_regular(candidate / item["relative_path"], 2097152)
                  for item in expected["modules"]}
        first = _runtime(expected)
        issues = []
        for field, reason in (("commit", "CODE_COMMIT_MISMATCH"), ("tree", "CODE_TREE_MISMATCH")):
            if before[field] != expected[field]:
                issues.append(reason)
        if not before["detached"]:
            issues.append("HEAD_NOT_DETACHED")
        if not before["clean"]:
            issues.append("CANDIDATE_NOT_CLEAN")
        if _sha(lock) != expected["lock_sha256"]:
            issues.append("LOCK_MISMATCH")
        prefix = _directory(first["prefix"])
        if prefix != _directory(candidate / ".venv"):
            issues.append("RUNTIME_PREFIX_MISMATCH")
        if first["python_version"] != expected["python_version"]:
            issues.append("PYTHON_VERSION_MISMATCH")
        for item in expected["modules"]:
            origin = Path(first["modules"][item["name"]]).absolute()
            if origin != candidate / item["relative_path"] or origin.resolve() != origin:
                issues.append("MODULE_ORIGIN_MISMATCH")
            if _sha(source[item["name"]]) != item["sha256"]:
                issues.append("MODULE_CONTENT_MISMATCH")
        for origin in first.get("loaded_modules", {}).values():
            if not Path(origin).resolve().is_relative_to(candidate / "src"):
                issues.append("LOADED_MODULE_MIXED")
        for item in expected["dependencies"]:
            observed = first["dependencies"][item["name"]]
            if observed["version"] != item["version"]:
                issues.append("DEPENDENCY_VERSION_MISMATCH")
            location = Path(observed["root"]).absolute()
            if location.resolve() != location or not location.is_relative_to(prefix):
                issues.append("DEPENDENCY_ORIGIN_MISMATCH")
        second = _runtime(expected)
        after = _git_state(candidate)
        if (before != after or first != second
                or lock != _read_regular(candidate / "uv.lock", 2097152)
                or any(raw != _read_regular(candidate / item["relative_path"], 2097152)
                       for item in expected["modules"] for raw in [source[item["name"]]])):
            issues.append("CONTEXT_CHANGED_DURING_CAPTURE")
        return _result("MISMATCH" if issues else "MATCHED", issues, expected_digest)
    except ContextError as exc:
        return _result("UNAVAILABLE", [str(exc)])
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        return _result("UNAVAILABLE", ["CONTEXT_UNAVAILABLE"])


class ContextParser(argparse.ArgumentParser):
    def error(self, message):
        raise ContextError("ARGUMENTS_INVALID")


def main():
    parser = ContextParser(description="후보 환경 지역 비교; 설치·등록·수집·주문 없음")
    parser.add_argument("--expected", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--main", required=True, type=Path)
    try:
        args = parser.parse_args()
        result = check_context(load_expected(args.expected), args.candidate, args.main)
    except ContextError as exc:
        result = _result("UNAVAILABLE", [str(exc)])
    raw = _encoded(result)
    if len(raw) > 16384:
        result = _result("UNAVAILABLE", ["RESULT_TOO_LARGE"])
        raw = _encoded(result)
    print(raw.decode())
    return 0 if result["status"] == "MATCHED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
