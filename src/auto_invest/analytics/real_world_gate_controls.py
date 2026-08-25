"""Empirical positive and null controls for edge gate version 2.0."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import zipfile
from datetime import UTC, date, datetime, timedelta
from io import BytesIO, StringIO
from typing import Any
from xml.etree import ElementTree

from auto_invest.analytics.backtest_overfitting import annualized_sharpe, probabilistic_sharpe
from auto_invest.analytics.edge_gate_calibration import GATE_VERSION, HOLDOUT_PSR_MIN
from auto_invest.analytics.multi_asset_trend import correlation
from auto_invest.analytics.risk_managed_beta import summarize

FAMA_FRENCH_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Research_Data_Factors_CSV.zip"
)
AQR_TSMOM_URL = (
    "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/"
    "Time-Series-Momentum-Factors-Monthly.xlsx"
)
CONTROL_START_MONTH = "2007-01"
REAL_WORLD_CONTROLS_VALID = "REAL_WORLD_CONTROLS_VALID"
REAL_WORLD_CONTROLS_FAILED = "REAL_WORLD_CONTROLS_FAILED"
FULL_GATE_CONTROLS_VALID = "FULL_GATE_CONTROLS_VALID"
FULL_GATE_CONTROLS_FAILED = "FULL_GATE_CONTROLS_FAILED"
MIN_CONTROL_OBSERVATIONS = 180
FULL_GATE_COST_BPS = 50


def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return _digest(raw)


def parse_fama_french_monthly(raw: bytes) -> dict[str, float]:
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(names) != 1:
                raise ValueError("Fama-French ZIP must contain one CSV")
            text = archive.read(names[0]).decode("utf-8", errors="strict")
    except (KeyError, UnicodeDecodeError, zipfile.BadZipFile) as exc:
        raise ValueError("Fama-French ZIP schema mismatch") from exc
    output: dict[str, float] = {}
    for row in csv.reader(StringIO(text)):
        if len(row) < 5:
            continue
        key = row[0].strip()
        if not re.fullmatch(r"\d{6}", key):
            continue
        value = float(row[1].strip()) / 100.0
        if not math.isfinite(value):
            raise ValueError("Fama-French market return is not finite")
        output[f"{key[:4]}-{key[4:]}"] = value
    if len(output) < 200:
        raise ValueError("Fama-French monthly coverage is incomplete")
    return output


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in item.findall(".//x:t", namespace)) for item in root]


def parse_aqr_tsmom_monthly(raw: bytes) -> dict[str, dict[str, float]]:
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            strings = _shared_strings(archive)
            root = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    except (KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise ValueError("AQR workbook schema mismatch") from exc

    headers: dict[str, str] = {}
    rows: list[dict[str, str]] = []
    for row in root.findall(".//x:sheetData/x:row", namespace):
        cells: dict[str, str] = {}
        for cell in row.findall("x:c", namespace):
            reference = str(cell.attrib.get("r", ""))
            column = re.sub(r"\d", "", reference)
            node = cell.find("x:v", namespace)
            if node is None or node.text is None:
                continue
            value = node.text
            if cell.attrib.get("t") == "s":
                value = strings[int(value)]
            cells[column] = value
        if cells.get("B") == "TSMOM":
            headers = cells
        elif headers and all(column in cells for column in ("A", "B", "C")):
            if all(
                not cells.get(column, "").strip()
                for column in ("A", "B", "C", "D", "E", "F")
            ):
                continue
            rows.append(cells)
    if headers.get("C") != "TSMOM^CM" or len(rows) < 200:
        raise ValueError("AQR workbook coverage or headers are incomplete")

    output = {"all": {}, "commodity": {}, "equity": {}, "fixed_income": {}, "fx": {}}
    column_names = {"B": "all", "C": "commodity", "D": "equity", "E": "fixed_income", "F": "fx"}
    origin = date(1899, 12, 30)
    for cells in rows:
        observed = origin + timedelta(days=int(float(cells["A"])))
        month = f"{observed:%Y-%m}"
        for column, name in column_names.items():
            if column not in cells:
                raise ValueError("AQR workbook factor column is incomplete")
            value = float(cells[column])
            if not math.isfinite(value):
                raise ValueError("AQR return is not finite")
            output[name][month] = value
    return output


def _month_age_days(month: str, current_date: date) -> int:
    year, value = (int(part) for part in month.split("-"))
    next_month = date(year + (value == 12), value % 12 + 1, 1)
    return (current_date - (next_month - timedelta(days=1))).days


def _control_row(control_id: str, provider: str, values: dict[str, float]) -> dict[str, Any]:
    selected = [value for month, value in sorted(values.items()) if month >= CONTROL_START_MONTH]
    if len(selected) < MIN_CONTROL_OBSERVATIONS:
        raise ValueError(f"{control_id} control window is incomplete")
    psr = probabilistic_sharpe(selected)
    mean = sum(selected) / len(selected)
    demeaned = [value - mean for value in selected]
    demeaned_psr = probabilistic_sharpe(demeaned)
    return {
        "control_id": control_id,
        "provider": provider,
        "window": [CONTROL_START_MONTH, max(values)],
        "observations": len(selected),
        "annual_sharpe": round(annualized_sharpe(selected), 6),
        "psr": None if psr is None else str(psr),
        "actual_live_passed": psr is not None and float(psr) >= HOLDOUT_PSR_MIN,
        "demeaned_psr": None if demeaned_psr is None else str(demeaned_psr),
        "demeaned_live_passed": demeaned_psr is not None
        and float(demeaned_psr) >= HOLDOUT_PSR_MIN,
    }


def run_real_world_gate_audit(
    fama_french_raw: bytes,
    aqr_raw: bytes,
    *,
    current_date: date,
    code_commit: str = "unknown",
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    market = parse_fama_french_monthly(fama_french_raw)
    tsmom = parse_aqr_tsmom_monthly(aqr_raw)
    controls = [
        _control_row("fama_french_market_excess", "Kenneth French Data Library", market),
        _control_row("aqr_diversified_tsmom", "AQR Capital Management", tsmom["all"]),
    ]
    freshness = {
        "fama_french_last_month": max(market),
        "fama_french_age_days": _month_age_days(max(market), current_date),
        "aqr_last_month": max(tsmom["all"]),
        "aqr_age_days": _month_age_days(max(tsmom["all"]), current_date),
    }
    fresh = freshness["fama_french_age_days"] <= 75 and freshness["aqr_age_days"] <= 150
    passed = bool(
        fresh
        and all(row["actual_live_passed"] for row in controls)
        and all(row["demeaned_live_passed"] is False for row in controls)
    )
    sources = {
        "fama_french": {"url": FAMA_FRENCH_URL, "digest": _digest(fama_french_raw)},
        "aqr_tsmom": {"url": AQR_TSMOM_URL, "digest": _digest(aqr_raw)},
    }
    fingerprint = _fingerprint(
        {
            "gate": GATE_VERSION,
            "threshold": HOLDOUT_PSR_MIN,
            "sources": sources,
            "controls": controls,
        }
    )
    return {
        "schema_version": "1.0",
        "gate_version": GATE_VERSION,
        "timestamp_utc": timestamp_utc or datetime.now(UTC).isoformat(),
        "code_commit": code_commit,
        "verdict": REAL_WORLD_CONTROLS_VALID if passed else REAL_WORLD_CONTROLS_FAILED,
        "promotion_control_passed": passed,
        "threshold": {"live_psr_min": HOLDOUT_PSR_MIN},
        "controls": controls,
        "freshness": freshness,
        "sources": sources,
        "control_fingerprint": fingerprint,
        "isolation": {
            "candidate_trial_count_contribution": 0,
            "promotion_candidate": False,
            "purpose": "gate diagnostic only",
        },
        "safety": ["no broker API", "no orders", "no capital or whitelist change"],
    }


def _annualized_relative_return(candidate: list[float], cash: list[float]) -> float:
    relative = math.prod(left / right for left, right in zip(candidate, cash, strict=True))
    return relative ** (12.0 / len(candidate)) - 1.0


def _complete_diversifier_control(
    control_id: str,
    excess_returns: list[float],
    cash_factors: list[float],
    incumbent_factors: list[float],
    *,
    cost_bps: int,
) -> dict[str, Any]:
    monthly_haircut = cost_bps / 10_000.0 / 12.0
    candidate = [
        cash * (1.0 + excess - monthly_haircut)
        for cash, excess in zip(cash_factors, excess_returns, strict=True)
    ]
    candidate_excess = [
        factor / cash - 1.0 for factor, cash in zip(candidate, cash_factors, strict=True)
    ]
    incumbent_stats = summarize(incumbent_factors)
    blend = [
        0.8 * incumbent + 0.2 * challenger
        for incumbent, challenger in zip(incumbent_factors, candidate, strict=True)
    ]
    blend_stats = summarize(blend)
    psr = probabilistic_sharpe(candidate_excess)
    annual_excess = _annualized_relative_return(candidate, cash_factors)
    incumbent_correlation = correlation(incumbent_factors, candidate)
    if incumbent_correlation is None:
        incumbent_correlation = 1.0
    blend_improvement = blend_stats.sharpe - incumbent_stats.sharpe
    raw_gates = (
        (
            "holdout_excess_psr",
            psr is not None and float(psr) >= HOLDOUT_PSR_MIN,
            psr,
            HOLDOUT_PSR_MIN,
        ),
        ("holdout_excess_50bps_positive", annual_excess > 0.0, annual_excess, "> 0"),
        ("incumbent_correlation", incumbent_correlation < 0.80, incumbent_correlation, "< 0.80"),
        ("blend_sharpe_improvement", blend_improvement >= 0.05, blend_improvement, ">= 0.05"),
        (
            "blend_drawdown_non_worsening",
            blend_stats.max_dd_pct <= incumbent_stats.max_dd_pct,
            blend_stats.max_dd_pct,
            incumbent_stats.max_dd_pct,
        ),
    )
    gates = [
        {
            "gate_id": gate_id,
            "passed": bool(passed),
            "actual": None if actual is None else str(actual),
            "required": str(required),
        }
        for gate_id, passed, actual, required in raw_gates
    ]
    return {
        "control_id": control_id,
        "cost_bps_annual": cost_bps,
        "psr": None if psr is None else str(psr),
        "annual_excess_return": round(annual_excess, 8),
        "incumbent_correlation": round(incumbent_correlation, 8),
        "incumbent_sharpe": round(incumbent_stats.sharpe, 8),
        "blend_sharpe": round(blend_stats.sharpe, 8),
        "blend_sharpe_improvement": round(blend_improvement, 8),
        "incumbent_max_drawdown_pct": incumbent_stats.max_dd_pct,
        "blend_max_drawdown_pct": blend_stats.max_dd_pct,
        "gates": gates,
        "passed": all(gate["passed"] for gate in gates),
    }


def run_full_gate_control_audit(
    aqr_returns: dict[str, float],
    *,
    months: list[str],
    cash_factors: list[float],
    incumbent_factors: list[float],
    psr_controls: dict[str, Any] | None = None,
    code_commit: str = "unknown",
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    """Evaluate a real diversifier and its null through the complete live decision."""
    if not (len(months) == len(cash_factors) == len(incumbent_factors)):
        raise ValueError("full-gate control inputs must align")
    if len(months) < MIN_CONTROL_OBSERVATIONS or len(set(months)) != len(months):
        raise ValueError("full-gate control months are incomplete or duplicated")
    try:
        values = [float(aqr_returns[month]) for month in months]
    except KeyError as exc:
        raise ValueError("AQR full-gate control months do not align") from exc
    if not all(math.isfinite(value) for value in values):
        raise ValueError("AQR full-gate returns are not finite")
    mean = sum(values) / len(values)
    positive = _complete_diversifier_control(
        "aqr_diversified_tsmom_50bps",
        values,
        cash_factors,
        incumbent_factors,
        cost_bps=FULL_GATE_COST_BPS,
    )
    null = _complete_diversifier_control(
        "aqr_diversified_tsmom_demeaned_50bps",
        [value - mean for value in values],
        cash_factors,
        incumbent_factors,
        cost_bps=FULL_GATE_COST_BPS,
    )
    psr_controls_passed = psr_controls is None or bool(
        psr_controls.get("verdict") == REAL_WORLD_CONTROLS_VALID
        and psr_controls.get("promotion_control_passed") is True
        and psr_controls.get("code_commit") == code_commit
    )
    passed = (
        positive["passed"] is True
        and null["passed"] is False
        and psr_controls_passed
    )
    fingerprint = _fingerprint(
        {
            "gate_version": GATE_VERSION,
            "months": [months[0], months[-1]],
            "cost_bps": FULL_GATE_COST_BPS,
            "positive": positive,
            "null": null,
            "psr_control_fingerprint": (
                psr_controls.get("control_fingerprint") if psr_controls else None
            ),
        }
    )
    return {
        "schema_version": "1.0",
        "gate_version": GATE_VERSION,
        "timestamp_utc": timestamp_utc or datetime.now(UTC).isoformat(),
        "code_commit": code_commit,
        "verdict": FULL_GATE_CONTROLS_VALID if passed else FULL_GATE_CONTROLS_FAILED,
        "conclusion": (
            "FULL_GATE_EMPIRICALLY_PASSABLE"
            if passed
            else "FULL_GATE_FEASIBILITY_NOT_PROVEN"
        ),
        "promotion_control_passed": passed,
        "window": [months[0], months[-1]],
        "observations": len(months),
        "positive_control": positive,
        "null_control": null,
        "psr_controls": psr_controls,
        "psr_controls_passed": psr_controls_passed,
        "control_fingerprint": fingerprint,
        "isolation": {
            "candidate_trial_count_contribution": 0,
            "promotion_candidate": False,
            "purpose": "complete gate diagnostic only",
        },
        "safety": ["no broker API", "no orders", "no capital or whitelist change"],
    }


__all__ = [
    "AQR_TSMOM_URL",
    "FAMA_FRENCH_URL",
    "FULL_GATE_CONTROLS_FAILED",
    "FULL_GATE_CONTROLS_VALID",
    "REAL_WORLD_CONTROLS_FAILED",
    "REAL_WORLD_CONTROLS_VALID",
    "parse_aqr_tsmom_monthly",
    "parse_fama_french_monthly",
    "run_full_gate_control_audit",
    "run_real_world_gate_audit",
]
