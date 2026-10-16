"""돈 경로 보고서의 실제 주문 차단 사유 선택. 판정·주문 권한은 변경하지 않는다."""

from collections.abc import Mapping
from typing import Any


def live_blocking_detail(money: Mapping[str, Any] | None) -> str:
    """Return an explicit live blocker; old or malformed details use caller fallback."""
    if not money:
        return ""
    live = money.get("live_money_state")
    if not isinstance(live, Mapping) or live.get("status") != "BLOCKED":
        return ""
    detail = live.get("detail")
    return detail.strip() if isinstance(detail, str) else ""
