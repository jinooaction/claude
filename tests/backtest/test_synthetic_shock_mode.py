"""T018 — synthetic-shock named-dataset replay end-to-end (Phase 3 / US1).

Drives ``auto_invest.backtest.engine.run_backtest`` in synthetic-shock
mode against the spec-007 hardened-canary entry point.

Two arms:

* **Known-good rule** (comment-only edit of a previously-promoted rule
  template) → expect a deterministic, frozen per-day report matching
  ``tests/backtest/fixtures/synthetic_shock_v1/golden.json``.
* **Deliberately-broken rule** (per-trade cap raised 100×) → expect
  zero fills landing; every order proposal must be rejected by the
  K1 risk gate without ever calling ``BacktestBroker.submit_order``.

Per tasks.md T018 + T068 (the wall-clock guard is folded into this same
test rather than living in a separate file, per the analyze-boost note
in HANDOFF-008.md).

This file is written BEFORE T019..T022 land, so the imports at module
top will ``ImportError``. That is the red signal. Once T022 / T041 land
and the fixture pair (``ohlcv.json`` + ``golden.json``) is checked in
alongside the engine implementation, the tests will exercise real code.
"""

from __future__ import annotations

import json
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from auto_invest.backtest.engine import run_backtest

from auto_invest.backtest.config import BacktestConfig, NamedDataset
from auto_invest.backtest.errors import BacktestError

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "synthetic_shock_v1"
GOLDEN_PATH = FIXTURE_ROOT / "golden.json"
OHLCV_PATH = FIXTURE_ROOT / "ohlcv.json"  # per-symbol daily bars covering shocks + warmup

EXPECTED_SHOCK_DATES = (
    date(2020, 3, 12),
    date(2020, 4, 20),
    date(2024, 8, 5),
    date(2026, 3, 20),
)


# ---------------------------------------------------------------- fixtures


def _known_good_rules_toml() -> str:
    """A previously-promoted rule template — comment-only edits welcome.

    Cap shape mirrors the sample-canary fixture used by spec 001. The
    point of US1 is "comment-only edit of a previously-promoted rule
    must pass synthetic-shock cleanly"; we use this rule template as
    the previously-promoted baseline.
    """
    return """
[caps]
per_trade_pct                  = 5.0
per_symbol_pct                 = 20.0
global_exposure_pct            = 80.0
canary_capital_pct             = 5.0
canary_min_duration_days       = 10
canary_acceptance_drawdown_pct = 3.0

[whitelist]
symbols     = ["AAPL", "MSFT", "SPY"]
accounts    = ["BACKTEST"]
order_types = ["LIMIT"]
sessions    = ["REGULAR"]

[[rules]]
id       = "spy-shock-buy"
symbol   = "SPY"
stage    = "PROMOTED"
priority = 10
enabled  = true

  [rules.trigger]
  kind             = "price"
  direction        = "<="
  threshold        = 540.00
  cooldown_seconds = 600

  [rules.action]
  side        = "BUY"
  order_type  = "LIMIT"
  qty         = 5
  limit_price = "trigger - 0.10"
"""


def _broken_rules_toml() -> str:
    """Same rule with the per-trade cap raised 100× (5.0 → 500.0).

    A 500% cap is impossible under any sane portfolio sizing — every
    proposed order MUST be rejected at the K1 risk gate before the
    BacktestBroker is ever invoked.
    """
    return _known_good_rules_toml().replace(
        "per_trade_pct                  = 5.0",
        "per_trade_pct                  = 500.0",
    )


@pytest.fixture
def known_good_rules(tmp_path: Path) -> Path:
    path = tmp_path / "known_good.toml"
    path.write_text(_known_good_rules_toml())
    return path


@pytest.fixture
def broken_rules(tmp_path: Path) -> Path:
    path = tmp_path / "broken.toml"
    path.write_text(_broken_rules_toml())
    return path


@pytest.fixture
def synthetic_ohlcv_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Pre-populate a local OHLCV cache under tmp_path/data/ohlcv/.

    The engine MUST NOT reach the network mid-replay (FR-B09). Routing
    the cache to ``tmp_path`` and pre-loading the bars guarantees that.
    The actual cache shape lives in T034; for now we point at the
    fixture JSON that T022's implementation will hydrate into the
    cache.
    """
    if not OHLCV_PATH.exists():
        pytest.skip(
            f"OHLCV fixture not present yet at {OHLCV_PATH}; "
            "will be checked in alongside T022 implementation"
        )
    cache_root = tmp_path / "data" / "ohlcv"
    cache_root.mkdir(parents=True, exist_ok=True)
    bars_by_symbol = json.loads(OHLCV_PATH.read_text())
    for symbol, bars in bars_by_symbol.items():
        vendor_dir = cache_root / "yfinance"
        vendor_dir.mkdir(parents=True, exist_ok=True)
        (vendor_dir / f"{symbol}.json").write_text(json.dumps(bars, indent=2))
    monkeypatch.setenv("AUTO_INVEST_OHLCV_CACHE_ROOT", str(cache_root))
    return cache_root


@pytest.fixture
def synthetic_dataset_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the engine at a tmp copy of ``synthetic_shock_v1.json``.

    Production runs read from ``data/ohlcv/datasets/``. For the test we
    write a tmp copy and route the loader at it so the test passes
    even before T020 lands the real file on disk.
    """
    datasets_root = tmp_path / "data" / "ohlcv" / "datasets"
    datasets_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "name": "synthetic_shock_v1",
        "frozen_at_utc": "2026-05-07T00:00:00Z",
        "dates": [d.isoformat() for d in EXPECTED_SHOCK_DATES],
        "rationale": {
            d.isoformat(): f"shock-day rationale for {d.isoformat()}" for d in EXPECTED_SHOCK_DATES
        },
        "constitutional_tier": "L4",
        "mutation_policy": "Operator-only.",
    }
    target = datasets_root / "synthetic_shock_v1.json"
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    monkeypatch.setenv("AUTO_INVEST_NAMED_DATASETS_ROOT", str(datasets_root))
    return target


# ---------------------------------------------------------------- known-good golden


def test_synthetic_shock_known_good_rule_matches_golden(
    known_good_rules: Path,
    synthetic_ohlcv_cache: Path,
    synthetic_dataset_manifest: Path,
    tmp_path: Path,
):
    """US1 acceptance: a previously-promoted rule replays without surprise.

    Compares ``report.json`` byte-by-byte against the frozen golden
    fixture, excluding only the run/run_id/timestamp fields per the
    FR-B12 byte-identity contract.

    T068 wall-clock guard: < 30 s end-to-end (local cache only — no
    vendor latency in the budget). Per SC-B05.
    """
    if not GOLDEN_PATH.exists():
        pytest.skip(
            f"golden fixture not present yet at {GOLDEN_PATH}; "
            "will be checked in alongside T022 implementation"
        )

    config = BacktestConfig(
        rule_set_path=known_good_rules,
        vendor="yfinance",
        window=NamedDataset(name="synthetic_shock_v1"),
        symbols=frozenset({"SPY"}),
        output_root=tmp_path / "data" / "backtests",
    )

    start = time.perf_counter()
    result = run_backtest(config)
    elapsed = time.perf_counter() - start

    # T068 / SC-B05 wall-clock guard.
    assert elapsed < 30.0, f"synthetic-shock replay took {elapsed:.2f}s; budget is 30s"

    report_path = Path(result.artifact_dir) / "report.json"
    assert report_path.exists()
    actual = json.loads(report_path.read_text())
    golden = json.loads(GOLDEN_PATH.read_text())

    # Drop fields excluded from the FR-B12 byte-identity contract.
    for excluded in ("run_id",):
        actual.pop(excluded, None)
        golden.pop(excluded, None)

    assert actual == golden, (
        "synthetic-shock known-good replay drifted from the frozen golden. "
        "If the engine logic intentionally changed, regenerate "
        f"{GOLDEN_PATH} and commit the diff as part of the relevant task."
    )


# ---------------------------------------------------------------- broken-rule rejection


def test_synthetic_shock_broken_rule_yields_zero_fills(
    broken_rules: Path,
    synthetic_ohlcv_cache: Path,
    synthetic_dataset_manifest: Path,
    tmp_path: Path,
):
    """US1 acceptance: a deliberately-broken rule produces ZERO fills.

    A per-trade cap of 500 % is impossible under K1. Every order
    proposal must be rejected at the gate; the BacktestBroker must
    never receive a ``submit_order`` call.

    The engine MUST still complete the run (no exception raised) — the
    rejections are a normal operational outcome, not a runtime error.
    The audit log shows a ``BACKTEST_COMPLETED`` event whose payload
    reports ``gate_rejections_count > 0`` and ``fills_count == 0``.
    """
    config = BacktestConfig(
        rule_set_path=broken_rules,
        vendor="yfinance",
        window=NamedDataset(name="synthetic_shock_v1"),
        symbols=frozenset({"SPY"}),
        output_root=tmp_path / "data" / "backtests",
    )

    result = run_backtest(config)

    report_path = Path(result.artifact_dir) / "report.json"
    report = json.loads(report_path.read_text())

    assert report["fills_count_total"] == 0, (
        "broken rule somehow produced fills — K1 gate is not protecting the run"
    )
    assert report["gate_rejections_total"] > 0, (
        "broken rule produced no rejections — proposals never reached the gate"
    )
    # 100% gate rejection rate: every order proposal hit the gate and was rejected.
    # No SimulatedFill row should carry gate_decision="allow".
    fills_path = Path(result.artifact_dir) / "fills.csv"
    if fills_path.exists():
        # Per data-model.md the fills.csv is per-fill; with zero fills the
        # file is allowed to be header-only. If present, every row's
        # gate_decision MUST be "reject".
        lines = fills_path.read_text().splitlines()
        if len(lines) > 1:
            header = lines[0].split(",")
            gate_idx = header.index("gate_decision")
            for row in lines[1:]:
                cells = row.split(",")
                assert cells[gate_idx] == "reject", (
                    f"broken rule produced an allowed fill row: {row}"
                )

    # Verdict is unambiguous: a strategy that places no orders does
    # not promote (total return is 0 by construction so the gate-floor
    # threshold may or may not pass, but at minimum the verdict must
    # be recorded).
    verdict = report["verdict"]
    assert isinstance(verdict["promote_eligible"], bool)
    assert isinstance(verdict["reasons"], list)
    assert len(verdict["reasons"]) >= 1


# ---------------------------------------------------------------- mutual exclusion


def test_synthetic_shock_payload_sets_named_dataset_not_window(
    known_good_rules: Path,
    synthetic_ohlcv_cache: Path,
    synthetic_dataset_manifest: Path,
    tmp_path: Path,
):
    """FR-B17 invariant: synthetic-shock runs set named_dataset, never window_*.

    Spec 008 T023 says: ``BACKTEST_STARTED`` payload's ``named_dataset``
    field is correctly populated when running in synthetic-shock mode
    (mutually exclusive with ``window_start`` / ``window_end``).
    """
    config = BacktestConfig(
        rule_set_path=known_good_rules,
        vendor="yfinance",
        window=NamedDataset(name="synthetic_shock_v1"),
        symbols=frozenset({"SPY"}),
        output_root=tmp_path / "data" / "backtests",
    )

    result = run_backtest(config)

    audit_events_path = Path(result.artifact_dir) / "audit-events.json"
    events = json.loads(audit_events_path.read_text())
    started = [e for e in events if e["event_type"] == "BACKTEST_STARTED"]
    assert len(started) == 1, f"expected exactly one BACKTEST_STARTED row, got {len(started)}"
    payload = started[0]["payload"]
    assert payload["named_dataset"] == "synthetic_shock_v1"
    assert payload["window_start"] is None
    assert payload["window_end"] is None


# ---------------------------------------------------------------- determinism smoke


def test_synthetic_shock_replay_is_deterministic(
    known_good_rules: Path,
    synthetic_ohlcv_cache: Path,
    synthetic_dataset_manifest: Path,
    tmp_path: Path,
):
    """FR-B12: two runs with identical inputs produce byte-identical report.json.

    Smoke-tested here for US1; the heavier 100-run check lives in
    tests/backtest/test_engine_determinism.py (T030, US2 phase).
    """
    base = BacktestConfig(
        rule_set_path=known_good_rules,
        vendor="yfinance",
        window=NamedDataset(name="synthetic_shock_v1"),
        symbols=frozenset({"SPY"}),
        output_root=tmp_path / "data" / "backtests",
    )

    r1 = run_backtest(base)
    r2 = run_backtest(base)

    report_1 = json.loads((Path(r1.artifact_dir) / "report.json").read_text())
    report_2 = json.loads((Path(r2.artifact_dir) / "report.json").read_text())

    # run_id is excluded from byte-identity by FR-B12.
    for r in (report_1, report_2):
        r.pop("run_id", None)

    assert report_1 == report_2, (
        "two runs of identical inputs diverged — determinism floor breached"
    )


# ---------------------------------------------------------------- engine error path


def test_synthetic_shock_unknown_dataset_raises_before_started(
    known_good_rules: Path,
    synthetic_ohlcv_cache: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Unknown named-dataset name fails BEFORE BACKTEST_STARTED is emitted.

    Pre-validation failures must not leave half-recorded audit rows
    (FR-B16 — emit either zero or a started+terminal pair, never just
    started).
    """
    empty_datasets_root = tmp_path / "empty"
    empty_datasets_root.mkdir()
    monkeypatch.setenv("AUTO_INVEST_NAMED_DATASETS_ROOT", str(empty_datasets_root))

    config = BacktestConfig(
        rule_set_path=known_good_rules,
        vendor="yfinance",
        window=NamedDataset(name="synthetic_shock_v1"),
        symbols=frozenset({"SPY"}),
        output_root=tmp_path / "data" / "backtests",
    )

    with pytest.raises(BacktestError):
        run_backtest(config)


# ---------------------------------------------------------------- supporting type


def test_run_backtest_returns_result_with_artifact_dir():
    """Smoke check the public return type the spec 007 harness consumes."""
    # Signature surface: run_backtest returns an object exposing
    # ``artifact_dir: str | Path`` and ``run_id: str`` (per R-9 dual entry).
    import inspect

    sig = inspect.signature(run_backtest)
    assert "config" in sig.parameters or list(sig.parameters)[0] == "config"
    # The actual return-type class is decided at T041; this is a
    # placeholder assertion that reminds us to verify a concrete
    # surface exists when the implementation lands.
    assert sig.return_annotation is not inspect.Signature.empty, (
        "run_backtest must declare a return annotation so spec 007's "
        "harness can program against a stable type"
    )


_ = Decimal  # silence unused-import lint until the test arms reference Decimal
