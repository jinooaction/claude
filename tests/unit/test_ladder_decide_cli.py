"""스펙 140 - 탐색 캐너리 입력을 자본 사다리에 잇는 CLI 회귀 테스트."""

from __future__ import annotations

import json
import math
import tomllib
from decimal import Decimal
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.analytics.backtest_overfitting import (
    annualized_sharpe,
    deflated_sharpe_from_trials,
    effective_independent_trials,
    probability_of_backtest_overfitting,
)
from auto_invest.cli import app
from auto_invest.config.caps import SizingCaps
from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.portfolio.autoarm import strategy_fingerprint_digest
from auto_invest.portfolio.fundability import assess_fundability

ROOT = Path(__file__).resolve().parents[2]
RUNNER = CliRunner()


def _json(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _invoke(tmp_path: Path, *, canary_verdict: str):
    forward = _json(
        tmp_path,
        "forward.json",
        {"verdict": "NO_EDGE", "n_obs": 41, "psr_vs_benchmark": "0.82727"},
    )
    profit = _json(
        tmp_path,
        "profit.json",
        {
            "deployment_match": {
                "candidate_id": "globalfixed-ensemble-3-6-9-12",
                "exploration_canary_ready": True,
            }
        },
    )
    canary = _json(tmp_path, "canary.json", {"verdict": canary_verdict})
    nav = _json(tmp_path, "nav.json", {"total_value_usd": "12000"})
    sentinel = tmp_path / "sentinel.request"
    sentinel.write_text("armed: false\ncapital_usd: 0\nrun_seq: 1\n", encoding="utf-8")
    return RUNNER.invoke(
        app,
        [
            "ladder-decide",
            "--verdict-json",
            str(forward),
            "--profit-evidence-json",
            str(profit),
            "--hardened-canary-json",
            str(canary),
            "--account-nav-json",
            str(nav),
            "--live-portfolio",
            str(ROOT / "deploy/canary-live-portfolio.toml"),
            "--validated-portfolio",
            str(ROOT / "deploy/global-trend-fixed-portfolio.toml"),
            "--sentinel",
            str(sentinel),
            "--format",
            "json",
        ],
    )


def test_exact_evidence_and_hardened_pass_enter_20pct_canary(tmp_path: Path) -> None:
    result = _invoke(tmp_path, canary_verdict="PASS")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["action"] == "PROMOTE"
    assert payload["target_rung"] == 2
    assert payload["target_capital_usd"] == 2400
    assert payload["exploration_verdict"]["hardened_canary_pass"] is True


def test_hardened_failure_keeps_real_money_disarmed(tmp_path: Path) -> None:
    result = _invoke(tmp_path, canary_verdict="FAIL")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["action"] == "WAIT_EDGE"
    assert payload["target_rung"] == 0
    assert payload["exploration_verdict"]["hardened_canary_pass"] is False


def _invoke_factory(tmp_path: Path, *, winner: bool, include_fundability: bool = True):
    live = ROOT / "deploy" / "canary-live-portfolio.toml"
    config_text = live.read_text(encoding="utf-8")
    config = PortfolioRebalanceConfig.model_validate(tomllib.loads(config_text)["portfolio"])
    fingerprint = strategy_fingerprint_digest(config)
    prior = [
        {
            "candidate_id": f"prior-{index}",
            "strategy_fingerprint": f"sha256:prior-{index}",
            "status": "EXPLORATORY_REJECTED",
        }
        for index in range(16)
    ]
    trials = [
        {
            "candidate_id": f"family-{index}",
            "strategy_fingerprint": f"sha256:family-{index}",
            "status": "complete",
        }
        for index in range(15)
    ] + [
        {
            "candidate_id": "factory-exact",
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
    factory = _json(
        tmp_path,
        "factory.json",
        {
            "gate_version": "3.0",
            "candidate_count": 16,
            "complete_trial_count": 16,
            "prior_trial_count": 16,
            "global_audit_trial_count": 32,
            "unique_trial_fingerprint_count": 32,
            "trial_records": trials,
            "audit_records": prior + trials,
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
                "passed": winner,
                "candidate_id": "factory-exact",
                "strategy_fingerprint": fingerprint,
            },
            "decision": {
                "verdict": "FACTORY_EDGE" if winner else "NO_FACTORY_EDGE",
                "research_canary_eligible": winner,
                "selected_candidate_id": "factory-exact" if winner else None,
                "selected_strategy_fingerprint": fingerprint if winner else None,
                "selected_deploy_config": config_text if winner else None,
                "psr": "0.999" if winner else None,
                "dsr": str(dsr) if winner else None,
                "pbo": str(pbo) if winner else None,
                "gates": [
                    {
                        "gate_id": "complete_family_trials",
                        "passed": True,
                        "actual": "16",
                        "required": "16",
                        "blocking": True,
                    },
                    {
                        "gate_id": "prior_audit_complete",
                        "passed": True,
                        "actual": "16",
                        "required": "16",
                        "blocking": True,
                    },
                    {
                        "gate_id": "global_audit_trials",
                        "passed": True,
                        "actual": "32",
                        "required": "32",
                        "blocking": True,
                    },
                    {
                        "gate_id": "unique_audit_fingerprints",
                        "passed": True,
                        "actual": "32",
                        "required": "32",
                        "blocking": True,
                    },
                    {
                        "gate_id": "holdout_excess_psr",
                        "passed": winner,
                        "blocking": True,
                    },
                ],
            },
        },
    )
    forward = _json(tmp_path, "forward.json", {"verdict": "NO_EDGE", "n_obs": 0})
    canary = _json(tmp_path, "canary.json", {"verdict": "PASS"})
    nav = _json(tmp_path, "nav.json", {"total_value_usd": "12000"})
    fundability = assess_fundability(
        target_weights={"AAA": Decimal("0.5"), "BBB": Decimal("0.5")},
        holdings={},
        prices={"AAA": Decimal("100"), "BBB": Decimal("100")},
        order_prices={"AAA": Decimal("100"), "BBB": Decimal("100")},
        planned_orders=[("AAA", "BUY", 5), ("BBB", "BUY", 6)],
        capital_usd=Decimal("1200"),
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
    fundability_path = _json(
        tmp_path,
        "fundability.json",
        {"fundability": fundability.as_dict()} if include_fundability else {},
    )
    sentinel = tmp_path / "sentinel.request"
    sentinel.write_text("armed: false\ncapital_usd: 0\nrun_seq: 1\n", encoding="utf-8")
    return RUNNER.invoke(
        app,
        [
            "ladder-decide",
            "--verdict-json",
            str(forward),
            "--factory-evidence-json",
            str(factory),
            "--factory-evidence-age-hours",
            "2",
            "--fundability-preview-json",
            str(fundability_path),
            "--hardened-canary-json",
            str(canary),
            "--account-nav-json",
            str(nav),
            "--live-portfolio",
            str(live),
            "--validated-portfolio",
            str(ROOT / "deploy/global-trend-fixed-portfolio.toml"),
            "--sentinel",
            str(sentinel),
            "--format",
            "json",
        ],
    )


def test_complete_exact_factory_winner_enters_only_10pct(tmp_path: Path) -> None:
    result = _invoke_factory(tmp_path, winner=True)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["action"] == "PROMOTE"
    assert payload["target_rung"] == 1
    assert payload["target_capital_usd"] == 1200
    assert payload["factory_verdict"]["contract_version"] == "family-complete-v3"
    assert payload["factory_verdict"]["contract_complete"] is True
    assert payload["factory_verdict"]["exact_strategy_match"] is True
    assert payload["factory_verdict"]["fundability_passed"] is True


def test_factory_winner_without_exact_fundability_stays_disarmed(tmp_path: Path) -> None:
    result = _invoke_factory(tmp_path, winner=True, include_fundability=False)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["action"] == "WAIT_EDGE"
    assert payload["target_rung"] == 0
    assert payload["factory_verdict"]["contract_complete"] is True
    assert payload["factory_verdict"]["fundability_passed"] is False


def test_current_no_factory_edge_stays_disarmed(tmp_path: Path) -> None:
    result = _invoke_factory(tmp_path, winner=False)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["action"] == "WAIT_EDGE"
    assert payload["target_rung"] == 0
    assert payload["target_capital_usd"] is None
    assert payload["factory_verdict"]["contract_complete"] is False
    assert "factory_edge" in payload["factory_verdict"]["contract_reasons"]


def test_separate_live_performance_demotes_unfilled_stale_entry(tmp_path: Path) -> None:
    forward = _json(tmp_path, "forward.json", {"verdict": "NO_EDGE", "n_obs": 47})
    profit = _json(
        tmp_path,
        "profit.json",
        {
            "deployment_match": {
                "candidate_id": "globalfixed-ensemble-3-6-9-12",
                "exploration_canary_ready": False,
            }
        },
    )
    canary = _json(tmp_path, "canary.json", {"verdict": "PASS"})
    growth = _json(
        tmp_path,
        "growth.json",
        {"snapshot_count": 1, "max_drawdown_pct": None, "period_days": None},
    )
    performance = _json(tmp_path, "performance.json", {"fills_count": 0})
    nav = _json(tmp_path, "nav.json", {"total_value_usd": "1457.59"})
    sentinel = tmp_path / "sentinel.request"
    sentinel.write_text(
        "armed: true\ncapital_usd: 293\nladder_rung: 1\nrung_entered: 2026-08-22\n",
        encoding="utf-8",
    )

    result = RUNNER.invoke(
        app,
        [
            "ladder-decide",
            "--verdict-json",
            str(forward),
            "--profit-evidence-json",
            str(profit),
            "--hardened-canary-json",
            str(canary),
            "--live-growth-json",
            str(growth),
            "--live-performance-json",
            str(performance),
            "--account-nav-json",
            str(nav),
            "--live-portfolio",
            str(ROOT / "deploy/canary-live-portfolio.toml"),
            "--validated-portfolio",
            str(ROOT / "deploy/global-trend-fixed-portfolio.toml"),
            "--sentinel",
            str(sentinel),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["action"] == "DEMOTE"
    assert payload["target_rung"] == 0
