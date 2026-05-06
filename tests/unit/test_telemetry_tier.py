"""Tests for `auto_invest.telemetry.thresholds` (T123)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.telemetry.thresholds import (
    KPI_DIRECTIONS,
    REQUIRED_KPIS,
    TierTableError,
    load_thresholds,
)


def test_default_table_loads_and_classifies():
    table = load_thresholds(Path("config/llm_kpi_thresholds.toml"))
    for name in REQUIRED_KPIS:
        assert name in table.entries
        assert table.entries[name].direction == KPI_DIRECTIONS[name]


def test_higher_is_better_boundaries():
    table = load_thresholds(Path("config/llm_kpi_thresholds.toml"))
    # cache_hit_rate: tier_c=0.40, tier_b=0.70, tier_a=0.90
    assert table.classify("cache_hit_rate", Decimal("0.95")) == "A"
    assert table.classify("cache_hit_rate", Decimal("0.90")) == "A"  # >= a
    assert table.classify("cache_hit_rate", Decimal("0.85")) == "B"
    assert table.classify("cache_hit_rate", Decimal("0.40")) == "C"  # >= c
    assert table.classify("cache_hit_rate", Decimal("0.39")) == "N/A"


def test_lower_is_better_boundaries():
    table = load_thresholds(Path("config/llm_kpi_thresholds.toml"))
    # tokens_per_decision_p95: tier_a=1500, tier_b=3000, tier_c=8000
    assert table.classify("tokens_per_decision_p95", 1000) == "A"
    assert table.classify("tokens_per_decision_p95", 1500) == "A"  # <= a
    assert table.classify("tokens_per_decision_p95", 2999) == "B"
    assert table.classify("tokens_per_decision_p95", 8000) == "C"  # <= c
    assert table.classify("tokens_per_decision_p95", 8001) == "N/A"


def test_unknown_kpi_returns_na():
    table = load_thresholds(Path("config/llm_kpi_thresholds.toml"))
    assert table.classify("nonexistent_kpi", 5) == "N/A"
    assert table.thresholds_for("nonexistent_kpi") == {}


def test_missing_kpi_rejected(tmp_path: Path):
    p = tmp_path / "thr.toml"
    p.write_text(
        """
[cache_hit_rate]
direction = "higher_is_better"
tier_c = 0.4
tier_b = 0.7
tier_a = 0.9
""",
        encoding="utf-8",
    )
    with pytest.raises(TierTableError):
        load_thresholds(p)


def test_unknown_kpi_rejected(tmp_path: Path):
    p = tmp_path / "thr.toml"
    p.write_text(
        """
[mystery_kpi]
direction = "higher_is_better"
tier_c = 1
tier_b = 2
tier_a = 3
""",
        encoding="utf-8",
    )
    with pytest.raises(TierTableError):
        load_thresholds(p)


def test_misordered_higher_is_better_rejected(tmp_path: Path):
    p = tmp_path / "thr.toml"
    p.write_text(
        """
[cache_hit_rate]
direction = "higher_is_better"
tier_c = 0.9
tier_b = 0.7
tier_a = 0.4

[tokens_per_decision_p95]
direction = "lower_is_better"
tier_c = 8000
tier_b = 3000
tier_a = 1500

[usd_per_decision_mean]
direction = "lower_is_better"
tier_c = 0.05
tier_b = 0.01
tier_a = 0.003

[latency_p95_ms]
direction = "lower_is_better"
tier_c = 5000
tier_b = 2000
tier_a = 800
""",
        encoding="utf-8",
    )
    with pytest.raises(TierTableError):
        load_thresholds(p)


def test_wrong_direction_rejected(tmp_path: Path):
    p = tmp_path / "thr.toml"
    p.write_text(
        """
[cache_hit_rate]
direction = "lower_is_better"
tier_c = 0.9
tier_b = 0.7
tier_a = 0.4

[tokens_per_decision_p95]
direction = "lower_is_better"
tier_c = 8000
tier_b = 3000
tier_a = 1500

[usd_per_decision_mean]
direction = "lower_is_better"
tier_c = 0.05
tier_b = 0.01
tier_a = 0.003

[latency_p95_ms]
direction = "lower_is_better"
tier_c = 5000
tier_b = 2000
tier_a = 800
""",
        encoding="utf-8",
    )
    with pytest.raises(TierTableError):
        load_thresholds(p)
