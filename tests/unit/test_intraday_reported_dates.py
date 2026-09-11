from datetime import date

import pytest

from auto_invest.broker.overseas import _parse_execution_snapshots


def row(**changes):
    return dict(dict(odno="order", pdno="SPY", sll_buy_dvsn_cd="02", ft_ccld_qty="2",
                     nccs_qty="0", ft_ccld_unpr3="101", ord_dvsn="00", ord_unpr="102"), **changes)


def test_order_date_is_preserved_without_inventing_utc_time():
    execution = _parse_execution_snapshots([row(ord_dt="20260910", ord_tmd="not-a-time")],
                                          "AMEX")[0]
    assert execution.reported_order_date == date(2026, 9, 10)
    assert execution.ordered_at_utc is None


def test_missing_date_remains_unknown():
    assert _parse_execution_snapshots([row()], "AMEX")[0].reported_order_date is None


@pytest.mark.parametrize("day", ["20260229", "20260931", "2026-09-10", "２０２６０９１０",
                                "2026091", "00000910"])
def test_invalid_calendar_or_format_is_rejected(day):
    with pytest.raises(ValueError, match="EXECUTIONS_ORDER_DATE_INVALID"):
        _parse_execution_snapshots([row(ord_dt=day)], "AMEX")


def test_leap_day_is_accepted():
    assert _parse_execution_snapshots([row(ord_dt="20240229")], "AMEX")[0].reported_order_date == (
        date(2024, 2, 29)
    )


@pytest.mark.parametrize("reverse", [False, True])
def test_conflicting_dates_cannot_be_selected_by_larger_fill(reverse):
    rows = [row(ord_dt="20260910", ft_ccld_qty="1"), row(ord_dt="20260911")]
    with pytest.raises(ValueError, match="EXECUTIONS_SNAPSHOT_CONFLICT"):
        _parse_execution_snapshots(rows[::-1] if reverse else rows, "AMEX")
