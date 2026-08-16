"""스펙 138 - 시간 분리 수익 증거 엔진 단위 테스트."""

from __future__ import annotations

from auto_invest.analytics.profit_evidence_engine import (
    FORWARD_VALIDATION,
    HOLDOUT_EDGE,
    apply_annual_cost_drag,
    evaluate_profit_evidence,
    registered_candidates,
)


def _dates() -> list[str]:
    dates: list[str] = []
    year, month = 1981, 1
    for _ in range(480):
        dates.append(f"{year:04d}-{month:02d}-01")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return dates


def _factors(up: float, down: float, n: int) -> list[float]:
    return [up if index % 2 == 0 else down for index in range(n)]


def _candidate_factors(n: int) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for candidate in registered_candidates():
        if candidate.allocation == "three_asset_fixed":
            up = {6: 1.0140, 8: 1.0145, 10: 1.0150, 12: 1.0142}[
                candidate.trend_window_months
            ]
            down = 0.997
        elif candidate.allocation == "three_asset_inverse_vol":
            up, down = 1.0115, 0.9975
        else:
            up, down = 1.0105, 0.9965
        out[candidate.candidate_id] = _factors(up, down, n)
    return out


def test_registered_search_space_is_fixed_and_deterministic() -> None:
    candidates = registered_candidates()
    assert len(candidates) == 12
    assert [candidate.trial_index for candidate in candidates] == list(range(1, 13))
    assert {candidate.trend_window_months for candidate in candidates} == {6, 8, 10, 12}


def test_cost_drag_reduces_every_positive_gross_factor() -> None:
    gross = [1.01, 0.99, 1.02]
    net = apply_annual_cost_drag(gross, annual_cost_bps=50)
    assert len(net) == len(gross)
    assert all(after < before for before, after in zip(gross, net, strict=True))


def test_engine_selects_family_before_holdout_and_requires_forward_gate() -> None:
    dates = _dates()
    report = evaluate_profit_evidence(
        dates=dates,
        candidate_factors=_candidate_factors(len(dates)),
        benchmark_factors=_factors(1.013, 0.985, len(dates)),
        leaderboard={
            "rows": [
                {
                    "key": "globalfixed",
                    "n_obs": 41,
                    "psr_vs_benchmark": "0.827270",
                    "verdict": "NO_EDGE",
                    "beats_benchmark_calmar": True,
                }
            ]
        },
        deployment_factors=_factors(1.015, 0.997, len(dates)),
    )

    assert report.trial_count == 12
    assert report.split.overlap_months == 0
    assert report.selected_candidate.allocation == "three_asset_fixed"
    assert report.selected_candidate.trend_window_months == 10
    assert report.historical_verdict == HOLDOUT_EDGE
    assert report.status == FORWARD_VALIDATION
    assert report.forward.track_key == "globalfixed"
    assert report.forward.psr_vs_benchmark == 0.82727
    assert all(gate.passed for gate in report.gates)
    assert len(report.neighbors) == 2
    assert report.deployment_match.historical_passed is True
    assert report.deployment_match.exploration_canary_ready is True
    assert report.deployment_match.trend_windows_months == (3, 6, 9, 12)
    assert report.deployment_match.annual_cost_bps == 50
    assert report.deployment_match.split.overlap_months == 0
    assert report.deployment_match.development is not None
    assert report.deployment_match.holdout is not None
    assert report.deployment_match.holdout.n_months >= 120
    assert {
        "deployment_temporal_split",
        "deployment_holdout_months",
        "deployment_annual_cost_bps",
    }.issubset({gate.gate_id for gate in report.deployment_match.gates})


def test_exploration_canary_requires_every_forward_floor() -> None:
    dates = _dates()
    base = {
        "key": "globalfixed",
        "n_obs": 40,
        "psr_vs_benchmark": "0.80",
        "verdict": "NO_EDGE",
        "beats_benchmark_calmar": True,
    }

    def report_for(**overrides):
        row = {**base, **overrides}
        return evaluate_profit_evidence(
            dates=dates,
            candidate_factors=_candidate_factors(len(dates)),
            benchmark_factors=_factors(1.013, 0.985, len(dates)),
            leaderboard={"rows": [row]},
            deployment_factors=_factors(1.015, 0.997, len(dates)),
        )

    assert report_for().deployment_match.exploration_canary_ready is True
    assert report_for(n_obs=39).deployment_match.exploration_canary_ready is False
    assert (
        report_for(psr_vs_benchmark="0.799999").deployment_match.exploration_canary_ready
        is False
    )
    assert (
        report_for(beats_benchmark_calmar=False).deployment_match.exploration_canary_ready
        is False
    )


def test_exploration_canary_fails_closed_without_exact_deployment_factors() -> None:
    dates = _dates()
    report = evaluate_profit_evidence(
        dates=dates,
        candidate_factors=_candidate_factors(len(dates)),
        benchmark_factors=_factors(1.013, 0.985, len(dates)),
        leaderboard={
            "rows": [
                {
                    "key": "globalfixed",
                    "n_obs": 100,
                    "psr_vs_benchmark": "0.99",
                    "verdict": "EDGE_CONFIRMED",
                    "beats_benchmark_calmar": True,
                }
            ]
        },
    )
    assert report.deployment_match.historical_passed is False
    assert report.deployment_match.exploration_canary_ready is False


def test_holdout_failure_is_not_reported_as_edge() -> None:
    dates = _dates()
    factors = _candidate_factors(len(dates))
    holdout_start = next(index for index, date in enumerate(dates) if date >= "2007-01-01")
    for candidate in registered_candidates():
        if candidate.allocation == "three_asset_fixed":
            factors[candidate.candidate_id][holdout_start:] = _factors(
                1.002, 0.994, len(dates) - holdout_start
            )

    report = evaluate_profit_evidence(
        dates=dates,
        candidate_factors=factors,
        benchmark_factors=_factors(1.013, 0.985, len(dates)),
    )

    assert report.historical_verdict == "NO_HOLDOUT_EDGE"
    assert report.status == "NO_HOLDOUT_EDGE"
    assert any(not gate.passed for gate in report.gates)
