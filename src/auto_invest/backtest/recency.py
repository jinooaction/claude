"""스펙 032 — 데이터 최근성(recency) 기준.

운영자 원칙(2026-06-01): "옛 데이터로 전략을 맞추는 것도 중요하다. 다만 *너무 과거*가
아니라 최근 N년(예: 5개년)처럼 기준을 명확히 하라."

백테스트는 전략을 발굴·적합하는 일급 도구다 — 단, **최근 데이터**여야 현재 regime 을
대표한다. 이 모듈은 그 기준을 명확히 한다:

1. `trailing_window(...)` — 가용 데이터의 *가장 최근* N년 창 [from, to] 를 고른다
   (to = 가장 최근 세션, from = to − N년). "최근 5개년"을 기계적으로 강제.
2. `assess_recency(...)` — 가장 최근 바가 *오늘* 대비 얼마나 오래됐는지(age) 를 재고
   신선도 등급(fresh/aging/stale)을 매긴다. stale 이면 "이 백테스트는 옛 regime 을
   측정한다"를 큰 소리로 경고 — 운영자 우려를 막연한 철학이 아니라 명확한 신호로.

오프라인·읽기 전용. Kernel 터치 0건.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# 신선도 임계 (오늘 대비 가장 최근 바의 나이, 일 단위). 명확한 공개 기준.
FRESH_MAX_AGE_DAYS = 183   # ~6개월: 현재 regime 으로 간주.
AGING_MAX_AGE_DAYS = 730   # ~2년: 쓸 수 있으나 regime 이 바뀌었을 수 있음.
# 그 이상은 stale: 옛 regime. 운영자 원칙상 단독 채택 근거로 삼지 말 것.

DEFAULT_TRAILING_YEARS = 5


@dataclass(frozen=True)
class DataRecency:
    """가용 데이터의 시간 범위 + 오늘 대비 신선도."""

    oldest_session: date
    newest_session: date
    span_days: int
    age_days: int  # today − newest_session
    staleness: str  # "fresh" | "aging" | "stale"
    today: date

    @property
    def is_stale(self) -> bool:
        return self.staleness == "stale"

    def banner(self) -> str:
        """사람이 읽는 한 줄 신선도 배너 (CLI 출력용)."""
        msg = (
            f"데이터 최근성: {self.oldest_session}~{self.newest_session} "
            f"(최신 바가 오늘 {self.today} 기준 {self.age_days}일 전), 등급={self.staleness}"
        )
        if self.staleness == "stale":
            msg += (
                "  ⚠ 경고: 이 데이터는 옛 regime 을 측정한다(현재 시장 구조와 다를 수 있음). "
                "단독으로 라이브를 정당화하지 말고 forward 페이퍼로 확인하라."
            )
        elif self.staleness == "aging":
            msg += "  주의: regime 이 일부 바뀌었을 수 있음 — 가장 최근 구간을 더 신뢰하라."
        return msg


# FORWARD-VALIDATION.md 교리를 도구 수준 stop-sign 으로 강제하는 메시지.
STALE_REFUSAL_HINT = (
    "REFUSED: 데이터가 stale 입니다(>2년 묵음). 옛 데이터 백테스트로 전략 결론을 "
    "내리지 마세요 — 교리 specs/032-portfolio-rebalancing/FORWARD-VALIDATION.md "
    "(현재 데이터 forward 페이퍼만 판정). 한계 시연용이면 --allow-stale 를 명시하세요."
)


def stale_guard(recency: DataRecency | None, *, allow_stale: bool) -> str | None:
    """FORWARD-VALIDATION 교리의 stop-sign.

    데이터가 stale 인데 호출자가 명시적으로 한계 시연을 옵트인하지 않았으면, CLI 가
    stderr 로 찍고 거부(exit 70)해야 할 텍스트를 돌려준다. 진행해도 안전하면
    (fresh/aging, 또는 ``allow_stale=True``) ``None`` 을 돌려준다. 옛 데이터 백테스트로
    전략 결론을 내리는 재발을 *도구 수준에서* 막는다 — 경고를 각주로 무시할 수 없게.
    """
    if recency is not None and recency.is_stale and not allow_stale:
        return recency.banner() + "\n" + STALE_REFUSAL_HINT
    return None


def _union_sessions(data_source, universe) -> list[date]:  # noqa: ANN001
    """유니버스 전 심볼의 세션 날짜 합집합(오름차순)."""
    seen: set[date] = set()
    for sym in universe:
        try:
            seen.update(data_source.session_dates(sym))
        except Exception:  # noqa: BLE001 — 데이터 소스가 심볼을 모르면 건너뜀
            continue
    return sorted(seen)


def _classify(age_days: int) -> str:
    if age_days <= FRESH_MAX_AGE_DAYS:
        return "fresh"
    if age_days <= AGING_MAX_AGE_DAYS:
        return "aging"
    return "stale"


def assess_recency(data_source, universe, *, today: date | None = None) -> DataRecency | None:  # noqa: ANN001
    """가용 데이터의 범위 + 오늘 대비 신선도. 세션이 없으면 None."""
    ref = today or date.today()
    sessions = _union_sessions(data_source, universe)
    if not sessions:
        return None
    oldest, newest = sessions[0], sessions[-1]
    age = (ref - newest).days
    return DataRecency(
        oldest_session=oldest,
        newest_session=newest,
        span_days=(newest - oldest).days,
        age_days=age,
        staleness=_classify(age),
        today=ref,
    )


def trailing_window(
    data_source,  # noqa: ANN001
    universe,  # noqa: ANN001
    *,
    trailing_years: int = DEFAULT_TRAILING_YEARS,
    today: date | None = None,
) -> tuple[date, date] | None:
    """가용 데이터의 가장 최근 ``trailing_years`` 년 창 [from, to] 를 고른다.

    ``to`` = 가장 최근 세션, ``from`` = ``to`` − trailing_years 년. 데이터가 그보다
    짧으면 가용한 전 구간을 쓴다(from 은 가장 오래된 세션으로 클램프). 세션이 없으면 None.

    *명확한 기준*: 평가 창을 임의로 잡지 않고 "데이터 끝에서 거꾸로 N년"으로 고정한다.
    """
    if trailing_years < 1:
        raise ValueError(f"trailing_years must be >= 1, got {trailing_years}")
    sessions = _union_sessions(data_source, universe)
    if not sessions:
        return None
    oldest, newest = sessions[0], sessions[-1]
    start = newest - timedelta(days=int(365.25 * trailing_years))
    if start < oldest:
        start = oldest
    return start, newest
