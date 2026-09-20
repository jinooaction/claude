"""Frozen spec 190 research; deliberately has no broker or network access."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from auto_invest.analytics import intraday_paper_challenger as paper

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
