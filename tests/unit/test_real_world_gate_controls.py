from __future__ import annotations

import math
import zipfile
from datetime import date, timedelta
from io import BytesIO

import pytest

from auto_invest.analytics.real_world_gate_controls import (
    REAL_WORLD_CONTROLS_VALID,
    parse_aqr_tsmom_monthly,
    parse_fama_french_monthly,
    run_real_world_gate_audit,
)


def _months(count: int = 240) -> list[date]:
    year, month = 2007, 1
    output: list[date] = []
    for _ in range(count):
        output.append(date(year, month, 1))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return output


def _ff_zip(returns: list[float]) -> bytes:
    lines = ["note", ",Mkt-RF,SMB,HML,RF"]
    lines.extend(
        f"{month:%Y%m},{value * 100:.8f},0,0,0"
        for month, value in zip(_months(), returns, strict=True)
    )
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("F-F_Research_Data_Factors.csv", "\n".join(lines))
    return buffer.getvalue()


def _aqr_xlsx(returns: list[float]) -> bytes:
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    strings = ["TSMOM", "TSMOM^CM", "TSMOM^EQ", "TSMOM^FI", "TSMOM^FX"]
    shared = "".join(f"<si><t>{value}</t></si>" for value in strings)
    rows = [
        '<row r="18"><c r="B18" t="s"><v>0</v></c><c r="C18" t="s"><v>1</v></c>'
        '<c r="D18" t="s"><v>2</v></c><c r="E18" t="s"><v>3</v></c>'
        '<c r="F18" t="s"><v>4</v></c></row>'
    ]
    origin = date(1899, 12, 30)
    for index, (month, value) in enumerate(
        zip(_months(), returns, strict=True), start=19
    ):
        month_end = date(month.year + (month.month == 12), month.month % 12 + 1, 1) - timedelta(
            days=1
        )
        serial = (month_end - origin).days
        rows.append(
            f'<row r="{index}"><c r="A{index}"><v>{serial}</v></c>'
            f'<c r="B{index}"><v>{value}</v></c><c r="C{index}"><v>{value / 2}</v></c>'
            f'<c r="D{index}"><v>{value / 3}</v></c><c r="E{index}"><v>{value / 2}</v></c>'
            f'<c r="F{index}"><v>{value / 3}</v></c></row>'
        )
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/sharedStrings.xml", f'<sst xmlns="{namespace}">{shared}</sst>')
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f'<worksheet xmlns="{namespace}"><sheetData>{"".join(rows)}</sheetData></worksheet>',
        )
    return buffer.getvalue()


def _append_blank_template_row(raw: bytes) -> bytes:
    source = BytesIO(raw)
    output = BytesIO()
    with zipfile.ZipFile(source) as archive, zipfile.ZipFile(output, "w") as rewritten:
        for name in archive.namelist():
            content = archive.read(name)
            if name == "xl/worksheets/sheet1.xml":
                content = content.replace(
                    b"</sheetData>",
                    b'<row r="999"><c r="A999"><v></v></c><c r="B999"><v></v></c>'
                    b'<c r="C999"><v></v></c><c r="D999"><v></v></c>'
                    b'<c r="E999"><v></v></c><c r="F999"><v></v></c></row>'
                    b"</sheetData>",
                )
            rewritten.writestr(name, content)
    return output.getvalue()


def _positive_returns() -> list[float]:
    return [0.012 + 0.025 * math.sin(index * 1.7) for index in range(240)]


def test_official_control_parsers_extract_fixed_monthly_series() -> None:
    values = _positive_returns()
    market = parse_fama_french_monthly(_ff_zip(values))
    tsmom = parse_aqr_tsmom_monthly(_aqr_xlsx(values))
    assert len(market) == 240
    assert market["2007-01"] == pytest.approx(values[0])
    assert len(tsmom["all"]) == 240
    assert tsmom["commodity"]["2026-12"] == pytest.approx(values[-1] / 2)


def test_real_controls_pass_and_demeaned_nulls_fail_same_gate() -> None:
    values = _positive_returns()
    payload = run_real_world_gate_audit(
        _ff_zip(values),
        _aqr_xlsx(values),
        current_date=date(2027, 1, 15),
        code_commit="abc123",
        timestamp_utc="2027-01-15T00:00:00Z",
    )
    assert payload["verdict"] == REAL_WORLD_CONTROLS_VALID
    assert payload["promotion_control_passed"] is True
    assert {row["control_id"] for row in payload["controls"]} == {
        "fama_french_market_excess",
        "aqr_diversified_tsmom",
    }
    assert all(row["actual_live_passed"] for row in payload["controls"])
    assert all(row["demeaned_live_passed"] is False for row in payload["controls"])


def test_aqr_parser_ignores_fully_blank_formatted_tail_rows() -> None:
    values = _positive_returns()

    parsed = parse_aqr_tsmom_monthly(_append_blank_template_row(_aqr_xlsx(values)))

    assert len(parsed["all"]) == len(values)


def test_malformed_or_stale_controls_fail_closed() -> None:
    values = _positive_returns()
    with pytest.raises(ValueError, match="AQR workbook"):
        parse_aqr_tsmom_monthly(b"not-xlsx")
    payload = run_real_world_gate_audit(
        _ff_zip(values),
        _aqr_xlsx(values),
        current_date=date(2028, 1, 1),
        code_commit="abc123",
    )
    assert payload["promotion_control_passed"] is False
