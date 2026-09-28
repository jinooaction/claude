"""Single preregistered late-session hypothesis; no broker or confirmation access."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import timedelta
from pathlib import Path

from auto_invest.analytics import intraday_paper_challenger as paper
from auto_invest.analytics.cost_aware_intraday import select_development, validate_development

CONTRACT_SHA256 = "9496b4825288a20acce4009fe7257e5e6eb32fdf0da5bb5cb626b4927a7482b4"
MANIFEST_SHA256 = "c4b6c6336ee0747464fde730f6d894ba3b8814c14567406f49cb0e528ea8fdfc"
LIMITATIONS = [
    "development_only_not_strategy_acceptance",
    "previously_observed_development_after_multiple_failed_hypotheses",
    "long_only_etf_variant_not_source_paper_replication",
    "source_paper_period_overlaps_future_confirmation",
    "fill_bar_total_volume_is_hindsight_liquidity_assumption",
    "session_exit_at_final_5m_open_not_exchange_close",
    "adjusted_prices_not_verified_execution_equivalence",
    "fixed_daily_allocation_not_broker_settlement_ledger",
    "microsecond_fill_timestamp_is_model_ordering_not_observed_execution",
]


def load_contract(path: Path, prior_path: Path):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
        raise ValueError("spec 198 contract differs from pre-evaluation seal")
    contract = json.loads(raw)
    if hashlib.sha256(prior_path.read_bytes()).hexdigest() != contract["prior_contract_sha256"]:
        raise ValueError("prior contract fingerprint mismatch")
    return contract, paper.load_preregistration(prior_path)


def candidate_registry(contract):
    identity = {
        "candidate_id": "late-session-5m-long-once", "family": "late_session",
        "timeframe_minutes": contract["timeframe_minutes"], "variant": "long_once",
        "parameters": {"first_observation_minutes": 30, "entry_minutes_before_close": 30},
    }
    fingerprint = paper._sha256(paper._canonical_bytes({
        **identity, "contract_sha256": CONTRACT_SHA256,
    }))
    return (paper.IntradayCandidate(**identity, strategy_fingerprint=fingerprint),)


def signal_plan(resampled, sessions):
    """Read completed prices at exact exchange slots, never substitute an older day."""
    if tuple(sorted(set(sessions))) != tuple(sessions):
        raise ValueError("sessions must be sorted and unique")
    boundaries = {}
    for day in sessions:
        boundaries[day] = (
            paper._CALENDAR.session_open(str(day)).to_pydatetime(),
            paper._CALENDAR.session_close(str(day)).to_pydatetime(),
            paper._CALENDAR.previous_session(str(day)).date(),
        )
    plan = {}
    for symbol in paper.EXPECTED_UNIVERSE:
        by_day = resampled[symbol]
        for day in sessions:
            start, close, previous = boundaries[day]
            bars = by_day[day]
            for index, bar in enumerate(bars):
                if (bar.symbol != symbol or bar.session_date != day or bar.bar_index != index
                        or bar.timeframe_minutes != 5 or bar.base_bar_count != 1
                        or bar.timestamp_utc != start + timedelta(minutes=5*index)
                        or bar.end_utc != bar.timestamp_utc + timedelta(minutes=5)
                        or bar.end_utc > close):
                    raise ValueError("late-session requires contiguous calendar-aligned 5m bars")
            previous_bars = by_day.get(previous, ())
            previous_close = None
            if previous_bars:
                last = previous_bars[-1]
                expected_close = paper._CALENDAR.session_close(str(previous)).to_pydatetime()
                if (last.complete and last.end_utc == expected_close
                        and math.isfinite(last.close) and last.close > 0):
                    previous_close = last.close
            first = None
            for bar in bars:
                if bar.end_utc == start + timedelta(minutes=30):
                    first = bar.close if bar.complete and math.isfinite(bar.close) else None
                buy = (
                    bar.end_utc == close - timedelta(minutes=30)
                    and bar.complete and bar.entry_eligible and math.isfinite(bar.close)
                    and previous_close is not None and first is not None
                    and first > previous_close and bar.close > previous_close
                )
                plan[(symbol, day, bar.bar_index)] = (
                    bool(buy), bar.end_utc == close - timedelta(minutes=5),
                )
    return plan


def load_development(bars_dir: Path, manifest: Path, prior):
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256:
        raise ValueError("only frozen development manifest accepted; price files not read")
    return paper.load_intraday_dataset(bars_dir, manifest, prior)


def run_development(dataset, contract, prior, *, code_commit: str):
    if not re.fullmatch(r"[0-9a-f]{40}", code_commit):
        raise ValueError("invalid code commit")
    validate_development(dataset, contract)
    resampled = paper.resample_dataset(dataset, 5)
    signals = signal_plan(resampled, dataset.sessions)
    evaluation_sessions = dataset.sessions[1:]
    if len(evaluation_sessions) != contract["development"]["evaluation_sessions"]:
        raise ValueError("evaluation session count mismatch")
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
        "warmup_session_count": 1, "evaluation_session_count": len(evaluation_sessions),
        "evaluations": evaluations, "selected_candidate_id": selected, "rejection_reasons": reasons,
        "verdict": "CONFIRMATION_REQUIRED" if selected else "DEVELOPMENT_REJECTED",
        "holdout_read": False, "minimum_cumulative_trials": 32,
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
