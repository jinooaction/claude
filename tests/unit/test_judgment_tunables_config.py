"""Spec 012 T005 — judgment_tunables.toml max_tokens 폴백 오버레이.

파일/키 없으면 하드코딩 기본값 유지(동작 무변경), 바닥 클램프 검증.
"""

from __future__ import annotations

from pathlib import Path

from auto_invest.judgment import registry
from auto_invest.judgment.registry import (
    JUDGMENT_MAX_TOKENS_FLOOR,
    _apply_tunables_overlay,
)


def _base() -> dict:
    # 하드코딩 기본값으로 재구성한 베이스 레지스트리(오버레이 적용 전 값).
    return {
        "volatility_assessment": registry.JudgmentPoint(
            decision_class="volatility_assessment",
            output_schema=registry.VolatilityAdvisory,
            latency_budget_ms=2_000,
            cost_budget_usd=registry.Decimal("0.01"),
            model="m",
            max_tokens=256,
            affects_capital=True,
            trigger_description="t",
            input_contract="i",
            fallback_description="f",
        ),
        "daily_summary": registry.JudgmentPoint(
            decision_class="daily_summary",
            output_schema=registry.DailySummaryAdvisory,
            latency_budget_ms=10_000,
            cost_budget_usd=registry.Decimal("0.05"),
            model="m",
            max_tokens=700,
            affects_capital=False,
            trigger_description="t",
            input_contract="i",
            fallback_description="f",
        ),
    }


def test_missing_file_keeps_defaults(tmp_path: Path):
    out = _apply_tunables_overlay(_base(), tmp_path / "nope.toml")
    assert out["volatility_assessment"].max_tokens == 256
    assert out["daily_summary"].max_tokens == 700


def test_partial_keys_fall_back(tmp_path: Path):
    p = tmp_path / "judgment_tunables.toml"
    p.write_text("[daily_summary]\nmax_tokens = 400\n", encoding="utf-8")
    out = _apply_tunables_overlay(_base(), p)
    assert out["daily_summary"].max_tokens == 400  # overridden
    assert out["volatility_assessment"].max_tokens == 256  # fallback (no section)


def test_invalid_value_falls_back(tmp_path: Path):
    p = tmp_path / "judgment_tunables.toml"
    p.write_text(
        '[volatility_assessment]\nmax_tokens = "oops"\n', encoding="utf-8"
    )
    out = _apply_tunables_overlay(_base(), p)
    assert out["volatility_assessment"].max_tokens == 256  # invalid → fallback


def test_bool_is_not_accepted_as_int(tmp_path: Path):
    p = tmp_path / "judgment_tunables.toml"
    p.write_text("[volatility_assessment]\nmax_tokens = true\n", encoding="utf-8")
    out = _apply_tunables_overlay(_base(), p)
    assert out["volatility_assessment"].max_tokens == 256


def test_floor_clamp(tmp_path: Path):
    p = tmp_path / "judgment_tunables.toml"
    p.write_text("[daily_summary]\nmax_tokens = 1\n", encoding="utf-8")
    out = _apply_tunables_overlay(_base(), p)
    assert out["daily_summary"].max_tokens == JUDGMENT_MAX_TOKENS_FLOOR


def test_malformed_toml_keeps_defaults(tmp_path: Path):
    p = tmp_path / "judgment_tunables.toml"
    p.write_text("this is = = not toml [[", encoding="utf-8")
    out = _apply_tunables_overlay(_base(), p)
    assert out["daily_summary"].max_tokens == 700


def test_live_registry_unchanged_by_default_config():
    # 저장소의 실제 config 는 하드코딩값과 동일해야 한다(동작 무변경 불변).
    assert registry.get("volatility_assessment").max_tokens == 256
    assert registry.get("daily_summary").max_tokens == 700
    assert registry.get("news_screen").max_tokens == 128
