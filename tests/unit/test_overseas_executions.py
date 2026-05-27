"""Unit tests for KIS execution-inquiry parsing (spec 015, T003)."""

from __future__ import annotations

from decimal import Decimal

from auto_invest.broker.overseas import _parse_executions
from auto_invest.config.enums import Side


def test_parse_full_fill_row() -> None:
    rows = [
        {
            "odno": "0000123",
            "pdno": "AAPL",
            "ft_ccld_qty": "100",
            "ft_ccld_unpr3": "150.25",
            "nccs_qty": "0",
            "sll_buy_dvsn_cd": "02",
        }
    ]
    out = _parse_executions(rows)
    assert len(out) == 1
    e = out[0]
    assert e.kis_order_id == "0000123"
    assert e.symbol == "AAPL"
    assert e.filled_qty == 100
    assert e.avg_fill_price_usd == Decimal("150.25")
    assert e.unfilled_qty == 0
    assert e.side is Side.BUY
    assert e.terminal is False


def test_parse_partial_fill_with_unfilled() -> None:
    rows = [
        {
            "odno": "0000200",
            "pdno": "VOO",
            "ccld_qty": "40",
            "ccld_unpr": "500.00",
            "nccs_qty": "60",
            "sll_buy_dvsn_cd": "01",
        }
    ]
    out = _parse_executions(rows)
    e = out[0]
    assert e.filled_qty == 40
    assert e.unfilled_qty == 60
    assert e.side is Side.SELL


def test_parse_aggregates_multiple_rows_per_order() -> None:
    # 한 주문에 두 부분체결 row → 누적 + 가중평균.
    rows = [
        {"odno": "0000300", "pdno": "MSFT", "ft_ccld_qty": "10", "ft_ccld_unpr3": "100"},
        {"odno": "0000300", "pdno": "MSFT", "ft_ccld_qty": "30", "ft_ccld_unpr3": "200"},
    ]
    out = _parse_executions(rows)
    assert len(out) == 1
    e = out[0]
    assert e.filled_qty == 40
    # 가중평균 = (10*100 + 30*200) / 40 = 175
    assert e.avg_fill_price_usd == Decimal("175")


def test_parse_terminal_status_marks_terminal() -> None:
    rows = [
        {
            "odno": "0000400",
            "pdno": "AAPL",
            "ft_ccld_qty": "0",
            "ft_ccld_unpr3": "0",
            "nccs_qty": "100",
            "prcs_stat_name": "취소완료",
        }
    ]
    out = _parse_executions(rows)
    assert out[0].terminal is True
    assert out[0].filled_qty == 0


def test_parse_empty_rows() -> None:
    assert _parse_executions([]) == []


def test_parse_skips_rows_without_order_id() -> None:
    rows = [{"pdno": "AAPL", "ft_ccld_qty": "10"}]
    assert _parse_executions(rows) == []


def test_parse_unknown_side_is_none() -> None:
    rows = [{"odno": "X", "pdno": "AAPL", "ft_ccld_qty": "1", "ft_ccld_unpr3": "1"}]
    assert _parse_executions(rows)[0].side is None
