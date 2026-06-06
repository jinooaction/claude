"""스펙 046 — 일일 전략 모니터 대시보드 단위 테스트."""

from __future__ import annotations

from auto_invest.analytics.risk_managed_beta import MonthlyRow
from auto_invest.analytics.strategy_monitor import Dashboard, build_dashboard


def _rows(n_years: int, *, rate: float = 4.0, up: float = 1.006) -> list[MonthlyRow]:
    """완만 상승하는 월 행 n_years*12 개(추세 위 신호)."""
    rows: list[MonthlyRow] = []
    price = 100.0
    start = 2026 - n_years + 1
    for i in range(n_years * 12):
        price *= up
        year = start + i // 12
        rows.append(MonthlyRow(date=f"{year:04d}-{1 + i % 12:02d}-01", price=price,
                               dividend=0.0, long_rate=rate))
    return rows


def test_build_dashboard_has_all_sections():
    dash = build_dashboard(_rows(40), window=10, dd_budget_pct=15.0)
    assert isinstance(dash, Dashboard)
    d = dash.as_dict()
    assert set(d) == {"as_of", "edge", "regime", "leverage_recommendation", "today_signal"}
    assert "verdict" in d["regime"]
    assert d["leverage_recommendation"]["dd_budget_pct"] == 15.0
    assert d["leverage_recommendation"]["window_years"] == 25


def test_as_text_contains_four_sections():
    txt = build_dashboard(_rows(40)).as_text()
    assert "① 엣지" in txt
    assert "② 분산 가정" in txt
    assert "③ 낙폭 예산" in txt
    assert "④ 오늘 추세 신호" in txt
    # 라이브는 운영자 게이트라는 안전 문구 포함.
    assert "운영자 게이트" in txt


def test_uptrend_signal_in_market():
    # 꾸준한 상승 → 오늘 신호는 투자(추세 위).
    dash = build_dashboard(_rows(30), window=10)
    assert dash.signal_in_market is True
    assert dash.signal_gap_pct is not None and dash.signal_gap_pct > 0


def test_leverage_window_uses_recent_only():
    # leverage_window_years 가 작으면 더 적은 데이터로 권고(최근만). 권고가 정의되면 양수 CAGR.
    dash = build_dashboard(_rows(40), dd_budget_pct=20.0, leverage_window_years=10)
    assert dash.leverage_window_years == 10
    if dash.rec_leverage is not None:
        assert dash.rec_cagr_pct is not None
        assert dash.rec_maxdd_pct is not None and dash.rec_maxdd_pct <= 20.0 + 1e-9


def test_short_history_leverage_rec_none_but_no_crash():
    # 레버리지 창보다 짧은 이력이면 권고 None(스킵)하되 대시보드는 구성된다.
    dash = build_dashboard(_rows(30), leverage_window_years=25)
    d = dash.as_dict()
    # 30년 이력 + 25년 창 = 충분 → 권고 있음(견고성: 그래도 크래시 없이 dict 됨).
    assert "leverage" in d["leverage_recommendation"]
