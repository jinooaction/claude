"""Tests for `auto_invest.worker.halt` (T022)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from auto_invest.worker.halt import (
    HaltState,
    clear_halt,
    is_halted,
    read_halt,
    set_halt,
)

ISO_MS_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def test_is_halted_false_when_no_file(tmp_path: Path):
    assert is_halted(tmp_path / "halt.flag") is False


def test_read_halt_none_when_no_file(tmp_path: Path):
    assert read_halt(tmp_path / "halt.flag") is None


def test_set_halt_creates_file_and_payload(tmp_path: Path):
    flag = tmp_path / "halt.flag"
    state = set_halt(flag, "investigating")

    assert flag.exists()
    assert is_halted(flag) is True
    assert state.reason == "investigating"
    assert ISO_MS_PATTERN.match(state.ts_utc)


def test_set_halt_creates_parent_directory(tmp_path: Path):
    flag = tmp_path / "nested" / "deeper" / "halt.flag"
    set_halt(flag, "ad-hoc")
    assert flag.exists()


def test_set_halt_strips_whitespace(tmp_path: Path):
    flag = tmp_path / "halt.flag"
    state = set_halt(flag, "   reason with edges   ")
    assert state.reason == "reason with edges"


def test_set_halt_rejects_empty_reason(tmp_path: Path):
    flag = tmp_path / "halt.flag"
    with pytest.raises(ValueError, match="non-empty"):
        set_halt(flag, "")


def test_set_halt_rejects_whitespace_only_reason(tmp_path: Path):
    flag = tmp_path / "halt.flag"
    with pytest.raises(ValueError, match="non-empty"):
        set_halt(flag, "   \t\n  ")


def test_set_halt_overwrites_existing(tmp_path: Path):
    flag = tmp_path / "halt.flag"
    first = set_halt(flag, "first")
    second = set_halt(flag, "second")

    assert first.reason == "first"
    assert second.reason == "second"
    state = read_halt(flag)
    assert state is not None
    assert state.reason == "second"


def test_clear_halt_returns_true_when_present(tmp_path: Path):
    flag = tmp_path / "halt.flag"
    set_halt(flag, "to be cleared")
    assert clear_halt(flag) is True
    assert is_halted(flag) is False


def test_clear_halt_returns_false_when_absent(tmp_path: Path):
    flag = tmp_path / "halt.flag"
    assert clear_halt(flag) is False


def test_payload_survives_simulated_restart(tmp_path: Path):
    """A new process would re-read the same file path. Simulate by
    discarding the in-memory state object and re-reading from disk."""
    flag = tmp_path / "halt.flag"
    set_halt(flag, "before restart")
    # Simulated restart: forget the in-memory state, re-read from disk.
    state = read_halt(flag)
    assert state is not None
    assert state.reason == "before restart"
    assert is_halted(flag) is True


def test_halt_state_is_frozen():
    state = HaltState(ts_utc="2026-05-02T13:31:00.000Z", reason="x")
    with pytest.raises(ValidationError):
        state.reason = "tampered"  # type: ignore[misc]


def test_halt_state_extra_field_rejected():
    with pytest.raises(ValidationError):
        HaltState(  # type: ignore[call-arg]
            ts_utc="2026-05-02T13:31:00.000Z",
            reason="x",
            unexpected="nope",
        )


def test_halt_state_round_trip_through_json(tmp_path: Path):
    flag = tmp_path / "halt.flag"
    written = set_halt(flag, "round trip")
    parsed = read_halt(flag)
    assert parsed == written
