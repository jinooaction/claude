"""Spec 004 T027 [US4] — 판단 지점 관측(폴백률) + 예산 초과 폴백 전환."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.rules import Action, JudgmentConfig, PriceTrigger, TradingRule
from auto_invest.judgment.budget import BudgetTracker
from auto_invest.judgment.client import JudgmentClient
from auto_invest.judgment.observability import judgment_efficiency
from auto_invest.judgment.runner import VolatilityJudgmentRunner
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import (
    JudgmentAdvisoryAppliedPayload,
    JudgmentFallbackPayload,
    LlmCallPayload,
)
from auto_invest.telemetry.prices import load_prices

_WIN_START = "2026-05-24T00:00:00.000Z"
_WIN_END = "2026-05-25T00:00:00.000Z"
_TS = "2026-05-24T12:00:00.000Z"


@dataclass
class _Bar:
    close_usd: Decimal


@pytest.fixture
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


@pytest.fixture
def prices():
    return load_prices(Path("config/llm_prices.toml"))


def test_efficiency_breakdown_counts_and_rate(conn):
    # volatility: 3 호출, 2 적용, 1 폴백 → fallback_rate = 1/(2+1) = 0.3333
    for _ in range(3):
        audit.append(
            conn,
            LlmCallPayload(
                model="m", decision_class="volatility_assessment", tokens_total=10,
                cost_usd="0.001", latency_ms=5, error_class=None,
            ),
            ts_utc=_TS,
        )
    for _ in range(2):
        audit.append(
            conn,
            JudgmentAdvisoryAppliedPayload(
                decision_class="volatility_assessment",
                advisory="size_down@0.6",
                applied_decision="size_down:0.5",
                canary_cohort=True,
            ),
            ts_utc=_TS,
        )
    audit.append(
        conn,
        JudgmentFallbackPayload(decision_class="volatility_assessment", reason="timeout"),
        ts_utc=_TS,
    )

    eff = judgment_efficiency(conn, window_start_utc=_WIN_START, window_end_utc=_WIN_END)
    vol = eff["volatility_assessment"]
    assert vol["llm_calls"] == 3
    assert vol["advisories_applied"] == 2
    assert vol["fallbacks"] == 1
    assert vol["fallback_rate"] == pytest.approx(0.3333, abs=1e-4)
    # 호출 없는 판단 지점은 rate None.
    assert eff["news_screen"]["fallback_rate"] is None


def test_window_excludes_out_of_range(conn):
    audit.append(
        conn,
        JudgmentFallbackPayload(decision_class="volatility_assessment", reason="failure"),
        ts_utc="2026-05-01T00:00:00.000Z",  # 윈도 밖
    )
    eff = judgment_efficiency(conn, window_start_utc=_WIN_START, window_end_utc=_WIN_END)
    assert eff["volatility_assessment"]["fallbacks"] == 0


def _rule() -> TradingRule:
    return TradingRule(
        id="vol",
        symbol="AAPL",
        stage=StrategyStage.CANARY,
        priority=1,
        enabled=True,
        trigger=PriceTrigger(direction="<=", threshold=Decimal("100"), cooldown_seconds=60),
        action=Action(side=Side.BUY, order_type=OrderType.LIMIT, qty=10, limit_price="10.00"),
        judgment=JudgmentConfig(enabled=True, volatility_threshold=0.0),
    )


class _ExplodingClient:
    class _M:
        async def create(self, **kw):
            raise RuntimeError("should not be called when budget exhausted")

    def __init__(self):
        self.messages = self._M()


@pytest.mark.asyncio
async def test_budget_exceeded_skips_call_and_records_fallback(conn, prices):
    budget = BudgetTracker(rolling_budget_usd={"volatility_assessment": Decimal("0.01")})
    budget.record("volatility_assessment", Decimal("0.02"))  # 이미 예산 초과
    runner = VolatilityJudgmentRunner(
        client=JudgmentClient(_ExplodingClient(), conn=conn, prices=prices),
        conn=conn,
        budget=budget,
    )
    bars = tuple(_Bar(close_usd=Decimal(p)) for p in ("100", "104", "98"))
    advisory, cid = await runner.assess(_rule(), bars, current_price=Decimal("99"))
    # 예산 소진 → LLM 호출 안 함, 폴백.
    assert advisory is None
    assert conn.execute("SELECT COUNT(*) c FROM token_usage").fetchone()["c"] == 0
    fb = [r for r in audit.read_all(conn) if r["event_type"] == "JUDGMENT_FALLBACK"]
    assert fb and "budget_exceeded" in fb[0]["payload_json"]
