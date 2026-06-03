"""스펙 032 — 데이터 최근성(recency) 기준 테스트.

운영자 원칙: 백테스트로 전략을 찾되 *너무 과거*가 아니라 최근 N년 같은 명확한 기준을
쓰라. 트레일링 창 선택 + 신선도 등급/경고가 의도대로 동작하는지 확인한다."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from auto_invest.backtest.recency import (
    AGING_MAX_AGE_DAYS,
    FRESH_MAX_AGE_DAYS,
    DataRecency,
    assess_recency,
    stale_guard,
    trailing_window,
)


@dataclass
class _Src:
    sessions_by_symbol: dict[str, list[date]]

    def session_dates(self, symbol: str) -> list[date]:
        return self.sessions_by_symbol.get(symbol, [])


def _daily(start: date, end: date) -> list[date]:
    out, d = [], start
    from datetime import timedelta

    while d <= end:
        out.append(d)
        d += timedelta(days=1)
    return out


def test_trailing_window_picks_most_recent_n_years():
    # 10년치 데이터 → 트레일링 5년은 끝에서 거꾸로 5년만.
    src = _Src({"A": _daily(date(2010, 1, 1), date(2020, 1, 1))})
    w = trailing_window(src, ["A"], trailing_years=5, today=date(2026, 1, 1))
    assert w is not None
    start, end = w
    assert end == date(2020, 1, 1)  # 가장 최근 세션
    assert date(2014, 12, 1) <= start <= date(2015, 2, 1)  # ~5년 전


def test_trailing_window_clamps_to_available_when_shorter():
    # 2년치만 있는데 5년을 요청 → 가용 전 구간(클램프).
    src = _Src({"A": _daily(date(2018, 1, 1), date(2020, 1, 1))})
    w = trailing_window(src, ["A"], trailing_years=5, today=date(2026, 1, 1))
    assert w == (date(2018, 1, 1), date(2020, 1, 1))


def test_assess_recency_classifies_stale_for_old_data():
    src = _Src({"A": _daily(date(2013, 1, 1), date(2018, 2, 7))})
    r = assess_recency(src, ["A"], today=date(2026, 6, 1))
    assert r is not None
    assert r.staleness == "stale"
    assert r.is_stale
    assert r.age_days > AGING_MAX_AGE_DAYS
    assert "경고" in r.banner()  # stale 은 큰 경고를 단다


def test_assess_recency_fresh_and_aging_boundaries():
    today = date(2026, 6, 1)
    # fresh: 최신 바가 오늘에 가까움.
    fresh = _Src({"A": [date(2026, 5, 1)]})
    assert assess_recency(fresh, ["A"], today=today).staleness == "fresh"
    # aging: FRESH 와 AGING 임계 사이.
    from datetime import timedelta

    aging_day = today - timedelta(days=(FRESH_MAX_AGE_DAYS + AGING_MAX_AGE_DAYS) // 2)
    aging = _Src({"A": [aging_day]})
    assert assess_recency(aging, ["A"], today=today).staleness == "aging"


def test_assess_recency_none_when_no_sessions():
    assert assess_recency(_Src({}), ["A"], today=date(2026, 1, 1)) is None
    assert trailing_window(_Src({}), ["A"], trailing_years=5) is None


# --------------------------------------------------------- stale_guard (stop-sign)


def _recency(staleness: str) -> DataRecency:
    return DataRecency(
        oldest_session=date(2013, 1, 1),
        newest_session=date(2018, 1, 1),
        span_days=1826,
        age_days=3000,
        staleness=staleness,
        today=date(2026, 1, 1),
    )


def test_stale_guard_refuses_stale_without_allow():
    # 재발 방지의 핵심: stale 데이터는 명시적 옵트인 없이는 거부 텍스트를 돌려준다.
    msg = stale_guard(_recency("stale"), allow_stale=False)
    assert msg is not None
    assert "REFUSED" in msg
    assert "FORWARD-VALIDATION" in msg
    assert "--allow-stale" in msg


def test_stale_guard_allows_stale_with_explicit_optin():
    assert stale_guard(_recency("stale"), allow_stale=True) is None


def test_stale_guard_proceeds_for_fresh_and_aging():
    assert stale_guard(_recency("fresh"), allow_stale=False) is None
    assert stale_guard(_recency("aging"), allow_stale=False) is None


def test_stale_guard_none_recency_proceeds():
    # 데이터가 없으면(평가 불가) 가드는 진행을 막지 않는다(다른 곳에서 처리).
    assert stale_guard(None, allow_stale=False) is None
