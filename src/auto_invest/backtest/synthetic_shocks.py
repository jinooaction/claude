"""Synthetic-shock date set for the backtest engine (T029, FR-B09).

Loads `config/synthetic_shocks.toml` and resolves the dynamic
"most_recent_quarterly_opex" entry to the appropriate Mar/Jun/Sep/Dec
third Friday on or before `today`, adjusted for early-close days via
`exchange_calendars.XNYS` (the same dep `worker/schedule.py` uses — no
K6 touch).

The shock set is the operator-authored safety surface that spec 007's
hardened canary replays against to surface regressions that single-metric
PnL cannot catch. Adding/removing dates here is operator-only per spec
007's promotion criteria.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import exchange_calendars as ec

from .data_model import SyntheticShockDay

DEFAULT_CONFIG_PATH = Path("config/synthetic_shocks.toml")

_DYNAMIC_NAME = "most_recent_quarterly_opex"
_QUARTERLY_MONTHS = (3, 6, 9, 12)
_XNYS = ec.get_calendar("XNYS")


class SyntheticShockConfigError(ValueError):
    """Raised when synthetic_shocks.toml is malformed or missing required entries."""


def _third_friday(year: int, month: int) -> date:
    """Date of the third Friday of (year, month) — equity options expiry convention."""
    first = date(year, month, 1)
    # Python weekday(): Monday=0 .. Sunday=6 → Friday=4.
    first_friday_offset = (4 - first.weekday()) % 7
    first_friday = first + timedelta(days=first_friday_offset)
    return first_friday + timedelta(days=14)


def _adjust_to_session_day(d: date) -> date:
    """Walk back to the nearest XNYS session day (handles holiday-on-3rd-Friday).

    Third Friday is rarely a holiday but Good-Friday + April-third-Friday alignment
    can shift OPEX in the rare overlap. Walking back keeps the resolver
    deterministic without baking in calendar exceptions.
    """
    cur = d
    for _ in range(7):
        if _XNYS.is_session(cur.isoformat()):
            return cur
        cur -= timedelta(days=1)
    raise SyntheticShockConfigError(
        f"could not find an XNYS session day on or before {d.isoformat()}"
    )


def most_recent_quarterly_opex(*, today: date) -> date:
    """Third Friday of the most recently COMPLETED Mar/Jun/Sep/Dec on or before today.

    "Most recently completed" means the third Friday must be < today; if today
    IS itself a third Friday, the result is the PRIOR quarter's OPEX (so the
    canary's input is stable for the full day rather than flipping at the
    intraday moment the new OPEX session closes).
    """
    candidates: list[date] = []
    # Look back across this year and last year — enough for any today.
    for year in (today.year, today.year - 1):
        for month in _QUARTERLY_MONTHS:
            opex = _adjust_to_session_day(_third_friday(year, month))
            if opex < today:
                candidates.append(opex)
    if not candidates:
        raise SyntheticShockConfigError(
            f"no quarterly OPEX day found on or before {today.isoformat()}"
        )
    return max(candidates)


@dataclass(frozen=True)
class _RawShock:
    name: str
    session_date_str: str
    expected_gate_trip: str
    note: str


def _read_raw_shocks(path: Path) -> list[_RawShock]:
    if not path.exists():
        raise SyntheticShockConfigError(f"synthetic_shocks.toml not found: {path}")
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    shocks_raw = raw.get("shocks", [])
    if not shocks_raw:
        raise SyntheticShockConfigError(f"no [[shocks]] entries in {path}")
    out: list[_RawShock] = []
    for i, entry in enumerate(shocks_raw):
        name = entry.get("name")
        session_date_str = entry.get("session_date")
        if not name or not session_date_str:
            raise SyntheticShockConfigError(
                f"[[shocks]] entry {i} missing name / session_date"
            )
        out.append(
            _RawShock(
                name=str(name),
                session_date_str=str(session_date_str),
                expected_gate_trip=str(entry.get("expected_gate_trip", "")),
                note=str(entry.get("note", "")),
            )
        )
    return out


def resolve_synthetic_shock_dates(
    *,
    today: date,
    path: Path | None = None,
) -> list[SyntheticShockDay]:
    """Resolve the operator-declared shocks, materialising any DYNAMIC entries.

    Returns the list of fully-resolved `SyntheticShockDay` rows in the order
    declared in the TOML. The `most_recent_quarterly_opex` entry's
    `session_date == "DYNAMIC"` placeholder is replaced with the computed
    third-Friday date.

    Determinism note: `today` is the only non-config input, so a backtest
    run from a fixed `today` parameter is reproducible. The CLI passes
    `today=date.today()` only outside the WallClockGuard scope; inside
    the guard the engine uses the already-resolved list.
    """
    raw_path = path or DEFAULT_CONFIG_PATH
    raws = _read_raw_shocks(raw_path)
    resolved: list[SyntheticShockDay] = []
    for r in raws:
        if r.name == _DYNAMIC_NAME and r.session_date_str.upper() == "DYNAMIC":
            session_date = most_recent_quarterly_opex(today=today)
        else:
            try:
                session_date = date.fromisoformat(r.session_date_str)
            except ValueError as exc:
                raise SyntheticShockConfigError(
                    f"shock {r.name!r}: session_date {r.session_date_str!r} not ISO-8601"
                ) from exc
        resolved.append(
            SyntheticShockDay(
                name=r.name,
                session_date=session_date,
                expected_gate_trip=r.expected_gate_trip,
                note=r.note,
            )
        )
    return resolved


def shock_window(shock: SyntheticShockDay, *, lookback_bars: int = 30) -> tuple[date, date]:
    """The replay window for one shock — N trading days BEFORE through the shock day.

    Lookback is needed because indicator triggers (EMA, RSI) require prior
    history; for v1 we give every shock a 30-trading-day lookback by default,
    which is enough for EMA(20) / RSI(14) to be armed by the shock date.
    """
    sessions = _XNYS.sessions_in_range(
        (shock.session_date - timedelta(days=120)).isoformat(),
        shock.session_date.isoformat(),
    )
    py_sessions = [
        s.date() if hasattr(s, "date") else s for s in sessions
    ]
    if shock.session_date not in py_sessions:
        # Shock day was not a session (data quality issue); fall back to
        # the last session on or before.
        py_sessions = [d for d in py_sessions if d <= shock.session_date]
    start = (
        py_sessions[0]
        if len(py_sessions) <= lookback_bars
        else py_sessions[-lookback_bars - 1]
    )
    return start, shock.session_date


def shock_names(shocks: Iterable[SyntheticShockDay]) -> list[str]:
    return [s.name for s in shocks]


__all__ = [
    "DEFAULT_CONFIG_PATH",
    "SyntheticShockConfigError",
    "most_recent_quarterly_opex",
    "resolve_synthetic_shock_dates",
    "shock_names",
    "shock_window",
]
