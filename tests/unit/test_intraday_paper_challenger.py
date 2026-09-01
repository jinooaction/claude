from __future__ import annotations

import copy
import csv
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import exchange_calendars as xcals
import pytest

from auto_invest.analytics.intraday_paper_challenger import (
    DatasetContractError,
    PreregistrationContractError,
    build_candidate_registry,
    load_intraday_dataset,
    load_preregistration,
    resample_dataset,
    run_intraday_paper_challenger,
    simulate_candidate,
)
from auto_invest.analytics.intraday_paper_challenger_evidence import assess_intraday_evidence

PREREGISTRATION = Path(
    "specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json"
)
SYMBOLS = ("SPY", "QQQ", "IWM", "TLT", "GLD")


def _write_dataset(
    root: Path,
    *,
    session_labels: tuple[str, ...] = ("2024-01-02", "2024-01-03"),
    synthetic: bool = True,
    bad_hash_symbol: str | None = None,
    volume: int = 2_000_000,
) -> tuple[Path, Path]:
    calendar = xcals.get_calendar("XNYS")
    files: dict[str, object] = {}
    for symbol_index, symbol in enumerate(SYMBOLS):
        path = root / f"{symbol}.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["timestamp_utc", "symbol", "open", "high", "low", "close", "volume"])
            rows = 0
            for session_index, label in enumerate(session_labels):
                session_open = calendar.session_open(label).to_pydatetime()
                session_close = calendar.session_close(label).to_pydatetime()
                cursor = session_open
                bar_index = 0
                while cursor < session_close:
                    base = 100 + symbol_index * 5 + session_index + bar_index * 0.03
                    writer.writerow(
                        [
                            cursor.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            symbol,
                            f"{base:.4f}",
                            f"{base + 0.08:.4f}",
                            f"{base - 0.04:.4f}",
                            f"{base + 0.05:.4f}",
                            volume,
                        ]
                    )
                    cursor += timedelta(minutes=5)
                    bar_index += 1
                    rows += 1
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if symbol == bad_hash_symbol:
            digest = "0" * 64
        files[symbol] = {"path": path.name, "sha256": f"sha256:{digest}", "rows": rows}
    manifest = root / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "dataset_id": "fixture-5m-v1",
                "provider": "pytest",
                "retrieved_at_utc": "2026-01-01T00:00:00Z",
                "adjustment_policy": "split-adjusted fixture",
                "base_timeframe_minutes": 5,
                "synthetic": synthetic,
                "files": files,
            }
        ),
        encoding="utf-8",
    )
    return root, manifest


def _mutate_csv_and_refresh_digest(
    root: Path,
    manifest: Path,
    symbol: str,
    mutate: object,
) -> None:
    path = root / f"{symbol}.csv"
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    mutate(rows)
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["files"][symbol]["sha256"] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(payload), encoding="utf-8")


def test_preregistration_has_exact_registry_and_zero_money_boundary() -> None:
    prereg = load_preregistration(PREREGISTRATION)
    registry = build_candidate_registry(prereg)

    assert len(registry) == 18
    assert len({candidate.candidate_id for candidate in registry}) == 18
    assert {candidate.timeframe_minutes for candidate in registry} == {15, 30, 60}
    assert {candidate.family for candidate in registry} == {
        "momentum",
        "opening_range_breakout",
        "vwap_mean_reversion",
    }
    assert all(candidate.strategy_fingerprint.startswith("sha256:") for candidate in registry)
    assert prereg["safety"] == {
        "capital_fraction": 0,
        "live_eligible": False,
        "promotion_allowed": False,
        "orders_submitted": 0,
        "broker_access": False,
        "live_configuration_mutation": False,
    }


def test_preregistration_rejects_post_result_cost_or_candidate_changes(tmp_path: Path) -> None:
    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    payload["cost_models"]["base"]["commission_bps_per_side"] = 0
    changed_cost = tmp_path / "changed-cost.json"
    changed_cost.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PreregistrationContractError, match="cost model"):
        load_preregistration(changed_cost)

    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    payload["candidates"][0]["parameters"]["lookback_bars"] = 99
    changed_candidate = tmp_path / "changed-candidate.json"
    changed_candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PreregistrationContractError, match="parameters"):
        load_preregistration(changed_candidate)

    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    payload["acceptance"]["confirmation_annualized_sharpe_min"] = 0
    changed_gate = tmp_path / "changed-gate.json"
    changed_gate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PreregistrationContractError, match="acceptance"):
        load_preregistration(changed_gate)


def test_manifest_digest_mismatch_fails_before_strategy_math(tmp_path: Path) -> None:
    bars_dir, manifest = _write_dataset(tmp_path, bad_hash_symbol="SPY")
    prereg = load_preregistration(PREREGISTRATION)

    with pytest.raises(DatasetContractError, match="sha256"):
        load_intraday_dataset(bars_dir, manifest, prereg)


@pytest.mark.parametrize(
    ("column", "value", "match"),
    [
        (1, "QQQ", "symbol mismatch"),
        (4, "999", "OHLC relationship"),
        (6, "0", "volume must be positive"),
        (0, "2024-01-02T00:00:00Z", "outside XNYS regular session"),
    ],
)
def test_csv_contract_rejects_symbol_ohlcv_and_session_corruption(
    tmp_path: Path,
    column: int,
    value: str,
    match: str,
) -> None:
    bars_dir, manifest = _write_dataset(tmp_path, session_labels=("2024-01-02",))

    def mutate(rows: list[list[str]]) -> None:
        rows[1][column] = value

    _mutate_csv_and_refresh_digest(bars_dir, manifest, "SPY", mutate)

    with pytest.raises(DatasetContractError, match=match):
        load_intraday_dataset(bars_dir, manifest, load_preregistration(PREREGISTRATION))


def test_manifest_row_count_mismatch_is_rejected(tmp_path: Path) -> None:
    bars_dir, manifest = _write_dataset(tmp_path, session_labels=("2024-01-02",))
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["files"]["SPY"]["rows"] += 1
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DatasetContractError, match="row count"):
        load_intraday_dataset(bars_dir, manifest, load_preregistration(PREREGISTRATION))


def test_manifest_missing_required_symbol_is_rejected(tmp_path: Path) -> None:
    bars_dir, manifest = _write_dataset(tmp_path, session_labels=("2024-01-02",))
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    del payload["files"]["GLD"]
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DatasetContractError, match="all five"):
        load_intraday_dataset(bars_dir, manifest, load_preregistration(PREREGISTRATION))


def test_resampling_is_anchored_to_open_and_final_sixty_minute_bar_is_not_entry_eligible(
    tmp_path: Path,
) -> None:
    bars_dir, manifest = _write_dataset(tmp_path, session_labels=("2024-01-02",))
    prereg = load_preregistration(PREREGISTRATION)
    dataset = load_intraday_dataset(bars_dir, manifest, prereg)

    resampled = resample_dataset(dataset, 60)
    bars = resampled["SPY"][dataset.sessions[0]]

    assert len(bars) == 7
    assert bars[0].base_bar_count == 12
    assert bars[-1].base_bar_count == 6
    assert bars[-1].complete is False
    assert bars[-1].entry_eligible is False


def test_simulation_uses_next_bar_and_stress_cost_is_not_better(tmp_path: Path) -> None:
    bars_dir, manifest = _write_dataset(tmp_path)
    prereg = load_preregistration(PREREGISTRATION)
    dataset = load_intraday_dataset(bars_dir, manifest, prereg)
    candidate = next(
        row
        for row in build_candidate_registry(prereg)
        if row.candidate_id == "intraday-momentum-15m-fast"
    )
    bars = resample_dataset(dataset, 15)

    base = simulate_candidate(candidate, bars, dataset.sessions, prereg, cost_model_name="base")
    stress = simulate_candidate(candidate, bars, dataset.sessions, prereg, cost_model_name="stress")

    buys = [row for row in base.ledger_rows if row["side"] == "BUY" and row["filled_qty"]]
    assert buys

    def parsed(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    assert all(parsed(row["eligible_at_utc"]) >= parsed(row["signal_at_utc"]) for row in buys)
    assert all(parsed(row["filled_at_utc"]) > parsed(row["signal_at_utc"]) for row in buys)
    sells = [row for row in base.ledger_rows if row["side"] == "SELL" and row["filled_qty"]]
    assert sells
    assert all(row["gross_pnl_usd"] is not None for row in sells)
    assert all(row["net_pnl_usd"] is not None for row in sells)
    assert all(row["holding_minutes"] > 0 for row in sells)
    assert all(row["unfilled_qty"] == row["requested_qty"] - row["filled_qty"] for row in sells)
    assert stress.total_net_pnl_usd <= base.total_net_pnl_usd
    assert stress.total_cost_usd >= base.total_cost_usd


def test_all_three_signal_families_create_deterministic_next_bar_orders(
    tmp_path: Path,
) -> None:
    bars_dir, manifest = _write_dataset(tmp_path, session_labels=("2024-01-02",))
    prereg = load_preregistration(PREREGISTRATION)
    dataset = load_intraday_dataset(bars_dir, manifest, prereg)
    original = resample_dataset(dataset, 15)
    depressed: dict[str, dict[object, tuple[object, ...]]] = {}
    for symbol, sessions in original.items():
        depressed[symbol] = {}
        for session, bars in sessions.items():
            changed = list(bars)
            changed[2] = replace(changed[2], low=89.0, close=90.0)
            depressed[symbol][session] = tuple(changed)

    candidates = {
        row.family: row
        for row in build_candidate_registry(prereg)
        if row.variant == "fast" and row.timeframe_minutes == 15
    }
    for family in ("momentum", "opening_range_breakout"):
        result = simulate_candidate(
            candidates[family],
            original,
            dataset.sessions,
            prereg,
            cost_model_name="base",
        )
        assert any(row["side"] == "BUY" and row["filled_qty"] for row in result.ledger_rows)
    mean_reversion = simulate_candidate(
        candidates["vwap_mean_reversion"],
        depressed,
        dataset.sessions,
        prereg,
        cost_model_name="base",
    )
    assert any(row["side"] == "BUY" and row["filled_qty"] for row in mean_reversion.ledger_rows)


def test_volume_participation_records_partial_and_unfilled_orders(tmp_path: Path) -> None:
    prereg = load_preregistration(PREREGISTRATION)
    candidate = next(
        row
        for row in build_candidate_registry(prereg)
        if row.candidate_id == "intraday-momentum-15m-fast"
    )

    partial_dir = tmp_path / "partial"
    partial_dir.mkdir()
    bars_dir, manifest = _write_dataset(
        partial_dir,
        session_labels=("2024-01-02",),
        volume=5_000,
    )
    partial_dataset = load_intraday_dataset(bars_dir, manifest, prereg)
    partial = simulate_candidate(
        candidate,
        resample_dataset(partial_dataset, 15),
        partial_dataset.sessions,
        prereg,
        cost_model_name="base",
    )
    assert any(row["fill_status"] == "PARTIAL" for row in partial.ledger_rows)

    unfilled_dir = tmp_path / "unfilled"
    unfilled_dir.mkdir()
    bars_dir, manifest = _write_dataset(
        unfilled_dir,
        session_labels=("2024-01-02",),
        volume=1,
    )
    unfilled_dataset = load_intraday_dataset(bars_dir, manifest, prereg)
    unfilled = simulate_candidate(
        candidate,
        resample_dataset(unfilled_dataset, 15),
        unfilled_dataset.sessions,
        prereg,
        cost_model_name="base",
    )
    assert any(row["fill_status"] == "UNFILLED" for row in unfilled.ledger_rows)
    assert all(row["filled_qty"] == 0 for row in unfilled.ledger_rows)


def test_short_synthetic_dataset_is_insufficient_and_never_opens_money(tmp_path: Path) -> None:
    bars_dir, manifest = _write_dataset(tmp_path, synthetic=True)
    prereg = load_preregistration(PREREGISTRATION)
    dataset = load_intraday_dataset(bars_dir, manifest, prereg)

    payload, ledger = run_intraday_paper_challenger(
        dataset,
        prereg,
        preregistration_bytes=PREREGISTRATION.read_bytes(),
        code_commit="test-commit",
        generated_at_utc="2026-09-02T00:00:00Z",
    )

    assert payload["decision"]["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert payload["decision"]["passed"] is False
    assert payload["safety"]["capital_fraction"] == 0
    assert payload["safety"]["live_eligible"] is False
    assert payload["safety"]["orders_submitted"] == 0
    assert isinstance(ledger, bytes)


def test_retrieved_at_must_be_utc_and_not_future(tmp_path: Path) -> None:
    bars_dir, manifest = _write_dataset(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["retrieved_at_utc"] = datetime(2099, 1, 1, tzinfo=UTC).isoformat()
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DatasetContractError, match="future"):
        load_intraday_dataset(bars_dir, manifest, load_preregistration(PREREGISTRATION))


def test_complete_non_synthetic_path_evaluates_all_candidates_and_revalidates(
    tmp_path: Path,
) -> None:
    labels = (
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
        "2024-01-08",
        "2024-01-09",
    )
    bars_dir, manifest = _write_dataset(
        tmp_path,
        session_labels=labels,
        synthetic=False,
    )
    prereg = copy.deepcopy(load_preregistration(PREREGISTRATION))
    prereg["time_split"].update(
        {
            "minimum_total_sessions": 6,
            "minimum_development_sessions": 2,
            "block_sessions": 2,
            "confirmation_sessions": 2,
            "development_pbo_segments": 2,
        }
    )
    prereg["minimum_evidence"].update(
        {"minimum_total_sessions": 6, "minimum_base_cost_closed_trades": 1}
    )
    preregistration_bytes = json.dumps(
        prereg,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    dataset = load_intraday_dataset(bars_dir, manifest, prereg)

    payload, ledger = run_intraday_paper_challenger(
        dataset,
        prereg,
        preregistration_bytes=preregistration_bytes,
        code_commit="test-complete-path",
        generated_at_utc="2026-09-02T00:00:00Z",
    )
    assessment = assess_intraday_evidence(
        payload,
        prereg,
        preregistration_bytes=preregistration_bytes,
        ledger_bytes=ledger,
    )

    assert len(payload["evaluations"]) == 18
    assert payload["selection"]["selected_candidate_id"] is not None
    assert payload["decision"]["verdict"] == "NO_INTRADAY_EDGE"
    selected = next(
        row
        for row in payload["evaluations"]
        if row["candidate_id"] == payload["selection"]["selected_candidate_id"]
    )
    assert selected["base"]["development"]["session_count"] == 2
    assert selected["base"]["block"]["session_count"] == 2
    assert selected["base"]["confirmation"]["session_count"] == 2
    assert assessment.valid is True
    assert assessment.capital_eligible is False
