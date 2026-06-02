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


# --- 해외 일봉 파서 (스펙 033: KIS 기간별시세) ---

from datetime import date  # noqa: E402

from auto_invest.broker.overseas import _parse_daily_bars  # noqa: E402


def _row(xymd: str, o: str, h: str, lo: str, c: str, v: str = "1000000") -> dict:
    return {"xymd": xymd, "open": o, "high": h, "low": lo, "clos": c, "tvol": v}


def test_parse_daily_bars_basic_and_ascending() -> None:
    rows = [
        _row("20260529", "180", "182", "179", "181"),
        _row("20260528", "178", "181", "177", "180"),
    ]
    bars = _parse_daily_bars(rows, "AAPL")
    assert [b.session_date for b in bars] == [date(2026, 5, 28), date(2026, 5, 29)]
    assert bars[0].symbol == "AAPL"
    assert bars[1].close == Decimal("181")
    assert bars[1].volume == 1_000_000


def test_parse_daily_bars_clamps_low_high() -> None:
    # low > close 인 깨진 행 → low/high 를 open/close 에 맞게 클램프(검증 통과 보장).
    bars = _parse_daily_bars([_row("20260529", "180", "180.5", "181", "182")], "X")
    b = bars[0]
    assert b.low <= min(b.open, b.close)
    assert b.high >= max(b.open, b.close)


def test_parse_daily_bars_skips_bad_and_duplicate() -> None:
    rows = [
        _row("2026052", "1", "1", "1", "1"),       # 날짜 길이 오류
        _row("20260529", "0", "1", "1", "1"),      # 비양수 가격
        _row("20260530", "1", "1", "1", "x"),      # 파싱 불가
        _row("20260531", "10", "11", "9", "10"),   # 정상
        _row("20260531", "10", "11", "9", "10"),   # 중복 날짜
    ]
    bars = _parse_daily_bars(rows, "X")
    assert [b.session_date for b in bars] == [date(2026, 5, 31)]


def test_parse_daily_bars_empty() -> None:
    assert _parse_daily_bars([], "X") == []
