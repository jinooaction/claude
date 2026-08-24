from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest

from auto_invest.analytics.fx_carry_factory import (
    FxCarrySnapshot,
    build_fx_snapshots,
    generate_fx_candidates,
    run_fx_carry_factory,
    validate_live_fx_evidence,
)
from auto_invest.analytics.risk_managed_beta import MonthlyRow
from auto_invest.config.rules import FxCarryPolicyConfig, PortfolioRebalanceConfig
from auto_invest.market_data.public_data import SeriesPoint
from auto_invest.portfolio.autoarm import strategy_fingerprint_digest
from auto_invest.strategy.rebalance import fx_carry_target_weights


def _rows(count: int = 444) -> list[MonthlyRow]:
    rows: list[MonthlyRow] = []
    year, month = 1990, 1
    for index in range(count):
        rows.append(
            MonthlyRow(
                date(year, month, 1).isoformat(),
                price=100 * (1.006**index),
                dividend=2.0,
                long_rate=4.0 + (index % 24 - 12) / 20,
            )
        )
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return rows


def _snapshots(rows: list[MonthlyRow]) -> list[FxCarrySnapshot]:
    spot_history: dict[str, list[Decimal]] = {
        currency: [] for currency in ("AUD", "CAD", "JPY", "GBP", "USD")
    }
    rate_history: dict[str, list[Decimal]] = {
        currency: [] for currency in ("AUD", "CAD", "JPY", "GBP", "USD")
    }
    output: list[FxCarrySnapshot] = []
    bases = {"AUD": Decimal("0.75"), "CAD": Decimal("0.80"), "JPY": Decimal("0.009"),
             "GBP": Decimal("1.30"), "USD": Decimal("1")}
    rate_bases = {"AUD": Decimal("5"), "CAD": Decimal("4"), "JPY": Decimal("1"),
                  "GBP": Decimal("4.5"), "USD": Decimal("3")}
    for index, row in enumerate(rows):
        spots = {
            currency: base
            * (Decimal("1") + Decimal((index + offset) % 24 - 12) / Decimal("1000"))
            for offset, (currency, base) in enumerate(bases.items())
        }
        spots["USD"] = Decimal("1")
        rates = {
            currency: base + Decimal((index + offset) % 18 - 9) / Decimal("20")
            for offset, (currency, base) in enumerate(rate_bases.items())
        }
        for currency in bases:
            spot_history[currency].append(spots[currency])
            rate_history[currency].append(rates[currency])
        output.append(
            FxCarrySnapshot(
                as_of_date=row.date,
                usd_spot=spots,
                short_rates=rates,
                observation_dates={"synthetic": row.date},
                spot_history={key: tuple(values) for key, values in spot_history.items()},
                rate_history={key: tuple(values) for key, values in rate_history.items()},
                complete=True,
                fresh=True,
            )
        )
    return output


def _prior_payload(count: int = 640) -> dict:
    return {
        "audit_records": [
            {
                "candidate_id": f"prior-{index:03d}",
                "strategy_fingerprint": f"sha256:prior-{index:03d}",
                "status": "complete",
                "segment_sharpes": [0.1] * 10,
            }
            for index in range(count)
        ]
    }


def _calibration() -> dict:
    return {
        "gate_version": "2.0",
        "verdict": "CALIBRATED",
        "code_commit": "abc123",
        "scenario": {"repetitions": 500},
        "thresholds": {"holdout_psr_min": 0.95, "paper_psr_min": 0.80},
        "family_calibrations": {
            "16": {
                "live_calibrated": True,
                "null_false_acceptance_rate": 0.04,
                "target_live_detection_rate": 0.84,
            }
        },
    }


def _run(snapshots: list[FxCarrySnapshot], *, prior_count: int = 640) -> dict:
    rows = _rows()
    return run_fx_carry_factory(
        rows,
        [400 * (1.004**index) for index in range(len(rows))],
        snapshots,
        fx_data_quality={"complete": True},
        prior_factory_payload=_prior_payload(prior_count),
        calibration_evidence=_calibration(),
        code_commit="abc123",
        timestamp_utc="2026-08-24T00:00:00Z",
    )


def test_candidate_grammar_is_16_unique_and_not_live_authorized() -> None:
    first, second = generate_fx_candidates(), generate_fx_candidates()
    assert len(first) == 16
    assert [item.candidate_id for item in first] == [item.candidate_id for item in second]
    assert len({item.strategy_fingerprint for item in first}) == 16
    assert {item.policy.family for item in first} == {
        "pure_carry",
        "carry_momentum",
        "carry_value",
        "defensive_carry",
    }
    assert all(item.as_dict()["live_expressible"] is False for item in first)


def test_shared_policy_is_long_only_and_stale_fails_closed() -> None:
    snapshot = _snapshots(_rows(40))[-1].as_dict(include_history=True)
    policy = FxCarryPolicyConfig(
        family="pure_carry",
        lookback_months=3,
        max_foreign_weight=Decimal("0.5"),
    )
    weights = fx_carry_target_weights(policy=policy, snapshot=snapshot)
    assert set(weights) == {"FXA", "FXC", "FXY", "FXB", "UUP"}
    assert sum(weights.values()) == Decimal("1.000000")
    assert all(weight >= 0 for weight in weights.values())
    snapshot["fresh"] = False
    with pytest.raises(ValueError, match="stale"):
        fx_carry_target_weights(policy=policy, snapshot=snapshot)


def test_fx_policy_changes_fingerprint_and_preserves_existing_digest() -> None:
    base = PortfolioRebalanceConfig(
        id="existing",
        universe=("SPY", "IEF", "GLD"),
        weights={"momentum": Decimal("1")},
        top_n=2,
    )
    assert strategy_fingerprint_digest(base) == (
        "sha256:0ec53e0d014ae5a0732eca4322d05e0f7b1f2afd7fd9d7bc35772bf27c22e922"
    )
    policy = FxCarryPolicyConfig(
        family="pure_carry", lookback_months=3, max_foreign_weight=Decimal("0.5")
    )
    fx = PortfolioRebalanceConfig(
        id="fx",
        universe=("FXA", "FXC", "FXY", "FXB", "UUP"),
        weights={"momentum": Decimal("1")},
        top_n=5,
        fx_carry_policy=policy,
    )
    changed = fx.model_copy(
        update={"fx_carry_policy": policy.model_copy(update={"lookback_months": 12})}
    )
    assert strategy_fingerprint_digest(fx) != strategy_fingerprint_digest(changed)


def test_point_in_time_snapshot_normalizes_quotes_and_lags_rates() -> None:
    series = {
        "DEXUSAL": [SeriesPoint("2020-01-31", Decimal("0.70"))],
        "DEXCAUS": [SeriesPoint("2020-01-31", Decimal("1.25"))],
        "DEXJPUS": [SeriesPoint("2020-01-31", Decimal("100"))],
        "DEXUSUK": [SeriesPoint("2020-01-31", Decimal("1.30"))],
    }
    for series_id in (
        "IRSTCI01AUM156N",
        "IRSTCI01CAM156N",
        "IRSTCI01JPM156N",
        "IRSTCI01GBM156N",
        "IRSTCI01USM156N",
    ):
        series[series_id] = [
            SeriesPoint("2020-01-01", Decimal("2")),
            SeriesPoint("2020-02-01", Decimal("9")),
        ]
    snapshot = build_fx_snapshots(["2020-02-01"], series=series)[0]
    assert snapshot.usd_spot["AUD"] == Decimal("0.70")
    assert snapshot.usd_spot["CAD"] == Decimal("0.8")
    assert snapshot.usd_spot["JPY"] == Decimal("0.01")
    assert snapshot.short_rates["AUD"] == Decimal("2")
    assert snapshot.complete is True
    assert snapshot.fresh is True

    bad = deepcopy(series)
    bad["DEXCAUS"] = [SeriesPoint("2020-01-31", Decimal("0"))]
    with pytest.raises(ValueError, match="positive"):
        build_fx_snapshots(["2020-02-01"], series=bad)


def test_factory_keeps_global_audit_separate_from_family_statistics() -> None:
    payload = _run(_snapshots(_rows()))
    assert payload["candidate_count"] == 16
    assert payload["prior_trial_count"] == 640
    assert payload["global_audit_trial_count"] == 656
    assert payload["multiplicity_trial_count"] == 16
    assert payload["unique_trial_fingerprint_count"] == 656
    assert payload["decision"]["selected_deploy_config"] is None
    assert payload["decision"]["live_whitelist_authorized"] is False


def test_missing_prior_audit_closes_common_gate() -> None:
    payload = _run(_snapshots(_rows()), prior_count=639)
    gates = {gate["gate_id"]: gate for gate in payload["decision"]["gates"]}
    assert gates["prior_audit_complete"]["passed"] is False
    assert payload["decision"]["research_canary_eligible"] is False
    assert payload["decision"]["paper_forward_eligible"] is False


def test_holdout_changes_do_not_reselect_development_winner() -> None:
    original = _snapshots(_rows())
    first = _run(original)
    altered = []
    for snapshot in original:
        if snapshot.as_of_date < "2007-01-01":
            altered.append(snapshot)
            continue
        spots = dict(snapshot.usd_spot)
        spots["AUD"] = spots["AUD"] * Decimal("1.5")  # type: ignore[operator]
        altered.append(
            FxCarrySnapshot(
                as_of_date=snapshot.as_of_date,
                usd_spot=spots,
                short_rates=snapshot.short_rates,
                observation_dates=snapshot.observation_dates,
                spot_history=snapshot.spot_history,
                rate_history=snapshot.rate_history,
                complete=True,
                fresh=True,
            )
        )
    second = _run(altered)
    assert (
        first["development_selection"]["selected_candidate_id"]
        == second["development_selection"]["selected_candidate_id"]
    )


def test_live_validator_rejects_paper_and_unapproved_whitelist() -> None:
    payload = {
        "gate_version": "2.0",
        "code_commit": "abc",
        "fx_data_fingerprint": "sha256:data",
        "decision": {
            "verdict": "PAPER_CHALLENGER",
            "research_canary_eligible": False,
            "live_whitelist_authorized": False,
        },
        "live_fx_evidence": {},
    }
    with pytest.raises(ValueError, match="paper"):
        validate_live_fx_evidence(
            payload, candidate_id="candidate", strategy_fingerprint="sha256:x"
        )

    payload["decision"] = {
        "verdict": "FACTORY_EDGE",
        "research_canary_eligible": True,
        "live_whitelist_authorized": False,
        "selected_candidate_id": "candidate",
        "selected_strategy_fingerprint": "sha256:x",
        "gates": [{"passed": True, "blocking": True}],
    }
    payload["research_live_parity"] = {"target_weights_digest": "sha256:weights"}
    payload["live_fx_evidence"] = {
        "candidate_id": "candidate",
        "strategy_fingerprint": "sha256:x",
        "data_fingerprint": "sha256:data",
        "code_commit": "abc",
        "target_weights_digest": "sha256:weights",
        "fresh": True,
        "complete": True,
        "live_whitelist_authorized": False,
        "latest_snapshot": {},
    }
    with pytest.raises(ValueError, match="whitelist"):
        validate_live_fx_evidence(
            payload, candidate_id="candidate", strategy_fingerprint="sha256:x"
        )

    eligible = deepcopy(payload)
    eligible["decision"]["live_whitelist_authorized"] = True
    eligible["live_fx_evidence"]["live_whitelist_authorized"] = True
    assert validate_live_fx_evidence(
        eligible, candidate_id="candidate", strategy_fingerprint="sha256:x"
    ) == {}

    stale = deepcopy(eligible)
    stale["live_fx_evidence"]["fresh"] = False
    with pytest.raises(ValueError, match="stale"):
        validate_live_fx_evidence(
            stale, candidate_id="candidate", strategy_fingerprint="sha256:x"
        )


def test_fx_evidence_validation_precedes_any_broker_path() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[2] / "src" / "auto_invest" / "cli.py").read_text(
        encoding="utf-8"
    )
    validation = text.index("fx_snapshot = validate_live_fx_evidence(")
    broker_path = text.index("async def _go_dry()")
    assert validation < broker_path
    assert "FX carry policy requires --fx-evidence before broker call" in text
