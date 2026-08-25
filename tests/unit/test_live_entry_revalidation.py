from __future__ import annotations

import tomllib
from pathlib import Path

from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.portfolio.autoarm import strategy_fingerprint_digest
from auto_invest.portfolio.live_entry_revalidation import (
    ACTIVE_LIVE_TRACK,
    ENTRY_BLOCKED,
    ENTRY_READY,
    evaluate_live_entry,
)

ROOT = Path(__file__).resolve().parents[2]


def _factory() -> tuple[dict, str]:
    config_text = (ROOT / "deploy/canary-live-portfolio.toml").read_text(encoding="utf-8")
    config = PortfolioRebalanceConfig.model_validate(tomllib.loads(config_text)["portfolio"])
    fingerprint = strategy_fingerprint_digest(config)
    return (
        {
            "gate_version": "2.0",
            "candidate_count": 16,
            "complete_trial_count": 16,
            "global_audit_trial_count": 704,
            "unique_trial_fingerprint_count": 704,
            "decision": {
                "verdict": "FACTORY_EDGE",
                "research_canary_eligible": True,
                "selected_candidate_id": "factory-winner",
                "selected_strategy_fingerprint": fingerprint,
                "selected_deploy_config": config_text,
                "gates": [
                    {
                        "gate_id": "complete_family_trials",
                        "passed": True,
                        "actual": "16",
                        "required": "16",
                    },
                    {
                        "gate_id": "prior_audit_complete",
                        "passed": True,
                        "actual": "688",
                        "required": "688",
                    },
                    {
                        "gate_id": "global_audit_trials",
                        "passed": True,
                        "actual": "704",
                        "required": "704",
                    },
                    {
                        "gate_id": "unique_audit_fingerprints",
                        "passed": True,
                        "actual": "704",
                        "required": "704",
                    },
                    {"gate_id": "holdout_excess_psr", "passed": True},
                ],
            },
        },
        fingerprint,
    )


def _profit(*, ready: bool = True, psr: float = 0.81) -> dict:
    return {
        "historical_verdict": "HOLDOUT_EDGE",
        "deployment_match": {
            "candidate_id": "globalfixed-ensemble-3-6-9-12",
            "historical_passed": True,
            "exploration_canary_ready": ready,
            "entry_policy": {"min_forward_obs": 40, "min_forward_psr": 0.8},
            "forward": {
                "n_obs": 47,
                "psr_vs_benchmark": psr,
                "beats_benchmark_calmar": True,
                "significance_method": "paired_active_return_psr_v1",
            },
        },
    }


def test_first_fill_requires_current_exploration_contract() -> None:
    result = evaluate_live_entry(
        _profit(), {"verdict": "PASS"}, {"fills_count": 0}, evidence_age_hours=2
    )
    assert result.allowed is True
    assert result.state == ENTRY_READY


def test_stale_entry_approval_fails_closed() -> None:
    result = evaluate_live_entry(
        _profit(ready=False, psr=0.60173),
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=2,
    )
    assert result.allowed is False
    assert result.state == ENTRY_BLOCKED
    assert "exploration_canary_ready" in result.reasons
    assert "forward_psr" in result.reasons


def test_legacy_forward_statistic_cannot_open_first_fill() -> None:
    profit = _profit()
    profit["deployment_match"]["forward"].pop("significance_method")

    result = evaluate_live_entry(
        profit, {"verdict": "PASS"}, {"fills_count": 0}, evidence_age_hours=2
    )

    assert result.allowed is False
    assert "forward_significance_method" in result.reasons


def test_missing_or_old_evidence_fails_closed_before_first_fill() -> None:
    missing = evaluate_live_entry(None, None, {"fills_count": 0}, evidence_age_hours=None)
    old = evaluate_live_entry(
        _profit(), {"verdict": "PASS"}, {"fills_count": 0}, evidence_age_hours=40
    )
    assert missing.allowed is False
    assert old.allowed is False
    assert "evidence_fresh" in old.reasons


def test_existing_fill_defers_to_live_risk_gates() -> None:
    result = evaluate_live_entry(None, None, {"fills_count": 1}, evidence_age_hours=None)
    assert result.allowed is True
    assert result.state == ACTIVE_LIVE_TRACK


def test_invalid_fill_count_never_opens_first_entry() -> None:
    result = evaluate_live_entry(_profit(), {"verdict": "PASS"}, {}, evidence_age_hours=1)
    assert result.allowed is False
    assert result.fills_count is None


def test_factory_winner_can_open_only_the_exact_10pct_strategy() -> None:
    factory, fingerprint = _factory()
    ready = evaluate_live_entry(
        None,
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=None,
        factory_evidence=factory,
        factory_evidence_age_hours=2,
        live_strategy_fingerprint=fingerprint,
    )
    mismatch = evaluate_live_entry(
        None,
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=None,
        factory_evidence=factory,
        factory_evidence_age_hours=2,
        live_strategy_fingerprint="sha256:other",
    )
    assert ready.allowed is True
    assert ready.evidence["entry_source"] == "strategy_factory"
    assert mismatch.allowed is False
    assert "factory_strategy_fingerprint" in mismatch.reasons


def test_incomplete_or_stale_factory_evidence_fails_closed() -> None:
    factory = {
        "candidate_count": 64,
        "complete_trial_count": 63,
        "decision": {
            "verdict": "FACTORY_EDGE",
            "research_canary_eligible": True,
            "selected_strategy_fingerprint": "sha256:exact",
            "selected_deploy_config": "[portfolio]\n",
            "gates": [{"gate_id": "complete_trials", "passed": True}],
        },
    }
    result = evaluate_live_entry(
        None,
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=None,
        factory_evidence=factory,
        factory_evidence_age_hours=40,
        live_strategy_fingerprint="sha256:exact",
    )
    assert result.allowed is False
    assert "factory_contract_complete" in result.reasons
    assert "factory_evidence_fresh" in result.reasons
