"""안전 게이트 (스펙 005, FR-A03·A14, R-3·R-7).

- 장 시간 게이트(헌법 VIII.A): 미국 정규장이 열려 있거나 개장 30분 전 마진
  안이면 L1 적용을 차단한다. 기존 `worker/schedule` 를 **읽기만** 한다(K6 미수정).
- 측정 기반 게이트(헌법 X): 윈도 표본이 최소 표본 미만이면 튜닝을 거부한다.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from auto_invest.worker import schedule

PRE_OPEN_MARGIN = timedelta(minutes=30)
DEFAULT_MIN_SAMPLE = 20


def market_hours_blocked(now: datetime) -> bool:
    """정규장 중이거나 개장 30분 전 마진 안이면 True(L1 적용 차단).

    정규장 전체를 차단하므로 FR-A03 의 '개장 후 30분/폐장 전 30분' 위험 창은
    자동으로 포함된다(헌법 VIII.A 글자 그대로 준수, 더 보수적).
    """
    if schedule.is_session_open(now):
        return True
    next_open = schedule.next_session_open(now)
    delta = (next_open - now).total_seconds()
    return 0 <= delta <= PRE_OPEN_MARGIN.total_seconds()


def measurement_sufficient(sample: int, min_sample: int = DEFAULT_MIN_SAMPLE) -> bool:
    """윈도 표본이 최소 표본 이상이면 True(헌법 X 측정 기반)."""
    return sample >= min_sample


__all__ = [
    "DEFAULT_MIN_SAMPLE",
    "PRE_OPEN_MARGIN",
    "market_hours_blocked",
    "measurement_sufficient",
]
