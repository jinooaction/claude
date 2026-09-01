from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from auto_invest.analytics.intraday_paper_challenger import (
    build_candidate_registry,
    load_preregistration,
)
from auto_invest.analytics.intraday_paper_challenger_evidence import assess_intraday_evidence

PREREGISTRATION = Path(
    "specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json"
)


def _insufficient_payload() -> tuple[dict[str, object], bytes]:
    prereg = load_preregistration(PREREGISTRATION)
    registry = [candidate.as_dict() for candidate in build_candidate_registry(prereg)]
    ledger = b""
    return (
        {
            "schema_version": "1.0",
            "gate_version": "intraday-paper-v1",
            "family_id": "intraday-etf-long-flat-diagnostic-v1",
            "generated_at_utc": "2026-09-02T00:00:00Z",
            "code_commit": "test",
            "preregistration_sha256": "sha256:"
            + hashlib.sha256(PREREGISTRATION.read_bytes()).hexdigest(),
            "data_quality": {
                "complete": False,
                "synthetic": False,
                "dataset_fingerprint": "sha256:" + "1" * 64,
                "session_count": 0,
                "reasons": ["minimum_total_sessions_not_met"],
            },
            "candidate_registry": registry,
            "evaluations": [],
            "selection": {
                "selected_candidate_id": None,
                "development_only": True,
                "candidate_count": 18,
                "development_pbo": None,
                "selected_dsr": None,
            },
            "decision": {
                "verdict": "INSUFFICIENT_EVIDENCE",
                "passed": False,
                "gates": {"data_complete": False},
                "reasons": ["minimum_total_sessions_not_met"],
                "next_step": "provide at least 756 complete XNYS sessions",
            },
            "audit": {
                "ledger_row_count": 0,
                "ledger_sha256": "sha256:" + hashlib.sha256(ledger).hexdigest(),
            },
            "safety": prereg["safety"],
        },
        ledger,
    )


def _window_metrics(*, sharpe: float = 1.2, net_return_pct: float = 2.0) -> dict[str, object]:
    return {
        "closed_trade_count": 70,
        "net_return_pct": net_return_pct,
        "annualized_sharpe": sharpe,
        "psr": 0.96,
        "max_drawdown_pct": 10.0,
        "profit_factor": 1.2,
        "positive_quarter_fraction": 0.75,
        "max_single_symbol_positive_contribution_fraction": 0.4,
        "top_five_trade_positive_contribution_fraction": 0.3,
        "daily_returns": [0.001, 0.002],
    }


def _complete_payload(*, confirmation_sharpe: float = 1.2) -> tuple[dict[str, object], bytes]:
    prereg = load_preregistration(PREREGISTRATION)
    registry = [candidate.as_dict() for candidate in build_candidate_registry(prereg)]
    evaluations: list[dict[str, object]] = []
    for index, candidate in enumerate(registry):
        development = _window_metrics(sharpe=2.0 if index == 0 else 1.0)
        evaluations.append(
            {
                **candidate,
                "base": {
                    "development": development,
                    "block": _window_metrics(),
                    "confirmation": _window_metrics(sharpe=confirmation_sharpe),
                    "total_cost_usd": 100.0,
                    "turnover_usd": 10_000.0 + index,
                    "unclosed_quantity": 0,
                },
                "stress": {
                    "confirmation": _window_metrics(net_return_pct=1.0),
                    "total_cost_usd": 150.0,
                    "turnover_usd": 10_000.0,
                    "unclosed_quantity": 0,
                },
            }
        )
    selected_id = registry[0]["candidate_id"]
    gates = {
        "block_net_positive": True,
        "confirmation_net_positive": True,
        "confirmation_sharpe": confirmation_sharpe >= 1.0,
        "confirmation_psr": True,
        "selected_dsr": True,
        "development_pbo": True,
        "max_drawdown": True,
        "profit_factor": True,
        "positive_quarters": True,
        "symbol_concentration": True,
        "trade_concentration": True,
        "stress_net_positive": True,
        "base_positions_closed": True,
        "stress_positions_closed": True,
    }
    verdict = "PAPER_CHALLENGER" if all(gates.values()) else "NO_INTRADAY_EDGE"
    ledger = b""
    return (
        {
            "schema_version": "1.0",
            "gate_version": "intraday-paper-v1",
            "family_id": "intraday-etf-long-flat-diagnostic-v1",
            "generated_at_utc": "2026-09-02T00:00:00Z",
            "code_commit": "test",
            "preregistration_sha256": "sha256:"
            + hashlib.sha256(PREREGISTRATION.read_bytes()).hexdigest(),
            "data_quality": {
                "complete": True,
                "synthetic": False,
                "dataset_fingerprint": "sha256:" + "1" * 64,
                "session_count": 756,
                "reasons": [],
            },
            "candidate_registry": registry,
            "evaluations": evaluations,
            "selection": {
                "selected_candidate_id": selected_id,
                "development_only": True,
                "candidate_count": 18,
                "development_pbo": 0.2,
                "selected_dsr": 0.96,
            },
            "decision": {
                "verdict": verdict,
                "passed": verdict == "PAPER_CHALLENGER",
                "gates": gates,
                "reasons": [name for name, passed in gates.items() if not passed],
                "next_step": "test",
            },
            "audit": {
                "ledger_row_count": 0,
                "ledger_sha256": "sha256:" + hashlib.sha256(ledger).hexdigest(),
            },
            "safety": prereg["safety"],
        },
        ledger,
    )


def test_independent_consumer_accepts_consistent_insufficient_evidence() -> None:
    payload, ledger = _insufficient_payload()
    assessment = assess_intraday_evidence(
        payload,
        load_preregistration(PREREGISTRATION),
        preregistration_bytes=PREREGISTRATION.read_bytes(),
        ledger_bytes=ledger,
    )

    assert assessment.valid is True
    assert assessment.verdict == "INSUFFICIENT_EVIDENCE"
    assert assessment.capital_eligible is False
    assert assessment.reasons == ()


def test_independent_consumer_rejects_safety_and_ledger_tampering() -> None:
    payload, ledger = _insufficient_payload()
    tampered = copy.deepcopy(payload)
    tampered["safety"]["capital_fraction"] = 0.1
    tampered["audit"]["ledger_sha256"] = "sha256:" + "0" * 64

    assessment = assess_intraday_evidence(
        tampered,
        load_preregistration(PREREGISTRATION),
        preregistration_bytes=PREREGISTRATION.read_bytes(),
        ledger_bytes=ledger,
    )

    assert assessment.valid is False
    assert "safety_contract_mismatch" in assessment.reasons
    assert "ledger_digest_mismatch" in assessment.reasons


def test_independent_consumer_rejects_candidate_identity_tampering() -> None:
    payload, ledger = _insufficient_payload()
    tampered = json.loads(json.dumps(payload))
    tampered["candidate_registry"][0]["candidate_id"] = "changed-after-results"

    assessment = assess_intraday_evidence(
        tampered,
        load_preregistration(PREREGISTRATION),
        preregistration_bytes=PREREGISTRATION.read_bytes(),
        ledger_bytes=ledger,
    )

    assert assessment.valid is False
    assert "candidate_registry_mismatch" in assessment.reasons


def test_independent_consumer_recalculates_complete_paper_challenger() -> None:
    payload, ledger = _complete_payload()

    assessment = assess_intraday_evidence(
        payload,
        load_preregistration(PREREGISTRATION),
        preregistration_bytes=PREREGISTRATION.read_bytes(),
        ledger_bytes=ledger,
    )

    assert assessment.valid is True
    assert assessment.verdict == "PAPER_CHALLENGER"
    assert assessment.capital_eligible is False


def test_independent_consumer_accepts_complete_no_edge_when_metric_fails() -> None:
    payload, ledger = _complete_payload(confirmation_sharpe=0.5)

    assessment = assess_intraday_evidence(
        payload,
        load_preregistration(PREREGISTRATION),
        preregistration_bytes=PREREGISTRATION.read_bytes(),
        ledger_bytes=ledger,
    )

    assert assessment.valid is True
    assert assessment.verdict == "NO_INTRADAY_EDGE"


def test_holdout_metric_change_cannot_change_development_selection() -> None:
    payload, ledger = _complete_payload()
    payload["evaluations"][1]["base"]["confirmation"]["annualized_sharpe"] = 99.0

    assessment = assess_intraday_evidence(
        payload,
        load_preregistration(PREREGISTRATION),
        preregistration_bytes=PREREGISTRATION.read_bytes(),
        ledger_bytes=ledger,
    )

    assert assessment.valid is True
    assert (
        payload["selection"]["selected_candidate_id"] == payload["evaluations"][0]["candidate_id"]
    )


def test_complete_data_with_too_few_trades_is_insufficient() -> None:
    payload, ledger = _complete_payload()
    selected = payload["evaluations"][0]
    selected["base"]["development"]["closed_trade_count"] = 66
    selected["base"]["block"]["closed_trade_count"] = 66
    selected["base"]["confirmation"]["closed_trade_count"] = 67
    payload["decision"] = {
        "verdict": "INSUFFICIENT_EVIDENCE",
        "passed": False,
        "gates": {
            "data_complete": True,
            "minimum_base_cost_closed_trades": False,
        },
        "reasons": ["minimum_base_cost_closed_trades_not_met"],
        "next_step": "collect more trades",
    }

    assessment = assess_intraday_evidence(
        payload,
        load_preregistration(PREREGISTRATION),
        preregistration_bytes=PREREGISTRATION.read_bytes(),
        ledger_bytes=ledger,
    )

    assert assessment.valid is True
    assert assessment.verdict == "INSUFFICIENT_EVIDENCE"


def test_independent_consumer_rejects_gate_and_verdict_tampering() -> None:
    payload, ledger = _complete_payload(confirmation_sharpe=0.5)
    tampered = copy.deepcopy(payload)
    tampered["decision"]["gates"]["confirmation_sharpe"] = True
    tampered["decision"]["verdict"] = "PAPER_CHALLENGER"
    tampered["decision"]["passed"] = True

    assessment = assess_intraday_evidence(
        tampered,
        load_preregistration(PREREGISTRATION),
        preregistration_bytes=PREREGISTRATION.read_bytes(),
        ledger_bytes=ledger,
    )

    assert assessment.valid is False
    assert "decision_gate_recalculation_mismatch" in assessment.reasons
    assert "verdict_recalculation_mismatch" in assessment.reasons


def test_independent_consumer_rejects_evaluation_identity_tampering() -> None:
    payload, ledger = _complete_payload()
    payload["evaluations"][0]["strategy_fingerprint"] = "sha256:" + "0" * 64

    assessment = assess_intraday_evidence(
        payload,
        load_preregistration(PREREGISTRATION),
        preregistration_bytes=PREREGISTRATION.read_bytes(),
        ledger_bytes=ledger,
    )

    assert assessment.valid is False
    assert "evaluation_identity_mismatch" in assessment.reasons


def test_independent_consumer_rejects_self_consistent_lookahead_ledger() -> None:
    payload, _ = _insufficient_payload()
    candidate_id = payload["candidate_registry"][0]["candidate_id"]
    row = {
        "candidate_id": candidate_id,
        "cost_model": "base",
        "session_date": "2024-01-02",
        "symbol": "SPY",
        "side": "BUY",
        "signal_at_utc": "2024-01-02T15:00:00Z",
        "eligible_at_utc": "2024-01-02T15:00:00Z",
        "filled_at_utc": "2024-01-02T15:00:00Z",
        "requested_qty": 10,
        "filled_qty": 10,
        "unfilled_qty": 0,
        "reference_price": 100.0,
        "fill_price": 100.1,
        "commission_usd": 1.0,
        "spread_usd": 0.1,
        "slippage_usd": 0.5,
        "gross_pnl_usd": None,
        "net_pnl_usd": None,
        "holding_minutes": None,
        "fill_status": "FULL",
        "reason": "strategy_entry",
    }
    ledger = json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    payload["audit"] = {
        "ledger_row_count": 1,
        "ledger_sha256": "sha256:" + hashlib.sha256(ledger).hexdigest(),
    }

    assessment = assess_intraday_evidence(
        payload,
        load_preregistration(PREREGISTRATION),
        preregistration_bytes=PREREGISTRATION.read_bytes(),
        ledger_bytes=ledger,
    )

    assert assessment.valid is False
    assert "ledger_row_contract_mismatch" in assessment.reasons
