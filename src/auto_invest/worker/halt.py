"""Halt-flag mechanism (FR-013, research R-10).

A halt-flag file (default `data/halt.flag`) signals "no new orders."
Presence of the file is the gate; absence means normal operation. The
mechanism is filesystem-mediated so it survives a worker restart and
can also be inspected or set manually from a shell when the worker is
unresponsive.

The risk gate `halt_gate` consumes `is_halted()` before every order
submission. The CLI `halt` and `resume` subcommands wrap `set_halt()`
and `clear_halt()` and write the corresponding `HALT_SET` / `HALT_CLEARED`
audit rows.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class HaltState(BaseModel):
    """Persisted halt payload — timestamp + operator-supplied reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    ts_utc: str
    reason: str


def is_halted(flag_path: Path) -> bool:
    """Cheap presence check; safe to call on every loop tick."""
    return flag_path.exists()


def read_halt(flag_path: Path) -> HaltState | None:
    """Return the parsed halt payload, or None when the worker is not halted."""
    if not flag_path.exists():
        return None
    raw = flag_path.read_text(encoding="utf-8")
    return HaltState.model_validate_json(raw)


def set_halt(flag_path: Path, reason: str) -> HaltState:
    """Write the halt flag with the given reason. Overwrites any prior flag.

    Raises:
        ValueError: when `reason` is empty or only whitespace.
    """
    cleaned = (reason or "").strip()
    if not cleaned:
        raise ValueError("halt reason must be a non-empty string")
    state = HaltState(ts_utc=_utcnow_iso_ms(), reason=cleaned)
    flag_path.parent.mkdir(parents=True, exist_ok=True)
    flag_path.write_text(state.model_dump_json(), encoding="utf-8")
    return state


def clear_halt(flag_path: Path) -> bool:
    """Remove the halt flag. Returns True if a flag was present, else False."""
    if not flag_path.exists():
        return False
    flag_path.unlink()
    return True


def _utcnow_iso_ms() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
