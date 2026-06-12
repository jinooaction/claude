"""레짐별 성과 층화 분석 — 전망적 결합·통계 손계산 대조·격리 불변식.

네트워크 0, 라이브 DB 0 — 입력은 CSV 텍스트와 Decimal 목록뿐.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.analytics.regime_stratified import (
    load_timeline_csv,
    load_value_series_csv,
    nav_to_returns,
    stratify_returns,
)

# ---------- 로더 ----------


def test_load_timeline_csv() -> None:
    text = "date,label,flags\n2026-06-01,RISK_ON,\n2026-06-02,CAUTION,vix\n"
    assert load_timeline_csv(text) == {
        "2026-06-01": "RISK_ON",
        "2026-06-02": "CAUTION",
    }
    with pytest.raises(ValueError, match="date/label"):
        load_timeline_csv("a,b\n1,2\n")


def test_load_value_series_csv_skips_missing() -> None:
    pts = load_value_series_csv("date,value\n2026-06-02,101\n2026-06-01,100\n2026-06-03,\n")
    assert pts == [("2026-06-01", Decimal("100")), ("2026-06-02", Decimal("101"))]
    with pytest.raises(ValueError, match="헤더"):
        load_value_series_csv("sym,px\nSPY,1\n")


def test_nav_to_returns_skips_nonpositive() -> None:
    nav = [
        ("2026-06-01", Decimal("100")),
        ("2026-06-02", Decimal("101")),
        ("2026-06-03", Decimal("0")),
        ("2026-06-04", Decimal("99")),
    ]
    rets = nav_to_returns(nav)
    assert rets == [("2026-06-02", Decimal("0.01"))]  # 0 NAV 전후 구간은 제외


# ---------- 전망적 결합 (d일 라벨 ↔ d+1 수익률) ----------


def test_stratify_prospective_join_and_unlabeled() -> None:
    timeline = {
        "2026-06-01": "RISK_ON",
        "2026-06-02": "CAUTION",
        "2026-06-03": "RISK_ON",
    }
    returns = [
        ("2026-06-01", Decimal("0.001")),  # 직전 타임라인 없음 → UNLABELED
        ("2026-06-02", Decimal("0.01")),   # 06-01 라벨(RISK_ON)의 다음 날
        ("2026-06-03", Decimal("-0.02")),  # 06-02 라벨(CAUTION)의 다음 날
        ("2026-06-04", Decimal("0.01")),   # 06-03 라벨(RISK_ON)의 다음 날
    ]
    out = stratify_returns(returns, timeline)
    assert out["by_label"]["RISK_ON"]["n_days"] == 2
    assert out["by_label"]["CAUTION"]["n_days"] == 1
    assert out["by_label"]["UNLABELED"]["n_days"] == 1
    assert out["total_return_days"] == 4
    assert out["all"]["n_days"] == 4


def test_stratify_stats_hand_computed() -> None:
    """+1% 후 -2%: 누적 -1.02%, 최대낙폭 (1.01-0.9898)/1.01 = 2.00%."""
    timeline = {"2026-06-01": "A"}
    returns = [
        ("2026-06-02", Decimal("0.01")),
        ("2026-06-03", Decimal("-0.02")),
    ]
    st = stratify_returns(returns, timeline)["by_label"]["A"]
    assert st["total_return_pct"] == "-1.02"
    assert st["max_drawdown_pct"] == "2.00"
    assert st["worst_day_pct"] == "-2.00" and st["best_day_pct"] == "1.00"
    assert "sharpe" not in st and "20개" in st["note"]  # 관측 부족 — 비율 생략


def test_stratify_ratios_present_with_enough_observations() -> None:
    timeline = {"2026-01-01": "A"}
    # 양의 평균 수익률 30일 — 샤프/연환산 존재, 부호 양수
    returns = [
        (f"2026-02-{i:02d}", Decimal("0.001") * (1 if i % 2 else 2)) for i in range(1, 29)
    ] + [("2026-03-01", Decimal("0.001")), ("2026-03-02", Decimal("0.002"))]
    st = stratify_returns(returns, timeline)["by_label"]["A"]
    assert st["n_days"] == 30
    assert Decimal(st["sharpe"]) > 0
    assert Decimal(st["ann_return_pct"]) > 0
    assert Decimal(st["ann_vol_pct"]) > 0


def test_stratify_empty_returns() -> None:
    out = stratify_returns([], {"2026-06-01": "A"})
    assert out["total_return_days"] == 0 and out["by_label"] == {}


# ---------- 격리 불변식 ----------

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_stratifier_is_research_only() -> None:
    text = (
        _REPO_ROOT / "src" / "auto_invest" / "analytics" / "regime_stratified.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "insert_bar",
        "auto_invest.db",
        "from auto_invest.persistence",
        "from auto_invest.broker",
        "from auto_invest.strategy",
    ):
        assert forbidden not in text, forbidden


def test_live_paths_do_not_import_stratifier() -> None:
    src = _REPO_ROOT / "src" / "auto_invest"
    for sub in ("strategy", "broker", "worker", "risk"):
        for py in (src / sub).rglob("*.py"):
            assert "regime_stratified" not in py.read_text(encoding="utf-8"), py
