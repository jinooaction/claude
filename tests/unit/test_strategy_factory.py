import tomllib
from datetime import date

from auto_invest.analytics.risk_managed_beta import MonthlyRow
from auto_invest.analytics.strategy_factory import (
    EXPECTED_CANDIDATES,
    generate_candidates,
    render_candidate_toml,
    run_strategy_factory,
)
from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.portfolio.autoarm import strategy_fingerprint_digest


def _monthly_rows() -> tuple[list[MonthlyRow], list[float]]:
    rows: list[MonthlyRow] = []
    gold: list[float] = []
    year, month = 1971, 1
    equity = 100.0
    gold_price = 35.0
    for index in range(56 * 12):
        equity *= 1.006 if index % 48 < 36 else 0.992
        gold_price *= 1.004 if index % 60 < 24 else 0.998
        rows.append(
            MonthlyRow(
                date(year, month, 1).isoformat(),
                equity,
                2.0,
                4.0,
            )
        )
        gold.append(gold_price)
        month += 1
        if month == 13:
            year += 1
            month = 1
    return rows, gold


def test_generates_exactly_64_unique_deterministic_candidates() -> None:
    first = generate_candidates()
    second = generate_candidates()
    assert first == second
    assert len(first) == EXPECTED_CANDIDATES
    assert len({candidate.candidate_id for candidate in first}) == EXPECTED_CANDIDATES
    assert {candidate.family for candidate in first} == {
        "trend_equal",
        "trend_inverse_vol",
        "relative_momentum",
        "defensive_low_turnover",
    }
    all_candidates = [
        candidate for sequence in range(4) for candidate in generate_candidates(sequence)
    ]
    assert len({candidate.strategy_fingerprint for candidate in all_candidates}) == 256


def test_every_candidate_renders_a_parseable_live_portfolio() -> None:
    for candidate in generate_candidates():
        payload = tomllib.loads(render_candidate_toml(candidate))
        config = PortfolioRebalanceConfig.model_validate(payload["portfolio"])
        assert config.id == candidate.candidate_id
        assert config.universe == ("SPY", "IEF", "GLD")
        assert strategy_fingerprint_digest(config) == candidate.strategy_fingerprint


def test_factory_records_all_trials_and_requires_every_gate() -> None:
    rows, gold = _monthly_rows()
    report = run_strategy_factory(
        rows,
        gold,
        code_commit="abc123",
        timestamp_utc="2026-08-23T00:00:00Z",
    )
    assert report["candidate_count"] == EXPECTED_CANDIDATES
    assert report["complete_trial_count"] == EXPECTED_CANDIDATES
    assert len(report["trial_records"]) == EXPECTED_CANDIDATES
    assert len(report["decision"]["gates"]) == 10
    all_passed = all(gate["passed"] for gate in report["decision"]["gates"])
    assert report["decision"]["research_canary_eligible"] is all_passed
    assert (report["decision"]["selected_deploy_config"] is not None) is all_passed
    assert all(0 <= row["segment_wins"] <= 10 for row in report["trial_records"])


def test_batch_and_strategy_fingerprints_are_reproducible() -> None:
    rows, gold = _monthly_rows()
    first = run_strategy_factory(rows, gold, code_commit="same")
    second = run_strategy_factory(rows, gold, code_commit="same")
    assert first["batch_id"] == second["batch_id"]
    assert first["data_fingerprint"] == second["data_fingerprint"]
    assert [row["strategy_fingerprint"] for row in first["candidates"]] == [
        row["strategy_fingerprint"] for row in second["candidates"]
    ]


def test_next_batch_preserves_prior_trials_in_multiplicity_correction() -> None:
    rows, gold = _monthly_rows()
    first = run_strategy_factory(rows, gold, code_commit="first", batch_sequence=0)
    second = run_strategy_factory(
        rows,
        gold,
        code_commit="second",
        batch_sequence=1,
        prior_trial_records=first["trial_records"],
    )
    assert second["batch_sequence"] == 1
    assert second["multiplicity_trial_count"] == 128
    assert {row["strategy_fingerprint"] for row in first["candidates"]}.isdisjoint(
        {row["strategy_fingerprint"] for row in second["candidates"]}
    )
