"""Publishing may append verified files; it cannot replace or remove history."""

import importlib.util
from pathlib import Path

import pytest

from auto_invest.analytics.filing_observations import RunStore

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/filing_publication.py"


def publisher():
    spec = importlib.util.spec_from_file_location("filing_publication", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def empty_run(root, identity="one", parent=None, hour="12"):
    stamp = f"2026-09-28T{hour}:00:00Z"
    store = RunStore(root, clock=lambda: stamp)
    digest = store.publish({
        "schema_version": 1, "run_id": identity, "source_commit": "a" * 40,
        "config_sha256": "b" * 64, "started_at": stamp, "ended_at": stamp,
        "previous_run_sha256": parent, "observations": [], "failures": [],
        "coverage": {"succeeded": 0, "failed": 0, "skipped": 0},
        "circuit": {"consecutive_failures": 0, "cooldown_until": None},
    }, [])
    return store, digest


def test_publish_append_retains_existing_bytes(tmp_path):
    module = publisher()
    source, first = empty_run(tmp_path / "source")
    destination = tmp_path / "destination"
    module.stage(source.root, destination)
    before = (destination / "runs/one.json").read_bytes()
    empty_run(source.root, "two", first, "13")
    result = module.stage(source.root, destination)
    assert result["added_files"] == 1
    assert (destination / "runs/one.json").read_bytes() == before
    assert len(RunStore(destination, read_only=True).verify()) == 2


def test_divergent_or_deleted_history_rejected_before_copy(tmp_path):
    module = publisher()
    source, _ = empty_run(tmp_path / "source")
    destination, _ = empty_run(tmp_path / "destination", "another")
    with pytest.raises(ValueError, match="history"):
        module.stage(source.root, destination.root)
    assert not (destination.root / "runs/one.json").exists()


def test_unreferenced_symlink_never_uploaded(tmp_path):
    module = publisher()
    source, _ = empty_run(tmp_path / "source")
    private = tmp_path / "private"
    private.write_text("not public")
    (source.root / "blobs" / ("a" * 64)).symlink_to(private)
    destination = tmp_path / "destination"
    with pytest.raises(ValueError, match="symlink"):
        module.stage(source.root, destination)
    assert not destination.exists()


def test_local_lock_is_excluded_and_unknown_files_refused(tmp_path):
    module = publisher()
    source, _ = empty_run(tmp_path / "source")
    (source.root / ".collector.lock").touch()
    destination = tmp_path / "destination"
    module.stage(source.root, destination)
    assert not (destination / ".collector.lock").exists()
    (source.root / "contact.txt").write_text("private")
    with pytest.raises(ValueError, match="unexpected"):
        module.stage(source.root, tmp_path / "refused")
