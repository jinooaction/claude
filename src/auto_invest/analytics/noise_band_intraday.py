"""Frozen long-only noise-band development research, without broker access."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import timedelta
from pathlib import Path

from auto_invest.analytics import intraday_paper_challenger as paper
from auto_invest.analytics.cost_aware_intraday import select_development, validate_development

CONTRACT_SHA256 = "023d00aa5df81b1ff603c0b19f63b7dce7a6f405c41fe441571e8ff7866d3a54"
MANIFEST_SHA256 = "c4b6c6336ee0747464fde730f6d894ba3b8814c14567406f49cb0e528ea8fdfc"
LIMITATIONS = [
    "development_only_not_strategy_acceptance",
    "long_only_one_attempt_variant_not_source_paper_replication",
    "source_paper_period_overlaps_future_confirmation",
    "fill_bar_total_volume_is_hindsight_liquidity_assumption",
    "session_exit_at_final_resampled_open_not_exchange_close",
    "adjusted_prices_not_verified_execution_equivalence",
    "bar_typical_price_vwap_not_trade_level_vwap",
]


def load_contract(path: Path, prior_path: Path):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
        raise ValueError("spec 192 contract differs from pre-evaluation seal")
    contract = json.loads(raw)
    if hashlib.sha256(prior_path.read_bytes()).hexdigest() != contract["prior_contract_sha256"]:
        raise ValueError("prior contract fingerprint mismatch")
    return contract, paper.load_preregistration(prior_path)


def candidate_registry(contract):
    identity = {
        "candidate_id": "noise-band-30m-long-once", "family": "noise_band",
        "timeframe_minutes": contract["timeframe_minutes"], "variant": "long_once",
        "parameters": {"lookback_sessions": contract["lookback_sessions"]},
    }
    fingerprint = paper._sha256(paper._canonical_bytes({
        **identity, "contract_sha256": CONTRACT_SHA256,
    }))
    return (paper.IntradayCandidate(**identity, strategy_fingerprint=fingerprint),)


def signal_plan(resampled, sessions):
    """Use only the preceding 14 exchange sessions and today's completed prefix.

    Resampled rows must come from the validated loader. Check slot continuity here
    too, so direct callers cannot silently align missing bars by list position.
    """
    if tuple(sorted(set(sessions))) != tuple(sessions):
        raise ValueError("sessions must be sorted and unique")
    plan = {}
    histories = {}
    for session in sessions:
        previous = paper._CALENDAR.previous_session(str(session))
        histories[session] = tuple(
            stamp.date() for stamp in paper._CALENDAR.sessions_window(previous, -14)
        )
    for symbol in paper.EXPECTED_UNIVERSE:
        by_day = resampled[symbol]
        for session in sessions:
            bars = by_day[session]
            for index, bar in enumerate(bars):
                if (bar.bar_index != index or bar.timeframe_minutes != 30
                        or not bar.complete or bar.base_bar_count != 6
                        or bar.timestamp_utc != bars[0].timestamp_utc + timedelta(minutes=30*index)
                        or bar.end_utc != bar.timestamp_utc + timedelta(minutes=30)):
                    raise ValueError("noise-band requires contiguous complete 30-minute bars")
            history = [by_day.get(day, ()) for day in histories[session]]
            for index, bar in enumerate(bars):
                key = (symbol, session, bar.bar_index)
                plan[key] = (False, False)
                if (len(history) != 14 or any(len(day) <= index for day in history)
                        or any(not day[index].complete or day[index].bar_index != index
                               or day[0].open <= 0 for day in history)):
                    continue
                mean = sum(abs(day[index].close / day[0].open - 1) for day in history) / 14
                upper = max(bars[0].open, history[-1][-1].close) * (1 + mean)
                vwap = paper._cumulative_vwap(bars, index)
                if vwap <= 0:
                    continue
                threshold = max(upper, vwap)
                plan[key] = (bar.entry_eligible and bar.close > threshold,
                             bar.close <= threshold)
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
    evaluation_sessions = dataset.sessions[14:]
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
        "warmup_session_count": 14, "evaluation_session_count": len(evaluation_sessions),
        "evaluations": evaluations, "selected_candidate_id": selected, "rejection_reasons": reasons,
        "verdict": "CONFIRMATION_REQUIRED" if selected else "DEVELOPMENT_REJECTED",
        "holdout_read": False, "minimum_cumulative_trials": 29,
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
