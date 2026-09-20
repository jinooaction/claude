"""Spec 191 development diagnostics; no holdout, broker, or promotion path."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from auto_invest.analytics import intraday_paper_challenger as paper
from auto_invest.analytics.cost_aware_intraday import select_development, validate_development

CONTRACT_SHA256 = "6665cab7eb7fb87b6ee11258f8323455087b00471036ed149006948961af9761"
MANIFEST_SHA256 = "c4b6c6336ee0747464fde730f6d894ba3b8814c14567406f49cb0e528ea8fdfc"
LIMITATIONS = [
    "development_only_not_strategy_acceptance",
    "signal_headroom_not_guaranteed_at_next_open",
    "close_triggered_stop_not_maximum_loss_guarantee",
    "fill_bar_total_volume_is_hindsight_liquidity_assumption",
    "session_exit_at_final_resampled_open_not_exchange_close",
    "adjusted_prices_not_verified_execution_equivalence",
]


def load_contract(path: Path, prior_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
        raise ValueError("spec 191 contract differs from the pre-evaluation seal")
    contract = json.loads(raw)
    if hashlib.sha256(prior_path.read_bytes()).hexdigest() != contract["prior_contract_sha256"]:
        raise ValueError("prior contract fingerprint mismatch")
    return contract, paper.load_preregistration(prior_path)


def candidate_registry(contract: Mapping[str, Any]) -> tuple[paper.IntradayCandidate, ...]:
    rows = []
    for timeframe in contract["timeframes_minutes"]:
        for variant in contract["exit_variants"]:
            identity = {
                "candidate_id": f"shock-recovery-{timeframe}m-{variant}",
                "family": "shock_recovery",
                "timeframe_minutes": timeframe,
                "variant": variant,
                "parameters": {
                    "shock_bps": contract["shock_bps"],
                    "headroom_bps": contract["headroom_bps"],
                    "stop_bps": contract["stop_bps"],
                    "exit_at_anchor": int(variant == "anchor"),
                },
            }
            fingerprint = paper._sha256(paper._canonical_bytes({
                **identity, "contract_sha256": CONTRACT_SHA256,
            }))
            rows.append(paper.IntradayCandidate(**identity, strategy_fingerprint=fingerprint))
    return tuple(rows)


def load_development(bars_dir: Path, manifest: Path, prior: Mapping[str, Any]):
    # Refuse a different manifest before opening any of its price files.
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256:
        raise ValueError("only the frozen development manifest is accepted; price files not read")
    return paper.load_intraday_dataset(bars_dir, manifest, prior)


def run_development(dataset, contract, prior, *, code_commit: str) -> tuple[dict, bytes]:
    if not re.fullmatch(r"[0-9a-f]{40}", code_commit):
        raise ValueError("invalid code commit")
    validate_development(dataset, contract)
    cache = {tf: paper.resample_dataset(dataset, tf) for tf in contract["timeframes_minutes"]}
    evaluations, ledger_rows = [], []
    for candidate in candidate_registry(contract):
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
        "schema_version": "1.0", "family_id": contract["family_id"], "stage": "development",
        "contract_sha256": CONTRACT_SHA256, "code_commit": code_commit,
        "dataset_fingerprint": dataset.dataset_fingerprint, "session_count": len(dataset.sessions),
        "evaluations": evaluations, "selected_candidate_id": selected, "rejection_reasons": reasons,
        "verdict": "CONFIRMATION_REQUIRED" if selected else "DEVELOPMENT_REJECTED",
        "holdout_read": False, "minimum_cumulative_trials": 28,
        "ledger_sha256": paper._sha256(ledger), "ledger_row_count": len(ledger_rows),
        "safety": dict(paper.EXPECTED_SAFETY), "limitations": list(LIMITATIONS),
    }
    payload["content_sha256"] = paper._sha256(paper._canonical_bytes(payload))
    return payload, ledger


def validate_seal(payload: Mapping[str, Any], ledger: bytes) -> None:
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


def verify_development(payload, ledger: bytes, dataset, contract, prior) -> dict:
    validate_seal(payload, ledger)
    expected, expected_ledger = run_development(
        dataset, contract, prior, code_commit=payload["code_commit"],
    )
    if (ledger != expected_ledger
            or paper._canonical_bytes(payload) != paper._canonical_bytes(expected)):
        raise ValueError("evidence differs from source replay")
    return expected
