"""T016 — named-dataset manifest tests (Phase 3 / US1).

Drives ``auto_invest.backtest.named_dataset.load`` against the canonical
``synthetic_shock_v1`` manifest under ``data/ohlcv/datasets/``.

This test is written BEFORE T019 (loader) and T020 (the manifest JSON
itself) land, so it MUST fail today. Once those tasks land the test
turns green and is the regression surface for FR-B18 / FR-B19 / FR-B20.

Scope per spec 008 tasks.md::

    T016 [P] [US1] Test tests/backtest/test_named_dataset.py:
      - load data/ohlcv/datasets/synthetic_shock_v1.json
      - assert membership = {2020-03-12, 2020-04-20, 2024-08-05, 2026-03-20}
      - assert schema_version=1, constitutional_tier="L4"
      - mutate a date and assert the loader rejects with
        OhlcvDataQualityError when the manifest's content hash drifts
        mid-run.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from auto_invest.backtest.named_dataset import NamedDatasetManifest, load

from auto_invest.backtest.errors import OhlcvDataQualityError

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_DATASETS_ROOT = REPO_ROOT / "data" / "ohlcv" / "datasets"

EXPECTED_DATES = (
    date(2020, 3, 12),
    date(2020, 4, 20),
    date(2024, 8, 5),
    date(2026, 3, 20),
)


# --------------------------------------------------------------- helpers


def _v1_manifest_dict() -> dict[str, object]:
    """Return the canonical v1 manifest content as a Python dict.

    Mirrors ``contracts/named-dataset.md`` §"v1 frozen content" verbatim.
    Used by tmp-path tests so they do not depend on T020 having landed.
    """
    return {
        "schema_version": 1,
        "name": "synthetic_shock_v1",
        "frozen_at_utc": "2026-05-07T00:00:00Z",
        "dates": ["2020-03-12", "2020-04-20", "2024-08-05", "2026-03-20"],
        "rationale": {
            "2020-03-12": "COVID circuit breakers (limit-down halts).",
            "2020-04-20": (
                "Negative oil futures — sanity check that limit-order-only "
                "enforcement holds when prices go through zero."
            ),
            "2024-08-05": ("Yen-carry unwind — global equity drawdown with cross-asset spillover."),
            "2026-03-20": (
                "Most recent quarterly OPEX at freeze time (third Friday of March 2026)."
            ),
        },
        "constitutional_tier": "L4",
        "mutation_policy": (
            "Operator-only. Subsequent quarterly OPEX days do NOT auto-roll "
            "into this dataset. Adding or removing a date is L4 per spec 005 "
            "(affects the safety surface). The engine refuses to silently "
            "mutate this file."
        ),
    }


def _write_manifest(root: Path, name: str, content: dict[str, object]) -> Path:
    target = root / "ohlcv" / "datasets" / f"{name}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(content, indent=2, sort_keys=True) + "\n")
    return target


# --------------------------------------------------------------- canonical-file tests


@pytest.mark.skipif(
    not (REAL_DATASETS_ROOT / "synthetic_shock_v1.json").exists(),
    reason="T020 has not landed yet; skipping the canonical-file assertions",
)
def test_load_canonical_synthetic_shock_v1_membership():
    """The real ``data/ohlcv/datasets/synthetic_shock_v1.json`` matches v1."""
    manifest = load("synthetic_shock_v1")
    assert isinstance(manifest, NamedDatasetManifest)
    assert manifest.name == "synthetic_shock_v1"
    assert manifest.schema_version == 1
    assert manifest.constitutional_tier == "L4"
    assert tuple(manifest.dates) == EXPECTED_DATES
    # rationale entries cover every listed date, no extras
    assert set(manifest.rationale) == {d.isoformat() for d in EXPECTED_DATES}


# --------------------------------------------------------------- tmp-path tests
# These exercise the loader API even before T020 lands.


def test_load_from_tmp_root_returns_frozen_manifest(tmp_path: Path):
    _write_manifest(tmp_path, "synthetic_shock_v1", _v1_manifest_dict())
    manifest = load("synthetic_shock_v1", root=tmp_path / "ohlcv" / "datasets")

    assert isinstance(manifest, NamedDatasetManifest)
    assert manifest.schema_version == 1
    assert manifest.constitutional_tier == "L4"
    assert tuple(manifest.dates) == EXPECTED_DATES

    # The returned model is frozen (pydantic ConfigDict(frozen=True)) so
    # the canary harness cannot mutate the in-memory view after load.
    with pytest.raises((TypeError, ValueError)):
        manifest.dates = []  # type: ignore[misc]


def test_loader_records_content_hash(tmp_path: Path):
    _write_manifest(tmp_path, "synthetic_shock_v1", _v1_manifest_dict())
    m1 = load("synthetic_shock_v1", root=tmp_path / "ohlcv" / "datasets")
    m2 = load("synthetic_shock_v1", root=tmp_path / "ohlcv" / "datasets")

    # 64-char lowercase hex sha256.
    assert isinstance(m1.content_hash, str)
    assert len(m1.content_hash) == 64
    assert all(c in "0123456789abcdef" for c in m1.content_hash)
    # Same file content => same hash (FR-B19 reproducibility floor).
    assert m1.content_hash == m2.content_hash


def test_loader_rejects_drift_when_expected_hash_supplied(tmp_path: Path):
    """FR-B19 / FR-B20: mutating a date mid-run is detected and rejected."""
    _write_manifest(tmp_path, "synthetic_shock_v1", _v1_manifest_dict())
    root = tmp_path / "ohlcv" / "datasets"
    first = load("synthetic_shock_v1", root=root)

    # Operator (or attacker) mutates a date AFTER the run captured the
    # expected hash. The engine's mid-run re-load MUST fail closed.
    mutated = _v1_manifest_dict()
    mutated["dates"] = [  # one date shifted by a day
        "2020-03-12",
        "2020-04-20",
        "2024-08-05",
        "2026-03-19",  # was 2026-03-20
    ]
    # rationale must stay key-aligned with `dates` (schema invariant), so
    # we rename the rationale key too — otherwise the loader's schema
    # check fires before the drift check and obscures the test signal.
    mutated["rationale"] = {
        "2020-03-12": _v1_manifest_dict()["rationale"]["2020-03-12"],
        "2020-04-20": _v1_manifest_dict()["rationale"]["2020-04-20"],
        "2024-08-05": _v1_manifest_dict()["rationale"]["2024-08-05"],
        "2026-03-19": "drift-test rationale (must not be accepted silently)",
    }
    _write_manifest(tmp_path, "synthetic_shock_v1", mutated)

    with pytest.raises(OhlcvDataQualityError):
        load(
            "synthetic_shock_v1",
            root=root,
            expected_content_hash=first.content_hash,
        )

    # And the second load WITHOUT an expected hash succeeds (it is the
    # operator's choice when to enforce; the engine's pre-flight does
    # enforce — see T021 / T022).
    second = load("synthetic_shock_v1", root=root)
    assert second.content_hash != first.content_hash


def test_loader_rejects_unknown_dataset(tmp_path: Path):
    """Missing file => OhlcvDataQualityError, not a bare FileNotFoundError."""
    with pytest.raises(OhlcvDataQualityError):
        load("does_not_exist", root=tmp_path / "ohlcv" / "datasets")


def test_loader_rejects_wrong_schema_version(tmp_path: Path):
    """schema_version != 1 is a breaking change and must be rejected."""
    bad = _v1_manifest_dict()
    bad["schema_version"] = 2
    _write_manifest(tmp_path, "synthetic_shock_v1", bad)
    with pytest.raises(OhlcvDataQualityError):
        load("synthetic_shock_v1", root=tmp_path / "ohlcv" / "datasets")


def test_loader_rejects_wrong_constitutional_tier(tmp_path: Path):
    """constitutional_tier must be ``"L4"`` for synthetic-shock datasets."""
    bad = _v1_manifest_dict()
    bad["constitutional_tier"] = "L3"
    _write_manifest(tmp_path, "synthetic_shock_v1", bad)
    with pytest.raises(OhlcvDataQualityError):
        load("synthetic_shock_v1", root=tmp_path / "ohlcv" / "datasets")


def test_loader_rejects_rationale_key_mismatch(tmp_path: Path):
    """rationale keys must equal the entries in ``dates``."""
    bad = _v1_manifest_dict()
    bad["rationale"] = {"2020-03-12": "only one key — missing the others"}
    _write_manifest(tmp_path, "synthetic_shock_v1", bad)
    with pytest.raises(OhlcvDataQualityError):
        load("synthetic_shock_v1", root=tmp_path / "ohlcv" / "datasets")


def test_loader_rejects_filename_mismatch(tmp_path: Path):
    """``name`` field must equal the file's basename."""
    bad = _v1_manifest_dict()
    bad["name"] = "synthetic_shock_v2"  # filename is still v1
    _write_manifest(tmp_path, "synthetic_shock_v1", bad)
    with pytest.raises(OhlcvDataQualityError):
        load("synthetic_shock_v1", root=tmp_path / "ohlcv" / "datasets")
