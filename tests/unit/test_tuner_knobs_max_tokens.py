"""스펙 012 T013 — max_tokens 노브 계산·원자적 TOML 교체."""

from __future__ import annotations

from pathlib import Path

from auto_invest.tuner.knobs import (
    MAX_TOKENS_FLOOR,
    apply_max_tokens,
    compute_max_tokens_reduce,
)


def test_reduce_one_step():
    # 700 * 0.2 = 140 → 700-140 = 560.
    assert compute_max_tokens_reduce(700) == 560


def test_reduce_clamps_to_floor():
    # 작은 값은 바닥 아래로 안 내려간다.
    out = compute_max_tokens_reduce(40, floor=32)
    assert out == 32


def test_at_or_below_floor_returns_none():
    assert compute_max_tokens_reduce(32, floor=32) is None
    assert compute_max_tokens_reduce(10, floor=32) is None


def test_min_step_is_one():
    # 33: 33*0.2=6 → 27 < floor(32) → clamp 32 (변화 있음).
    assert compute_max_tokens_reduce(33, floor=32) == 32


def test_apply_replaces_only_target_line(tmp_path: Path):
    p = tmp_path / "judgment_tunables.toml"
    p.write_text(
        "# comment\n[daily_summary]\nmax_tokens = 700  # trailing\n"
        "[news_screen]\nmax_tokens = 128\n",
        encoding="utf-8",
    )
    old, new = apply_max_tokens(p, "daily_summary", 560)
    assert (old, new) == ("700", "560")
    text = p.read_text(encoding="utf-8")
    assert "max_tokens = 560  # trailing" in text  # 주석 보존
    assert "max_tokens = 128" in text  # 다른 섹션 불변
    assert "# comment" in text


def test_apply_missing_section_raises(tmp_path: Path):
    p = tmp_path / "judgment_tunables.toml"
    p.write_text("[daily_summary]\nmax_tokens = 700\n", encoding="utf-8")
    try:
        apply_max_tokens(p, "nonexistent", 100)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_floor_constant_positive():
    assert MAX_TOKENS_FLOOR > 0
