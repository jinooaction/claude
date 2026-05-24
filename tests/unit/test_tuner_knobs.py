"""스펙 005 — 튜닝 노브: 조이기 수학·클램프·원자적 쓰기 (SC-A05)."""

from __future__ import annotations

import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.telemetry.thresholds import ThresholdEntry, load_thresholds
from auto_invest.tuner.knobs import apply_threshold, compute_tighten

SRC = Path("config/llm_kpi_thresholds.toml")


def test_compute_tighten_lower_is_better() -> None:
    # latency: c=5000 b=2000 a=800 → new_b = 2000 - 0.2*(2000-800) = 1760
    entry = ThresholdEntry(
        direction="lower_is_better",
        tier_c=Decimal(5000),
        tier_b=Decimal(2000),
        tier_a=Decimal(800),
    )
    assert compute_tighten(entry) == Decimal(1760)


def test_compute_tighten_higher_is_better() -> None:
    # cache: c=0.4 b=0.7 a=0.9 → new_b = 0.7 + 0.2*(0.9-0.7) = 0.74
    entry = ThresholdEntry(
        direction="higher_is_better",
        tier_c=Decimal("0.4"),
        tier_b=Decimal("0.7"),
        tier_a=Decimal("0.9"),
    )
    assert compute_tighten(entry) == Decimal("0.74")


def test_tighten_stays_in_band() -> None:
    """새 tier_b 는 항상 (tier_a, tier_c) 안 (SC-A05)."""
    for direction, c, b, a in [
        ("lower_is_better", 5000, 2000, 800),
        ("higher_is_better", 0.4, 0.7, 0.9),
    ]:
        entry = ThresholdEntry(
            direction=direction,
            tier_c=Decimal(str(c)),
            tier_b=Decimal(str(b)),
            tier_a=Decimal(str(a)),
        )
        new_b = compute_tighten(entry)
        assert new_b is not None
        lo, hi = sorted([Decimal(str(a)), Decimal(str(c))])
        assert lo < new_b < hi


def test_no_room_returns_none() -> None:
    # tier_b 이미 tier_a 에 매우 근접 → 한 스텝이 무의미하거나 밴드 침범 시 None 또는 작은 값.
    entry = ThresholdEntry(
        direction="lower_is_better",
        tier_c=Decimal(5000),
        tier_b=Decimal(801),
        tier_a=Decimal(800),
    )
    new_b = compute_tighten(entry)
    # gap=1, step=0.2 → 800.8, 정수 아님 → 그대로. 밴드 안.
    assert new_b is None or Decimal(800) < new_b < Decimal(5000)


def test_apply_threshold_changes_only_target(tmp_path: Path) -> None:
    dst = tmp_path / "thresholds.toml"
    shutil.copy(SRC, dst)
    before = dst.read_text(encoding="utf-8")
    old, new = apply_threshold(dst, "latency_p95_ms", Decimal(1760))
    assert old == "2000"
    assert new == "1760"
    after = dst.read_text(encoding="utf-8")
    # 다른 KPI 의 tier_b 는 보존(usd_per_decision_mean tier_b=0.01).
    reloaded = load_thresholds(dst)
    assert reloaded.entries["latency_p95_ms"].tier_b == Decimal(1760)
    assert reloaded.entries["usd_per_decision_mean"].tier_b == Decimal("0.01")
    # 주석 보존 확인.
    assert "# KPI threshold table" in after
    # 첫 줄 주석이 그대로.
    assert before.splitlines()[0] == after.splitlines()[0]


def test_apply_threshold_missing_kpi_raises(tmp_path: Path) -> None:
    dst = tmp_path / "thresholds.toml"
    shutil.copy(SRC, dst)
    with pytest.raises(ValueError):
        apply_threshold(dst, "nonexistent_kpi", Decimal(1))
