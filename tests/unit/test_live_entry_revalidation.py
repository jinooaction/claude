from __future__ import annotations

import math
import tomllib
from decimal import Decimal
from pathlib import Path

from auto_invest.analytics.backtest_overfitting import (
    annualized_sharpe,
    deflated_sharpe_from_trials,
    effective_independent_trials,
    probability_of_backtest_overfitting,
)
from auto_invest.analytics.research_family_audit import (
    annotate_research_families,
    build_research_family_audit,
)
from auto_invest.config.caps import SizingCaps
from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.portfolio.autoarm import strategy_fingerprint_digest
from auto_invest.portfolio.fundability import assess_fundability
from auto_invest.portfolio.live_entry_revalidation import (
    ACTIVE_LIVE_TRACK,
    ENTRY_BLOCKED,
    ENTRY_READY,
    evaluate_live_entry,
)
from auto_invest.portfolio.operational_canary_evidence import (
    build_operational_canary_evidence,
)

ROOT = Path(__file__).resolve().parents[2]


def _operational_evidence(*, commit: str = "a" * 40, fingerprint: str) -> dict:
    dates: list[str] = []
    year, month = 1991, 1
    for _ in range(360):
        dates.append(f"{year:04d}-{month:02d}-01")
        month += 1
        if month == 13:
            year += 1
            month = 1
    candidate = [1.012 if index % 2 == 0 else 0.998 for index in range(360)]
    benchmark = [1.010 if index % 2 == 0 else 0.985 for index in range(360)]
    return build_operational_canary_evidence(
        dates=dates,
        candidate_monthly_factors=candidate,
        benchmark_monthly_factors=benchmark,
        development_months=180,
        annual_cost_bps=50,
        code_commit=commit,
        generated_at_utc="2026-08-31T01:00:00Z",
        strategy_fingerprint=fingerprint,
    )


def _research_calibration() -> dict:
    return {
        "research_entry_gate_version": "3.1",
        "verdict": "CALIBRATED",
        "code_commit": "abc123",
        "scenario": {"seed": 60_000, "repetitions": 500},
        "thresholds": {"holdout_psr_min": 0.95, "research_entry_pbo_max": 0.25},
        "required": {
            "family_false_acceptance_max": 0.01,
            "detection_min": 0.80,
            "program_false_acceptance_budget": 0.20,
            "maximum_research_families": 20,
        },
        "family_calibrations": {
            size: {
                "research_entry_calibrated": True,
                "null_research_entry_acceptance_rate": 0.01,
                "target_research_entry_detection_rate": 0.81,
            }
            for size in ("16", "64")
        },
    }


def _fundability(
    capital: Decimal = Decimal("1000"),
    *,
    canary_capital_pct: Decimal = Decimal("10"),
) -> dict:
    result = assess_fundability(
        target_weights={"AAA": Decimal("0.5"), "BBB": Decimal("0.5")},
        holdings={},
        prices={"AAA": Decimal("100"), "BBB": Decimal("100")},
        order_prices={"AAA": Decimal("100"), "BBB": Decimal("100")},
        planned_orders=[("AAA", "BUY", 4), ("BBB", "BUY", 5)],
        capital_usd=capital,
        invested_fraction=Decimal("0.99"),
        caps=SizingCaps(
            per_trade_pct=Decimal("50"),
            per_symbol_pct=Decimal("60"),
            global_exposure_pct=Decimal("100"),
            canary_capital_pct=canary_capital_pct,
            canary_min_duration_days=14,
            canary_acceptance_drawdown_pct=Decimal("10"),
        ),
    )
    return result.as_dict()


def _factory() -> tuple[dict, str]:
    config_text = (ROOT / "deploy/canary-live-portfolio.toml").read_text(encoding="utf-8")
    config = PortfolioRebalanceConfig.model_validate(tomllib.loads(config_text)["portfolio"])
    fingerprint = strategy_fingerprint_digest(config)
    prior = [
        {
            "candidate_id": f"prior-{index}",
            "strategy_fingerprint": f"sha256:prior-{index}",
            "status": "EXPLORATORY_REJECTED",
            "batch_id": "strategy-factory-test-prior",
        }
        for index in range(16)
    ]
    trials = [
        {
            "candidate_id": f"options-vrp-factory-{index}",
            "strategy_fingerprint": f"sha256:factory-{index}",
            "status": "complete",
        }
        for index in range(15)
    ] + [
        {
            "candidate_id": "options-vrp-factory-winner",
            "strategy_fingerprint": fingerprint,
            "status": "complete",
        }
    ]
    development_returns = []
    development_segments = []
    for index, row in enumerate(trials):
        mean = 0.005 if index == 15 else -0.001 + 0.00005 * index
        returns = [mean + 0.01 * math.sin(month * 1.7 + index) for month in range(80)]
        segments = [
            annualized_sharpe(returns[start : start + 10]) for start in range(0, 80, 10)
        ]
        row["holdout_psr"] = "0.999"
        development_returns.append(returns)
        development_segments.append(segments)
    dsr = deflated_sharpe_from_trials(
        development_returns[-1],
        [annualized_sharpe(row) for row in development_returns],
        effective_trial_count=effective_independent_trials(development_returns),
    )
    pbo = probability_of_backtest_overfitting(development_segments)
    assert dsr is not None and pbo is not None
    audit_records = annotate_research_families(prior + trials)
    trials = audit_records[-16:]
    family_audit = build_research_family_audit(audit_records)
    return (
        {
            "gate_version": "3.1",
            "code_commit": "abc123",
            "candidate_count": 16,
            "complete_trial_count": 16,
            "prior_trial_count": 16,
            "global_audit_trial_count": 32,
            "unique_trial_fingerprint_count": 32,
            "program_research_family_count": len(family_audit),
            "research_family_audit": family_audit,
            "trial_records": trials,
            "audit_records": audit_records,
            "development_returns": development_returns,
            "development_segment_sharpes": development_segments,
            "criterion_audit": {
                "historical_reuse": False,
                "public_history_point_in_time": True,
                "benchmark_execution_parity": True,
                "threshold_change_after_results": False,
                "prior_candidate_reclassification": False,
            },
            "research_live_parity": {
                "passed": True,
                "candidate_id": "options-vrp-factory-winner",
                "strategy_fingerprint": fingerprint,
            },
            "development_selection": {
                "selected_candidate_id": "options-vrp-factory-winner"
            },
            "repository_gate_calibration": _research_calibration(),
            "decision": {
                "verdict": "FACTORY_EDGE",
                "research_canary_eligible": True,
                "selected_candidate_id": "options-vrp-factory-winner",
                "selected_strategy_fingerprint": fingerprint,
                "selected_deploy_config": config_text,
                "psr": "0.999",
                "dsr": str(dsr),
                "pbo": str(pbo),
                "gates": [
                    {
                        "gate_id": gate_id,
                        "passed": True,
                        "actual": str(actual),
                        "required": str(actual),
                        "blocking": True,
                    }
                    for gate_id, actual in (
                        ("complete_family_trials", 16),
                        ("prior_audit_complete", 16),
                        ("global_audit_trials", 32),
                        ("unique_audit_fingerprints", 32),
                    )
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


def test_first_fill_requires_current_exploration_and_fundability_contracts() -> None:
    result = evaluate_live_entry(
        _profit(),
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=2,
        fundability_evidence=_fundability(),
        expected_capital_usd=Decimal("1000"),
        execution_proxy_parity_passed=True,
    )
    assert result.allowed is True
    assert result.state == ENTRY_READY


def test_stale_entry_approval_fails_closed() -> None:
    result = evaluate_live_entry(
        _profit(ready=False, psr=0.60173),
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=2,
        fundability_evidence=_fundability(),
        expected_capital_usd=Decimal("1000"),
        execution_proxy_parity_passed=True,
    )
    assert result.allowed is False
    assert result.state == ENTRY_BLOCKED
    assert "exploration_canary_ready" in result.reasons
    assert "forward_psr" in result.reasons


def test_legacy_forward_statistic_cannot_open_first_fill() -> None:
    profit = _profit()
    profit["deployment_match"]["forward"].pop("significance_method")

    result = evaluate_live_entry(
        profit,
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=2,
        fundability_evidence=_fundability(),
        expected_capital_usd=Decimal("1000"),
        execution_proxy_parity_passed=True,
    )

    assert result.allowed is False
    assert "forward_significance_method" in result.reasons


def test_missing_or_old_evidence_fails_closed_before_first_fill() -> None:
    missing = evaluate_live_entry(None, None, {"fills_count": 0}, evidence_age_hours=None)
    old = evaluate_live_entry(
        _profit(),
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=40,
        fundability_evidence=_fundability(),
        expected_capital_usd=Decimal("1000"),
        execution_proxy_parity_passed=True,
    )
    assert missing.allowed is False
    assert old.allowed is False
    assert "evidence_fresh" in old.reasons


def test_missing_fundability_blocks_first_fill() -> None:
    result = evaluate_live_entry(
        _profit(), {"verdict": "PASS"}, {"fills_count": 0}, evidence_age_hours=2
    )

    assert result.allowed is False
    assert "fundability" in result.reasons


def test_missing_proxy_parity_blocks_first_fill() -> None:
    result = evaluate_live_entry(
        _profit(),
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=2,
        fundability_evidence=_fundability(),
        expected_capital_usd=Decimal("1000"),
        execution_proxy_parity_passed=False,
    )

    assert result.allowed is False
    assert "execution_proxy_parity" in result.reasons


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
        fundability_evidence=_fundability(),
        expected_capital_usd=Decimal("1000"),
        execution_proxy_parity_passed=True,
    )
    mismatch = evaluate_live_entry(
        None,
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=None,
        factory_evidence=factory,
        factory_evidence_age_hours=2,
        live_strategy_fingerprint="sha256:other",
        fundability_evidence=_fundability(),
        expected_capital_usd=Decimal("1000"),
        execution_proxy_parity_passed=True,
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
        fundability_evidence=_fundability(),
        expected_capital_usd=Decimal("1000"),
        execution_proxy_parity_passed=True,
    )
    assert result.allowed is False
    assert "factory_contract_complete" in result.reasons
    assert "factory_evidence_fresh" in result.reasons


def test_operational_route_allows_first_fill_but_never_claims_alpha() -> None:
    fingerprint = "sha256:" + "a" * 64
    result = evaluate_live_entry(
        None,
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=None,
        operational_evidence=_operational_evidence(fingerprint=fingerprint),
        operational_evidence_age_hours=2,
        expected_code_commit="a" * 40,
        live_strategy_fingerprint=fingerprint,
        validated_strategy_fingerprint=fingerprint,
        entry_route="operational_canary",
        fundability_evidence=_fundability(),
        expected_capital_usd=Decimal("1000"),
        execution_proxy_parity_passed=True,
    )

    assert result.allowed is True
    assert result.state == ENTRY_READY
    assert result.evidence["entry_source"] == "operational_canary"
    assert result.evidence["operational_assessment"]["alpha_confirmed"] is False
    assert result.evidence["operational_assessment"]["max_rung"] == 1


def test_operational_route_accepts_bounded_below_one_share_target() -> None:
    fingerprint = "sha256:" + "a" * 64
    fundability = assess_fundability(
        target_weights={
            "SCHX": Decimal("0.333334"),
            "IAUM": Decimal("0.083333"),
        },
        holdings={},
        prices={"SCHX": Decimal("30.09"), "IAUM": Decimal("43.28")},
        order_prices={"SCHX": Decimal("30.09")},
        planned_orders=[("SCHX", "BUY", 2)],
        capital_usd=Decimal("142"),
        invested_fraction=Decimal("0.99"),
        caps=SizingCaps(
            per_trade_pct=Decimal("50"),
            per_symbol_pct=Decimal("60"),
            global_exposure_pct=Decimal("100"),
            canary_capital_pct=Decimal("10"),
            canary_min_duration_days=14,
            canary_acceptance_drawdown_pct=Decimal("10"),
        ),
    )
    result = evaluate_live_entry(
        None,
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=None,
        operational_evidence=_operational_evidence(fingerprint=fingerprint),
        operational_evidence_age_hours=2,
        expected_code_commit="a" * 40,
        live_strategy_fingerprint=fingerprint,
        validated_strategy_fingerprint=fingerprint,
        entry_route="operational_canary",
        fundability_evidence=fundability.as_dict(),
        expected_capital_usd=Decimal("142"),
        execution_proxy_parity_passed=True,
    )

    assert result.allowed is True
    assert result.state == ENTRY_READY
    assert result.evidence["operational_checks"]["operational_fundability"] is True


def test_operational_first_fill_rejects_declared_canary_capital_mismatch() -> None:
    fingerprint = "sha256:" + "a" * 64
    result = evaluate_live_entry(
        None,
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=None,
        operational_evidence=_operational_evidence(fingerprint=fingerprint),
        operational_evidence_age_hours=2,
        expected_code_commit="a" * 40,
        live_strategy_fingerprint=fingerprint,
        validated_strategy_fingerprint=fingerprint,
        entry_route="operational_canary",
        fundability_evidence=_fundability(canary_capital_pct=Decimal("5")),
        expected_capital_usd=Decimal("1000"),
        execution_proxy_parity_passed=True,
    )

    assert result.allowed is False
    assert "operational_canary_capital_contract" in result.reasons


def test_operational_first_fill_fails_on_route_commit_fingerprint_or_staleness() -> None:
    fingerprint = "sha256:" + "a" * 64
    evidence = _operational_evidence(fingerprint=fingerprint)
    common = {
        "operational_evidence": evidence,
        "live_strategy_fingerprint": fingerprint,
        "validated_strategy_fingerprint": fingerprint,
        "fundability_evidence": _fundability(),
        "expected_capital_usd": Decimal("1000"),
        "execution_proxy_parity_passed": True,
    }
    wrong_route = evaluate_live_entry(
        None,
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=None,
        operational_evidence_age_hours=2,
        expected_code_commit="a" * 40,
        entry_route="factory_research",
        **common,
    )
    wrong_commit = evaluate_live_entry(
        None,
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=None,
        operational_evidence_age_hours=2,
        expected_code_commit="b" * 40,
        entry_route="operational_canary",
        **common,
    )
    stale = evaluate_live_entry(
        None,
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=None,
        operational_evidence_age_hours=40,
        expected_code_commit="a" * 40,
        entry_route="operational_canary",
        **common,
    )

    assert wrong_route.allowed is False
    assert "entry_route_evidence_mismatch" in wrong_route.reasons
    assert wrong_commit.allowed is False
    assert "operational_code_commit" in wrong_commit.reasons
    assert stale.allowed is False
    assert "operational_evidence_fresh" in stale.reasons
