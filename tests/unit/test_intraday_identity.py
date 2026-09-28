"""Changes to shared execution dependencies invalidate prior evidence."""

import ast
import importlib.util
import shutil
from pathlib import Path

import pytest

from auto_invest.analytics.intraday_paper_challenger import (
    build_candidate_registry,
    load_preregistration,
)
from auto_invest.execution import intraday_identity as identity
from auto_invest.execution.intraday_signals import execution_fingerprint

ROOT = Path(__file__).resolve().parents[2]
PROVIDER = "kis-nasdaq-partial-unadjusted"


def candidate():
    return build_candidate_registry(load_preregistration(
        ROOT / "specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json"
    ))[0]


@pytest.mark.parametrize("source", [
    "execution/order_router.py", "execution/authority.py",
    "risk/gates.py", "market_data/intraday.py",
])
def test_shared_execution_change_invalidates_identity(monkeypatch, source):
    selected = candidate()
    before = execution_fingerprint(selected, PROVIDER)
    read = Path.read_bytes

    def changed(path):
        raw = read(path)
        return raw + b"\n# changed dependency\n" if path.as_posix().endswith(source) else raw

    monkeypatch.setattr(Path, "read_bytes", changed)
    assert execution_fingerprint(selected, PROVIDER) != before


def test_reviewed_list_covers_static_local_imports_and_packages():
    covered = set(identity.SOURCE_PATHS)
    missing = set()
    for name in covered:
        path = ROOT / name
        if path.suffix != ".py":
            continue
        package = ".".join(path.relative_to(ROOT / "src").with_suffix("").parts[:-1])
        for node in ast.walk(ast.parse(path.read_text())):
            modules = []
            if isinstance(node, ast.Import):
                modules = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level:
                    module = importlib.util.resolve_name("." * node.level + module, package)
                modules = [module, *(module + "." + item.name for item in node.names
                                     if item.name != "*")]
            for module in modules:
                if module != "auto_invest" and not module.startswith("auto_invest."):
                    continue
                parts = module.split(".")
                for length in range(1, len(parts) + 1):
                    stem = ROOT.joinpath("src", *parts[:length])
                    for dependency in (stem.with_suffix(".py"), stem / "__init__.py"):
                        relative = dependency.relative_to(ROOT).as_posix()
                        if dependency.is_file() and relative not in covered:
                            missing.add(relative)
    assert not missing, sorted(missing)


def test_identity_is_portable_and_ignores_research_documents(tmp_path, monkeypatch):
    selected = candidate()
    before = execution_fingerprint(selected, PROVIDER)
    for name in identity.SOURCE_PATHS:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    monkeypatch.setattr(identity, "ROOT", tmp_path)
    assert execution_fingerprint(selected, PROVIDER) == before
    (tmp_path / "HANDOFF.md").write_text("different research notes")
    assert execution_fingerprint(selected, PROVIDER) == before
    assert all(not Path(item["path"]).is_absolute() for item in identity.source_identity())


@pytest.fixture
def small_sources(tmp_path, monkeypatch):
    names = ("src/auto_invest/a.py", "src/auto_invest/b.py")
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("pass\n")
    monkeypatch.setattr(identity, "ROOT", tmp_path)
    monkeypatch.setattr(identity, "SOURCE_PATHS", names)
    return [tmp_path / name for name in names]


def test_names_are_bound_even_when_contents_are_identical(small_sources):
    records = identity.source_identity()
    assert records[0]["sha256"] == records[1]["sha256"]
    assert records[0]["path"] != records[1]["path"]


@pytest.mark.parametrize("fault", ["delete", "directory", "symlink", "hardlink"])
def test_nonregular_or_missing_source_refused(small_sources, fault):
    first, second = small_sources
    first.unlink()
    if fault == "directory":
        first.mkdir()
    elif fault == "symlink":
        first.symlink_to(second)
    elif fault == "hardlink":
        first.hardlink_to(second)
    with pytest.raises(ValueError, match="EXECUTION_SOURCE_UNAVAILABLE"):
        identity.source_identity()


def test_read_error_refused(small_sources, monkeypatch):
    def fail(_):
        raise PermissionError("sensitive local details")

    monkeypatch.setattr(Path, "read_bytes", fail)
    with pytest.raises(ValueError, match="^EXECUTION_SOURCE_UNAVAILABLE$"):
        identity.source_identity()


@pytest.mark.parametrize("change_earlier", [False, True])
def test_change_during_snapshot_refused(small_sources, monkeypatch, change_earlier):
    original = Path.read_bytes
    first, second = small_sources

    def read(path):
        raw = original(path)
        if path == second:
            (first if change_earlier else second).write_bytes(b"changed source\n")
        return raw

    monkeypatch.setattr(Path, "read_bytes", read)
    with pytest.raises(ValueError, match="EXECUTION_SOURCE_CHANGED"):
        identity.source_identity()


def test_duplicate_list_refused(small_sources, monkeypatch):
    monkeypatch.setattr(identity, "SOURCE_PATHS", identity.SOURCE_PATHS * 2)
    with pytest.raises(ValueError, match="EXECUTION_SOURCE_LIST_INVALID"):
        identity.source_identity()
