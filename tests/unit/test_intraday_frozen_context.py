import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/intraday_frozen_context.py"
spec = importlib.util.spec_from_file_location("frozen_context", SCRIPT)
context = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)
RUNTIME_READER = context._runtime


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def make_repo(root):
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.name", "Synthetic")
    git(root, "config", "user.email", "synthetic@example.invalid")
    (root / ".gitignore").write_text(".venv/\n__pycache__/\n")
    (root / "uv.lock").write_text("synthetic-lock\n")
    package = root / "src/auto_invest"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("raise RuntimeError('must never import')\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "synthetic baseline")
    git(root, "checkout", "--detach", "-q")
    return root


@pytest.fixture
def setup(tmp_path, monkeypatch):
    candidate, main = make_repo(tmp_path / "candidate"), make_repo(tmp_path / "main")
    prefix = candidate / ".venv"
    prefix.mkdir()
    site = prefix / "site-packages"
    site.mkdir()
    expected = dict(schema=1, scope="EXPECTED_LOCAL_FROZEN_CONTEXT",
                    commit=git(candidate, "rev-parse", "HEAD"),
                    tree=git(candidate, "rev-parse", "HEAD^{tree}"),
                    lock_sha256=hashlib.sha256((candidate / "uv.lock").read_bytes()).hexdigest(),
                    python_version="3.11.13",
                    modules=[dict(name="auto_invest", relative_path="src/auto_invest/__init__.py",
                                  sha256=hashlib.sha256(
                                      (candidate / "src/auto_invest/__init__.py").read_bytes()
                                  ).hexdigest())],
                    dependencies=[dict(name="example-package", version="1.2.3")])
    runtime = dict(prefix=str(prefix), python_version="3.11.13",
                   modules={"auto_invest": str(candidate / "src/auto_invest/__init__.py")},
                   dependencies={"example-package": dict(version="1.2.3", root=str(site))})
    monkeypatch.setattr(context, "_runtime", lambda _: copy.deepcopy(runtime))
    return candidate, main, expected, runtime


def run(setup):
    candidate, main, expected, _ = setup
    return context.check_context(expected, candidate, main)


def test_main_changes_leave_frozen_candidate_and_original_files_unchanged(setup):
    candidate, main, expected, _ = setup
    before = (candidate / "uv.lock").read_bytes()
    assert run(setup)["status"] == "MATCHED"
    git(main, "commit", "--allow-empty", "-qm", "new main")
    result = run(setup)
    assert result["status"] == "MATCHED"
    assert before == (candidate / "uv.lock").read_bytes()
    assert git(candidate, "rev-parse", "HEAD") == expected["commit"]
    assert git(candidate, "status", "--porcelain") == ""
    assert result["orders_submitted"] == 0 and result["live_eligible"] is False
    assert result["declaration_authenticated"] is False
    assert result["dependency_files_verified"] is False
    assert result["continuous_immutability_verified"] is False
    assert result["program_readiness"] == "NOT_ASSESSED"


def test_identical_tree_new_commit_is_mismatch(setup):
    candidate, _, expected, _ = setup
    git(candidate, "commit", "--allow-empty", "-qm", "same tree new commit")
    assert git(candidate, "rev-parse", "HEAD^{tree}") == expected["tree"]
    assert "CODE_COMMIT_MISMATCH" in run(setup)["issues"]


@pytest.mark.parametrize("mutation", ["tracked", "untracked", "lock", "branch", "tree"])
def test_git_and_lock_changes_are_refused(setup, mutation):
    candidate, _, expected, _ = setup
    if mutation == "tracked":
        (candidate / "src/auto_invest/__init__.py").write_text("changed")
    elif mutation == "untracked":
        (candidate / "unknown.py").write_text("new")
    elif mutation == "lock":
        expected["lock_sha256"] = "0" * 64
    elif mutation == "branch":
        git(candidate, "checkout", "-qb", "moving-branch")
    else:
        expected["tree"] = "0" * 40
    assert run(setup)["status"] == "MISMATCH"


@pytest.mark.parametrize("mutation", ["prefix", "python", "module", "version", "dependency",
                                      "source_hash", "prefix_alias", "source_alias"])
def test_runtime_source_and_dependency_mixing_is_refused(setup, mutation):
    candidate, main, expected, runtime = setup
    if mutation == "prefix":
        runtime["prefix"] = str(main)
    elif mutation == "python":
        runtime["python_version"] = "3.12.0"
    elif mutation == "module":
        runtime["modules"]["auto_invest"] = str(main / "src/auto_invest/__init__.py")
    elif mutation == "version":
        runtime["dependencies"]["example-package"]["version"] = "1.2.4"
    elif mutation == "dependency":
        runtime["dependencies"]["example-package"]["root"] = str(main)
    elif mutation == "source_hash":
        expected["modules"][0]["sha256"] = "0" * 64
    elif mutation == "prefix_alias":
        alias = candidate / "alias"
        alias.symlink_to(candidate / ".venv", target_is_directory=True)
        runtime["prefix"] = str(alias)
    else:
        source = candidate / "src/auto_invest/__init__.py"
        source.unlink()
        source.symlink_to(main / "src/auto_invest/__init__.py")
    assert run(setup)["status"] != "MATCHED"


@pytest.mark.parametrize("which", ["same", "alias", "nested", "main_missing"])
def test_root_aliases_and_overlap_are_refused(setup, which):
    candidate, main, expected, _ = setup
    if which == "same":
        main = candidate
    elif which == "alias":
        alias = main.parent / "alias"
        alias.symlink_to(candidate, target_is_directory=True)
        main = alias
    elif which == "nested":
        main = candidate / ".venv"
    else:
        main = main.parent / "absent"
    assert context.check_context(expected, candidate, main)["status"] != "MATCHED"


@pytest.mark.parametrize("field,value", [("schema", True), ("schema", 2),
    ("scope", "other"), ("commit", "main"), ("tree", "a" * 41),
    ("lock_sha256", "X" * 64), ("python_version", "3.11"),
    ("modules", []), ("dependencies", []), ("KIS_APP_KEY", "do-not-print")])
def test_invalid_expectations_are_closed_and_not_echoed(setup, field, value):
    setup[2][field] = value
    result = run(setup)
    assert result["status"] == "UNAVAILABLE"
    assert "EXPECTED_CONTEXT_INVALID" in result["issues"]
    assert "do-not-print" not in json.dumps(result)


@pytest.mark.parametrize("mutation", ["module_path", "module_name", "duplicate_module",
                                      "duplicate_dependency", "too_many", "version_type"])
def test_declaration_limits_and_unique_names(setup, mutation):
    expected = setup[2]
    if mutation == "module_path":
        expected["modules"][0]["relative_path"] = "src/../secret.py"
    elif mutation == "module_name":
        expected["modules"][0]["name"] = "auto_invest.submodule"
    elif mutation == "duplicate_module":
        expected["modules"] *= 2
    elif mutation == "duplicate_dependency":
        expected["dependencies"] *= 2
    elif mutation == "too_many":
        expected["dependencies"] *= 33
    else:
        expected["dependencies"][0]["version"] = 1
    assert run(setup)["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("mutation", ["head", "lock", "runtime"])
def test_change_during_capture_is_refused(setup, monkeypatch, mutation):
    candidate, _, _, runtime = setup
    calls = []

    def observe(_):
        if not calls:
            if mutation == "head":
                git(candidate, "commit", "--allow-empty", "-qm", "concurrent update")
            elif mutation == "lock":
                (candidate / "uv.lock").write_text("concurrent update")
            else:
                runtime["python_version"] = "3.11.14"
        calls.append(True)
        return copy.deepcopy(runtime)

    monkeypatch.setattr(context, "_runtime", observe)
    assert run(setup)["status"] != "MATCHED"


def test_module_lookup_does_not_import_candidate_code(setup, monkeypatch):
    candidate, _, expected, _ = setup
    monkeypatch.syspath_prepend(str(candidate / "src"))
    monkeypatch.delitem(__import__("sys").modules, "auto_invest", raising=False)
    assert context._module_origin("auto_invest") == str(candidate / "src/auto_invest/__init__.py")
    assert "auto_invest" not in __import__("sys").modules
    assert expected["modules"][0]["name"] == "auto_invest"


@pytest.mark.parametrize("raw", [b"x" * 32769, b'{"schema":1,"schema":1}', b'[]', b'NaN'])
def test_expected_input_size_duplicates_and_format(tmp_path, raw):
    source = tmp_path / "expected.json"
    source.write_bytes(raw)
    with pytest.raises(context.ContextError):
        context.load_expected(source)


def test_symlink_input_and_missing_files_are_refused(setup, tmp_path):
    source = tmp_path / "raw.json"
    source.write_text(json.dumps(setup[2]))
    alias = tmp_path / "alias.json"
    alias.symlink_to(source)
    with pytest.raises(context.ContextError):
        context.load_expected(alias)
    (setup[0] / "uv.lock").unlink()
    assert run(setup)["status"] != "MATCHED"


def test_git_failure_is_sanitized(setup, monkeypatch):
    def fail(*_):
        raise context.ContextError("GIT_UNAVAILABLE")
    monkeypatch.setattr(context, "_git_state", fail)
    assert run(setup)["issues"] == ["GIT_UNAVAILABLE"]


def test_cli_error_is_bounded_json_without_paths(tmp_path):
    result = subprocess.run([__import__("sys").executable, str(SCRIPT), "--expected",
        str(tmp_path / "secret-key-never-opened"), "--candidate", str(tmp_path),
        "--main", str(tmp_path)], capture_output=True, text=True, check=False)
    assert result.returncode == 2
    output = json.loads(result.stdout)
    assert output["status"] == "UNAVAILABLE" and output["orders_submitted"] == 0
    assert "secret-key-never-opened" not in result.stdout
    assert result.stderr == ""


def test_missing_cli_arguments_are_sanitized():
    result = subprocess.run([sys.executable, str(SCRIPT), "--unexpected", "do-not-print"],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert json.loads(result.stdout)["issues"] == ["ARGUMENTS_INVALID"]
    assert result.stderr == "" and "do-not-print" not in result.stdout


def test_injected_git_environment_is_not_used(setup, monkeypatch):
    monkeypatch.setenv("GIT_DIR", str(setup[1] / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(setup[1]))
    assert run(setup)["status"] == "MATCHED"


def test_fsmonitor_helper_is_not_executed(setup):
    root = setup[0]
    marker = root / "must-not-be-created"
    git(root, "config", "core.fsmonitor", f"touch {marker}")
    assert run(setup)["status"] == "MATCHED"
    assert not marker.exists()


@pytest.mark.parametrize("kind", ["timeout", "output", "nonzero"])
def test_git_timeout_output_limit_and_error(setup, monkeypatch, kind):
    def execute(*args, **kwargs):
        if kind == "timeout":
            raise subprocess.TimeoutExpired("secret-not-echoed", 3)
        if kind == "output":
            kwargs["stdout"].write(b"x" * 65537)
        return SimpleNamespace(returncode=1 if kind == "nonzero" else 0)
    monkeypatch.setattr(context.subprocess, "run", execute)
    assert run(setup)["issues"] == ["GIT_UNAVAILABLE"]


def test_loaded_module_from_main_is_detected(setup, monkeypatch):
    monkeypatch.setitem(sys.modules, "auto_invest",
                        SimpleNamespace(__file__=str(setup[1] / "src/auto_invest/__init__.py")))
    assert context._module_origin("auto_invest") == str(setup[1] / "src/auto_invest/__init__.py")


def test_loaded_child_module_mixing_is_refused(setup):
    setup[3]["loaded_modules"] = {"auto_invest.child": str(setup[1] / "src/auto_invest/child.py")}
    assert "LOADED_MODULE_MIXED" in run(setup)["issues"]


def test_non_repository_main_is_refused(setup, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert context.check_context(setup[2], setup[0], plain)["status"] == "UNAVAILABLE"


def test_actual_metadata_and_origin_lookup_with_synthetic_package(setup, monkeypatch):
    candidate, _, expected, runtime = setup
    sample = candidate / "src/frozen_test_sample"
    sample.mkdir()
    source = sample / "__init__.py"
    source.write_text("raise RuntimeError('do not import')")
    expected = copy.deepcopy(expected)
    expected["modules"] = [dict(name="frozen_test_sample",
                                relative_path="src/frozen_test_sample/__init__.py",
                                sha256=hashlib.sha256(source.read_bytes()).hexdigest())]
    site = Path(runtime["dependencies"]["example-package"]["root"])
    metadata = site / "example_package-1.2.3.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text("Name: example-package\nVersion: 1.2.3\n")
    monkeypatch.syspath_prepend(str(site))
    monkeypatch.syspath_prepend(str(candidate / "src"))
    monkeypatch.setattr(context.sys, "prefix", str(candidate / ".venv"))
    monkeypatch.setattr(context.platform, "python_version", lambda: "3.11.13")
    observed = RUNTIME_READER(expected)
    assert observed["modules"]["frozen_test_sample"] == str(source)
    assert observed["dependencies"]["example-package"] == dict(version="1.2.3", root=str(site))
    assert observed["prefix"] == str(candidate / ".venv")
    assert "frozen_test_sample" not in sys.modules


def test_recursive_json_input_is_sanitized(tmp_path):
    source = tmp_path / "nested.json"
    source.write_text("[" * 2000 + "]" * 2000)
    with pytest.raises(context.ContextError):
        context.load_expected(source)
