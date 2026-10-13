"""Small synthetic install images; no installed candidate, broker or secret."""

import copy
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/intraday_installed_tree.py"
SPEC = importlib.util.spec_from_file_location("installed_tree", SCRIPT)
tree = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tree)


@pytest.fixture
def image(tmp_path):
    installed, main = tmp_path / "image", tmp_path / "main"
    installed.mkdir()
    main.mkdir()
    for name in ["lib", "lib/pkg", "bin", "empty"]:
        (installed / name).mkdir(mode=0o755)
        (installed / name).chmod(0o755)
    for name, content in {
        "lib/pkg/version.txt": b"1.0",
        "lib/pkg/code.py": b"SAFE = 1\n",
        "lib/startup.pth": b"import forbidden_candidate_execution\n",
        "bin/python": b"not an executable Python",
        "empty.dat": b"",
    }.items():
        (installed / name).write_bytes(content)
        (installed / name).chmod(0o644)
    entries = []
    for path in sorted(installed.rglob("*")):
        item = dict(
            path=path.relative_to(installed).as_posix(),
            kind="directory" if path.is_dir() else "file",
            mode=path.stat().st_mode & 0o777,
        )
        if path.is_file():
            raw = path.read_bytes()
            item.update(size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        entries.append(item)
    value = dict(schema=1, scope="EXPECTED_INSTALLED_TREE", entries=entries)
    expected = tmp_path / "expected.json"
    expected.write_text(json.dumps(value))
    return installed, main, expected, value


def check(image):
    installed, main, expected, _ = image
    return tree.compare(expected, installed, main)


def test_matching_tree_has_no_authority(image):
    result = check(image)
    assert result["status"] == "MATCHED"
    assert result["compared_entries"] == 9
    assert result["declared_tree_files_compared"] is True
    for key in [
        "declaration_authenticated",
        "runtime_closure_verified",
        "continuous_immutability_verified",
        "registration_verified",
        "live_eligible",
        "promotion_allowed",
    ]:
        assert result[key] is False
    assert result["orders_submitted"] == 0 and result["program_readiness"] == "NOT_ASSESSED"


@pytest.mark.parametrize(
    "change", ["byte", "add", "remove", "mode", "directory", "hidden", "empty"]
)
def test_same_version_content_changes_refused(image, change):
    installed, _, _, _ = image
    code = installed / "lib/pkg/code.py"
    if change == "byte":
        code.write_bytes(b"SAFE = 0\n")
    elif change == "add":
        (installed / "lib/pkg/extra.py").write_text("EXTRA")
    elif change == "remove":
        code.unlink()
    elif change == "mode":
        code.chmod(0o755)
    elif change == "directory":
        (installed / "empty").rmdir()
    elif change == "hidden":
        (installed / ".hidden").write_text("not ignored")
    else:
        (installed / "empty.dat").write_bytes(b"nonempty")
    assert (installed / "lib/pkg/version.txt").read_bytes() == b"1.0"
    assert check(image)["status"] == "MISMATCH"


@pytest.mark.parametrize(
    "change", ["symlink", "directory_link", "hardlink", "fifo", "setuid", "sticky_directory"]
)
def test_unsafe_tree_nodes_refused(image, change):
    installed, main, _, _ = image
    if change == "symlink":
        (installed / "leak").symlink_to(main / "missing")
    elif change == "directory_link":
        (installed / "linked").symlink_to(main, target_is_directory=True)
    elif change == "hardlink":
        os.link(installed / "empty.dat", installed / "another")
    elif change == "fifo":
        os.mkfifo(installed / "pipe")
    elif change == "setuid":
        (installed / "empty.dat").chmod(0o4644)
    else:
        (installed / "empty").chmod(0o1777)
    assert check(image)["status"] == "UNAVAILABLE"


@pytest.mark.parametrize(
    "path",
    [
        "../escape",
        "/absolute",
        "lib//pkg",
        "./lib",
        "lib/..",
        "with space",
        "with\nnewline",
        "x/" * 33 + "y",
        "x" * 1025,
        "é",
    ],
)
def test_nonportable_paths_refused(image, path):
    _, _, expected, original = image
    value = copy.deepcopy(original)
    value["entries"][0]["path"] = path
    expected.write_text(json.dumps(value))
    assert check(image)["status"] == "UNAVAILABLE"


@pytest.mark.parametrize(
    "change",
    [
        "unknown",
        "schema_bool",
        "scope",
        "entries_empty",
        "duplicate",
        "missing_parent",
        "bad_kind",
        "mode_bool",
        "mode_bits",
        "size_bool",
        "size_negative",
        "sha",
        "file_unknown",
    ],
)
def test_closed_manifest_refuses_bad_entries(image, change):
    _, _, expected, original = image
    value = copy.deepcopy(original)
    file = next(item for item in value["entries"] if item["kind"] == "file")
    if change == "unknown":
        value["extra"] = "private"
    elif change == "schema_bool":
        value["schema"] = True
    elif change == "scope":
        value["scope"] = "EXECUTION_ALLOWED"
    elif change == "entries_empty":
        value["entries"] = []
    elif change == "duplicate":
        value["entries"].append(copy.deepcopy(value["entries"][0]))
    elif change == "missing_parent":
        value["entries"] = [item for item in value["entries"] if item["path"] != "lib"]
    elif change == "bad_kind":
        file["kind"] = "symlink"
    elif change == "mode_bool":
        file["mode"] = True
    elif change == "mode_bits":
        file["mode"] = 0o4644
    elif change == "size_bool":
        file["size"] = True
    elif change == "size_negative":
        file["size"] = -1
    elif change == "sha":
        file["sha256"] = "invalid"
    else:
        file["unknown"] = "private"
    expected.write_text(json.dumps(value))
    assert check(image)["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("value", ['{"schema":1,"schema":1}', "[" * 1500, "NaN", "{}"])
def test_invalid_json_refused(image, value):
    image[2].write_text(value)
    assert check(image)["status"] == "UNAVAILABLE"


def test_main_changes_do_not_change_image(image):
    (image[1] / "main.py").write_text("updated")
    assert check(image)["status"] == "MATCHED"


@pytest.mark.parametrize(
    "change", ["same", "nested", "root_link", "parent_link", "expected_inside"]
)
def test_roots_are_separate_and_not_aliased(image, tmp_path, change):
    installed, main, expected, value = image
    if change == "same":
        main = installed
    elif change == "nested":
        main = installed / "empty"
    elif change == "root_link":
        alias = tmp_path / "alias"
        alias.symlink_to(installed, target_is_directory=True)
        installed = alias
    elif change == "parent_link":
        alias = tmp_path / "parent"
        alias.symlink_to(tmp_path, target_is_directory=True)
        installed = alias / "image"
    else:
        expected = installed / "expected.json"
        expected.write_text(json.dumps(value))
    assert tree.compare(expected, installed, main)["status"] == "UNAVAILABLE"


def test_mutation_between_observations_refused(image, monkeypatch):
    original = tree._snapshot
    calls = 0

    def changed(*args):
        nonlocal calls
        result = original(*args)
        calls += 1
        if calls == 1:
            (image[0] / "lib/pkg/code.py").write_bytes(b"SAFE = 0\n")
        return result

    monkeypatch.setattr(tree, "_snapshot", changed)
    assert check(image)["reason"] == "TREE_OR_MANIFEST_CHANGED"


def test_read_failure_does_not_echo_path(image, monkeypatch):
    def failure(*args):
        raise OSError("private secret /actual/account")

    monkeypatch.setattr(tree, "_snapshot", failure)
    result = check(image)
    assert result["reason"] == "READ_UNAVAILABLE"
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize("limit", ["MAX_FILE", "MAX_TOTAL", "MAX_MANIFEST", "MAX_ENTRIES"])
def test_bounds_refused(image, monkeypatch, limit):
    monkeypatch.setattr(tree, limit, 1)
    assert check(image)["status"] == "UNAVAILABLE"


def test_read_budget_refused(image, monkeypatch):
    def expired(_):
        raise tree.TreeError("READ_BUDGET_EXCEEDED")

    monkeypatch.setattr(tree, "_check_time", expired)
    assert check(image)["reason"] == "READ_BUDGET_EXCEEDED"


def test_no_candidate_or_startup_code_is_executed(image, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("no subprocess")

    monkeypatch.setattr(subprocess, "run", forbidden)
    assert check(image)["status"] == "MATCHED"
    assert "forbidden_candidate_execution" not in sys.modules


@pytest.mark.parametrize("valid", [True, False])
def test_cli_is_single_safe_json(image, valid):
    script = Path(tree.__file__).resolve()
    args = [sys.executable, str(script)]
    if valid:
        args += ["--installed", str(image[0]), "--main", str(image[1]), "--expected", str(image[2])]
    else:
        args += ["--private-account", "do-not-echo"]
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    value = json.loads(result.stdout)
    assert value["status"] == ("MATCHED" if valid else "UNAVAILABLE")
    assert result.returncode == (0 if valid else 2)
    assert result.stderr == "" and len(result.stdout.encode()) < 16384
    assert str(image[0]) not in result.stdout and "do-not-echo" not in result.stdout


def test_case_alias_manifest_refused_on_all_platforms(image):
    value = copy.deepcopy(image[3])
    value["entries"].append(dict(path="LIB", kind="directory", mode=0o755))
    image[2].write_text(json.dumps(value))
    assert check(image)["status"] == "UNAVAILABLE"


def test_file_change_during_read_refused(image, monkeypatch):
    target = image[0] / "lib/pkg/code.py"
    inode = target.stat().st_ino
    original = os.read
    changed = False

    def read(fd, size):
        nonlocal changed
        content = original(fd, size)
        if os.fstat(fd).st_ino == inode and not changed:
            changed = True
            target.write_bytes(b"SAFE = 0\n")
        return content

    monkeypatch.setattr(os, "read", read)
    assert check(image)["reason"] == "TREE_CHANGED"


def test_manifest_same_content_replacement_refused(image, monkeypatch):
    original = tree._snapshot
    calls = 0

    def capture(*args):
        nonlocal calls
        result = original(*args)
        calls += 1
        if calls == 1:
            other = image[2].with_suffix(".replacement")
            other.write_bytes(image[2].read_bytes())
            other.replace(image[2])
        return result

    monkeypatch.setattr(tree, "_snapshot", capture)
    assert check(image)["reason"] == "TREE_OR_MANIFEST_CHANGED"


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "missing"])
def test_manifest_unavailable_is_not_match(image, tmp_path, kind):
    expected = image[2]
    if kind == "hardlink":
        os.link(expected, tmp_path / "second-manifest")
    else:
        expected.unlink()
        if kind == "symlink":
            expected.symlink_to(tmp_path / "missing")
        elif kind == "fifo":
            os.mkfifo(expected)
    assert check(image)["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("limit", ["MAX_FILE", "MAX_TOTAL", "MAX_ENTRIES"])
def test_observed_tree_limits_independently_refused(image, monkeypatch, limit):
    tree.validate_manifest(image[3])
    monkeypatch.setattr(tree, limit, 1)
    with pytest.raises(tree.TreeError):
        tree._snapshot(image[0], tree.time.monotonic() + 120)


def test_cross_device_node_refused(image, monkeypatch):
    original = os.stat

    def observed(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path == "empty.dat" and kwargs.get("dir_fd") is not None:
            values = list(info)
            values[2] = info.st_dev + 1
            return os.stat_result(values)
        return info

    monkeypatch.setattr(os, "stat", observed)
    assert check(image)["reason"] == "TREE_KIND_OR_DEVICE_INVALID"


def test_inspector_preserves_original_bytes_modes_and_directory_entries(image):
    before = [
        (
            p.relative_to(image[0]).as_posix(),
            p.stat().st_mode,
            p.read_bytes() if p.is_file() else None,
        )
        for p in sorted(image[0].rglob("*"))
    ]
    expected = image[2].read_bytes()
    assert check(image)["status"] == "MATCHED"
    after = [
        (
            p.relative_to(image[0]).as_posix(),
            p.stat().st_mode,
            p.read_bytes() if p.is_file() else None,
        )
        for p in sorted(image[0].rglob("*"))
    ]
    assert before == after and expected == image[2].read_bytes()


def test_earlier_file_changes_while_later_file_is_read_refused(image, monkeypatch):
    target = image[0] / "lib/pkg/code.py"
    late_inode = (image[0] / "empty.dat").stat().st_ino
    original = os.read
    original_scan = os.scandir
    reads = 0

    @contextmanager
    def ordered_scan(fd):
        with original_scan(fd) as scan:
            entries = sorted(scan, key=lambda item: (item.name == "empty.dat", item.name))
        yield iter(entries)

    def read(fd, size):
        nonlocal reads
        content = original(fd, size)
        if os.fstat(fd).st_ino == late_inode:
            reads += 1
            if reads == 2:
                target.write_bytes(b"SAFE = 0\n")
        return content

    monkeypatch.setattr(os, "read", read)
    monkeypatch.setattr(os, "scandir", ordered_scan)
    assert check(image)["status"] == "UNAVAILABLE"
