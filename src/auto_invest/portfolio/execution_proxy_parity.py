"""Frozen economic-parity audit for whole-share execution proxies."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from statistics import median
from typing import Any

from auto_invest.backtest.data_source import HistoricalDataSource

PREREGISTERED_EXECUTION_SYMBOL_MAP: dict[str, str] = {
    "SPY": "SCHX",
    "IEF": "SPTI",
    "GLD": "IAUM",
}
LOOKBACK_SESSIONS = 252
MIN_COMMON_SESSIONS = 252
MIN_RETURN_CORRELATION = 0.95
MAX_ANNUALIZED_TRACKING_ERROR = 0.06
MAX_ANNUALIZED_RETURN_GAP = 0.03
MIN_MEDIAN_DOLLAR_VOLUME_USD = Decimal("1000000")
MAX_MARKET_DATA_AGE_DAYS = 7
MAX_EVIDENCE_AGE_HOURS = 36.0


def _contract() -> dict[str, Any]:
    return {
        "lookback_sessions": LOOKBACK_SESSIONS,
        "min_common_sessions": MIN_COMMON_SESSIONS,
        "min_return_correlation": MIN_RETURN_CORRELATION,
        "max_annualized_tracking_error": MAX_ANNUALIZED_TRACKING_ERROR,
        "max_annualized_return_gap": MAX_ANNUALIZED_RETURN_GAP,
        "min_median_dollar_volume_usd": str(MIN_MEDIAN_DOLLAR_VOLUME_USD),
        "max_market_data_age_days": MAX_MARKET_DATA_AGE_DAYS,
        "max_evidence_age_hours": MAX_EVIDENCE_AGE_HOURS,
    }


@dataclass(frozen=True)
class ExecutionProxyPairEvidence:
    signal_symbol: str
    execution_symbol: str
    common_sessions: int
    first_session: str | None
    last_session: str | None
    signal_latest_session: str | None
    execution_latest_session: str | None
    return_correlation: float | None
    annualized_tracking_error: float | None
    annualized_return_gap: float | None
    median_execution_dollar_volume_usd: str | None
    checks: dict[str, bool]

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(self.checks.values())

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "passed": self.passed}


@dataclass(frozen=True)
class ExecutionProxyParityEvidence:
    observed_at_utc: str
    dataset_version: str
    symbol_map: dict[str, str]
    contract: dict[str, Any]
    checks: dict[str, bool]
    pairs: tuple[ExecutionProxyPairEvidence, ...]
    passed: bool
    evidence_digest: str

    SCHEMA_VERSION = "1.0"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "observed_at_utc": self.observed_at_utc,
            "dataset_version": self.dataset_version,
            "symbol_map": dict(self.symbol_map),
            "contract": dict(self.contract),
            "checks": dict(self.checks),
            "pairs": [pair.as_dict() for pair in self.pairs],
            "passed": self.passed,
            "evidence_digest": self.evidence_digest,
        }


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "evidence_digest"}
    encoded = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _returns(closes: list[float]) -> list[float]:
    return [closes[index] / closes[index - 1] - 1.0 for index in range(1, len(closes))]


def _correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    left_var = sum((value - left_mean) ** 2 for value in left)
    right_var = sum((value - right_mean) ** 2 for value in right)
    if left_var <= 0 or right_var <= 0:
        return None
    covariance = sum(
        (l_value - left_mean) * (r_value - right_mean)
        for l_value, r_value in zip(left, right, strict=True)
    )
    return covariance / math.sqrt(left_var * right_var)


def _annualized_tracking_error(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    active = [l_value - r_value for l_value, r_value in zip(left, right, strict=True)]
    active_mean = sum(active) / len(active)
    variance = sum((value - active_mean) ** 2 for value in active) / (len(active) - 1)
    return math.sqrt(variance) * math.sqrt(252.0)


def _annualized_return(closes: list[float]) -> float | None:
    periods = len(closes) - 1
    if periods < 1 or closes[0] <= 0 or closes[-1] <= 0:
        return None
    return (closes[-1] / closes[0]) ** (252.0 / periods) - 1.0


def _pair_evidence(
    data_source: HistoricalDataSource,
    *,
    signal_symbol: str,
    execution_symbol: str,
    observed_at: datetime,
) -> ExecutionProxyPairEvidence:
    common = sorted(
        set(data_source.session_dates(signal_symbol))
        & set(data_source.session_dates(execution_symbol))
    )[-LOOKBACK_SESSIONS:]
    if not common:
        checks = {
            "common_sessions": False,
            "latest_session_aligned": False,
            "freshness": False,
            "return_correlation": False,
            "annualized_tracking_error": False,
            "annualized_return_gap": False,
            "execution_liquidity": False,
        }
        return ExecutionProxyPairEvidence(
            signal_symbol=signal_symbol,
            execution_symbol=execution_symbol,
            common_sessions=0,
            first_session=None,
            last_session=None,
            signal_latest_session=None,
            execution_latest_session=None,
            return_correlation=None,
            annualized_tracking_error=None,
            annualized_return_gap=None,
            median_execution_dollar_volume_usd=None,
            checks=checks,
        )

    start, end = common[0], common[-1]
    signal_bars = {
        bar.session_date: bar
        for bar in data_source.read_bars(signal_symbol, start, end)
        if bar.session_date in common
    }
    execution_bars = {
        bar.session_date: bar
        for bar in data_source.read_bars(execution_symbol, start, end)
        if bar.session_date in common
    }
    aligned = [
        session
        for session in common
        if session in signal_bars and session in execution_bars
    ]
    signal_closes = [float(signal_bars[session].close) for session in aligned]
    execution_closes = [float(execution_bars[session].close) for session in aligned]
    signal_returns = _returns(signal_closes)
    execution_returns = _returns(execution_closes)
    correlation = _correlation(signal_returns, execution_returns)
    tracking_error = _annualized_tracking_error(signal_returns, execution_returns)
    signal_annualized = _annualized_return(signal_closes)
    execution_annualized = _annualized_return(execution_closes)
    annualized_gap = (
        abs(signal_annualized - execution_annualized)
        if signal_annualized is not None and execution_annualized is not None
        else None
    )
    dollar_volumes = [
        execution_bars[session].close * Decimal(execution_bars[session].volume)
        for session in aligned
    ]
    median_dollar_volume = median(dollar_volumes) if dollar_volumes else None
    latest_signal = max(data_source.session_dates(signal_symbol), default=None)
    latest_execution = max(data_source.session_dates(execution_symbol), default=None)
    market_age_days = (observed_at.date() - end).days
    checks = {
        "common_sessions": len(aligned) >= MIN_COMMON_SESSIONS,
        "latest_session_aligned": latest_signal == latest_execution == end,
        "freshness": 0 <= market_age_days <= MAX_MARKET_DATA_AGE_DAYS,
        "return_correlation": (
            correlation is not None and correlation >= MIN_RETURN_CORRELATION
        ),
        "annualized_tracking_error": (
            tracking_error is not None
            and tracking_error <= MAX_ANNUALIZED_TRACKING_ERROR
        ),
        "annualized_return_gap": (
            annualized_gap is not None and annualized_gap <= MAX_ANNUALIZED_RETURN_GAP
        ),
        "execution_liquidity": (
            median_dollar_volume is not None
            and median_dollar_volume >= MIN_MEDIAN_DOLLAR_VOLUME_USD
        ),
    }
    return ExecutionProxyPairEvidence(
        signal_symbol=signal_symbol,
        execution_symbol=execution_symbol,
        common_sessions=len(aligned),
        first_session=aligned[0].isoformat() if aligned else None,
        last_session=aligned[-1].isoformat() if aligned else None,
        signal_latest_session=(latest_signal.isoformat() if latest_signal is not None else None),
        execution_latest_session=(
            latest_execution.isoformat() if latest_execution is not None else None
        ),
        return_correlation=correlation,
        annualized_tracking_error=tracking_error,
        annualized_return_gap=annualized_gap,
        median_execution_dollar_volume_usd=(
            str(median_dollar_volume) if median_dollar_volume is not None else None
        ),
        checks=checks,
    )


def assess_execution_proxy_parity(
    data_source: HistoricalDataSource,
    *,
    symbol_map: Mapping[str, str],
    observed_at: datetime | None = None,
) -> ExecutionProxyParityEvidence:
    """Assess the frozen map on point-in-time adjusted KIS-compatible bars."""

    now = (observed_at or datetime.now(UTC)).astimezone(UTC)
    normalized = {
        str(signal).strip().upper(): str(execution).strip().upper()
        for signal, execution in symbol_map.items()
    }
    pairs = tuple(
        _pair_evidence(
            data_source,
            signal_symbol=signal,
            execution_symbol=execution,
            observed_at=now,
        )
        for signal, execution in sorted(normalized.items())
    )
    checks = {
        "mapping_exact": normalized == PREREGISTERED_EXECUTION_SYMBOL_MAP,
        "pair_count": len(pairs) == len(PREREGISTERED_EXECUTION_SYMBOL_MAP),
        "all_pairs_passed": bool(pairs) and all(pair.passed for pair in pairs),
    }
    passed = all(checks.values())
    body = {
        "schema_version": ExecutionProxyParityEvidence.SCHEMA_VERSION,
        "observed_at_utc": now.isoformat().replace("+00:00", "Z"),
        "dataset_version": data_source.dataset_version,
        "symbol_map": normalized,
        "contract": _contract(),
        "checks": checks,
        "pairs": [pair.as_dict() for pair in pairs],
        "passed": passed,
    }
    return ExecutionProxyParityEvidence(
        observed_at_utc=body["observed_at_utc"],
        dataset_version=str(body["dataset_version"]),
        symbol_map=normalized,
        contract=dict(body["contract"]),
        checks=checks,
        pairs=pairs,
        passed=passed,
        evidence_digest=_canonical_digest(body),
    )


def _finite_float(value: object) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("finite float required")
    return parsed


def validate_execution_proxy_parity_evidence(
    evidence: object,
    *,
    expected_symbol_map: Mapping[str, str],
    now: datetime | None = None,
) -> bool:
    """Recompute the evidence and require both authenticity and a passing result."""

    if not isinstance(evidence, Mapping) or evidence.get("schema_version") != "1.0":
        return False
    current = (now or datetime.now(UTC)).astimezone(UTC)
    try:
        observed = datetime.fromisoformat(str(evidence["observed_at_utc"]).replace("Z", "+00:00"))
        age_hours = (current - observed.astimezone(UTC)).total_seconds() / 3600.0
        symbol_map = {str(k): str(v) for k, v in dict(evidence["symbol_map"]).items()}
        expected = {str(k): str(v) for k, v in expected_symbol_map.items()}
        if symbol_map != expected or symbol_map != PREREGISTERED_EXECUTION_SYMBOL_MAP:
            return False
        if evidence.get("contract") != _contract() or not (
            0.0 <= age_hours <= MAX_EVIDENCE_AGE_HOURS
        ):
            return False
        rows = evidence["pairs"]
        if not isinstance(rows, list) or len(rows) != len(expected):
            return False
        pair_passes: list[bool] = []
        for row in rows:
            if not isinstance(row, Mapping):
                return False
            signal = str(row["signal_symbol"])
            execution = str(row["execution_symbol"])
            if expected.get(signal) != execution:
                return False
            common_sessions = int(row["common_sessions"])
            last_session = date.fromisoformat(str(row["last_session"]))
            signal_latest = date.fromisoformat(str(row["signal_latest_session"]))
            execution_latest = date.fromisoformat(str(row["execution_latest_session"]))
            correlation = _finite_float(row["return_correlation"])
            tracking_error = _finite_float(row["annualized_tracking_error"])
            annualized_gap = _finite_float(row["annualized_return_gap"])
            liquidity = Decimal(str(row["median_execution_dollar_volume_usd"]))
            if not liquidity.is_finite():
                return False
            recomputed_checks = {
                "common_sessions": common_sessions >= MIN_COMMON_SESSIONS,
                "latest_session_aligned": (
                    signal_latest == execution_latest == last_session
                ),
                "freshness": 0 <= (current.date() - last_session).days <= MAX_MARKET_DATA_AGE_DAYS,
                "return_correlation": correlation >= MIN_RETURN_CORRELATION,
                "annualized_tracking_error": tracking_error <= MAX_ANNUALIZED_TRACKING_ERROR,
                "annualized_return_gap": annualized_gap <= MAX_ANNUALIZED_RETURN_GAP,
                "execution_liquidity": liquidity >= MIN_MEDIAN_DOLLAR_VOLUME_USD,
            }
            if dict(row["checks"]) != recomputed_checks:
                return False
            pair_passed = all(recomputed_checks.values())
            if row.get("passed") is not pair_passed:
                return False
            pair_passes.append(pair_passed)
        recomputed_top = {
            "mapping_exact": True,
            "pair_count": len(rows) == len(expected),
            "all_pairs_passed": all(pair_passes),
        }
        passed = all(recomputed_top.values())
        if dict(evidence["checks"]) != recomputed_top or evidence.get("passed") is not passed:
            return False
        return passed and evidence.get("evidence_digest") == _canonical_digest(evidence)
    except (
        ArithmeticError,
        InvalidOperation,
        KeyError,
        TypeError,
        ValueError,
    ):
        return False


__all__ = [
    "ExecutionProxyPairEvidence",
    "ExecutionProxyParityEvidence",
    "PREREGISTERED_EXECUTION_SYMBOL_MAP",
    "assess_execution_proxy_parity",
    "validate_execution_proxy_parity_evidence",
]
