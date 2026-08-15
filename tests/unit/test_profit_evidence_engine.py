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
                }
            ]
        },
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
