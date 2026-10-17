"""Single preregistered cost-range hypothesis; no broker or confirmation access."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from auto_invest.analytics import intraday_paper_challenger as paper
from auto_invest.analytics.cost_aware_intraday import select_development, validate_development

CONTRACT_SHA256 = "0f2e08ce713ebaff8dc48a64ddd00d3a150324b92222259d6d3c895bcda6d71c"
MANIFEST_SHA256 = "c4b6c6336ee0747464fde730f6d894ba3b8814c14567406f49cb0e528ea8fdfc"
LIMITATIONS = [
    "development_only_not_strategy_acceptance",
    "previously_observed_development_after_multiple_failed_hypotheses",
    "single_cost_range_hypothesis_not_paper_replication",
    "opening_range_does_not_guarantee_remaining_profitable_move",
    "fill_bar_total_volume_is_hindsight_liquidity_assumption",
    "session_exit_at_final_30m_open_not_exchange_close",
    "adjusted_prices_not_verified_execution_equivalence",
    "fixed_daily_allocation_not_broker_settlement_ledger",
    "microsecond_fill_timestamp_is_model_ordering_not_observed_execution",
]


def load_contract(path: Path, prior_path: Path):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
        raise ValueError("spec 220 contract differs from pre-evaluation seal")
    contract = json.loads(raw)
    if hashlib.sha256(prior_path.read_bytes()).hexdigest() != contract["prior_contract_sha256"]:
        raise ValueError("prior contract fingerprint mismatch")
    return contract, paper.load_preregistration(prior_path)


def candidate_registry(contract):
    identity = {
        "candidate_id": "cost-range-orb-30m-long-once", "family": "cost_range_breakout",
        "timeframe_minutes": contract["timeframe_minutes"], "variant": "long_once",
        "parameters": {"range_bars": 1, "cost_gate_numerator": 10040,
                       "cost_gate_denominator": 9960, "breakout_buffer_bps": 0},
    }
    fingerprint = paper._sha256(paper._canonical_bytes({
        **identity, "contract_sha256": CONTRACT_SHA256,
    }))
    return (paper.IntradayCandidate(**identity, strategy_fingerprint=fingerprint),)


def signal_plan(resampled, sessions):
    """Only completed opening-range and current-bar observations affect entry."""
    if not sessions or tuple(sorted(set(sessions))) != tuple(sessions):
        raise ValueError("sessions must be sorted and unique")
    if set(resampled) != set(paper.EXPECTED_UNIVERSE):
        raise ValueError("fixed five-symbol universe required")
    plan = {}
    for symbol in paper.EXPECTED_UNIVERSE:
        by_day = resampled[symbol]
        if set(by_day) != set(sessions):
            raise ValueError("exact session coverage required")
        for day in sessions:
            start = paper._CALENDAR.session_open(str(day)).to_pydatetime()
            close = paper._CALENDAR.session_close(str(day)).to_pydatetime()
            bars = by_day[day]
            count = int((close-start).total_seconds()/1800)
            if len(bars) != count:
                raise ValueError("contiguous calendar-aligned 30m bars required")
            for index, bar in enumerate(bars):
                if (bar.symbol != symbol or bar.session_date != day or bar.bar_index != index
                        or bar.timeframe_minutes != 30 or bar.base_bar_count != 6
                        or bar.timestamp_utc != start + timedelta(minutes=30*index)
                        or bar.end_utc != bar.timestamp_utc + timedelta(minutes=30)
                        or bar.end_utc > close):
                    raise ValueError("contiguous calendar-aligned 30m bars required")
                if any(not math.isfinite(value) or value <= 0
                       for value in (bar.open, bar.high, bar.low, bar.close)):
                    raise ValueError("finite positive observations required")
            opening = bars[0]
            cost_covered = (
                opening.complete
                and Decimal(str(opening.high)) * 9960 >= Decimal(str(opening.low)) * 10040
            )
            for index, bar in enumerate(bars):
                buy = (0 < index < len(bars)-2 and cost_covered
                       and bar.complete and bar.entry_eligible and bar.close > opening.high)
                plan[(symbol, day, bar.bar_index)] = (bool(buy), index == len(bars)-2)
    return plan


def load_development(bars_dir: Path, manifest: Path, prior):
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256:
        raise ValueError("only frozen development manifest accepted; price files not read")
    return paper.load_intraday_dataset(bars_dir, manifest, prior)


def run_development(dataset, contract, prior, *, code_commit: str):
    if not re.fullmatch(r"[0-9a-f]{40}", code_commit):
        raise ValueError("invalid code commit")
    validate_development(dataset, contract)
    resampled = paper.resample_dataset(dataset, 30)
    signals = signal_plan(resampled, dataset.sessions)
    evaluation_sessions = dataset.sessions
    evaluations, ledger_rows = [], []
    for candidate in candidate_registry(contract):
        row = candidate.as_dict()
        for model in ("base", "stress"):
            run = paper.simulate_candidate(candidate, resampled, dataset.sessions, prior,
                                           cost_model_name=model, signal_plan=signals)
            row[model] = {
                **paper._window_metrics(run, evaluation_sessions,
                                       capital=float(prior["portfolio"]["initial_capital_usd"])),
                "unclosed_quantity": run.unclosed_quantity, "turnover_usd": run.turnover_usd,
                "total_cost_usd": run.total_cost_usd,
            }
            ledger_rows.extend(run.ledger_rows)
        evaluations.append(row)
    selected, reasons = select_development(evaluations)
    ledger = paper._ledger_bytes(ledger_rows)
    payload = {
        "schema_version": "1.0", "family_id": contract["family_id"], "stage": "development",
        "contract_sha256": CONTRACT_SHA256, "code_commit": code_commit,
        "dataset_fingerprint": dataset.dataset_fingerprint, "session_count": len(dataset.sessions),
        "warmup_session_count": 0, "evaluation_session_count": len(evaluation_sessions),
        "evaluations": evaluations, "selected_candidate_id": selected, "rejection_reasons": reasons,
        "verdict": "CONFIRMATION_REQUIRED" if selected else "DEVELOPMENT_REJECTED",
        "holdout_read": False, "minimum_cumulative_trials": 37,
        "ledger_sha256": paper._sha256(ledger), "ledger_row_count": len(ledger_rows),
        "safety": dict(paper.EXPECTED_SAFETY), "limitations": list(LIMITATIONS),
    }
    payload["content_sha256"] = paper._sha256(paper._canonical_bytes(payload))
    return payload, ledger


def validate_seal(payload, ledger: bytes):
    body = dict(payload)
    seal = body.pop("content_sha256", None)
    if seal != paper._sha256(paper._canonical_bytes(body)):
        raise ValueError("content fingerprint mismatch")
    if body.get("contract_sha256") != CONTRACT_SHA256 or body.get("stage") != "development":
        raise ValueError("stage or contract mismatch")
    if body.get("safety") != paper.EXPECTED_SAFETY or body.get("holdout_read") is not False:
        raise ValueError("research boundary mismatch")
    if not re.fullmatch(r"[0-9a-f]{40}", str(body.get("code_commit", ""))):
        raise ValueError("invalid evidence code commit")
    if body.get("ledger_sha256") != paper._sha256(ledger):
        raise ValueError("ledger fingerprint mismatch")
    if body.get("ledger_row_count") != len(ledger.splitlines()):
        raise ValueError("ledger row count mismatch")


def verify_development(payload, ledger, dataset, contract, prior):
    validate_seal(payload, ledger)
    expected, expected_ledger = run_development(
        dataset, contract, prior, code_commit=payload["code_commit"],
    )
    if (ledger != expected_ledger
            or paper._canonical_bytes(payload) != paper._canonical_bytes(expected)):
        raise ValueError("evidence differs from source replay")
    return expected
