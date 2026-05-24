"""Per-judgment-point rolling cost budget (US4 / FR-041).

판단 지점별 롤링 비용을 추적해 선언된 윈도 예산을 초과하면 그 지점을
비활성(폴백 전환)으로 표시한다. 비용 폭주 시 거래는 계속 동작하되 그 판단
지점만 결정론적 폴백으로 떨어진다(서킷브레이커와 별개의 비용 가드).

인메모리·결정론적: 주입 가능한 clock 으로 테스트에서 시간 진행을 통제한다.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class BudgetTracker:
    """판단 지점별 롤링 윈도 비용 추적 + 예산 초과 판정.

    `rolling_budget_usd[decision_class]` 가 윈도 내 누적 비용 상한이다. 해당
    키가 없으면 그 판단 지점은 예산 무제한(추적만)으로 취급한다.
    """

    rolling_budget_usd: dict[str, Decimal] = field(default_factory=dict)
    window_seconds: float = 86_400.0
    clock: Callable[[], float] = field(default=time.monotonic)
    _events: dict[str, deque[tuple[float, Decimal]]] = field(
        init=False, default_factory=dict
    )

    def record(self, decision_class: str, cost_usd: Decimal) -> None:
        """한 번의 판단 호출 비용을 기록."""
        now = self.clock()
        bucket = self._events.setdefault(decision_class, deque())
        bucket.append((now, Decimal(cost_usd)))
        self._evict(decision_class, now)

    def rolling_cost(self, decision_class: str) -> Decimal:
        """윈도 내 누적 비용(USD)."""
        now = self.clock()
        self._evict(decision_class, now)
        bucket = self._events.get(decision_class)
        if not bucket:
            return Decimal("0")
        return sum((cost for _, cost in bucket), Decimal("0"))

    def is_disabled(self, decision_class: str) -> bool:
        """롤링 비용이 예산 이상이면 True(폴백 전환 대상)."""
        budget = self.rolling_budget_usd.get(decision_class)
        if budget is None:
            return False
        return self.rolling_cost(decision_class) >= budget

    def _evict(self, decision_class: str, now: float) -> None:
        bucket = self._events.get(decision_class)
        if not bucket:
            return
        cutoff = now - self.window_seconds
        while bucket and bucket[0][0] < cutoff:
            bucket.popleft()
