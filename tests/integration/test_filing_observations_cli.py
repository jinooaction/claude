"""Offline command boundaries: never create a store during read-only commands."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from auto_invest.analytics.filing_observations import Observation, RunStore

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/filing_observations.py"


def run_cli(*args):
    env = dict(os.environ)
    env.pop("SEC_USER_AGENT", None)
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          env=env, capture_output=True, text=True, timeout=10)


def sample_store(root):
    store = RunStore(root, clock=lambda: "2026-09-28T12:00:05Z")
    raw = (b"<html>Offline TEST scheduled earnings September 30, 2026 "
           b"after market close.</html>")
    item = Observation(
        "84dc0271-07f0-41ea-856b-510002131b80", "0000789019",
        "0000789019-26-000001", "primary",
        "https://www.sec.gov/Archives/edgar/data/789019/000078901926000001/doc.htm",
        store.blobs.put(raw), "2026-09-28T12:00:00Z", "2026-09-28T12:00:01Z",
        "2026-09-28T12:00:02Z", {},
    )
    store.publish({
        "schema_version": 1, "run_id": "fixture", "source_commit": "a" * 40,
        "config_sha256": "b" * 64, "started_at": "2026-09-28T12:00:00Z",
        "ended_at": "2026-09-28T12:00:03Z", "previous_run_sha256": None,
        "observations": [], "failures": [],
        "coverage": {"succeeded": 1, "failed": 0, "skipped": 0},
        "circuit": {"consecutive_failures": 0, "cooldown_until": None},
    }, [item])
    return item, raw


def test_verify_missing_store_does_not_create_it(tmp_path):
    root = tmp_path / "missing"
    result = run_cli("verify", "--store", root)
    assert result.returncode == 2
    assert "Filing operation refused:" in result.stderr
    assert not root.exists()


def test_verify_query_export_and_output_collision(tmp_path):
    root = tmp_path / "store"
    item, raw = sample_store(root)
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result = run_cli("verify", "--store", root)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["completed_runs"] == 1
    output = tmp_path / "query.json"
    result = run_cli("query", "--store", root, "--as-of", "2026-09-28T12:00:04Z",
                     "--output", output)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_bytes())["observations"] == []
    assert run_cli("query", "--store", root, "--as-of", "2026-09-28T12:00:06Z",
                   "--output", output).returncode == 2
    exported = tmp_path / "export"
    result = run_cli("export", "--store", root, "--observation", item.observation_id,
                     "--output", exported)
    assert result.returncode == 0, result.stderr
    assert (exported / "source.bin").read_bytes() == raw
    metadata = json.loads((exported / "metadata.json").read_bytes())
    assert metadata["reviewed_event"] is False
    assert metadata["observation"]["verified_at"] == item.verified_at
    assert run_cli("export", "--store", root, "--observation", item.observation_id,
                   "--output", exported).returncode == 2
    after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert after == before


def test_collect_missing_identification_has_no_network_or_store(tmp_path):
    result = run_cli("collect", "--store", tmp_path / "store", "--config", "absent.json",
                     "--run-id", "test")
    assert result.returncode == 2
    assert "Filing operation refused:" in result.stderr
    assert not (tmp_path / "store").exists()


def test_export_unknown_observation_does_not_create_output(tmp_path):
    root = tmp_path / "store"
    sample_store(root)
    output = tmp_path / "export"
    result = run_cli("export", "--store", root, "--observation", "../../private",
                     "--output", output)
    assert result.returncode == 2
    assert "Filing operation refused:" in result.stderr
    assert not output.exists()


def test_read_only_store_rejects_mutations(tmp_path):
    root = tmp_path / "store"
    sample_store(root)
    store = RunStore(root, read_only=True)
    with pytest.raises(ValueError, match="read-only"):
        store.blobs.put(b"new")
    with pytest.raises(ValueError, match="read-only"):
        store.publish({}, [])


def test_query_cannot_write_inside_store(tmp_path):
    root = tmp_path / "store"
    sample_store(root)
    result = run_cli("query", "--store", root, "--as-of", "2026-09-28T12:00:06Z",
                     "--output", root / "runs/poison.json")
    assert result.returncode == 2
    assert "Filing operation refused:" in result.stderr
    assert not (root / "runs/poison.json").exists()


def test_recovery_command_exports_original_without_review_claim(tmp_path, monkeypatch, capsys):
    import importlib.util

    spec = importlib.util.spec_from_file_location("filing_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "source_commit", lambda: "a" * 40)
    artifact = tmp_path / "artifact"
    item, raw = sample_store(artifact)
    store = tmp_path / "store"
    assert module.main(["recover", "--store", str(store), "--artifact", str(artifact),
                        "--run-id", "recovered"]) == 0
    assert json.loads(capsys.readouterr().out)["new_network_observations"] == 0
    output = tmp_path / "exported"
    result = run_cli("export", "--store", store, "--observation", item.observation_id,
                     "--output", output)
    assert result.returncode == 0, result.stderr
    assert (output / "source.bin").read_bytes() == raw
    assert json.loads((output / "metadata.json").read_bytes())["reviewed_event"] is False


def test_export_to_existing195_preserves_current_review_time_and_document_identity(tmp_path):
    from freezegun import freeze_time

    from auto_invest.analytics.earnings_event_inputs import import_bundle, query_bundle

    root = tmp_path / "store"
    item, raw = sample_store(root)
    exported = tmp_path / "export"
    result = run_cli("export", "--store", root, "--observation", item.observation_id,
                     "--output", exported)
    assert result.returncode == 0, result.stderr
    metadata = json.loads((exported / "metadata.json").read_bytes())
    # Deliberately supplied review of a synthetic fixture, never auto-generated
    # from an 8-K form or promoted to a research/live candidate.
    reviewed = {
        "schema_version": 1, "issuers": [item.issuer_cik],
        "documents": [{"id": "reviewed-doc-1", "path": "source.bin",
                       "sha256": metadata["observation"]["blob_sha256"], "url": item.url,
                       "source_claims": [f"collector receipt {item.observation_id}"]}],
        "events": [{"id": "reviewed-event-1", "event_key": "fixture-2026-q3",
                    "issuer_cik": item.issuer_cik, "kind": "scheduled",
                    "report_period_end": None, "event_date": "2026-09-30",
                    "time_label": "after_close", "document_id": "reviewed-doc-1",
                    "evidence_quotes": ["September 30, 2026 after market close."],
                    "supersedes": None, "symbol": "MSFT", "lineage_status": "unverified"}],
    }
    reviewed_path = exported / "reviewed-input.json"
    reviewed_path.write_text(json.dumps(reviewed))
    bundle = tmp_path / "reviewed-bundle"
    with freeze_time("2026-09-29T10:00:00Z"):
        import_bundle(reviewed_path, bundle)
    assert query_bundle(bundle, "2026-09-28T12:00:05Z")["events"] == []
    visible = query_bundle(bundle, "2026-09-29T10:00:00Z")
    assert len(visible["events"]) == 1
    assert visible["live_eligible"] is False
    manifest = json.loads((bundle / "manifest.json").read_bytes())
    assert manifest["events"][0]["verified_at"].startswith("2026-09-29T10:00:00")
    assert manifest["documents"][0]["observed_start"].startswith("2026-09-29T10:00:00")
    assert (bundle / "documents/reviewed-doc-1.html").read_bytes() == raw
    # Reobserving identical bytes does not authorize reusing a reviewed ID.
    with freeze_time("2026-09-29T11:00:00Z"), pytest.raises(ValueError, match="duplicate document"):
        import_bundle(reviewed_path, tmp_path / "collision", previous=bundle)
    reviewed["documents"][0]["id"] = "reviewed-doc-2"
    reviewed["events"][0].update(id="reviewed-event-2", document_id="reviewed-doc-2",
                                 supersedes="reviewed-event-1")
    reviewed_path.write_text(json.dumps(reviewed))
    revised = tmp_path / "revised-bundle"
    with freeze_time("2026-09-29T11:00:00Z"):
        import_bundle(reviewed_path, revised, previous=bundle)
    assert query_bundle(revised, "2026-09-29T10:30:00Z")["events"] == visible["events"]
    assert query_bundle(revised, "2026-09-29T11:00:00Z")["events"][0]["id"] == "reviewed-event-2"
