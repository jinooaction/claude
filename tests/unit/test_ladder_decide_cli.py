"""스펙 140 - 탐색 캐너리 입력을 자본 사다리에 잇는 CLI 회귀 테스트."""

from __future__ import annotations

import hashlib
import json
import math
import tomllib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from typer.testing import CliRunner

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
from auto_invest.cli import app
from auto_invest.config.caps import SizingCaps
from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.portfolio.autoarm import strategy_fingerprint_digest
from auto_invest.portfolio.execution_proxy_parity import (
    LOOKBACK_SESSIONS,
    MAX_ANNUALIZED_RETURN_GAP,
    MAX_ANNUALIZED_TRACKING_ERROR,
    MAX_EVIDENCE_AGE_HOURS,
    MAX_MARKET_DATA_AGE_DAYS,
    MIN_COMMON_SESSIONS,
    MIN_MEDIAN_DOLLAR_VOLUME_USD,
    MIN_RETURN_CORRELATION,
    PREREGISTERED_EXECUTION_SYMBOL_MAP,
)
from auto_invest.portfolio.fundability import assess_fundability
from auto_invest.portfolio.operational_canary_evidence import (
    build_operational_canary_evidence,
)

ROOT = Path(__file__).resolve().parents[2]
RUNNER = CliRunner()


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


def _json(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _proxy_parity_json(tmp_path: Path) -> Path:
    observed = datetime.now(UTC)
    pair_checks = {
        "common_sessions": True,
        "latest_session_aligned": True,
        "freshness": True,
        "return_correlation": True,
        "annualized_tracking_error": True,
        "annualized_return_gap": True,
        "execution_liquidity": True,
    }
    pairs = [
        {
            "signal_symbol": signal,
            "execution_symbol": execution,
            "common_sessions": MIN_COMMON_SESSIONS,
            "first_session": (observed.date() - timedelta(days=365)).isoformat(),
            "last_session": observed.date().isoformat(),
            "signal_latest_session": observed.date().isoformat(),
            "execution_latest_session": observed.date().isoformat(),
            "return_correlation": 0.99,
            "annualized_tracking_error": 0.01,
            "annualized_return_gap": 0.01,
            "median_execution_dollar_volume_usd": "10000000",
            "checks": dict(pair_checks),
            "passed": True,
        }
        for signal, execution in sorted(PREREGISTERED_EXECUTION_SYMBOL_MAP.items())
    ]
    body = {
        "schema_version": "1.0",
        "observed_at_utc": observed.isoformat().replace("+00:00", "Z"),
        "dataset_version": "test",
        "symbol_map": PREREGISTERED_EXECUTION_SYMBOL_MAP,
        "contract": {
            "lookback_sessions": LOOKBACK_SESSIONS,
            "min_common_sessions": MIN_COMMON_SESSIONS,
            "min_return_correlation": MIN_RETURN_CORRELATION,
            "max_annualized_tracking_error": MAX_ANNUALIZED_TRACKING_ERROR,
            "max_annualized_return_gap": MAX_ANNUALIZED_RETURN_GAP,
            "min_median_dollar_volume_usd": str(MIN_MEDIAN_DOLLAR_VOLUME_USD),
            "max_market_data_age_days": MAX_MARKET_DATA_AGE_DAYS,
            "max_evidence_age_hours": MAX_EVIDENCE_AGE_HOURS,
        },
        "checks": {
            "mapping_exact": True,
            "pair_count": True,
            "all_pairs_passed": True,
        },
        "pairs": pairs,
        "passed": True,
    }
    encoded = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    body["evidence_digest"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
    return _json(tmp_path, "proxy-parity.json", body)


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
        tmp_path, "exploration-fundability.json", {"fundability": fundability.as_dict()}
    )
    proxy_parity_path = _proxy_parity_json(tmp_path)
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
            "--fundability-preview-json",
            str(fundability_path),
            "--execution-proxy-parity-json",
            str(proxy_parity_path),
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


def test_exact_exploration_evidence_remains_diagnostic_without_route_calibration(
    tmp_path: Path,
) -> None:
    result = _invoke(tmp_path, canary_verdict="PASS")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["action"] == "WAIT_EDGE"
    assert payload["target_rung"] == 0
    assert payload["exploration_verdict"]["hardened_canary_pass"] is True
    assert payload["exploration_verdict"]["route_calibrated"] is False


def test_operational_evidence_opens_only_rung1(tmp_path: Path) -> None:
    live = ROOT / "deploy/canary-live-portfolio.toml"
    config = PortfolioRebalanceConfig.model_validate(
        tomllib.loads(live.read_text(encoding="utf-8"))["portfolio"]
    )
    fingerprint = strategy_fingerprint_digest(config)
    dates: list[str] = []
    year, month = 1991, 1
    for _ in range(360):
        dates.append(f"{year:04d}-{month:02d}-01")
        month += 1
        if month == 13:
            year += 1
            month = 1
    operational = _json(
        tmp_path,
        "operational.json",
        build_operational_canary_evidence(
            dates=dates,
            candidate_monthly_factors=[
                1.012 if index % 2 == 0 else 0.998 for index in range(360)
            ],
            benchmark_monthly_factors=[
                1.010 if index % 2 == 0 else 0.985 for index in range(360)
            ],
            development_months=180,
            annual_cost_bps=50,
            code_commit="a" * 40,
            generated_at_utc="2026-08-31T01:00:00Z",
            strategy_fingerprint=fingerprint,
        ),
    )
    forward = _json(tmp_path, "forward.json", {"verdict": "NO_EDGE", "n_obs": 4})
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
        tmp_path, "fundability-operational.json", {"fundability": fundability.as_dict()}
    )
    sentinel = tmp_path / "sentinel-operational.request"
    sentinel.write_text("armed: false\ncapital_usd: 0\nrun_seq: 1\n", encoding="utf-8")

    result = RUNNER.invoke(
        app,
        [
            "ladder-decide",
            "--verdict-json",
            str(forward),
            "--operational-evidence-json",
            str(operational),
            "--operational-evidence-age-hours",
            "2",
            "--expected-code-commit",
            "a" * 40,
            "--fundability-preview-json",
            str(fundability_path),
            "--execution-proxy-parity-json",
            str(_proxy_parity_json(tmp_path)),
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

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["action"] == "PROMOTE"
    assert payload["target_rung"] == 1
    assert payload["target_capital_usd"] == 1200
    assert payload["entry_route"] == "operational_canary"
    assert payload["operational_verdict"]["alpha_confirmed"] is False
    assert payload["operational_verdict"]["max_rung"] == 1


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
            "batch_id": "strategy-factory-test-prior",
        }
        for index in range(16)
    ]
    trials = [
        {
            "candidate_id": f"options-vrp-family-{index}",
            "strategy_fingerprint": f"sha256:family-{index}",
            "status": "complete",
        }
        for index in range(15)
    ] + [
        {
            "candidate_id": "options-vrp-factory-exact",
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
    factory = _json(
        tmp_path,
        "factory.json",
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
                "passed": winner,
                "candidate_id": "options-vrp-factory-exact",
                "strategy_fingerprint": fingerprint,
            },
            "development_selection": {
                "selected_candidate_id": "options-vrp-factory-exact"
            },
            "repository_gate_calibration": _research_calibration(),
            "decision": {
                "verdict": "FACTORY_EDGE" if winner else "NO_FACTORY_EDGE",
                "research_canary_eligible": winner,
                "selected_candidate_id": "options-vrp-factory-exact" if winner else None,
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
    proxy_parity_path = _proxy_parity_json(tmp_path)
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
            "--execution-proxy-parity-json",
            str(proxy_parity_path),
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
    assert (
        payload["factory_verdict"]["contract_version"]
        == "calibrated-family-entry-v3.1"
    )
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
