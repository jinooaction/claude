"""Small input checks only; real Git laboratory runs on GitHub Linux."""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "source_lab", Path(__file__).parents[2] / "scripts/intraday_source_input_lab.py"
)
lab = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lab)


@pytest.mark.parametrize("system,env", [
    ("Darwin", {"GITHUB_ACTIONS": "true", "RUNNER_OS": "Linux"}),
    ("Linux", {}),
    ("Linux", {"GITHUB_ACTIONS": "false", "RUNNER_OS": "Linux"}),
    ("Linux", {"GITHUB_ACTIONS": "true", "RUNNER_OS": "macOS"}),
])
def test_local_guard_precedes_git(system, env):
    with pytest.raises(lab.LabError):
        lab.guard(env, system)


def test_environment_does_not_inherit(monkeypatch):
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_CONFIG_COUNT", "LD_PRELOAD", "PYTHONPATH"):
        monkeypatch.setenv(key, "untrusted")
    env = lab.git_environment()
    assert not any(env.get(k) == "untrusted" for k in os.environ)
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert env["GIT_CONFIG_GLOBAL"] == "/dev/null"


def test_inventory_detects_bytes_mode_and_extra(tmp_path):
    p = tmp_path / "value"
    p.write_bytes(b"one")
    original = lab.inventory(tmp_path)
    p.write_bytes(b"two")
    assert lab.inventory(tmp_path) != original
    p.write_bytes(b"one")
    p.chmod(0o755)
    assert lab.inventory(tmp_path) != original
    (tmp_path / "extra").write_bytes(b"")
    assert "extra" in lab.inventory(tmp_path)


@pytest.mark.parametrize("kind", ["symlink", "directory_symlink", "hardlink", "fifo"])
def test_non_regular_inputs_rejected(tmp_path, kind):
    base = tmp_path / "root"
    base.mkdir()
    target = tmp_path / "outside"
    target.write_bytes(b"not-read")
    p = base / "value"
    if kind == "symlink":
        p.symlink_to(target)
    elif kind == "directory_symlink":
        p.symlink_to(tmp_path, target_is_directory=True)
    elif kind == "hardlink":
        os.link(target, p)
    else:
        os.mkfifo(p)
    with pytest.raises(lab.LabError):
        lab.inventory(base)


def test_root_symlink_rejected(tmp_path):
    link = tmp_path / "link"
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(lab.LabError):
        lab.inventory(link)


@pytest.mark.parametrize("limit", ["bytes", "entries", "depth"])
def test_inventory_limits(tmp_path, limit):
    if limit == "bytes":
        (tmp_path / "x").write_bytes(b"12345")
        kwargs = {"max_bytes": 4}
    elif limit == "entries":
        (tmp_path / "x").touch()
        (tmp_path / "y").touch()
        kwargs = {"max_entries": 1}
    else:
        (tmp_path / "a/b/c").mkdir(parents=True)
        kwargs = {"max_depth": 1}
    with pytest.raises(lab.LabError):
        lab.inventory(tmp_path, **kwargs)


@pytest.mark.parametrize("path", [".env", "credentials", "ledger.sqlite", ".git/config"])
def test_contaminated_inventory_rejected_before_git(tmp_path, monkeypatch, path):
    (tmp_path / "repo").mkdir()
    (tmp_path / "inputs").mkdir()
    expected = {"repo": lab.inventory(tmp_path / "repo"),
                "inputs": lab.inventory(tmp_path / "inputs")}
    p = tmp_path / "repo" / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"synthetic-contaminant")
    monkeypatch.setattr(lab, "git", lambda *a: pytest.fail("untrusted Git invoked"))
    with pytest.raises(lab.LabError, match="INPUT_MISMATCH"):
        lab.verify(tmp_path, expected)


def test_install_input_changed_before_git(tmp_path, monkeypatch):
    (tmp_path / "repo").mkdir()
    (tmp_path / "inputs").mkdir()
    p = tmp_path / "inputs" / "toy.txt"
    p.write_bytes(b"original")
    expected = {"repo": lab.inventory(tmp_path / "repo"),
                "inputs": lab.inventory(tmp_path / "inputs")}
    p.write_bytes(b"changed")
    monkeypatch.setattr(lab, "git", lambda *a: pytest.fail("Git invoked"))
    with pytest.raises(lab.LabError, match="INPUT_MISMATCH"):
        lab.verify(tmp_path, expected)


def test_report_has_no_authority():
    result = lab.receipt("a" * 40, "b" * 64, [])
    assert all(result[k] is False for k in lab.FALSE_FLAGS)
    assert result["container_starts"] == 0
    assert result["package_installs"] == 0


def test_report_source_strict():
    with pytest.raises(lab.LabError):
        lab.receipt("not-a-commit", "b" * 64, [])


def test_report_does_not_overwrite(tmp_path):
    p = tmp_path / "result.json"
    p.write_text("original")
    with pytest.raises(FileExistsError):
        lab.publish(p, {"value": 1})
    assert p.read_text() == "original"


def test_report_size_bound(tmp_path):
    p = tmp_path / "result.json"
    with pytest.raises(lab.LabError):
        lab.publish(p, {"value": "x" * 32768})
    assert not p.exists()


@pytest.mark.parametrize("kind", ["output", "timeout", "failure"])
def test_command_failures_are_bounded_and_redacted(tmp_path, kind):
    code, options, reason = {
        "output": ("print('x'*10000)", {"output_limit": 100}, "OUTPUT_LIMIT"),
        "timeout": ("import time; time.sleep(5)", {"timeout": 0.05}, "COMMAND_TIMEOUT"),
        "failure": ("raise SystemExit('private error')", {}, "GIT_FAILED"),
    }[kind]
    with pytest.raises(lab.LabError, match=reason) as exc:
        lab.command([sys.executable, "-I", "-S", "-c", code], tmp_path, **options)
    assert "private" not in str(exc.value)


def test_main_does_not_publish_after_cleanup_failure(tmp_path, monkeypatch, capsys):
    output = tmp_path / "result.json"
    monkeypatch.setattr(sys, "argv", ["lab", "--output", str(output)])
    def failure(*args):
        raise OSError("sensitive cleanup path")
    monkeypatch.setattr(lab, "run_lab", failure)
    assert lab.main() == 1
    assert not output.exists()
    assert capsys.readouterr().out == "SOURCE_INPUT_LAB_FAILED\n"
