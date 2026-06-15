"""스펙 047 후속 — 깊은 OOS walk-forward 비교 단위 테스트.

순수·결정론을 못 박는다. 실데이터(네트워크) 없이 합성 시계열·직접 구성한 LegStats 로 *판정
수학*을 검증한다(구간 타일링·방어 엣지 기준·챔피언 선정·정렬·결정성).
"""

from __future__ import annotations

import pytest

from auto_invest.analytics.deep_walk_forward import (
    VERDICT_DEFENSE_EDGE,
    VERDICT_NO_EDGE,
    VERDICT_RETURN_EDGE,
    CandidateRobustness,
    _classify_robustness,
    _meets_defense,
    deep_walk_forward_compare,
    evaluate_candidate,
    tile_windows,
)
from auto_invest.analytics.global_trend import align_gold_levels
from auto_invest.analytics.risk_managed_beta import LegStats, MonthlyRow

# ──────────────────────────── 보조: 합성 데이터 ────────────────────────────


def _rows(prices: list[float], *, div: float = 0.0, rate: float = 4.0) -> list[MonthlyRow]:
    return [
        MonthlyRow(
            date=f"19{71 + i // 12:02d}-{1 + i % 12:02d}-01",
            price=p,
            dividend=div,
            long_rate=rate,
        )
        for i, p in enumerate(prices)
    ]


def _gold_for_rows(rows: list[MonthlyRow], prices: list[float]) -> dict[str, float]:
    return {r.date[:7]: p for r, p in zip(rows, prices, strict=True)}


def _leg(
    *,
    cagr: float,
    sharpe: float,
    max_dd: float,
    calmar: float | None,
    n: int = 120,
) -> LegStats:
    return LegStats(
        cagr_pct=cagr,
        vol_pct=10.0,
        sharpe=sharpe,
        max_dd_pct=max_dd,
        calmar=calmar,
        psr_gt0=0.9,
        pct_in_market=1.0,
        n_months=n,
    )


# ──────────────────────────── 구간 타일링 ────────────────────────────


def test_tile_windows_exact_multiple() -> None:
    assert tile_windows(120, segment_months=60, min_window_months=24) == [
        (0, 60),
        (60, 60),
    ]


def test_tile_windows_keeps_long_enough_remainder() -> None:
    # 100 = 60 + 40, 40 >= 24 → 독립 구간으로 유지.
    assert tile_windows(100, segment_months=60, min_window_months=24) == [
        (0, 60),
        (60, 40),
    ]


def test_tile_windows_absorbs_short_remainder() -> None:
    # 70 = 60 + 10, 10 < 24 → 직전 구간에 흡수.
    assert tile_windows(70, segment_months=60, min_window_months=24) == [(0, 70)]


def test_tile_windows_absorbs_short_tail_of_three() -> None:
    # 130 = 60 + 60 + 10 → 마지막 10 흡수 → 60 + 70.
    assert tile_windows(130, segment_months=60, min_window_months=24) == [
        (0, 60),
        (60, 70),
    ]


def test_tile_windows_too_short_returns_empty() -> None:
    assert tile_windows(20, segment_months=60, min_window_months=24) == []


def test_tile_windows_segment_smaller_than_min_raises() -> None:
    with pytest.raises(ValueError, match="segment_months"):
        tile_windows(100, segment_months=12, min_window_months=24)


def test_tile_windows_total_length_preserved() -> None:
    for n in (24, 59, 60, 61, 119, 120, 121, 240, 301):
        tiles = tile_windows(n, segment_months=60, min_window_months=24)
        if tiles:
            assert sum(length for _, length in tiles) == n
            # 연속·비중첩.
            cursor = 0
            for start, length in tiles:
                assert start == cursor
                cursor += length


# ──────────────────────────── 방어 엣지 기준 ────────────────────────────


def test_meets_defense_true_when_dd_cut_calmar_up_sharpe_ok() -> None:
    bench = _leg(cagr=8, sharpe=0.5, max_dd=50, calmar=0.16)
    cand = _leg(cagr=7, sharpe=0.9, max_dd=10, calmar=0.7)
    assert _meets_defense(cand, bench) is True


def test_meets_defense_false_when_dd_not_cut_enough() -> None:
    bench = _leg(cagr=8, sharpe=0.5, max_dd=50, calmar=0.16)
    cand = _leg(cagr=7, sharpe=0.9, max_dd=45, calmar=0.7)  # 45 > 0.8*50=40
    assert _meets_defense(cand, bench) is False


def test_meets_defense_false_when_sharpe_worse() -> None:
    bench = _leg(cagr=8, sharpe=0.9, max_dd=50, calmar=0.16)
    cand = _leg(cagr=7, sharpe=0.4, max_dd=10, calmar=0.7)  # 샤프 악화
    assert _meets_defense(cand, bench) is False


def test_meets_defense_false_when_calmar_none() -> None:
    bench = _leg(cagr=8, sharpe=0.5, max_dd=50, calmar=None)
    cand = _leg(cagr=7, sharpe=0.9, max_dd=10, calmar=0.7)
    assert _meets_defense(cand, bench) is False


# ──────────────────────────── 전체표본 판정 ────────────────────────────


def test_classify_defense_edge() -> None:
    bench = _leg(cagr=8, sharpe=0.5, max_dd=50, calmar=0.16)
    cand = _leg(cagr=7, sharpe=0.9, max_dd=10, calmar=0.7)  # 방어인데 CAGR 은 낮음
    verdict, reason = _classify_robustness(cand, bench, sharpe_wins=3, n_windows=11)
    assert verdict == VERDICT_DEFENSE_EDGE
    assert "구간 샤프 승 3/11" in reason


def test_classify_return_edge_needs_sharpe_and_cagr_both_higher() -> None:
    bench = _leg(cagr=8, sharpe=0.5, max_dd=50, calmar=0.16)
    cand = _leg(cagr=10, sharpe=1.0, max_dd=10, calmar=1.0)  # 방어 + 샤프 + CAGR
    verdict, _ = _classify_robustness(cand, bench, sharpe_wins=8, n_windows=11)
    assert verdict == VERDICT_RETURN_EDGE


def test_classify_no_edge_when_defense_fails() -> None:
    bench = _leg(cagr=8, sharpe=0.5, max_dd=50, calmar=0.16)
    cand = _leg(cagr=6, sharpe=0.4, max_dd=48, calmar=0.12)
    verdict, reason = _classify_robustness(cand, bench, sharpe_wins=1, n_windows=11)
    assert verdict == VERDICT_NO_EDGE
    assert "낙폭 충분히 안 줄음" in reason


def test_classify_no_edge_when_calmar_undefined() -> None:
    bench = _leg(cagr=8, sharpe=0.5, max_dd=0, calmar=None)
    cand = _leg(cagr=7, sharpe=0.9, max_dd=0, calmar=None)
    verdict, reason = _classify_robustness(cand, bench, sharpe_wins=0, n_windows=5)
    assert verdict == VERDICT_NO_EDGE
    assert "칼마 정의 불가" in reason


# ──────────────────────────── 후보 평가 ────────────────────────────


def test_evaluate_candidate_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="align"):
        evaluate_candidate(
            [1.0, 1.0, 1.0],
            [1.0, 1.0],
            key="x",
            label="x",
            spec="000",
            segment_months=60,
            min_window_months=24,
        )


def test_evaluate_candidate_identical_streams_no_edge() -> None:
    # 후보 == 벤치마크 → 어디서도 *엄격히* 이기지 못함 → 엣지 없음.
    stream = [1.01, 0.99, 1.02, 0.98, 1.01, 1.0] * 10  # 60 개월
    result = evaluate_candidate(
        stream,
        list(stream),
        key="id",
        label="동일",
        spec="000",
        segment_months=30,
        min_window_months=24,
    )
    assert result.sharpe_wins == 0
    assert result.defense_edge_wins == 0
    assert result.verdict == VERDICT_NO_EDGE
    assert result.n_windows == 2


def test_evaluate_candidate_is_deterministic() -> None:
    cand = [1.02, 0.99, 1.01, 1.0, 1.03, 0.98] * 10
    bench = [1.01, 1.0, 1.0, 1.01, 1.0, 1.0] * 10
    a = evaluate_candidate(
        cand, bench, key="k", label="L", spec="047",
        segment_months=30, min_window_months=24,
    )
    b = evaluate_candidate(
        cand, bench, key="k", label="L", spec="047",
        segment_months=30, min_window_months=24,
    )
    assert a.as_dict(include_windows=True) == b.as_dict(include_windows=True)


def test_evaluate_candidate_window_count_and_dict_shape() -> None:
    cand = [1.01, 1.0, 1.02, 0.99] * 30  # 120 개월
    bench = [1.0, 1.01, 1.0, 1.0] * 30
    result = evaluate_candidate(
        cand, bench, key="k", label="L", spec="047",
        segment_months=60, min_window_months=24,
    )
    assert result.n_windows == 2
    assert 0 <= result.sharpe_wins <= result.n_windows
    d = result.as_dict()
    assert set(d) >= {
        "key", "label", "spec", "verdict", "full_period", "full_benchmark",
        "sharpe_wins", "defense_edge_wins", "worst_window_cagr_pct",
    }
    assert "windows" not in d  # 기본은 미포함
    assert "windows" in result.as_dict(include_windows=True)


# ──────────────────────────── 전체 비교(합성 통합) ────────────────────────────


def _synthetic_inputs(n: int = 84) -> tuple[list[MonthlyRow], list[float]]:
    # 완만한 상승 + 중간 폭락(추세가 방어할 거리)을 가진 합성 시계열.
    prices: list[float] = []
    p = 100.0
    for i in range(n):
        if 36 <= i < 42:  # 6개월 약세장
            p *= 0.93
        else:
            p *= 1.012
        prices.append(p)
    rows = _rows(prices, div=0.2, rate=4.0)
    # 금: 주식과 어긋난 위상의 완만한 시계열.
    gold_prices = [50.0 * (1.0 + 0.004 * i + 0.05 * ((i % 7) - 3)) for i in range(n)]
    gold = align_gold_levels(rows, _gold_for_rows(rows, gold_prices))
    return rows, gold


def test_compare_alignment_validation() -> None:
    rows, gold = _synthetic_inputs()
    with pytest.raises(ValueError, match="align"):
        deep_walk_forward_compare(rows, gold[:-1])


def test_compare_produces_four_candidates_with_shared_benchmark() -> None:
    rows, gold = _synthetic_inputs()
    report = deep_walk_forward_compare(
        rows, gold, window=10, segment_months=24, min_window_months=12
    )
    keys = [c.key for c in report.candidates]
    assert keys == [
        "trend_equity",
        "trend_2asset",
        "trend_3asset_fixed",
        "trend_3asset_invvol",
    ]
    # 모든 후보가 *같은* 벤치마크(등가중 단순 보유)와 비교된다.
    benches = {c.full_benchmark.as_dict()["cagr_pct"] for c in report.candidates}
    assert len(benches) == 1
    # 각 후보 판정은 정의된 셋 중 하나.
    valid = {VERDICT_RETURN_EDGE, VERDICT_DEFENSE_EDGE, VERDICT_NO_EDGE}
    assert all(c.verdict in valid for c in report.candidates)


def test_compare_is_deterministic() -> None:
    rows, gold = _synthetic_inputs()
    a = deep_walk_forward_compare(rows, gold, segment_months=24, min_window_months=12)
    b = deep_walk_forward_compare(rows, gold, segment_months=24, min_window_months=12)
    assert a.as_dict(include_windows=True) == b.as_dict(include_windows=True)


def test_compare_champion_is_best_edged_or_none() -> None:
    rows, gold = _synthetic_inputs()
    report = deep_walk_forward_compare(
        rows, gold, segment_months=24, min_window_months=12
    )
    champ = report.champion
    if champ is not None:
        assert champ.verdict != VERDICT_NO_EDGE
        # as_dict 의 champion_key 와 일치.
        assert report.as_dict()["champion_key"] == champ.key
    else:
        assert report.as_dict()["champion_key"] is None


def test_report_dict_shape() -> None:
    rows, gold = _synthetic_inputs()
    report = deep_walk_forward_compare(
        rows, gold, segment_months=24, min_window_months=12
    )
    d = report.as_dict()
    assert d["schema_version"] == "1.0"
    assert set(d) >= {
        "window", "segment_months", "n_months_total", "n_windows",
        "benchmark_label", "champion_key", "champion_verdict", "candidates",
    }
    assert isinstance(d["candidates"], list)
    assert len(d["candidates"]) == 4


def test_candidate_robustness_is_frozen() -> None:
    rows, gold = _synthetic_inputs()
    report = deep_walk_forward_compare(
        rows, gold, segment_months=24, min_window_months=12
    )
    c = report.candidates[0]
    assert isinstance(c, CandidateRobustness)
    with pytest.raises((AttributeError, TypeError)):
        c.verdict = "x"  # type: ignore[misc]
