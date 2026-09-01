"""Deterministic, no-order intraday ETF paper challenger (spec 177).

This module deliberately has no broker, database, workflow, or network imports. It consumes
operator-supplied five-minute CSV files, evaluates a frozen research family, and emits diagnostic
evidence that can never authorize capital.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import exchange_calendars as xcals
import numpy as np
import pandas as pd

from auto_invest.analytics.backtest_overfitting import (
    annualized_sharpe,
    deflated_sharpe_from_trials,
    probabilistic_sharpe,
    probability_of_backtest_overfitting,
)
from auto_invest.backtest.metrics import max_drawdown_pct, sharpe_ratio, win_loss_stats

SCHEMA_VERSION = "1.0"
GATE_VERSION = "intraday-paper-v1"
FAMILY_ID = "intraday-etf-long-flat-diagnostic-v1"
VERDICTS = {"PAPER_CHALLENGER", "NO_INTRADAY_EDGE", "INSUFFICIENT_EVIDENCE"}
EXPECTED_UNIVERSE = ("SPY", "QQQ", "IWM", "TLT", "GLD")
EXPECTED_TIMEFRAMES = (15, 30, 60)
EXPECTED_FAMILIES = {"momentum", "opening_range_breakout", "vwap_mean_reversion"}
EXPECTED_SAFETY = {
    "capital_fraction": 0,
    "live_eligible": False,
    "promotion_allowed": False,
    "orders_submitted": 0,
    "broker_access": False,
    "live_configuration_mutation": False,
}
_CSV_FIELDS = ("timestamp_utc", "symbol", "open", "high", "low", "close", "volume")
_CALENDAR = xcals.get_calendar("XNYS")
_EXPECTED_SESSION = {
    "calendar": "XNYS",
    "regular_hours_only": True,
    "overnight_positions": False,
    "entry_on_partial_final_bar": False,
}
_EXPECTED_PORTFOLIO = {
    "initial_capital_usd": 100000,
    "per_symbol_cap_fraction": 0.2,
    "global_exposure_cap_fraction": 0.8,
    "whole_shares_only": True,
    "shorting": False,
    "margin": False,
    "leverage": False,
}
_EXPECTED_COST_MODELS = {
    "base": {
        "commission_bps_per_side": 25,
        "spread_bps_per_side": 1,
        "slippage_bps_per_side": 5,
        "max_volume_participation": 0.01,
    },
    "stress": {
        "commission_bps_per_side": 25,
        "spread_bps_per_side": 3,
        "slippage_bps_per_side": 12,
        "max_volume_participation": 0.0025,
    },
}
_EXPECTED_CANDIDATE_PARAMETERS = {
    ("momentum", "fast"): {"lookback_bars": 2, "hold_bars": 2, "threshold_bps": 0},
    ("momentum", "slow"): {"lookback_bars": 4, "hold_bars": 4, "threshold_bps": 5},
    ("opening_range_breakout", "fast"): {
        "range_bars": 1,
        "breakout_buffer_bps": 0,
    },
    ("opening_range_breakout", "slow"): {
        "range_bars": 2,
        "breakout_buffer_bps": 5,
    },
    ("vwap_mean_reversion", "fast"): {"deviation_bps": 50, "hold_bars": 2},
    ("vwap_mean_reversion", "slow"): {"deviation_bps": 100, "hold_bars": 4},
}
_EXPECTED_SELECTION = {
    "metric": "development_base_cost_annualized_sharpe",
    "tie_breakers": ["lower_max_drawdown", "lower_turnover", "candidate_id"],
    "holdouts_used_for_selection": False,
}
_EXPECTED_ACCEPTANCE = {
    "block_net_return_gt": 0,
    "confirmation_net_return_gt": 0,
    "confirmation_annualized_sharpe_min": 1.0,
    "confirmation_psr_min": 0.95,
    "selected_dsr_min": 0.95,
    "development_pbo_max": 0.25,
    "confirmation_max_drawdown_pct_max": 15.0,
    "confirmation_profit_factor_min": 1.1,
    "confirmation_positive_quarter_fraction_min": 0.5,
    "max_single_symbol_positive_contribution_fraction": 0.5,
    "max_top_five_trade_positive_contribution_fraction": 0.35,
    "stress_confirmation_net_return_gt": 0,
}
_EXPECTED_FAMILY_RULES = {
    "momentum": {
        "signal": "closed_bar_return_over_lookback_at_or_above_threshold",
        "exit": "maximum_hold_bars_or_session_close",
    },
    "opening_range_breakout": {
        "signal": "closed_bar_close_above_first_n_bar_high_plus_buffer",
        "exit": "session_close",
        "maximum_entries_per_symbol_session": 1,
    },
    "vwap_mean_reversion": {
        "signal": "closed_bar_close_below_cumulative_vwap_by_threshold",
        "exit": "close_at_or_above_vwap_or_maximum_hold_bars_or_session_close",
    },
}
_EXPECTED_FORWARD_OBSERVATION = {
    "required_sessions": 60,
    "automatic_start": False,
    "automatic_live_promotion": False,
}


class PreregistrationContractError(ValueError):
    """The frozen research policy is malformed or incomplete."""


class DatasetContractError(ValueError):
    """The supplied bytes contradict their manifest or bar contract."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _finite_float(value: object, *, field: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise DatasetContractError(f"{field} must be numeric") from exc
    if not math.isfinite(parsed):
        raise DatasetContractError(f"{field} must be finite")
    return parsed


def _parse_utc(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise DatasetContractError(f"{field} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DatasetContractError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise DatasetContractError(f"{field} must be timezone-aware")
    return parsed.astimezone(UTC)


@dataclass(frozen=True)
class IntradayCandidate:
    candidate_id: str
    family: str
    timeframe_minutes: int
    variant: str
    parameters: dict[str, int | float]
    strategy_fingerprint: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class IntradayBar:
    symbol: str
    timestamp_utc: datetime
    session_date: date
    session_open_utc: datetime
    session_close_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True)
class ResampledBar:
    symbol: str
    session_date: date
    timestamp_utc: datetime
    end_utc: datetime
    timeframe_minutes: int
    bar_index: int
    open: float
    high: float
    low: float
    close: float
    volume: int
    base_bar_count: int
    complete: bool
    entry_eligible: bool


@dataclass(frozen=True)
class IntradayDataset:
    dataset_id: str
    provider: str
    synthetic: bool
    dataset_fingerprint: str
    bars_by_symbol: dict[str, tuple[IntradayBar, ...]]
    sessions: tuple[date, ...]
    quality_reasons: tuple[str, ...]


@dataclass(frozen=True)
class SimulationResult:
    candidate_id: str
    cost_model_name: str
    daily_pnl_usd: dict[date, float]
    trade_records: tuple[dict[str, object], ...]
    ledger_rows: tuple[dict[str, object], ...]
    total_net_pnl_usd: float
    total_cost_usd: float
    turnover_usd: float
    unclosed_quantity: int


def load_preregistration(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreregistrationContractError(f"cannot read preregistration: {path}") from exc
    if not isinstance(payload, dict):
        raise PreregistrationContractError("preregistration root must be an object")
    if (
        payload.get("schema_version") != SCHEMA_VERSION
        or payload.get("gate_version") != GATE_VERSION
        or payload.get("family_id") != FAMILY_ID
        or payload.get("purpose") != "diagnostic_only"
    ):
        raise PreregistrationContractError("preregistration identity mismatch")
    if tuple(payload.get("universe", ())) != EXPECTED_UNIVERSE:
        raise PreregistrationContractError("universe must match the frozen five-symbol order")
    if tuple(payload.get("evaluation_timeframes_minutes", ())) != EXPECTED_TIMEFRAMES:
        raise PreregistrationContractError("timeframes must be 15, 30, and 60 minutes")
    if payload.get("base_timeframe_minutes") != 5:
        raise PreregistrationContractError("base timeframe must be five minutes")
    if payload.get("safety") != EXPECTED_SAFETY:
        raise PreregistrationContractError("zero-money safety contract mismatch")
    if payload.get("session") != _EXPECTED_SESSION:
        raise PreregistrationContractError("session contract mismatch")
    if payload.get("portfolio") != _EXPECTED_PORTFOLIO:
        raise PreregistrationContractError("portfolio contract mismatch")
    if payload.get("cost_models") != _EXPECTED_COST_MODELS:
        raise PreregistrationContractError("cost model contract mismatch")
    time_split = payload.get("time_split")
    if not isinstance(time_split, dict) or time_split != {
        "method": "chronological_tail_holdouts_v1",
        "minimum_total_sessions": 756,
        "minimum_development_sessions": 504,
        "block_sessions": 126,
        "confirmation_sessions": 126,
        "development_pbo_segments": 8,
    }:
        raise PreregistrationContractError("time split contract mismatch")
    if payload.get("minimum_evidence") != {
        "required_symbols": 5,
        "minimum_total_sessions": 756,
        "minimum_base_cost_closed_trades": 200,
    }:
        raise PreregistrationContractError("minimum evidence contract mismatch")
    if payload.get("selection") != _EXPECTED_SELECTION:
        raise PreregistrationContractError("selection contract mismatch")
    if payload.get("acceptance") != _EXPECTED_ACCEPTANCE:
        raise PreregistrationContractError("acceptance contract mismatch")
    if payload.get("family_rules") != _EXPECTED_FAMILY_RULES:
        raise PreregistrationContractError("family rules contract mismatch")
    if payload.get("forward_observation") != _EXPECTED_FORWARD_OBSERVATION:
        raise PreregistrationContractError("forward observation contract mismatch")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 18:
        raise PreregistrationContractError("exactly 18 candidates are required")
    ids: list[str] = []
    combinations: list[tuple[str, int, str]] = []
    for row in candidates:
        if not isinstance(row, dict):
            raise PreregistrationContractError("candidate rows must be objects")
        candidate_id = row.get("candidate_id")
        family = row.get("family")
        timeframe = row.get("timeframe_minutes")
        variant = row.get("variant")
        parameters = row.get("parameters")
        if (
            not isinstance(candidate_id, str)
            or family not in EXPECTED_FAMILIES
            or timeframe not in EXPECTED_TIMEFRAMES
            or variant not in {"fast", "slow"}
            or not isinstance(parameters, dict)
            or not parameters
        ):
            raise PreregistrationContractError("candidate contract mismatch")
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in parameters.values()
        ):
            raise PreregistrationContractError("candidate parameters must be numeric")
        expected_prefix = {
            "momentum": "momentum",
            "opening_range_breakout": "orb",
            "vwap_mean_reversion": "vwap",
        }[str(family)]
        if candidate_id != f"intraday-{expected_prefix}-{timeframe}m-{variant}":
            raise PreregistrationContractError("candidate ID does not match its frozen identity")
        if parameters != _EXPECTED_CANDIDATE_PARAMETERS[(str(family), str(variant))]:
            raise PreregistrationContractError("candidate parameters differ from frozen version")
        ids.append(candidate_id)
        combinations.append((str(family), int(timeframe), str(variant)))
    if len(set(ids)) != 18 or len(set(combinations)) != 18:
        raise PreregistrationContractError("candidate identities must be unique")
    expected_combinations = {
        (family, timeframe, variant)
        for family in EXPECTED_FAMILIES
        for timeframe in EXPECTED_TIMEFRAMES
        for variant in ("fast", "slow")
    }
    if set(combinations) != expected_combinations:
        raise PreregistrationContractError("candidate grid is incomplete")
    return payload


def build_candidate_registry(preregistration: Mapping[str, Any]) -> tuple[IntradayCandidate, ...]:
    common = {
        "family_id": preregistration["family_id"],
        "universe": preregistration["universe"],
        "session": preregistration["session"],
        "portfolio": preregistration["portfolio"],
        "cost_models": preregistration["cost_models"],
        "family_rules": preregistration["family_rules"],
    }
    registry: list[IntradayCandidate] = []
    for row in preregistration["candidates"]:
        identity = {"common": common, "candidate": row}
        registry.append(
            IntradayCandidate(
                candidate_id=row["candidate_id"],
                family=row["family"],
                timeframe_minutes=int(row["timeframe_minutes"]),
                variant=row["variant"],
                parameters=dict(row["parameters"]),
                strategy_fingerprint=_sha256(_canonical_bytes(identity)),
            )
        )
    return tuple(registry)


def _manifest_object(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetContractError(f"cannot read manifest: {path}") from exc
    if not isinstance(payload, dict):
        raise DatasetContractError("manifest root must be an object")
    return payload, raw


def _session_for_timestamp(moment: datetime) -> tuple[date, datetime, datetime]:
    timestamp = pd.Timestamp(moment)
    if not _CALENDAR.is_open_on_minute(timestamp):
        raise DatasetContractError(f"bar outside XNYS regular session: {moment.isoformat()}")
    try:
        session = _CALENDAR.minute_to_session(timestamp, direction="none")
    except ValueError as exc:
        raise DatasetContractError(
            f"bar cannot be mapped to XNYS session: {moment.isoformat()}"
        ) from exc
    session_open = _CALENDAR.session_open(session).to_pydatetime().astimezone(UTC)
    session_close = _CALENDAR.session_close(session).to_pydatetime().astimezone(UTC)
    if moment < session_open or moment >= session_close:
        raise DatasetContractError(f"bar outside XNYS regular session: {moment.isoformat()}")
    offset = (moment - session_open).total_seconds() / 60.0
    if offset % 5 != 0 or moment.second or moment.microsecond:
        raise DatasetContractError(f"bar is not aligned to five minutes: {moment.isoformat()}")
    return session.date(), session_open, session_close


def _read_symbol_csv(path: Path, symbol: str) -> tuple[tuple[IntradayBar, ...], int]:
    bars: list[IntradayBar] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != _CSV_FIELDS:
                raise DatasetContractError(f"CSV header mismatch: {path.name}")
            previous: datetime | None = None
            for row_number, row in enumerate(reader, start=2):
                moment = _parse_utc(row["timestamp_utc"], field="timestamp_utc")
                if row["symbol"] != symbol:
                    raise DatasetContractError(f"symbol mismatch in {path.name} row {row_number}")
                if previous is not None and moment <= previous:
                    raise DatasetContractError(
                        f"timestamps must be unique and increasing: {path.name}"
                    )
                open_price = _finite_float(row["open"], field="open")
                high = _finite_float(row["high"], field="high")
                low = _finite_float(row["low"], field="low")
                close = _finite_float(row["close"], field="close")
                if min(open_price, high, low, close) <= 0 or not (
                    low <= open_price <= high and low <= close <= high
                ):
                    raise DatasetContractError(f"OHLC relationship invalid in {path.name}")
                try:
                    volume = int(row["volume"])
                except (TypeError, ValueError) as exc:
                    raise DatasetContractError(f"volume must be an integer: {path.name}") from exc
                if volume <= 0:
                    raise DatasetContractError(f"volume must be positive: {path.name}")
                session_date, session_open, session_close = _session_for_timestamp(moment)
                bars.append(
                    IntradayBar(
                        symbol=symbol,
                        timestamp_utc=moment,
                        session_date=session_date,
                        session_open_utc=session_open,
                        session_close_utc=session_close,
                        open=open_price,
                        high=high,
                        low=low,
                        close=close,
                        volume=volume,
                    )
                )
                previous = moment
    except OSError as exc:
        raise DatasetContractError(f"cannot read CSV: {path}") from exc
    return tuple(bars), len(bars)


def _validate_complete_sessions(
    bars_by_symbol: Mapping[str, tuple[IntradayBar, ...]],
) -> tuple[tuple[date, ...], tuple[str, ...]]:
    reasons: list[str] = []
    session_sets: list[set[date]] = []
    for symbol in EXPECTED_UNIVERSE:
        grouped: dict[date, list[IntradayBar]] = defaultdict(list)
        for bar in bars_by_symbol[symbol]:
            grouped[bar.session_date].append(bar)
        complete_sessions: set[date] = set()
        for session_date, rows in grouped.items():
            first = rows[0]
            expected_count = int(
                (first.session_close_utc - first.session_open_utc).total_seconds() // 300
            )
            expected_times = {
                first.session_open_utc + timedelta(minutes=5 * index)
                for index in range(expected_count)
            }
            actual_times = {row.timestamp_utc for row in rows}
            if len(rows) == expected_count and actual_times == expected_times:
                complete_sessions.add(session_date)
            else:
                reasons.append(f"incomplete_session:{symbol}:{session_date.isoformat()}")
        session_sets.append(complete_sessions)
    common = set.intersection(*session_sets) if session_sets else set()
    union = set.union(*session_sets) if session_sets else set()
    if common != union:
        reasons.append("symbol_session_coverage_mismatch")
    return tuple(sorted(common)), tuple(sorted(set(reasons)))


def load_intraday_dataset(
    bars_dir: Path,
    manifest_path: Path,
    preregistration: Mapping[str, Any],
) -> IntradayDataset:
    manifest, manifest_bytes = _manifest_object(manifest_path)
    if (
        manifest.get("schema_version") != "1.0"
        or manifest.get("base_timeframe_minutes") != 5
        or not isinstance(manifest.get("dataset_id"), str)
        or not manifest.get("dataset_id")
        or not isinstance(manifest.get("provider"), str)
        or not manifest.get("provider")
        or not isinstance(manifest.get("adjustment_policy"), str)
        or not manifest.get("adjustment_policy")
        or not isinstance(manifest.get("synthetic"), bool)
    ):
        raise DatasetContractError("manifest identity or metadata mismatch")
    retrieved = _parse_utc(manifest.get("retrieved_at_utc"), field="retrieved_at_utc")
    if retrieved > datetime.now(UTC) + timedelta(minutes=5):
        raise DatasetContractError("retrieved_at_utc cannot be in the future")
    if tuple(preregistration.get("universe", ())) != EXPECTED_UNIVERSE:
        raise DatasetContractError("preregistration universe mismatch")
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != set(EXPECTED_UNIVERSE):
        raise DatasetContractError("manifest must describe all five symbol files")
    bars_by_symbol: dict[str, tuple[IntradayBar, ...]] = {}
    file_identities: list[dict[str, object]] = []
    for symbol in EXPECTED_UNIVERSE:
        entry = files[symbol]
        if not isinstance(entry, dict):
            raise DatasetContractError(f"manifest file entry invalid: {symbol}")
        filename = entry.get("path")
        if (
            not isinstance(filename, str)
            or Path(filename).name != filename
            or filename != f"{symbol}.csv"
        ):
            raise DatasetContractError(f"manifest path invalid: {symbol}")
        path = bars_dir / filename
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise DatasetContractError(f"missing CSV: {filename}") from exc
        digest = _sha256(raw)
        if entry.get("sha256") != digest:
            raise DatasetContractError(f"sha256 mismatch: {symbol}")
        bars, row_count = _read_symbol_csv(path, symbol)
        if entry.get("rows") != row_count:
            raise DatasetContractError(f"row count mismatch: {symbol}")
        bars_by_symbol[symbol] = bars
        file_identities.append({"symbol": symbol, "sha256": digest, "rows": row_count})
    sessions, quality_reasons = _validate_complete_sessions(bars_by_symbol)
    dataset_fingerprint = _sha256(
        _canonical_bytes(
            {
                "manifest_sha256": _sha256(manifest_bytes),
                "files": file_identities,
                "sessions": [value.isoformat() for value in sessions],
            }
        )
    )
    return IntradayDataset(
        dataset_id=manifest["dataset_id"],
        provider=manifest["provider"],
        synthetic=manifest["synthetic"],
        dataset_fingerprint=dataset_fingerprint,
        bars_by_symbol=bars_by_symbol,
        sessions=sessions,
        quality_reasons=quality_reasons,
    )


def resample_dataset(
    dataset: IntradayDataset,
    timeframe_minutes: int,
) -> dict[str, dict[date, tuple[ResampledBar, ...]]]:
    if timeframe_minutes not in EXPECTED_TIMEFRAMES:
        raise ValueError("timeframe must be 15, 30, or 60 minutes")
    expected_base_count = timeframe_minutes // 5
    output: dict[str, dict[date, tuple[ResampledBar, ...]]] = {}
    for symbol in EXPECTED_UNIVERSE:
        grouped: dict[date, list[IntradayBar]] = defaultdict(list)
        for bar in dataset.bars_by_symbol[symbol]:
            if bar.session_date in dataset.sessions:
                grouped[bar.session_date].append(bar)
        session_output: dict[date, tuple[ResampledBar, ...]] = {}
        for session_date in dataset.sessions:
            rows = grouped[session_date]
            buckets: dict[int, list[IntradayBar]] = defaultdict(list)
            for row in rows:
                offset = int((row.timestamp_utc - row.session_open_utc).total_seconds() // 60)
                buckets[offset // timeframe_minutes].append(row)
            max_bucket = max(buckets) if buckets else -1
            aggregated: list[ResampledBar] = []
            for bucket_index in sorted(buckets):
                values = buckets[bucket_index]
                complete = len(values) == expected_base_count
                aggregated.append(
                    ResampledBar(
                        symbol=symbol,
                        session_date=session_date,
                        timestamp_utc=values[0].timestamp_utc,
                        end_utc=values[-1].timestamp_utc + timedelta(minutes=5),
                        timeframe_minutes=timeframe_minutes,
                        bar_index=bucket_index,
                        open=values[0].open,
                        high=max(value.high for value in values),
                        low=min(value.low for value in values),
                        close=values[-1].close,
                        volume=sum(value.volume for value in values),
                        base_bar_count=len(values),
                        complete=complete,
                        entry_eligible=complete and bucket_index < max_bucket,
                    )
                )
            session_output[session_date] = tuple(aggregated)
        output[symbol] = session_output
    return output


def _cumulative_vwap(bars: Sequence[ResampledBar], index: int) -> float:
    selected = bars[: index + 1]
    denominator = sum(row.volume for row in selected)
    if denominator <= 0:
        return 0.0
    numerator = sum(((row.high + row.low + row.close) / 3.0) * row.volume for row in selected)
    return numerator / denominator


def _entry_signal(candidate: IntradayCandidate, bars: Sequence[ResampledBar], index: int) -> bool:
    bar = bars[index]
    params = candidate.parameters
    if not bar.entry_eligible:
        return False
    if candidate.family == "momentum":
        lookback = int(params["lookback_bars"])
        if index < lookback:
            return False
        change_bps = (bar.close / bars[index - lookback].close - 1.0) * 10_000.0
        return change_bps >= float(params["threshold_bps"])
    if candidate.family == "opening_range_breakout":
        range_bars = int(params["range_bars"])
        if index < range_bars:
            return False
        opening_high = max(value.high for value in bars[:range_bars])
        threshold = opening_high * (1.0 + float(params["breakout_buffer_bps"]) / 10_000.0)
        return bar.close > threshold
    if candidate.family == "vwap_mean_reversion":
        vwap = _cumulative_vwap(bars, index)
        threshold = vwap * (1.0 - float(params["deviation_bps"]) / 10_000.0)
        return vwap > 0 and bar.close <= threshold
    raise ValueError(f"unknown family: {candidate.family}")


def _exit_signal(
    candidate: IntradayCandidate,
    bars: Sequence[ResampledBar],
    index: int,
    entry_index: int,
) -> bool:
    if candidate.family == "opening_range_breakout":
        return False
    hold_bars = int(candidate.parameters["hold_bars"])
    if index - entry_index >= hold_bars:
        return True
    if candidate.family == "vwap_mean_reversion":
        return bars[index].close >= _cumulative_vwap(bars, index)
    return False


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _cost_values(
    reference_price: float,
    qty: int,
    side: str,
    model: Mapping[str, Any],
) -> tuple[float, float, float, float]:
    commission = reference_price * qty * float(model["commission_bps_per_side"]) / 10_000.0
    spread = reference_price * qty * float(model["spread_bps_per_side"]) / 10_000.0
    slippage = reference_price * qty * float(model["slippage_bps_per_side"]) / 10_000.0
    adverse_bps = float(model["spread_bps_per_side"]) + float(model["slippage_bps_per_side"])
    direction = 1.0 if side == "BUY" else -1.0
    fill_price = reference_price * (1.0 + direction * adverse_bps / 10_000.0)
    return fill_price, commission, spread, slippage


def simulate_candidate(
    candidate: IntradayCandidate,
    resampled: Mapping[str, Mapping[date, tuple[ResampledBar, ...]]],
    sessions: Sequence[date],
    preregistration: Mapping[str, Any],
    *,
    cost_model_name: str,
) -> SimulationResult:
    cost_model = preregistration["cost_models"].get(cost_model_name)
    if not isinstance(cost_model, Mapping):
        raise ValueError(f"unknown cost model: {cost_model_name}")
    capital = float(preregistration["portfolio"]["initial_capital_usd"])
    symbol_cap = float(preregistration["portfolio"]["per_symbol_cap_fraction"])
    global_cap = float(preregistration["portfolio"]["global_exposure_cap_fraction"])
    allocation = capital * min(symbol_cap, global_cap / len(EXPECTED_UNIVERSE))
    participation = float(cost_model["max_volume_participation"])
    daily_pnl: dict[date, float] = {session: 0.0 for session in sessions}
    ledger: list[dict[str, object]] = []
    trades: list[dict[str, object]] = []
    total_cost = 0.0
    turnover = 0.0
    unclosed_quantity = 0

    for session_date in sessions:
        for symbol in EXPECTED_UNIVERSE:
            bars = resampled[symbol][session_date]
            position_qty = 0
            entry_fill_price = 0.0
            entry_reference_price = 0.0
            entry_commission = 0.0
            entry_index = -1
            pending: tuple[str, datetime, str] | None = None
            entered_once = False
            for index, bar in enumerate(bars):
                if pending is not None:
                    side, signal_at, reason = pending
                    requested_qty = (
                        math.floor(allocation / bar.open) if side == "BUY" else position_qty
                    )
                    participation_qty = math.floor(bar.volume * participation)
                    filled_qty = min(requested_qty, max(0, participation_qty))
                    status = (
                        "UNFILLED"
                        if filled_qty == 0
                        else "FULL"
                        if filled_qty == requested_qty
                        else "PARTIAL"
                    )
                    fill_price, commission, spread, slippage = _cost_values(
                        bar.open, filled_qty, side, cost_model
                    )
                    total_cost += commission + spread + slippage
                    turnover += bar.open * filled_qty
                    row = {
                        "candidate_id": candidate.candidate_id,
                        "cost_model": cost_model_name,
                        "session_date": session_date.isoformat(),
                        "symbol": symbol,
                        "side": side,
                        "signal_at_utc": _iso(signal_at),
                        "eligible_at_utc": _iso(bar.timestamp_utc),
                        "filled_at_utc": (
                            _iso(bar.timestamp_utc + timedelta(microseconds=1))
                            if filled_qty
                            else None
                        ),
                        "requested_qty": requested_qty,
                        "filled_qty": filled_qty,
                        "unfilled_qty": requested_qty - filled_qty,
                        "reference_price": round(bar.open, 8),
                        "fill_price": round(fill_price, 8),
                        "commission_usd": round(commission, 8),
                        "spread_usd": round(spread, 8),
                        "slippage_usd": round(slippage, 8),
                        "gross_pnl_usd": None,
                        "net_pnl_usd": None,
                        "holding_minutes": None,
                        "fill_status": status,
                        "reason": reason if filled_qty else "volume_participation_zero",
                    }
                    if side == "BUY" and filled_qty:
                        position_qty = filled_qty
                        entry_fill_price = fill_price
                        entry_reference_price = bar.open
                        entry_commission = commission
                        entry_index = index
                        entered_once = True
                    elif side == "SELL" and filled_qty:
                        sell_fraction = filled_qty / position_qty if position_qty else 0.0
                        allocated_buy_commission = entry_commission * sell_fraction
                        net_pnl = (
                            (fill_price - entry_fill_price) * filled_qty
                            - allocated_buy_commission
                            - commission
                        )
                        gross_pnl = (bar.open - entry_reference_price) * filled_qty
                        row["gross_pnl_usd"] = round(gross_pnl, 8)
                        row["net_pnl_usd"] = round(net_pnl, 8)
                        row["holding_minutes"] = int(
                            (bar.timestamp_utc - bars[entry_index].timestamp_utc).total_seconds()
                            // 60
                        )
                        daily_pnl[session_date] += net_pnl
                        trades.append(
                            {
                                "candidate_id": candidate.candidate_id,
                                "cost_model": cost_model_name,
                                "session_date": session_date.isoformat(),
                                "symbol": symbol,
                                "qty": filled_qty,
                                "gross_pnl_usd": round(gross_pnl, 8),
                                "net_pnl_usd": round(net_pnl, 8),
                            }
                        )
                        position_qty -= filled_qty
                        entry_commission -= allocated_buy_commission
                        if position_qty == 0:
                            entry_index = -1
                    ledger.append(row)
                    pending = None

                if index >= len(bars) - 1:
                    continue
                if position_qty > 0:
                    must_exit_next = index == len(bars) - 2
                    if must_exit_next or _exit_signal(candidate, bars, index, entry_index):
                        pending = (
                            "SELL",
                            bar.end_utc,
                            "session_close" if must_exit_next else "strategy_exit",
                        )
                elif (
                    pending is None
                    and not (candidate.family == "opening_range_breakout" and entered_once)
                    and _entry_signal(candidate, bars, index)
                ):
                    pending = ("BUY", bar.end_utc, "strategy_entry")
            if position_qty > 0:
                unclosed_quantity += position_qty
                ledger.append(
                    {
                        "candidate_id": candidate.candidate_id,
                        "cost_model": cost_model_name,
                        "session_date": session_date.isoformat(),
                        "symbol": symbol,
                        "side": "SELL",
                        "signal_at_utc": _iso(bars[-1].end_utc),
                        "eligible_at_utc": _iso(bars[-1].end_utc),
                        "filled_at_utc": None,
                        "requested_qty": position_qty,
                        "filled_qty": 0,
                        "unfilled_qty": position_qty,
                        "reference_price": round(bars[-1].close, 8),
                        "fill_price": round(bars[-1].close, 8),
                        "commission_usd": 0.0,
                        "spread_usd": 0.0,
                        "slippage_usd": 0.0,
                        "gross_pnl_usd": None,
                        "net_pnl_usd": None,
                        "holding_minutes": None,
                        "fill_status": "UNFILLED",
                        "reason": "session_close_liquidity_failure",
                    }
                )
    return SimulationResult(
        candidate_id=candidate.candidate_id,
        cost_model_name=cost_model_name,
        daily_pnl_usd=daily_pnl,
        trade_records=tuple(trades),
        ledger_rows=tuple(ledger),
        total_net_pnl_usd=round(sum(daily_pnl.values()), 8),
        total_cost_usd=round(total_cost, 8),
        turnover_usd=round(turnover, 8),
        unclosed_quantity=unclosed_quantity,
    )


def _window_metrics(
    run: SimulationResult,
    sessions: Sequence[date],
    *,
    capital: float,
) -> dict[str, object]:
    selected = set(sessions)
    pnls = [float(run.daily_pnl_usd.get(session, 0.0)) for session in sessions]
    returns = [pnl / capital for pnl in pnls]
    equity = [capital]
    for pnl in pnls:
        equity.append(equity[-1] + pnl)
    trades = [
        row for row in run.trade_records if date.fromisoformat(str(row["session_date"])) in selected
    ]
    trade_pnls = [float(row["net_pnl_usd"]) for row in trades]
    stats = win_loss_stats([_to_decimal(value) for value in trade_pnls])
    psr = probabilistic_sharpe(returns, periods_per_year=252)
    quarter_returns: dict[tuple[int, int], float] = defaultdict(float)
    for session, value in zip(sessions, returns, strict=True):
        quarter_returns[(session.year, (session.month - 1) // 3 + 1)] += value
    positive_quarter_fraction = (
        sum(value > 0 for value in quarter_returns.values()) / len(quarter_returns)
        if quarter_returns
        else 0.0
    )
    symbol_positive: dict[str, float] = defaultdict(float)
    positives: list[float] = []
    for row in trades:
        value = float(row["net_pnl_usd"])
        if value > 0:
            symbol_positive[str(row["symbol"])] += value
            positives.append(value)
    positive_total = sum(positives)
    single_symbol_fraction = (
        max(symbol_positive.values(), default=0.0) / positive_total if positive_total > 0 else 1.0
    )
    top_five_fraction = (
        sum(sorted(positives, reverse=True)[:5]) / positive_total if positive_total > 0 else 1.0
    )
    return {
        "session_count": len(sessions),
        "closed_trade_count": len(trades),
        "net_return_pct": round((equity[-1] / capital - 1.0) * 100.0, 8),
        "annualized_sharpe": float(sharpe_ratio(returns)),
        "psr": float(psr) if psr is not None else None,
        "max_drawdown_pct": float(max_drawdown_pct(equity)),
        "profit_factor": float(stats.profit_factor) if stats.profit_factor is not None else None,
        "positive_quarter_fraction": round(positive_quarter_fraction, 8),
        "max_single_symbol_positive_contribution_fraction": round(single_symbol_fraction, 8),
        "top_five_trade_positive_contribution_fraction": round(top_five_fraction, 8),
        "daily_returns": [round(value, 12) for value in returns],
    }


def _to_decimal(value: float):
    from decimal import Decimal

    return Decimal(str(value))


def _segment_scores(
    daily_returns: Sequence[float],
    *,
    segments: int,
) -> list[float]:
    indexes = np.array_split(np.arange(len(daily_returns)), segments)
    return [
        annualized_sharpe([daily_returns[int(index)] for index in group], periods_per_year=252)
        if len(group) >= 2
        else 0.0
        for group in indexes
    ]


def _candidate_evaluation(
    candidate: IntradayCandidate,
    base: SimulationResult,
    stress: SimulationResult,
    development: Sequence[date],
    block: Sequence[date],
    confirmation: Sequence[date],
    *,
    capital: float,
) -> dict[str, object]:
    return {
        **candidate.as_dict(),
        "base": {
            "development": _window_metrics(base, development, capital=capital),
            "block": _window_metrics(base, block, capital=capital),
            "confirmation": _window_metrics(base, confirmation, capital=capital),
            "total_cost_usd": base.total_cost_usd,
            "turnover_usd": base.turnover_usd,
            "unclosed_quantity": base.unclosed_quantity,
        },
        "stress": {
            "confirmation": _window_metrics(stress, confirmation, capital=capital),
            "total_cost_usd": stress.total_cost_usd,
            "turnover_usd": stress.turnover_usd,
            "unclosed_quantity": stress.unclosed_quantity,
        },
    }


def _select_candidate(evaluations: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    return min(
        evaluations,
        key=lambda row: (
            -float(row["base"]["development"]["annualized_sharpe"]),
            float(row["base"]["development"]["max_drawdown_pct"]),
            float(row["base"]["turnover_usd"]),
            str(row["candidate_id"]),
        ),
    )


def _decision_for_complete_data(
    selected: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    *,
    development_pbo: float | None,
    selected_dsr: float | None,
) -> tuple[dict[str, bool], list[str]]:
    acceptance = preregistration["acceptance"]
    block = selected["base"]["block"]
    confirmation = selected["base"]["confirmation"]
    stress = selected["stress"]["confirmation"]
    gates = {
        "block_net_positive": float(block["net_return_pct"])
        > float(acceptance["block_net_return_gt"]),
        "confirmation_net_positive": float(confirmation["net_return_pct"])
        > float(acceptance["confirmation_net_return_gt"]),
        "confirmation_sharpe": float(confirmation["annualized_sharpe"])
        >= float(acceptance["confirmation_annualized_sharpe_min"]),
        "confirmation_psr": confirmation["psr"] is not None
        and float(confirmation["psr"]) >= float(acceptance["confirmation_psr_min"]),
        "selected_dsr": selected_dsr is not None
        and selected_dsr >= float(acceptance["selected_dsr_min"]),
        "development_pbo": development_pbo is not None
        and development_pbo <= float(acceptance["development_pbo_max"]),
        "max_drawdown": float(confirmation["max_drawdown_pct"])
        <= float(acceptance["confirmation_max_drawdown_pct_max"]),
        "profit_factor": confirmation["profit_factor"] is not None
        and float(confirmation["profit_factor"])
        >= float(acceptance["confirmation_profit_factor_min"]),
        "positive_quarters": float(confirmation["positive_quarter_fraction"])
        >= float(acceptance["confirmation_positive_quarter_fraction_min"]),
        "symbol_concentration": float(
            confirmation["max_single_symbol_positive_contribution_fraction"]
        )
        <= float(acceptance["max_single_symbol_positive_contribution_fraction"]),
        "trade_concentration": float(confirmation["top_five_trade_positive_contribution_fraction"])
        <= float(acceptance["max_top_five_trade_positive_contribution_fraction"]),
        "stress_net_positive": float(stress["net_return_pct"])
        > float(acceptance["stress_confirmation_net_return_gt"]),
        "base_positions_closed": int(selected["base"]["unclosed_quantity"]) == 0,
        "stress_positions_closed": int(selected["stress"]["unclosed_quantity"]) == 0,
    }
    return gates, [name for name, passed in gates.items() if not passed]


def _ledger_bytes(rows: Sequence[Mapping[str, object]]) -> bytes:
    ordered = sorted(
        rows,
        key=lambda row: (
            str(row["candidate_id"]),
            str(row["cost_model"]),
            str(row["session_date"]),
            str(row["eligible_at_utc"]),
            str(row["symbol"]),
            str(row["side"]),
        ),
    )
    return b"".join(_canonical_bytes(row) + b"\n" for row in ordered)


def run_intraday_paper_challenger(
    dataset: IntradayDataset,
    preregistration: Mapping[str, Any],
    *,
    preregistration_bytes: bytes,
    code_commit: str,
    generated_at_utc: str,
) -> tuple[dict[str, object], bytes]:
    registry = build_candidate_registry(preregistration)
    minimum = preregistration["minimum_evidence"]
    reasons = list(dataset.quality_reasons)
    if dataset.synthetic:
        reasons.append("synthetic_dataset_not_promotion_evidence")
    if len(dataset.sessions) < int(minimum["minimum_total_sessions"]):
        reasons.append("minimum_total_sessions_not_met")
    evaluations: list[dict[str, object]] = []
    selected_id: str | None = None
    development_pbo: float | None = None
    selected_dsr: float | None = None
    all_ledger_rows: list[dict[str, object]] = []
    gates: dict[str, bool] = {"data_complete": not reasons}

    if not reasons:
        block_count = int(preregistration["time_split"]["block_sessions"])
        confirmation_count = int(preregistration["time_split"]["confirmation_sessions"])
        development = dataset.sessions[: -(block_count + confirmation_count)]
        block = dataset.sessions[-(block_count + confirmation_count) : -confirmation_count]
        confirmation = dataset.sessions[-confirmation_count:]
        capital = float(preregistration["portfolio"]["initial_capital_usd"])
        cache = {
            timeframe: resample_dataset(dataset, timeframe) for timeframe in EXPECTED_TIMEFRAMES
        }
        runs: dict[tuple[str, str], SimulationResult] = {}
        for candidate in registry:
            for model in ("base", "stress"):
                run = simulate_candidate(
                    candidate,
                    cache[candidate.timeframe_minutes],
                    dataset.sessions,
                    preregistration,
                    cost_model_name=model,
                )
                runs[(candidate.candidate_id, model)] = run
                all_ledger_rows.extend(run.ledger_rows)
            evaluations.append(
                _candidate_evaluation(
                    candidate,
                    runs[(candidate.candidate_id, "base")],
                    runs[(candidate.candidate_id, "stress")],
                    development,
                    block,
                    confirmation,
                    capital=capital,
                )
            )
        selected = _select_candidate(evaluations)
        selected_id = str(selected["candidate_id"])
        total_selected_trades = sum(
            int(selected["base"][window]["closed_trade_count"])
            for window in ("development", "block", "confirmation")
        )
        if total_selected_trades < int(minimum["minimum_base_cost_closed_trades"]):
            reasons.append("minimum_base_cost_closed_trades_not_met")
        development_matrix = [
            _segment_scores(
                row["base"]["development"]["daily_returns"],
                segments=int(preregistration["time_split"]["development_pbo_segments"]),
            )
            for row in evaluations
        ]
        pbo = probability_of_backtest_overfitting(development_matrix)
        development_pbo = float(pbo) if pbo is not None else None
        confirmation_trial_sharpes = [
            float(row["base"]["confirmation"]["annualized_sharpe"]) for row in evaluations
        ]
        selected_returns = selected["base"]["confirmation"]["daily_returns"]
        dsr = deflated_sharpe_from_trials(
            selected_returns,
            confirmation_trial_sharpes,
            periods_per_year=252,
        )
        selected_dsr = float(dsr) if dsr is not None else None
        if not reasons:
            gates, failed = _decision_for_complete_data(
                selected,
                preregistration,
                development_pbo=development_pbo,
                selected_dsr=selected_dsr,
            )
            reasons.extend(failed)
        else:
            gates = {
                "data_complete": True,
                "minimum_base_cost_closed_trades": total_selected_trades
                >= int(minimum["minimum_base_cost_closed_trades"]),
            }

    if any(
        reason.startswith(("synthetic_", "minimum_", "incomplete_", "symbol_session_"))
        for reason in reasons
    ):
        verdict = "INSUFFICIENT_EVIDENCE"
    elif reasons:
        verdict = "NO_INTRADAY_EDGE"
    else:
        verdict = "PAPER_CHALLENGER"
    ledger_bytes = _ledger_bytes(all_ledger_rows)
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "gate_version": GATE_VERSION,
        "family_id": FAMILY_ID,
        "generated_at_utc": generated_at_utc,
        "code_commit": code_commit,
        "preregistration_sha256": _sha256(preregistration_bytes),
        "data_quality": {
            "complete": not dataset.quality_reasons,
            "synthetic": dataset.synthetic,
            "dataset_fingerprint": dataset.dataset_fingerprint,
            "session_count": len(dataset.sessions),
            "reasons": list(dataset.quality_reasons),
        },
        "candidate_registry": [candidate.as_dict() for candidate in registry],
        "evaluations": evaluations,
        "selection": {
            "selected_candidate_id": selected_id,
            "development_only": True,
            "candidate_count": len(registry),
            "development_pbo": development_pbo,
            "selected_dsr": selected_dsr,
        },
        "decision": {
            "verdict": verdict,
            "passed": verdict == "PAPER_CHALLENGER",
            "gates": gates,
            "reasons": sorted(set(reasons)),
            "next_step": (
                "start a separate 60-session forward paper observation with zero capital"
                if verdict == "PAPER_CHALLENGER"
                else "provide at least 756 complete XNYS sessions and 200 base-cost trades"
                if verdict == "INSUFFICIENT_EVIDENCE"
                else "retain the incumbent and do not promote this intraday family"
            ),
        },
        "audit": {
            "ledger_row_count": len(all_ledger_rows),
            "ledger_sha256": _sha256(ledger_bytes),
        },
        "safety": dict(EXPECTED_SAFETY),
    }
    return payload, ledger_bytes


def render_intraday_markdown(payload: Mapping[str, Any]) -> str:
    quality = payload["data_quality"]
    selection = payload["selection"]
    decision = payload["decision"]
    lines = [
        "# 장중매매 페이퍼 챌린저 최신 결과",
        "",
        f"- 판정: `{decision['verdict']}`",
        f"- 완전한 공통 세션: {quality['session_count']}개",
        f"- 합성 자료: {quality['synthetic']}",
        f"- 후보: {selection['candidate_count']}개",
        f"- 개발 구간 선택 후보: `{selection['selected_candidate_id']}`",
        f"- 개발 PBO: {selection['development_pbo']}",
        f"- 선택 후보 DSR: {selection['selected_dsr']}",
        f"- 실패/대기 이유: {', '.join(decision['reasons']) or '없음'}",
        "- 실제 주문: 0건",
        "- 자본: 0%",
        "- 라이브 승격: 불가",
        "",
        f"다음 단계: {decision['next_step']}",
    ]
    return "\n".join(lines)


__all__ = [
    "DatasetContractError",
    "GATE_VERSION",
    "FAMILY_ID",
    "IntradayBar",
    "IntradayCandidate",
    "IntradayDataset",
    "PreregistrationContractError",
    "ResampledBar",
    "SimulationResult",
    "build_candidate_registry",
    "load_intraday_dataset",
    "load_preregistration",
    "render_intraday_markdown",
    "resample_dataset",
    "run_intraday_paper_challenger",
    "simulate_candidate",
]
