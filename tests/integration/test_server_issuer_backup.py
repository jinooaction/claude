"""Server archives must restore a verified separate issuer chain, never arbitrary files."""

import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

from auto_invest.analytics.filing_observations import ISSUER_CIK, ISSUER_FEED, Observation, RunStore

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/filing_server_snapshot.py"
FIRST = "server-" + "a" * 32
SECOND = "server-" + "b" * 32


def _snapshot(source, archive):
    with tarfile.open(archive, "w:gz") as bundle:
        for name in ("blobs", "observations", "runs"):
            bundle.add(source / name, arcname=name)


def _unpack(archive, destination):
    return subprocess.run([sys.executable, str(SCRIPT), "unpack", "--archive",
                           str(archive), "--destination", str(destination)],
                          cwd=ROOT, capture_output=True, text=True, check=False)


def _stage(source, destination):
    result = subprocess.run([sys.executable, str(ROOT / "scripts/filing_publication.py"),
                             "--mode", "stage", "--source", str(source),
                             "--destination", str(destination)], cwd=ROOT,
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _inspect(source):
    result = subprocess.run([sys.executable, str(SCRIPT), "inspect-store", "--source",
                             str(source)], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _manifest(run_id, parent, started, ended, observations):
    return {
        "schema_version": 1, "run_id": run_id, "source_commit": "a" * 40,
        "config_sha256": "b" * 64, "started_at": started, "ended_at": ended,
        "previous_run_sha256": parent, "observations": [], "failures": [],
        "coverage": {"succeeded": observations, "failed": 0, "skipped": 0},
        "selection": {"unselected": 0, "limit_skipped": 0},
        "circuit": {"consecutive_failures": 0, "cooldown_until": None},
    }


def test_two_exports_replay_only_additions_and_preserve_first_run(tmp_path):
    ticks = iter(["2026-10-01T00:00:05Z", "2026-10-01T00:15:05Z"])
    source = RunStore(tmp_path / "server", clock=lambda: next(ticks))
    digest = source.blobs.put(b"issuer feed")
    receipt = Observation(
        "84dc0271-07f0-41ea-856b-510002131b80", ISSUER_CIK, None,
        "issuer_listing", ISSUER_FEED, digest, "2026-10-01T00:00:00Z",
        "2026-10-01T00:00:01Z", "2026-10-01T00:00:02Z", {},
    )
    first = source.publish(_manifest(FIRST, None, "2026-10-01T00:00:00Z",
                                     "2026-10-01T00:00:03Z", 1), [receipt])
    archive1 = tmp_path / "first.tar.gz"
    _snapshot(source.root, archive1)
    unpacked1 = tmp_path / "unpacked1"
    result1 = _unpack(archive1, unpacked1)
    assert result1.returncode == 0, result1.stderr
    first_bytes = (unpacked1 / "runs" / f"{FIRST}.json").read_bytes()
    offsite = tmp_path / "offsite"
    assert _stage(unpacked1, offsite)["added_files"] == 3

    source.publish(_manifest(SECOND, first, "2026-10-01T00:15:00Z",
                             "2026-10-01T00:15:03Z", 0), [])
    archive2 = tmp_path / "second.tar.gz"
    _snapshot(source.root, archive2)
    unpacked2 = tmp_path / "unpacked2"
    result2 = _unpack(archive2, unpacked2)
    assert result2.returncode == 0, result2.stderr
    one, two = json.loads(result1.stdout), json.loads(result2.stdout)
    assert one["completed_runs"] == 1 and two["completed_runs"] == 2
    assert (unpacked2 / "runs" / f"{FIRST}.json").read_bytes() == first_bytes
    assert two["head_sha256"] == source.verify()[-1]["sha256"]
    assert _stage(unpacked2, offsite)["added_files"] == 1
    assert (offsite / "runs" / f"{FIRST}.json").read_bytes() == first_bytes
    assert _inspect(offsite)["inventory_sha256"] == two["inventory_sha256"]

    # A changed old run is neither an acceptable server snapshot nor an update
    # to the off-server append-only copy.
    (source.root / "runs" / f"{FIRST}.json").write_bytes(first_bytes + b" ")
    tampered = tmp_path / "tampered.tar.gz"
    _snapshot(source.root, tampered)
    result_bad = _unpack(tampered, tmp_path / "tampered-unpack")
    assert result_bad.returncode == 2
    assert (offsite / "runs" / f"{FIRST}.json").read_bytes() == first_bytes


def test_snapshot_rejects_symlinks_and_unexpected_paths(tmp_path):
    archive = tmp_path / "bad.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        link = tarfile.TarInfo("blobs/" + "a" * 64)
        link.type = tarfile.SYMTYPE
        link.linkname = "/opt/auto-invest/.env"
        bundle.addfile(link)
        secret = tarfile.TarInfo("../../account.env")
        secret.size = 1
        bundle.addfile(secret, io.BytesIO(b"x"))
    result = _unpack(archive, tmp_path / "refused")
    assert result.returncode == 2
    assert not (tmp_path / "account.env").exists()


def test_snapshot_rejects_regulatory_source_even_with_server_run_id(tmp_path):
    source = RunStore(tmp_path / "wrong-source", clock=lambda: "2026-10-01T00:00:05Z")
    digest = source.blobs.put(b"regulatory listing")
    receipt = Observation(
        "84dc0271-07f0-41ea-856b-510002131b80", ISSUER_CIK, None,
        "listing", f"https://data.sec.gov/submissions/CIK{ISSUER_CIK}.json", digest,
        "2026-10-01T00:00:00Z", "2026-10-01T00:00:01Z",
        "2026-10-01T00:00:02Z", {},
    )
    source.publish(_manifest(FIRST, None, "2026-10-01T00:00:00Z",
                             "2026-10-01T00:00:03Z", 1), [receipt])
    archive = tmp_path / "wrong-source.tar.gz"
    _snapshot(source.root, archive)
    assert _unpack(archive, tmp_path / "refused-source").returncode == 2
