"""Tests for risk gates (T030, US1).

Constitution principles I (sizing) and II (deny-by-default) are
enforced by these six gates. Every gate returns a `GateDecision`; a
single Deny short-circuits the order router and is recorded as
ORDER_REJECTED_BY_GATE in the audit log.

Each cap is exercised at three points:
  - well below the cap (allow)
  - exactly at the cap (allow — boundary is inclusive)
  - one cent over the cap (deny)
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from auto_invest.broker.models import OrderRequest
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.whitelist import Whitelist
from auto_invest.risk.gates import (
    global_exposure_gate,
    halt_gate,
    per_symbol_cap_gate,
    per_trade_cap_gate,
    stage_uniqueness_gate,
    whitelist_gate,
)
from auto_invest.worker.halt import set_halt

CAPS = SizingCaps(
    per_trade_pct=Decimal("5"),
    per_symbol_pct=Decimal("20"),
    global_exposure_pct=Decimal("80"),
    canary_capital_pct=Decimal("5"),
    canary_min_duration_days=10,
    canary_acceptance_drawdown_pct=Decimal("3"),
)

WHITELIST = Whitelist(
    symbols={"AAPL", "MSFT"},
    accounts={"acct-1"},
)

CAPITAL = Decimal("10000")


def _request(
    *,
    symbol: str = "AAPL",
    account: str = "acct-1",
    side: Side = Side.BUY,
    order_type: OrderType = OrderType.LIMIT,
    qty: int = 1,
    limit_price: Decimal | None = Decimal("100"),
) -> OrderRequest:
    return OrderRequest(
        account=account,
        symbol=symbol,
        side=side,
        order_type=order_type,
        qty=qty,
        limit_price_usd=limit_price,
    )


# ---------------------------------------------------------- whitelist_gate


def test_whitelist_gate_allows_known_symbol_account_order_type():
    decision = whitelist_gate(_request(), whitelist=WHITELIST)
    assert decision.allow is True
    assert decision.gate == "whitelist_gate"


def test_whitelist_gate_denies_unknown_symbol():
    decision = whitelist_gate(_request(symbol="TSLA"), whitelist=WHITELIST)
    assert decision.allow is False
    assert "TSLA" in decision.reason
    assert decision.metadata["symbol"] == "TSLA"


def test_whitelist_gate_denies_unknown_account():
    decision = whitelist_gate(_request(account="acct-99"), whitelist=WHITELIST)
    assert decision.allow is False
    assert "account" in decision.reason.lower()


def test_whitelist_gate_denies_unknown_order_type():
    wl_limit_only = Whitelist(symbols={"AAPL"}, accounts={"acct-1"})
    decision = whitelist_gate(
        _request(order_type=OrderType.MARKET, limit_price=None),
        whitelist=wl_limit_only,
    )
    assert decision.allow is False
    assert decision.metadata["order_type"] == "MARKET"


# ---------------------------------------------------------- halt_gate


def test_halt_gate_allows_when_no_flag(tmp_path: Path):
    decision = halt_gate(_request(), halt_path=tmp_path / "halt.flag")
    assert decision.allow is True


def test_halt_gate_denies_when_flag_set(tmp_path: Path):
    flag = tmp_path / "halt.flag"
    set_halt(flag, "investigating")
    decision = halt_gate(_request(), halt_path=flag)
    assert decision.allow is False
    assert "halt" in decision.reason.lower()


# ---------------------------------------------------------- per_trade_cap_gate


def test_per_trade_cap_allows_well_below():
    # 1 * 100 = 100, cap = 5% of 10000 = 500
    decision = per_trade_cap_gate(
        _request(qty=1, limit_price=Decimal("100")),
        caps=CAPS,
        total_capital_usd=CAPITAL,
        quote_price_usd=Decimal("100"),
    )
    assert decision.allow is True


def test_per_trade_cap_allows_at_boundary():
    # 5 * 100 = 500 = cap
    decision = per_trade_cap_gate(
        _request(qty=5, limit_price=Decimal("100")),
        caps=CAPS,
        total_capital_usd=CAPITAL,
        quote_price_usd=Decimal("100"),
    )
    assert decision.allow is True


def test_per_trade_cap_denies_just_over():
    # 1 * 500.01 = 500.01 > 500
    decision = per_trade_cap_gate(
        _request(qty=1, limit_price=Decimal("500.01")),
        caps=CAPS,
        total_capital_usd=CAPITAL,
        quote_price_usd=Decimal("500.01"),
    )
    assert decision.allow is False
    assert decision.metadata["cap_pct"] == "5"


def test_per_trade_cap_uses_quote_when_market_order():
    decision = per_trade_cap_gate(
        OrderRequest(
            account="acct-1",
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.MARKET,
            qty=10,
            limit_price_usd=None,
        ),
        caps=CAPS,
        total_capital_usd=CAPITAL,
        quote_price_usd=Decimal("100"),  # notional 1000 > cap 500
    )
    assert decision.allow is False


# ---------------------------------------------------------- per_symbol_cap_gate


def test_per_symbol_cap_allows_buy_well_below():
    # current 1000 + new 500 = 1500, cap = 20% of 10000 = 2000
    decision = per_symbol_cap_gate(
        _request(qty=5, limit_price=Decimal("100")),
        caps=CAPS,
        total_capital_usd=CAPITAL,
        quote_price_usd=Decimal("100"),
        current_symbol_exposure_usd=Decimal("1000"),
    )
    assert decision.allow is True


def test_per_symbol_cap_allows_at_boundary():
    # current 1500 + new 500 = 2000 = cap
    decision = per_symbol_cap_gate(
        _request(qty=5, limit_price=Decimal("100")),
        caps=CAPS,
        total_capital_usd=CAPITAL,
        quote_price_usd=Decimal("100"),
        current_symbol_exposure_usd=Decimal("1500"),
    )
    assert decision.allow is True


def test_per_symbol_cap_denies_just_over_boundary():
    # current 1500.01 + new 500 = 2000.01 > 2000
    decision = per_symbol_cap_gate(
        _request(qty=5, limit_price=Decimal("100")),
        caps=CAPS,
        total_capital_usd=CAPITAL,
        quote_price_usd=Decimal("100"),
        current_symbol_exposure_usd=Decimal("1500.01"),
    )
    assert decision.allow is False
    assert decision.metadata["cap_pct"] == "20"


def test_per_symbol_cap_sell_always_allowed():
    decision = per_symbol_cap_gate(
        _request(side=Side.SELL, qty=5, limit_price=Decimal("100")),
        caps=CAPS,
        total_capital_usd=CAPITAL,
        quote_price_usd=Decimal("100"),
        current_symbol_exposure_usd=Decimal("9999"),
    )
    assert decision.allow is True


# ---------------------------------------------------------- global_exposure_gate


def test_global_exposure_allows_buy_well_below():
    # current 5000 + new 500 = 5500, cap = 80% of 10000 = 8000
    decision = global_exposure_gate(
        _request(qty=5, limit_price=Decimal("100")),
        caps=CAPS,
        total_capital_usd=CAPITAL,
        quote_price_usd=Decimal("100"),
        current_global_exposure_usd=Decimal("5000"),
    )
    assert decision.allow is True


def test_global_exposure_at_boundary_allowed():
    # current 7500 + new 500 = 8000 = cap
    decision = global_exposure_gate(
        _request(qty=5, limit_price=Decimal("100")),
        caps=CAPS,
        total_capital_usd=CAPITAL,
        quote_price_usd=Decimal("100"),
        current_global_exposure_usd=Decimal("7500"),
    )
    assert decision.allow is True


def test_global_exposure_just_over_denied():
    decision = global_exposure_gate(
        _request(qty=5, limit_price=Decimal("100")),
        caps=CAPS,
        total_capital_usd=CAPITAL,
        quote_price_usd=Decimal("100"),
        current_global_exposure_usd=Decimal("7500.01"),
    )
    assert decision.allow is False


def test_global_exposure_sell_always_allowed():
    decision = global_exposure_gate(
        _request(side=Side.SELL, qty=5, limit_price=Decimal("100")),
        caps=CAPS,
        total_capital_usd=CAPITAL,
        quote_price_usd=Decimal("100"),
        current_global_exposure_usd=Decimal("8000"),
    )
    assert decision.allow is True


# ---------------------------------------------------------- stage_uniqueness_gate


def test_stage_uniqueness_allows_when_no_other_rules():
    decision = stage_uniqueness_gate(
        rule_id="r1",
        symbol="AAPL",
        proposed_stage=StrategyStage.CANARY,
        active_stages_for_symbol={},
    )
    assert decision.allow is True


def test_stage_uniqueness_allows_when_other_at_lower_stage():
    decision = stage_uniqueness_gate(
        rule_id="r1",
        symbol="AAPL",
        proposed_stage=StrategyStage.FULL_LIVE,
        active_stages_for_symbol={"r2": StrategyStage.CANARY},
    )
    assert decision.allow is True


def test_stage_uniqueness_ignores_self():
    decision = stage_uniqueness_gate(
        rule_id="r1",
        symbol="AAPL",
        proposed_stage=StrategyStage.FULL_LIVE,
        active_stages_for_symbol={"r1": StrategyStage.CANARY},
    )
    assert decision.allow is True


def test_stage_uniqueness_denies_when_higher_stage_active():
    decision = stage_uniqueness_gate(
        rule_id="r1",
        symbol="AAPL",
        proposed_stage=StrategyStage.CANARY,
        active_stages_for_symbol={"r2": StrategyStage.FULL_LIVE},
    )
    assert decision.allow is False
    assert decision.metadata["active_rule_id"] == "r2"
    assert decision.metadata["active_stage"] == "FULL_LIVE"
    assert decision.metadata["proposed_stage"] == "CANARY"


def test_stage_uniqueness_allows_two_canary_rules_same_symbol():
    # Concurrent canary rules on the same symbol are not blocked by
    # this gate; it only enforces "no higher-stage version active".
    decision = stage_uniqueness_gate(
        rule_id="r1",
        symbol="AAPL",
        proposed_stage=StrategyStage.CANARY,
        active_stages_for_symbol={"r2": StrategyStage.CANARY},
    )
    assert decision.allow is True
