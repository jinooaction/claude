"""XNYS regular-session identity for production live-order deduplication."""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from auto_invest.worker.schedule import is_session_open, next_session_open

_NEW_YORK = ZoneInfo("America/New_York")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def open_xnys_session_key(
    now: datetime | None = None,
    *,
    clock: Callable[[], datetime] = _utcnow,
) -> str | None:
    """Return the New York date only while the XNYS regular session is open."""
    moment = now if now is not None else clock()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    moment = moment.astimezone(UTC)
    if not is_session_open(moment):
        return None
    return moment.astimezone(_NEW_YORK).date().isoformat()


def main() -> int:
    """Print the current open-session key, or exit 75 without consuming a claim."""
    moment = _utcnow()
    key = open_xnys_session_key(moment)
    if key is None:
        next_open = next_session_open(moment)
        print(
            "REFUSED: XNYS regular session is closed; "
            f"checked_at={moment.isoformat()} next_open={next_open.isoformat()}",
            file=sys.stderr,
        )
        return 75
    print(key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
