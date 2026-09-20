"""Frozen spec 190 research; deliberately has no broker or network access."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from auto_invest.analytics import intraday_paper_challenger as paper
from auto_invest.analytics.backtest_overfitting import (
    deflated_sharpe_from_trials,
    probability_of_backtest_overfitting,
)

CONTRACT_SHA256 = "234d71ad3418c10d1f8bcd6c0e6fcf72eece1a6b41d75bed2d912423d8efd181"


def load_contract(path: Path, prior_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
        raise ValueError("spec 190 preregistration differs from the pre-evaluation seal")
    contract = json.loads(raw)
    if hashlib.sha256(prior_path.read_bytes()).hexdigest() != contract["prior_contract_sha256"]:
        raise ValueError("prior contract fingerprint mismatch")
    return contract, paper.load_preregistration(prior_path)


def candidate_registry(contract: Mapping[str, Any]) -> tuple[paper.IntradayCandidate, ...]:
    candidates = []
    for timeframe in contract["timeframes_minutes"]:
        for buffer in contract["breakout_buffer_bps"]:
            identity = {
                "contract_sha256": CONTRACT_SHA256,
                "candidate_id": f"cost-aware-orb-{timeframe}m-{buffer}bp",
                "family": "opening_range_breakout",
                "timeframe_minutes": timeframe,
                "variant": f"cost-{buffer // 62}",
                "parameters": {"range_bars": 1, "breakout_buffer_bps": buffer},
            }
            fingerprint = paper._sha256(paper._canonical_bytes(identity))
            del identity["contract_sha256"]
            candidates.append(paper.IntradayCandidate(**identity, strategy_fingerprint=fingerprint))
    return tuple(candidates)


def select_development(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[str | None, dict[str, list[str]]]:
    """Filter on development only, then retain the prior deterministic rank order."""
    eligible = []
    rejected = {}
    for row in rows:
        reasons = []
        for model in ("base", "stress"):
            for field in ("net_return_pct", "annualized_sharpe", "max_drawdown_pct",
                          "turnover_usd", "closed_trade_count", "unclosed_quantity"):
                if not math.isfinite(float(row[model][field])):
                    raise ValueError(f"non-finite development metric: {field}")
            if float(row[model]["net_return_pct"]) <= 0:
                reasons.append(f"{model}_net_not_positive")
            if int(row[model]["unclosed_quantity"]) != 0:
                reasons.append(f"{model}_positions_unclosed")
        if int(row["base"]["closed_trade_count"]) < 200:
            reasons.append("minimum_development_trades_not_met")
        rejected[str(row["candidate_id"])] = reasons
        if not reasons:
            eligible.append(row)
    if not eligible:
        return None, rejected
    selected = min(eligible, key=lambda row: (
        -float(row["base"]["annualized_sharpe"]),
        float(row["base"]["max_drawdown_pct"]),
        float(row["base"]["turnover_usd"]),
        str(row["candidate_id"]),
    ))
    return str(selected["candidate_id"]), rejected


def validate_development(dataset: paper.IntradayDataset, contract: Mapping[str, Any]) -> None:
    expected = contract["development"]
    if dataset.synthetic or dataset.quality_reasons or not dataset.sessions:
        raise ValueError("development dataset is synthetic, empty, or incomplete")
    if (
        dataset.dataset_fingerprint != expected["dataset_fingerprint"]
        or len(dataset.sessions) != expected["sessions"]
        or dataset.sessions[0].isoformat() != expected["first_session"]
        or dataset.sessions[-1].isoformat() != expected["last_session"]
    ):
        raise ValueError("development dataset does not match the preregistered interval")


def run_development(
    dataset: paper.IntradayDataset,
    contract: Mapping[str, Any],
    prior: Mapping[str, Any],
    *,
    code_commit: str,
) -> tuple[dict[str, Any], bytes]:
    validate_development(dataset, contract)
    registry = candidate_registry(contract)
    cache = {tf: paper.resample_dataset(dataset, tf) for tf in (30, 60)}
    evaluations = []
    ledger_rows = []
    for candidate in registry:
        row = candidate.as_dict()
        for model in ("base", "stress"):
            run = paper.simulate_candidate(
                candidate, cache[candidate.timeframe_minutes], dataset.sessions, prior,
                cost_model_name=model,
            )
            row[model] = {
                **paper._window_metrics(
                    run, dataset.sessions, capital=float(prior["portfolio"]["initial_capital_usd"]),
                ),
                "unclosed_quantity": run.unclosed_quantity,
                "turnover_usd": run.turnover_usd,
                "total_cost_usd": run.total_cost_usd,
            }
            ledger_rows.extend(run.ledger_rows)
        evaluations.append(row)
    selected, reasons = select_development(evaluations)
    ledger = paper._ledger_bytes(ledger_rows)
    payload = {
        "schema_version": "1.0",
        "family_id": contract["family_id"],
        "stage": "development",
        "contract_sha256": CONTRACT_SHA256,
        "code_commit": code_commit,
        "dataset_fingerprint": dataset.dataset_fingerprint,
        "session_count": len(dataset.sessions),
        "evaluations": evaluations,
        "selected_candidate_id": selected,
        "rejection_reasons": reasons,
        "verdict": "SELECTION_SEALED" if selected else "DEVELOPMENT_REJECTED",
        "holdout_read": False,
        "ledger_sha256": paper._sha256(ledger),
        "ledger_row_count": len(ledger_rows),
        "safety": dict(paper.EXPECTED_SAFETY),
    }
    payload["content_sha256"] = paper._sha256(paper._canonical_bytes(payload))
    return payload, ledger


def validate_seal(payload: Mapping[str, Any], ledger: bytes, *, stage: str) -> None:
    body = dict(payload)
    seal = body.pop("content_sha256", None)
    if seal != paper._sha256(paper._canonical_bytes(body)):
        raise ValueError("evidence content fingerprint mismatch")
    if body.get("stage") != stage or body.get("contract_sha256") != CONTRACT_SHA256:
        raise ValueError("evidence stage or contract mismatch")
    if body.get("safety") != paper.EXPECTED_SAFETY:
        raise ValueError("research safety boundary mismatch")
    if not re.fullmatch(r"[0-9a-f]{40}", str(body.get("code_commit", ""))):
        raise ValueError("invalid evidence code commit")
    if body.get("ledger_sha256") != paper._sha256(ledger):
        raise ValueError("evidence ledger fingerprint mismatch")
    if body.get("ledger_row_count") != len(ledger.splitlines()):
        raise ValueError("evidence ledger row count mismatch")


def verify_development(
    payload: Mapping[str, Any], ledger: bytes, dataset: paper.IntradayDataset,
    contract: Mapping[str, Any], prior: Mapping[str, Any],
) -> dict[str, Any]:
    """Reconstruct evidence from source bars, not from self-reported metrics or hashes."""
    validate_seal(payload, ledger, stage="development")
    expected, expected_ledger = run_development(
        dataset, contract, prior, code_commit=str(payload["code_commit"]),
    )
    if (expected_ledger != ledger
            or paper._canonical_bytes(expected) != paper._canonical_bytes(payload)):
        raise ValueError("development evidence differs from independent source replay")
    return expected


def require_selected_development(payload: Mapping[str, Any]) -> str:
    if payload.get("verdict") != "SELECTION_SEALED" or not payload.get("selected_candidate_id"):
        raise ValueError("development rejected; holdout must remain unopened")
    return str(payload["selected_candidate_id"])


def validate_holdout(
    dataset: paper.IntradayDataset, development: paper.IntradayDataset,
    contract: Mapping[str, Any],
) -> None:
    expected = contract["holdout"]
    if dataset.synthetic or dataset.quality_reasons or not dataset.sessions:
        raise ValueError("holdout is synthetic, empty, or incomplete")
    if (
        len(dataset.sessions) != expected["sessions"]
        or dataset.sessions[0].isoformat() != expected["first_session"]
        or dataset.sessions[-1].isoformat() != expected["last_session"]
        or dataset.sessions[0] <= development.sessions[-1]
        or dataset.provider != development.provider
    ):
        raise ValueError("holdout period, provider, or development separation mismatch")
    calendar_sessions = tuple(
        stamp.date() for stamp in paper._CALENDAR.sessions_in_range(
            dataset.sessions[0].isoformat(), dataset.sessions[-1].isoformat(),
        )
    )
    if dataset.sessions != calendar_sessions:
        raise ValueError("holdout has missing or unordered calendar sessions")


def run_confirmation(
    dataset: paper.IntradayDataset, development: paper.IntradayDataset,
    verified_development: Mapping[str, Any], contract: Mapping[str, Any], prior: Mapping[str, Any],
    *, code_commit: str,
) -> tuple[dict[str, Any], bytes]:
    selected_id = require_selected_development(verified_development)
    validate_development(development, contract)
    validate_holdout(dataset, development, contract)
    new_registry = candidate_registry(contract)
    if selected_id not in {row.candidate_id for row in new_registry}:
        raise ValueError("selected candidate is outside the frozen six")
    registry = (*paper.build_candidate_registry(prior), *new_registry)
    if len(registry) != 24 or len({c.strategy_fingerprint for c in registry}) != 24:
        raise ValueError("multiplicity registry must retain all 18 prior and 6 new trials")
    cache_dev = {tf: paper.resample_dataset(development, tf) for tf in (15, 30, 60)}
    cache_holdout = {tf: paper.resample_dataset(dataset, tf) for tf in (15, 30, 60)}
    block_count = contract["holdout"]["block_sessions"]
    block, confirmation = dataset.sessions[:block_count], dataset.sessions[block_count:]
    trials, scores, sharpes, ledger_rows = [], [], [], []
    selected = None
    for candidate in registry:
        dev_run = paper.simulate_candidate(
            candidate, cache_dev[candidate.timeframe_minutes], development.sessions, prior,
            cost_model_name="base",
        )
        base = paper.simulate_candidate(
            candidate, cache_holdout[candidate.timeframe_minutes], dataset.sessions, prior,
            cost_model_name="base",
        )
        stress = paper.simulate_candidate(
            candidate, cache_holdout[candidate.timeframe_minutes], dataset.sessions, prior,
            cost_model_name="stress",
        )
        capital = float(prior["portfolio"]["initial_capital_usd"])
        dev_metrics = paper._window_metrics(dev_run, development.sessions, capital=capital)
        row = paper._candidate_evaluation(
            candidate, base, stress, (), block, confirmation, capital=capital,
        )
        row["base"]["development"] = dev_metrics
        row["development_turnover_usd"] = dev_run.turnover_usd
        trials.append(row)
        scores.append(paper._segment_scores(
            dev_metrics["daily_returns"], segments=contract["development"]["pbo_segments"],
        ))
        sharpes.append(float(row["base"]["confirmation"]["annualized_sharpe"]))
        ledger_rows.extend(base.ledger_rows)
        ledger_rows.extend(stress.ledger_rows)
        if candidate.candidate_id == selected_id:
            selected = row
    if selected is None:
        raise ValueError("selected candidate missing from replay")
    pbo_value = probability_of_backtest_overfitting(scores)
    dsr_value = deflated_sharpe_from_trials(
        selected["base"]["confirmation"]["daily_returns"], sharpes, periods_per_year=252,
        effective_trial_count=24,
    )
    pbo = None if pbo_value is None else float(pbo_value)
    dsr = None if dsr_value is None else float(dsr_value)
    gates, reasons = paper._decision_for_complete_data(
        selected, prior, development_pbo=pbo, selected_dsr=dsr,
    )
    ledger = paper._ledger_bytes(ledger_rows)
    payload = {
        "schema_version": "1.0", "family_id": contract["family_id"], "stage": "confirmation",
        "contract_sha256": CONTRACT_SHA256, "code_commit": code_commit,
        "development_content_sha256": verified_development["content_sha256"],
        "dataset_fingerprint": dataset.dataset_fingerprint,
        "selected_candidate_id": selected_id, "evaluations": trials,
        "session_count": len(dataset.sessions), "block_sessions": len(block),
        "confirmation_sessions": len(confirmation), "trial_count": len(trials),
        "development_pbo": pbo, "selected_dsr": dsr, "gates": gates, "reasons": reasons,
        "verdict": "RESEARCH_REJECTED" if reasons else "RESEARCH_PASSED",
        "holdout_read": True, "ledger_sha256": paper._sha256(ledger),
        "ledger_row_count": len(ledger_rows), "safety": dict(paper.EXPECTED_SAFETY),
    }
    payload["content_sha256"] = paper._sha256(paper._canonical_bytes(payload))
    return payload, ledger


def verify_confirmation(
    payload: Mapping[str, Any], ledger: bytes, dataset: paper.IntradayDataset,
    development: paper.IntradayDataset, verified_development: Mapping[str, Any],
    contract: Mapping[str, Any], prior: Mapping[str, Any],
) -> dict[str, Any]:
    validate_seal(payload, ledger, stage="confirmation")
    expected, expected_ledger = run_confirmation(
        dataset, development, verified_development, contract, prior,
        code_commit=str(payload["code_commit"]),
    )
    if (expected_ledger != ledger
            or paper._canonical_bytes(expected) != paper._canonical_bytes(payload)):
        raise ValueError("confirmation evidence differs from independent source replay")
    return expected
